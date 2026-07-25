from __future__ import annotations

import hashlib
import json
import time
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.ai_platform.characters import validate_grounding, validate_output
from apps.ai_platform.models import AIOutput, AIRequest, AITaskType
from apps.ai_platform.providers import AIProviderError
from apps.ai_platform.rag import format_chunks, retrieve_for_collection, retrieve_for_source
from apps.subscriptions.services import refund_character_request

from .analytics import build_authoritative_student_metrics
from .materializers import materialize_output
from .prompts import get_prompt_definition, render_prompt
from .router import RoutedProvider, route_provider


class AIRequestExecutionError(RuntimeError):
    pass


def canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def build_source_context(request: AIRequest) -> tuple[str, list[dict[str, Any]]]:
    query = str(request.parameters.get('topic') or request.input_payload.get('query') or '')
    limit = max(1, min(int(request.parameters.get('retrieval_limit') or 12), 40))
    max_chars = int(getattr(settings, 'AI_PLATFORM_MAX_CONTEXT_CHARS', 50000))
    if request.source_id:
        if not request.source.extracted_text:
            raise AIRequestExecutionError('المصدر لا يحتوي نصاً مستخرجاً وجاهزاً للمعالجة.')
        chunks = retrieve_for_source(request.source, query=query, limit=limit)
        return format_chunks(chunks, max_chars=max_chars)
    if request.collection_id:
        chunks = retrieve_for_collection(request.collection, query=query, limit=limit)
        if not chunks:
            raise AIRequestExecutionError('المجلد لا يحتوي مصادر نصية جاهزة.')
        return format_chunks(chunks, max_chars=max_chars)
    direct_text = str(request.input_payload.get('text') or request.input_payload.get('transcript') or '')
    return direct_text[:max_chars], []


def build_rules_context(request: AIRequest) -> dict[str, Any]:
    """Prepare deterministic inputs. LLMs explain; backend owns calculations."""

    context = dict(request.input_payload.get('context') or {})
    context['task_type'] = request.task_type
    context['character'] = request.character
    if request.task_type == AITaskType.KHOTA_GENERATE_PLAN:
        daily_limit = max(15, min(int(request.parameters.get('daily_minutes') or 60), 720))
        context['daily_minutes_limit'] = daily_limit
        context['must_not_exceed_daily_limit'] = True
        context['priority_inputs'] = request.input_payload.get('priority_inputs') or []
    elif request.task_type == AITaskType.RASHEED_RECOMMEND:
        context['analytics_are_authoritative'] = True
        context['calculated_metrics'] = build_authoritative_student_metrics(request)
        context['client_context_is_non_authoritative'] = request.input_payload.get('metrics') or {}
    return context


def estimate_cost(provider: RoutedProvider, input_tokens: int, output_tokens: int) -> Decimal:
    amount = (
        (Decimal(input_tokens) / Decimal(1_000_000)) * Decimal(str(provider.input_cost_per_million))
        + (Decimal(output_tokens) / Decimal(1_000_000)) * Decimal(str(provider.output_cost_per_million))
    )
    return amount.quantize(Decimal('0.000001'))


