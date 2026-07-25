from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.models import BaseModel


class AIJob(BaseModel):
    class Character(models.TextChoices):
        FAHES = "fahes", "فاحص"
        KHOTA = "khota", "خطى"
        RASHEED = "rasheed", "رشيد"
        KHOLASA = "kholasa", "خلاصة"
        SADA = "sada", "صدى"

    class TaskType(models.TextChoices):
        FAHES_GENERATE_QUIZ = "fahes_generate_quiz", "Generate quiz"
        KHOTA_GENERATE_PLAN = "khota_generate_plan", "Generate study plan"
        RASHEED_RECOMMENDATIONS = "rasheed_recommendations", "Performance recommendations"
        KHOLASA_SUMMARY = "kholasa_summary", "Summarize source"
        SADA_TRANSCRIPTION = "sada_transcription", "Transcribe audio"

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        QUEUED = "queued", "Queued"
        SUBMITTED = "submitted", "Submitted to AI service"
        PROCESSING = "processing", "Processing"
        VALIDATING = "validating", "Validating"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_jobs",
    )
    character = models.CharField(max_length=20, choices=Character.choices, db_index=True)
    task_type = models.CharField(max_length=50, choices=TaskType.choices, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED, db_index=True)
    source = models.ForeignKey(
        "sources.StudentSource",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_jobs",
    )
    collection = models.ForeignKey(
        "sources.StudentSourceCollection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_jobs",
    )
    subject = models.ForeignKey(
        "subjects.Subject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_jobs",
    )
    external_job_id = models.CharField(max_length=128, blank=True, db_index=True)
    idempotency_key = models.CharField(max_length=128, db_index=True)
    input_payload = models.JSONField(default=dict, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    result_payload = models.JSONField(default=dict, blank=True)
    result_type = models.CharField(max_length=40, blank=True)
    result_id = models.CharField(max_length=64, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.TextField(blank=True)
    credits_reserved = models.BooleanField(default=False)
    credits_committed = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    service_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("user", "idempotency_key"),
                name="unique_ai_job_idempotency_per_user",
            ),
            models.CheckConstraint(
                condition=Q(source__isnull=True) | Q(collection__isnull=True),
                name="ai_job_single_source_target",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "status", "-created_at"), name="ai_job_user_status_idx"),
            models.Index(fields=("task_type", "status", "-created_at"), name="ai_job_task_status_idx"),
        ]

    def __str__(self):
        return f"{self.public_id} - {self.task_type} - {self.status}"


class AIFeedback(BaseModel):
    class FeedbackType(models.TextChoices):
        GENERAL = "general", "General"
        INCORRECT = "incorrect", "Incorrect"
        NOT_GROUNDED = "not_grounded", "Not grounded"
        UNCLEAR = "unclear", "Unclear"
        TOO_EASY = "too_easy", "Too easy"
        TOO_HARD = "too_hard", "Too hard"
        TOO_LONG = "too_long", "Too long"
        TOO_SHORT = "too_short", "Too short"
        OTHER = "other", "Other"

    job = models.ForeignKey(AIJob, on_delete=models.CASCADE, related_name="feedback")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_feedback")
    rating = models.PositiveSmallIntegerField()
    is_helpful = models.BooleanField(null=True, blank=True)
    feedback_type = models.CharField(max_length=30, choices=FeedbackType.choices, default=FeedbackType.GENERAL)
    reason_codes = models.JSONField(default=list, blank=True)
    comment = models.TextField(blank=True)
    corrected_output = models.JSONField(default=dict, blank=True)
    training_consent = models.BooleanField(default=False)
    consent_version = models.CharField(max_length=40, blank=True)
    forwarded_to_ai_service = models.BooleanField(default=False)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=("job", "user"), name="unique_feedback_per_ai_job_user"),
            models.CheckConstraint(condition=Q(rating__gte=1) & Q(rating__lte=5), name="ai_feedback_rating_1_5"),
        ]


class AIWebhookEvent(models.Model):
    event_id = models.CharField(max_length=128, unique=True)
    event_type = models.CharField(max_length=80)
    external_job_id = models.CharField(max_length=128, blank=True, db_index=True)
    payload_hash = models.CharField(max_length=64)
    processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-received_at",)
