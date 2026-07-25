from celery import shared_task

from .models import AIFeedback, AIJob
from .client import AIServiceClient, AIServiceError
from .services import fail_job, forward_feedback, submit_job_to_service


@shared_task(bind=True, autoretry_for=(), max_retries=3, retry_backoff=True, retry_jitter=True, name="ai_integration.dispatch_job")
def dispatch_ai_job(self, job_id):
    job = AIJob.objects.get(pk=job_id)
    if job.status not in {AIJob.Status.QUEUED, AIJob.Status.CREATED}:
        return str(job.public_id)
    try:
        submit_job_to_service(job)
    except Exception as exc:
        if getattr(exc, "retryable", False) and self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        fail_job(job, exc)
        raise
    return str(job.public_id)


@shared_task(bind=True, max_retries=3, retry_backoff=True, retry_jitter=True, name="ai_integration.forward_feedback")
def forward_ai_feedback(self, feedback_id):
    feedback = AIFeedback.objects.select_related("job").get(pk=feedback_id)
    if feedback.forwarded_to_ai_service:
        return feedback.id
    try:
        forward_feedback(feedback)
    except Exception as exc:
        raise self.retry(exc=exc)
    return feedback.id


@shared_task(bind=True, max_retries=3, retry_backoff=True, retry_jitter=True, name="ai_integration.cancel_external_job")
def cancel_external_ai_job(self, external_job_id):
    try:
        AIServiceClient().cancel_job(external_job_id)
    except AIServiceError as exc:
        if exc.retryable:
            raise self.retry(exc=exc)
        return False
    return True