def _constraint_errors(request: AIRequest, data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if request.task_type == AITaskType.FAHES_GENERATE_QUIZ:
        expected_count = int(request.parameters.get('questions_count') or 10)
        actual_count = len(data.get('questions') or [])
        if actual_count != expected_count:
            errors.append(f'Expected {expected_count} questions but provider returned {actual_count}.')
    elif request.task_type == AITaskType.KHOTA_GENERATE_PLAN:
        daily_limit = max(15, min(int(request.parameters.get('daily_minutes') or 60), 720))
        start_date = str(request.parameters.get('start_date') or '')
        end_date = str(request.parameters.get('end_date') or '')
        for day in data.get('plan_days') or []:
            day_value = str(day.get('date') or '')
            if start_date and day_value < start_date:
                errors.append(f'Plan day {day_value} is before requested start date.')
            if end_date and day_value > end_date:
                errors.append(f'Plan day {day_value} is after requested end date.')
            total = sum(
                int(item.get('estimated_minutes') or 0)
                for item in day.get('tasks') or []
                if isinstance(item, dict)
            )
            if total > daily_limit:
                errors.append(f'Plan day {day_value} exceeds the requested {daily_limit}-minute limit.')
    return errors


def _refund_once(request: AIRequest) -> None:
    metadata = dict(request.metadata or {})
    if not metadata.get('usage_reserved') or metadata.get('usage_refunded'):
        return
    refund_character_request(request.user, request.character)
    metadata['usage_refunded'] = True
    request.metadata = metadata
    request.save(update_fields=['metadata', 'updated_at'])


@transaction.atomic
def cancel_ai_request(request: AIRequest) -> AIRequest:
    locked = AIRequest.objects.select_for_update().get(pk=request.pk)
    if locked.status in {AIRequest.Status.COMPLETED, AIRequest.Status.FAILED, AIRequest.Status.CANCELED}:
        return locked
    locked.status = AIRequest.Status.CANCELED
    locked.completed_at = timezone.now()
    locked.save(update_fields=['status', 'completed_at', 'updated_at'])
    _refund_once(locked)
    return locked


def _claim_request(request_id: int) -> AIRequest:
    """Atomically claim a queued job so duplicate workers cannot execute it twice."""

    with transaction.atomic():
        locked = AIRequest.objects.select_for_update().get(pk=request_id)
        if locked.status != AIRequest.Status.QUEUED:
            return locked
        locked.status = AIRequest.Status.PROCESSING
        locked.started_at = timezone.now()
        locked.error_code = ''
        locked.error_message = ''
        locked.save(
            update_fields=['status', 'started_at', 'error_code', 'error_message', 'updated_at']
        )
    return AIRequest.objects.select_related('user', 'source', 'collection').get(pk=request_id)


def execute_ai_request(request_id: int) -> AIRequest:
    request = _claim_request(request_id)
    if request.status != AIRequest.Status.PROCESSING:
        return request
    started = time.monotonic()

    try:
        source_text, references = build_source_context(request)
        definition, prompt_model = get_prompt_definition(request.task_type)
        context = build_rules_context(request)
        user_prompt = render_prompt(
            definition,
            source_text=source_text,
            parameters=request.parameters,
            context=context,
        )
        if prompt_model:
            request.prompt_version = prompt_model

        providers = route_provider(
            task_type=request.task_type,
            requested_provider=request.requested_provider,
        )
        if not providers:
            raise AIRequestExecutionError('لا يوجد مزود ذكاء اصطناعي مهيأ لهذه المهمة.')

        last_error: Exception | None = None
        provider_result = None
        selected: RoutedProvider | None = None
        attempts: list[dict[str, Any]] = []
        for provider in providers:
            selected = provider
            try:
                provider_result = provider.client.generate_json(
                    system_prompt=definition.system_prompt,
                    user_prompt=user_prompt,
                    output_schema=definition.output_schema,
                    temperature=float(request.parameters.get('temperature') or 0.2),
                    max_output_tokens=int(request.parameters.get('max_output_tokens') or 4000),
                )
                attempts.append({'provider': provider.name, 'model': provider.model_name, 'success': True})
                break
            except AIProviderError as exc:
                attempts.append(
                    {
                        'provider': provider.name,
                        'model': provider.model_name,
                        'success': False,
                        'code': exc.code,
                    }
                )
                last_error = exc
                if not exc.retryable and request.requested_provider != 'auto':
                    break

        if provider_result is None or selected is None:
            raise last_error or AIRequestExecutionError('فشل تنفيذ طلب الذكاء الاصطناعي.')

        # A user may cancel while the upstream provider is processing. Do not
        # overwrite that state or materialize records after cancellation.
        if AIRequest.objects.filter(pk=request.pk, status=AIRequest.Status.CANCELED).exists():
            return AIRequest.objects.get(pk=request.pk)

        request.status = AIRequest.Status.VALIDATING
        request.selected_provider = selected.name
        request.selected_model = provider_result.model_name or selected.model_name
        request.provider_request_id = provider_result.provider_request_id
        request.input_tokens = provider_result.input_tokens
        request.output_tokens = provider_result.output_tokens
        request.estimated_cost = estimate_cost(selected, request.input_tokens, request.output_tokens)
        request.latency_ms = int((time.monotonic() - started) * 1000)
        request.metadata = {**(request.metadata or {}), 'provider_attempts': attempts}
        request.save(
            update_fields=[
                'status', 'selected_provider', 'selected_model', 'provider_request_id',
                'prompt_version', 'input_tokens', 'output_tokens', 'estimated_cost',
                'latency_ms', 'metadata', 'updated_at',
            ]
        )

        validation_errors = validate_output(request.task_type, provider_result.data)
        validation_errors.extend(_constraint_errors(request, provider_result.data))
        grounding_errors, groundedness_score = validate_grounding(
            request.task_type,
            provider_result.data,
            references,
        )
        validation_errors.extend(grounding_errors)
        validation_errors = list(dict.fromkeys(validation_errors))
        validation_status = (
            AIOutput.ValidationStatus.VALID
            if not validation_errors
            else AIOutput.ValidationStatus.NEEDS_REVIEW
        )
        quality_score = max(0, 100 - min(len(validation_errors) * 15, 80))
        AIOutput.objects.update_or_create(
            request=request,
            defaults={
                'output_json': provider_result.data,
                'raw_provider_response': (
                    provider_result.raw_response
                    if getattr(settings, 'AI_PLATFORM_STORE_RAW_PROVIDER_RESPONSE', False)
                    else {}
                ),
                'validation_status': validation_status,
                'validation_errors': validation_errors,
                'quality_score': quality_score,
                'groundedness_score': groundedness_score,
                'source_references': references,
            },
        )
        if validation_errors and getattr(settings, 'AI_PLATFORM_REJECT_INVALID_OUTPUTS', True):
            raise AIRequestExecutionError('فشل فحص جودة المخرجات: ' + '; '.join(validation_errors))

        with transaction.atomic():
            locked = AIRequest.objects.select_for_update().get(pk=request.pk)
            if locked.status == AIRequest.Status.CANCELED:
                return locked
            materialized_result = materialize_output(request, provider_result.data)
            if materialized_result:
                request.metadata = {
                    **(request.metadata or {}),
                    'materialized_result': materialized_result,
                }
            request.status = AIRequest.Status.COMPLETED
            request.completed_at = timezone.now()
            request.actual_cost = request.estimated_cost
            request.save(
                update_fields=['status', 'completed_at', 'actual_cost', 'metadata', 'updated_at']
            )
        return request
    except Exception as exc:
        current = AIRequest.objects.get(pk=request.pk)
        if current.status == AIRequest.Status.CANCELED:
            return current
        request.status = AIRequest.Status.FAILED
        request.completed_at = timezone.now()
        request.latency_ms = int((time.monotonic() - started) * 1000)
        request.error_code = getattr(exc, 'code', 'ai_request_failed')
        request.error_message = str(exc)[:2000]
        request.save(
            update_fields=[
                'status', 'completed_at', 'latency_ms', 'error_code', 'error_message', 'updated_at'
            ]
        )
        _refund_once(request)
        return request


@transaction.atomic
def fail_queued_ai_request(request: AIRequest, *, code: str, message: str) -> AIRequest:
    """Fail and refund a request that could not be submitted to the worker queue."""

    locked = AIRequest.objects.select_for_update().get(pk=request.pk)
    if locked.status != AIRequest.Status.QUEUED:
        return locked
    locked.status = AIRequest.Status.FAILED
    locked.error_code = code[:80]
    locked.error_message = message[:2000]
    locked.completed_at = timezone.now()
    locked.save(
        update_fields=['status', 'error_code', 'error_message', 'completed_at', 'updated_at']
    )
    _refund_once(locked)
    return locked
