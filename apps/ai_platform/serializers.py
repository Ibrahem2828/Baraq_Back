from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.sources.models import StudentSource, StudentSourceCollection
from apps.subscriptions.services import reserve_character_request

from .models import (
    AICharacter,
    AIFeedback,
    AIOutput,
    AIProvider,
    AIRequest,
    AITaskType,
)
from .orchestration import canonical_hash
from .training import create_or_update_training_candidate


TASK_CHARACTER_MAP = {
    AITaskType.FAHES_GENERATE_QUIZ: AICharacter.FAHES,
    AITaskType.KHOTA_GENERATE_PLAN: AICharacter.KHOTA,
    AITaskType.RASHEED_RECOMMEND: AICharacter.RASHEED,
    AITaskType.KHOLASA_SUMMARIZE: AICharacter.KHOLASA,
    AITaskType.SADA_TRANSCRIBE: AICharacter.SADA,
}
PHASE_TWO_TASKS = {AITaskType.KHOLASA_SUMMARIZE, AITaskType.SADA_TRANSCRIBE}


def _source_version_payload(source, collection) -> dict:
    """Include content versions in cache keys, not only database identifiers."""

    if source is not None:
        return {
            'source_id': source.id,
            'source_updated_at': source.updated_at.isoformat(),
            'source_text_hash': canonical_hash({'text': source.extracted_text or ''}),
        }
    if collection is not None:
        source_versions = list(
            collection.sources.order_by('id').values_list('id', 'updated_at')
        )
        return {
            'collection_id': collection.id,
            'collection_updated_at': collection.updated_at.isoformat(),
            'collection_source_versions': [
                [source_id, updated_at.isoformat()]
                for source_id, updated_at in source_versions
            ],
        }
    return {}


def _clone_cached_request(*, cached, user, source, collection, validated_data, input_hash):
    metadata = {
        'usage_reserved': False,
        'usage_refunded': False,
        'cache_hit': True,
        'cached_from_public_id': str(cached.public_id),
        'dataset_consent_version': (
            getattr(settings, 'AI_DATASET_CONSENT_VERSION', '')
            if validated_data.get('consent_to_dataset')
            else ''
        ),
        'dataset_consented_at': (
            timezone.now().isoformat()
            if validated_data.get('consent_to_dataset')
            else None
        ),
    }
    previous_result = (cached.metadata or {}).get('materialized_result')
    if previous_result:
        metadata['materialized_result'] = previous_result

    cloned = AIRequest.objects.create(
        user=user,
        source=source,
        collection=collection,
        input_hash=input_hash,
        status=AIRequest.Status.COMPLETED,
        selected_provider=cached.selected_provider,
        selected_model=cached.selected_model,
        prompt_version=cached.prompt_version,
        provider_request_id='',
        input_tokens=0,
        output_tokens=0,
        estimated_cost=0,
        actual_cost=0,
        latency_ms=0,
        started_at=timezone.now(),
        completed_at=timezone.now(),
        metadata=metadata,
        **validated_data,
    )
    previous_output = cached.output
    AIOutput.objects.create(
        request=cloned,
        output_json=previous_output.output_json,
        validation_status=previous_output.validation_status,
        validation_errors=previous_output.validation_errors,
        quality_score=previous_output.quality_score,
        groundedness_score=previous_output.groundedness_score,
        source_references=previous_output.source_references,
        is_accepted=None,
        is_used_by_student=False,
    )
    return cloned


class AIOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIOutput
        fields = (
            'id',
            'output_json',
            'validation_status',
            'validation_errors',
            'quality_score',
            'groundedness_score',
            'source_references',
            'is_accepted',
            'is_used_by_student',
            'created_at',
        )
        read_only_fields = fields


class AIFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIFeedback
        fields = (
            'id',
            'rating',
            'is_helpful',
            'feedback_type',
            'issue_types',
            'comment',
            'corrected_output',
            'allow_training',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate_issue_types(self, value):
        allowed = {choice for choice, _ in AIFeedback.FeedbackType.choices}
        invalid = [item for item in value if item not in allowed]
        if invalid:
            raise serializers.ValidationError(f'Unsupported issue types: {invalid}')
        return list(dict.fromkeys(value))

    @transaction.atomic
    def create(self, validated_data):
        output = self.context['output']
        user = self.context['request'].user
        feedback, _ = AIFeedback.objects.update_or_create(
            user=user,
            output=output,
            defaults=validated_data,
        )
        output.is_accepted = feedback.is_helpful
        output.save(update_fields=['is_accepted', 'updated_at'])
        create_or_update_training_candidate(feedback)
        return feedback


class AIRequestSerializer(serializers.ModelSerializer):
    output = AIOutputSerializer(read_only=True)
    result_type = serializers.SerializerMethodField()
    result_id = serializers.SerializerMethodField()

    class Meta:
        model = AIRequest
        fields = (
            'public_id',
            'character',
            'task_type',
            'status',
            'requested_provider',
            'selected_provider',
            'selected_model',
            'source_id',
            'collection_id',
            'parameters',
            'input_tokens',
            'output_tokens',
            'estimated_cost',
            'actual_cost',
            'latency_ms',
            'error_code',
            'error_message',
            'consent_to_dataset',
            'started_at',
            'completed_at',
            'created_at',
            'output',
            'result_type',
            'result_id',
        )
        read_only_fields = fields

    def get_result_type(self, obj):
        return ((obj.metadata or {}).get('materialized_result') or {}).get('result_type')

    def get_result_id(self, obj):
        return ((obj.metadata or {}).get('materialized_result') or {}).get('result_id')


class AIRequestCreateSerializer(serializers.Serializer):
    character = serializers.ChoiceField(choices=AICharacter.choices, required=False)
    task_type = serializers.ChoiceField(choices=AITaskType.choices)
    requested_provider = serializers.ChoiceField(
        choices=AIProvider.choices,
        default=AIProvider.AUTO,
    )
    source_id = serializers.IntegerField(required=False, allow_null=True)
    collection_id = serializers.IntegerField(required=False, allow_null=True)
    input_payload = serializers.JSONField(required=False, default=dict)
    parameters = serializers.JSONField(required=False, default=dict)
    consent_to_dataset = serializers.BooleanField(default=False)

    def validate(self, attrs):
        task_type = attrs['task_type']
        requested_provider = attrs.get('requested_provider', AIProvider.AUTO)
        request_user = self.context['request'].user
        if requested_provider != AIProvider.AUTO and not request_user.is_staff:
            raise serializers.ValidationError(
                {'requested_provider': 'Provider selection is controlled by the server router.'}
            )
        if requested_provider == AIProvider.MOCK and not getattr(settings, 'AI_PLATFORM_ALLOW_MOCK', False):
            raise serializers.ValidationError({'requested_provider': 'Mock provider is disabled.'})
        if requested_provider == AIProvider.LOCAL and not (
            getattr(settings, 'AI_LOCAL_BASE_URL', '') and getattr(settings, 'AI_LOCAL_MODEL', '')
        ):
            raise serializers.ValidationError({'requested_provider': 'Local provider is not configured.'})

        expected_character = TASK_CHARACTER_MAP[task_type]
        supplied_character = attrs.get('character')
        if supplied_character and supplied_character != expected_character:
            raise serializers.ValidationError(
                {'character': f'Task {task_type} belongs to {expected_character}.'}
            )
        attrs['character'] = expected_character

        if task_type in PHASE_TWO_TASKS and not getattr(settings, 'AI_PLATFORM_PHASE_TWO_ENABLED', False):
            raise serializers.ValidationError(
                {'task_type': 'هذه المهمة ضمن المرحلة الثانية ولم يتم تفعيلها بعد.'}
            )

        source_id = attrs.get('source_id')
        collection_id = attrs.get('collection_id')
        if source_id and collection_id:
            raise serializers.ValidationError('Choose a source or collection, not both.')

        user = self.context['request'].user
        if source_id:
            source = StudentSource.objects.filter(pk=source_id, user=user).first()
            if source is None:
                raise serializers.ValidationError({'source_id': 'Source was not found.'})
            if source.status != StudentSource.Status.READY or not source.extracted_text:
                raise serializers.ValidationError({'source_id': 'Source text is not ready.'})
            attrs['source'] = source
        if collection_id:
            collection = StudentSourceCollection.objects.filter(pk=collection_id, user=user).first()
            if collection is None:
                raise serializers.ValidationError({'collection_id': 'Collection was not found.'})
            attrs['collection'] = collection

        direct_payload = attrs.get('input_payload') or {}
        if not source_id and not collection_id:
            has_direct_input = any(
                direct_payload.get(key)
                for key in ('text', 'transcript', 'metrics', 'context', 'priority_inputs')
            )
            if not has_direct_input:
                raise serializers.ValidationError(
                    {'input_payload': 'Provide a source, collection, text, metrics, or calculated context.'}
                )

        direct_text = str(direct_payload.get('text') or direct_payload.get('transcript') or '')
        max_chars = int(getattr(settings, 'AI_PLATFORM_MAX_CONTEXT_CHARS', 50000))
        if len(direct_text) > max_chars:
            raise serializers.ValidationError(
                {'input_payload': f'Direct text exceeds the {max_chars}-character limit.'}
            )
        parameters = attrs.get('parameters') or {}
        max_output_tokens = int(parameters.get('max_output_tokens') or 4000)
        if not 100 <= max_output_tokens <= 16000:
            raise serializers.ValidationError(
                {'parameters': 'max_output_tokens must be between 100 and 16000.'}
            )

        if task_type == AITaskType.KHOTA_GENERATE_PLAN:
            daily_minutes = int((attrs.get('parameters') or {}).get('daily_minutes') or 60)
            if not 15 <= daily_minutes <= 720:
                raise serializers.ValidationError({'parameters': 'daily_minutes must be between 15 and 720.'})
        if task_type == AITaskType.FAHES_GENERATE_QUIZ:
            count = int((attrs.get('parameters') or {}).get('questions_count') or 10)
            if not 1 <= count <= 50:
                raise serializers.ValidationError({'parameters': 'questions_count must be between 1 and 50.'})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user
        source = validated_data.pop('source', None)
        collection = validated_data.pop('collection', None)
        validated_data.pop('source_id', None)
        validated_data.pop('collection_id', None)
        character = validated_data['character']
        input_payload = validated_data.get('input_payload') or {}
        parameters = validated_data.get('parameters') or {}
        force_refresh = bool(parameters.get('force_refresh', False))
        input_hash = canonical_hash(
            {
                'user_id': user.id,
                **_source_version_payload(source, collection),
                'task_type': validated_data['task_type'],
                'input_payload': input_payload,
                'parameters': {key: value for key, value in parameters.items() if key != 'force_refresh'},
            }
        )

        if getattr(settings, 'AI_PLATFORM_CACHE_COMPLETED_REQUESTS', True) and not force_refresh:
            cached = (
                AIRequest.objects.filter(
                    user=user,
                    task_type=validated_data['task_type'],
                    input_hash=input_hash,
                    status=AIRequest.Status.COMPLETED,
                    output__validation_status=AIOutput.ValidationStatus.VALID,
                )
                .select_related('output', 'prompt_version')
                .order_by('-completed_at')
                .first()
            )
            if cached is not None:
                return _clone_cached_request(
                    cached=cached,
                    user=user,
                    source=source,
                    collection=collection,
                    validated_data=validated_data,
                    input_hash=input_hash,
                )

        reserve_character_request(user, character)
        return AIRequest.objects.create(
            user=user,
            source=source,
            collection=collection,
            input_hash=input_hash,
            metadata={
                'usage_reserved': True,
                'usage_refunded': False,
                'cache_hit': False,
                'dataset_consent_version': (
                    getattr(settings, 'AI_DATASET_CONSENT_VERSION', '')
                    if validated_data.get('consent_to_dataset')
                    else ''
                ),
                'dataset_consented_at': (
                    timezone.now().isoformat()
                    if validated_data.get('consent_to_dataset')
                    else None
                ),
            },
            **validated_data,
        )
