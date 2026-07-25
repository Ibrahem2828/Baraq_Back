from __future__ import annotations

import hashlib
import json
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.sources.models import StudentSourceInteraction
from apps.subscriptions.services import refund_character_request, reserve_character_request

from .client import AIServiceClient, AIServiceError
from .materializers import materialize_job
from .models import AIFeedback, AIJob

logger = logging.getLogger(__name__)

TASK_CHARACTER = {
    AIJob.TaskType.FAHES_GENERATE_QUIZ: AIJob.Character.FAHES,
    AIJob.TaskType.KHOTA_GENERATE_PLAN: AIJob.Character.KHOTA,
    AIJob.TaskType.RASHEED_RECOMMENDATIONS: AIJob.Character.RASHEED,
    AIJob.TaskType.KHOLASA_SUMMARY: AIJob.Character.KHOLASA,
    AIJob.TaskType.SADA_TRANSCRIPTION: AIJob.Character.SADA,
}


def build_idempotency_key(user_id, task_type, source_id, collection_id, payload, parameters):
    canonical = json.dumps(
        {
            "user_id": user_id,
            "task_type": task_type,
            "source_id": source_id,
            "collection_id": collection_id,
            "payload": payload,
            "parameters": parameters,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_job_ownership(user, source=None, collection=None, subject=None):
    if source and source.user_id != user.id:
        raise ValidationError({"source": "You do not own this source."})
    if collection and collection.user_id != user.id:
        raise ValidationError({"collection": "You do not own this collection."})
    if source and collection:
        raise ValidationError("Choose either source or collection, not both.")
    if source and subject and source.subject_id and source.subject_id != subject.id:
        raise ValidationError({"subject": "Subject does not match the selected source."})


@transaction.atomic
def create_ai_job(*, user, task_type, source=None, collection=None, subject=None, input_payload=None, parameters=None, force=False):
    input_payload = input_payload or {}
    parameters = parameters or {}
    character = TASK_CHARACTER[task_type]
    validate_job_ownership(user, source, collection, subject)
    key = build_idempotency_key(user.id, task_type, getattr(source, "id", None), getattr(collection, "id", None), input_payload, parameters)
    if not force:
        existing = AIJob.objects.filter(user=user, idempotency_key=key).exclude(status__in=[AIJob.Status.FAILED, AIJob.Status.CANCELED]).first()
        if existing:
            return existing, False
    if force:
        key = hashlib.sha256(f"{key}:{timezone.now().isoformat()}".encode()).hexdigest()
    reserve_character_request(user, character)
    job = AIJob.objects.create(
        user=user,
        character=character,
        task_type=task_type,
        source=source,
        collection=collection,
        subject=subject or getattr(source, "subject", None) or getattr(collection, "subject", None),
        idempotency_key=key,
        input_payload=input_payload,
        parameters=parameters,
        status=AIJob.Status.QUEUED,
        credits_reserved=True,
    )
    StudentSourceInteraction.objects.create(
        user=user,
        source=source,
        collection=collection,
        character=character,
        action={
            AIJob.Character.FAHES: StudentSourceInteraction.Action.CREATE_QUIZ,
            AIJob.Character.KHOTA: StudentSourceInteraction.Action.CREATE_STUDY_PLAN,
            AIJob.Character.RASHEED: StudentSourceInteraction.Action.STUDY_ADVICE,
            AIJob.Character.KHOLASA: StudentSourceInteraction.Action.SUMMARIZE,
            AIJob.Character.SADA: StudentSourceInteraction.Action.VOICE_HELP,
        }[character],
        status=StudentSourceInteraction.Status.CREATED,
        metadata={"ai_job_id": str(job.public_id)},
    ) if source or collection else None
    from .tasks import dispatch_ai_job
    transaction.on_commit(lambda: dispatch_ai_job.delay(job.pk))
    return job, True


def build_service_payload(job):
    base = settings.PUBLIC_API_BASE_URL.rstrip("/")
    return {
        "client_job_id": str(job.public_id),
        "user_id": job.user_id,
        "character": job.character,
        "task_type": job.task_type,
        "source_id": job.source_id,
        "collection_id": job.collection_id,
        "subject_id": job.subject_id,
        "input": job.input_payload,
        "parameters": job.parameters,
        "callback_url": f"{base}/api/internal/v1/ai/webhooks/jobs/",
        "source_manifest_url": f"{base}/api/internal/v1/ai/sources/{job.source_id}/manifest/" if job.source_id else None,
        "collection_manifest_url": f"{base}/api/internal/v1/ai/collections/{job.collection_id}/manifest/" if job.collection_id else None,
        "user_context_url": f"{base}/api/internal/v1/ai/users/{job.user_id}/context/",
    }


def submit_job_to_service(job):
    response = AIServiceClient().create_job(build_service_payload(job), str(job.public_id))
    data = response.data
    external_job_id = str(data.get("job_id") or data.get("id") or "")
    if not external_job_id:
        raise AIServiceError('AI service did not return a job identifier.', code='invalid_ai_service_response', retryable=False)
    job.external_job_id = external_job_id
    job.status = AIJob.Status.SUBMITTED
    job.submitted_at = timezone.now()
    job.last_synced_at = timezone.now()
    job.service_metadata = {**job.service_metadata, "submit_response": data}
    job.save(update_fields=["external_job_id", "status", "submitted_at", "last_synced_at", "service_metadata", "updated_at"])
    return job


@transaction.atomic
def fail_job(job, error):
    job = AIJob.objects.select_for_update().get(pk=job.pk)
    if job.status in {AIJob.Status.COMPLETED, AIJob.Status.CANCELED, AIJob.Status.FAILED}:
        return job
    job.status = AIJob.Status.FAILED
    job.error_code = getattr(error, "code", "ai_job_failed")
    job.error_message = str(error)[:2000]
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "error_code", "error_message", "completed_at", "updated_at"])
    if job.credits_reserved and not job.credits_committed:
        refund_character_request(job.user, job.character)
        job.credits_reserved = False
        job.save(update_fields=["credits_reserved", "updated_at"])
    from apps.notifications.models import Notification
    Notification.objects.create(
        user=job.user,
        category=Notification.Category.AI,
        title="تعذر إكمال الطلب الذكي",
        body="لم يكتمل الطلب. لم يتم احتساب الاستخدام المحجوز ويمكنك المحاولة مجددًا.",
        data={"ai_job_id": str(job.public_id), "task_type": job.task_type, "error_code": job.error_code},
        action_url=f"/ai/jobs/{job.public_id}",
    )
    return job


@transaction.atomic
def complete_job(job, result_payload, metadata=None):
    job = AIJob.objects.select_for_update().select_related("user", "source", "collection", "subject").get(pk=job.pk)
    if job.status == AIJob.Status.COMPLETED:
        return job
    if job.status in {AIJob.Status.CANCELED, AIJob.Status.FAILED}:
        logger.warning('Ignoring late AI completion for terminal job %s in status %s.', job.public_id, job.status)
        return job
    result_type, result_id = materialize_job(job, result_payload)
    job.status = AIJob.Status.COMPLETED
    job.result_payload = result_payload
    job.result_type = result_type
    job.result_id = result_id
    job.credits_committed = True
    job.completed_at = timezone.now()
    job.last_synced_at = timezone.now()
    job.service_metadata = {**job.service_metadata, **(metadata or {})}
    job.save()
    StudentSourceInteraction.objects.filter(metadata__ai_job_id=str(job.public_id)).update(
        status=StudentSourceInteraction.Status.COMPLETED,
        result_type=result_type,
        result_id=int(result_id) if str(result_id).isdigit() else None,
    )
    from apps.notifications.models import Notification
    Notification.objects.create(
        user=job.user,
        category=Notification.Category.AI,
        title="اكتملت المعالجة الذكية",
        body="أصبحت نتيجة الطلب جاهزة للمراجعة.",
        data={"ai_job_id": str(job.public_id), "task_type": job.task_type, "result_type": result_type, "result_id": result_id},
        action_url=f"/ai/jobs/{job.public_id}",
    )
    return job


def cancel_job(job):
    external_job_id = ''
    with transaction.atomic():
        job = AIJob.objects.select_for_update().get(pk=job.pk)
        if job.status in {AIJob.Status.COMPLETED, AIJob.Status.FAILED, AIJob.Status.CANCELED}:
            return job
        external_job_id = job.external_job_id
        job.status = AIJob.Status.CANCELED
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "completed_at", "updated_at"])
        if job.credits_reserved and not job.credits_committed:
            refund_character_request(job.user, job.character)
            job.credits_reserved = False
            job.save(update_fields=["credits_reserved", "updated_at"])
    if external_job_id:
        from .tasks import cancel_external_ai_job
        transaction.on_commit(lambda: cancel_external_ai_job.delay(external_job_id))
    return job


def forward_feedback(feedback):
    payload = {
        "client_feedback_id": feedback.id,
        "client_job_id": str(feedback.job.public_id),
        "external_job_id": feedback.job.external_job_id,
        "user_id": feedback.user_id,
        "rating": feedback.rating,
        "is_helpful": feedback.is_helpful,
        "feedback_type": feedback.feedback_type,
        "reason_codes": feedback.reason_codes,
        "comment": feedback.comment,
        "corrected_output": feedback.corrected_output,
        "training_consent": feedback.training_consent,
        "consent_version": feedback.consent_version,
    }
    AIServiceClient().send_feedback(payload, f"feedback:{feedback.id}")
    feedback.forwarded_to_ai_service = True
    feedback.save(update_fields=["forwarded_to_ai_service", "updated_at"])
