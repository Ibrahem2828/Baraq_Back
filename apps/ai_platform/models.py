from __future__ import annotations

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import BaseModel


class AICharacter(models.TextChoices):
    FAHES = 'fahes', 'Fahes'
    KHOTA = 'khota', 'Khota'
    RASHEED = 'rasheed', 'Rasheed'
    KHOLASA = 'kholasa', 'Kholasa'
    SADA = 'sada', 'Sada'


class AIProvider(models.TextChoices):
    AUTO = 'auto', 'Automatic router'
    OPENAI = 'openai', 'OpenAI'
    GEMINI = 'gemini', 'Google Gemini'
    DEEPSEEK = 'deepseek', 'DeepSeek'
    LOCAL = 'local', 'Local model'
    MOCK = 'mock', 'Mock provider'


class AITaskType(models.TextChoices):
    FAHES_GENERATE_QUIZ = 'fahes_generate_quiz', 'Fahes: Generate quiz'
    KHOTA_GENERATE_PLAN = 'khota_generate_plan', 'Khota: Generate study plan'
    RASHEED_RECOMMEND = 'rasheed_recommend', 'Rasheed: Recommendations'
    KHOLASA_SUMMARIZE = 'kholasa_summarize', 'Kholasa: Summarize'
    SADA_TRANSCRIBE = 'sada_transcribe', 'Sada: Transcribe audio'


class PromptVersion(BaseModel):
    name = models.CharField(max_length=120)
    version = models.PositiveIntegerField(default=1)
    character = models.CharField(max_length=20, choices=AICharacter.choices)
    task_type = models.CharField(max_length=50, choices=AITaskType.choices)
    system_prompt = models.TextField()
    prompt_template = models.TextField()
    output_schema = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_ai_prompts',
    )

    class Meta:
        ordering = ('name', '-version')
        constraints = [
            models.UniqueConstraint(
                fields=('name', 'version'),
                name='unique_ai_prompt_name_version',
            ),
            models.UniqueConstraint(
                fields=('task_type',),
                condition=models.Q(is_active=True),
                name='one_active_prompt_per_ai_task',
            ),
        ]

    def __str__(self):
        return f'{self.name} v{self.version}'


class ModelDeployment(BaseModel):
    name = models.CharField(max_length=120, unique=True)
    provider = models.CharField(max_length=20, choices=AIProvider.choices)
    model_name = models.CharField(max_length=160)
    supported_tasks = models.JSONField(default=list, blank=True)
    capabilities = models.JSONField(default=dict, blank=True)
    input_cost_per_million = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
    )
    output_cost_per_million = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
    )
    priority = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ('priority', 'name')

    def __str__(self):
        return f'{self.provider}:{self.model_name}'


class AIRequest(BaseModel):
    class Status(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        PROCESSING = 'processing', 'Processing'
        VALIDATING = 'validating', 'Validating'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        CANCELED = 'canceled', 'Canceled'

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_requests',
    )
    source = models.ForeignKey(
        'sources.StudentSource',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_requests',
    )
    collection = models.ForeignKey(
        'sources.StudentSourceCollection',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_requests',
    )
    character = models.CharField(max_length=20, choices=AICharacter.choices)
    task_type = models.CharField(max_length=50, choices=AITaskType.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    requested_provider = models.CharField(
        max_length=20,
        choices=AIProvider.choices,
        default=AIProvider.AUTO,
    )
    selected_provider = models.CharField(max_length=20, blank=True)
    selected_model = models.CharField(max_length=160, blank=True)
    prompt_version = models.ForeignKey(
        PromptVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requests',
    )
    input_payload = models.JSONField(default=dict)
    parameters = models.JSONField(default=dict, blank=True)
    input_hash = models.CharField(max_length=64, db_index=True)
    schema_version = models.CharField(max_length=30, default='1.0')
    provider_request_id = models.CharField(max_length=255, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.TextField(blank=True)
    consent_to_dataset = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('user', 'status', '-created_at')),
            models.Index(fields=('task_type', 'status')),
            models.Index(fields=('input_hash', 'task_type')),
        ]

    def __str__(self):
        return f'{self.public_id} - {self.task_type} - {self.status}'


class AIOutput(BaseModel):
    class ValidationStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        VALID = 'valid', 'Valid'
        INVALID = 'invalid', 'Invalid'
        NEEDS_REVIEW = 'needs_review', 'Needs review'

    request = models.OneToOneField(
        AIRequest,
        on_delete=models.CASCADE,
        related_name='output',
    )
    output_json = models.JSONField(default=dict)
    raw_provider_response = models.JSONField(default=dict, blank=True)
    validation_status = models.CharField(
        max_length=20,
        choices=ValidationStatus.choices,
        default=ValidationStatus.PENDING,
    )
    validation_errors = models.JSONField(default=list, blank=True)
    quality_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    groundedness_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    source_references = models.JSONField(default=list, blank=True)
    is_accepted = models.BooleanField(null=True, blank=True)
    is_used_by_student = models.BooleanField(default=False)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'Output for {self.request.public_id}'


class AIFeedback(BaseModel):
    class FeedbackType(models.TextChoices):
        GENERAL = 'general', 'General'
        INCORRECT = 'incorrect', 'Incorrect'
        NOT_GROUNDED = 'not_grounded', 'Not grounded in source'
        UNCLEAR = 'unclear', 'Unclear'
        TOO_EASY = 'too_easy', 'Too easy'
        TOO_HARD = 'too_hard', 'Too hard'
        TOO_LONG = 'too_long', 'Too long'
        TOO_SHORT = 'too_short', 'Too short'
        OTHER = 'other', 'Other'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_feedback',
    )
    output = models.ForeignKey(
        AIOutput,
        on_delete=models.CASCADE,
        related_name='feedback',
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    is_helpful = models.BooleanField()
    feedback_type = models.CharField(
        max_length=30,
        choices=FeedbackType.choices,
        default=FeedbackType.GENERAL,
    )
    issue_types = models.JSONField(default=list, blank=True)
    comment = models.TextField(blank=True)
    corrected_output = models.JSONField(default=dict, blank=True)
    allow_training = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'output'),
                name='one_ai_feedback_per_user_output',
            )
        ]

    def __str__(self):
        return f'{self.user_id} -> {self.output_id}: {self.rating}/5'


class SourceChunk(BaseModel):
    source = models.ForeignKey(
        'sources.StudentSource',
        on_delete=models.CASCADE,
        related_name='ai_chunks',
    )
    chunk_index = models.PositiveIntegerField()
    chunk_text = models.TextField()
    content_hash = models.CharField(max_length=64, db_index=True)
    page_number = models.PositiveIntegerField(null=True, blank=True)
    topic = models.CharField(max_length=255, blank=True)
    embedding = models.JSONField(default=list, blank=True)
    embedding_model = models.CharField(max_length=160, blank=True)
    token_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ('source_id', 'chunk_index')
        constraints = [
            models.UniqueConstraint(
                fields=('source', 'chunk_index'),
                name='unique_source_ai_chunk_index',
            )
        ]
        indexes = [models.Index(fields=('source', 'content_hash'))]

    def __str__(self):
        return f'{self.source_id}:{self.chunk_index}'


class TrainingDatasetCandidate(BaseModel):
    class ReviewStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    output = models.OneToOneField(
        AIOutput,
        on_delete=models.CASCADE,
        related_name='training_candidate',
    )
    feedback = models.ForeignKey(
        AIFeedback,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='training_candidates',
    )
    anonymized_input = models.JSONField(default=dict)
    expected_output = models.JSONField(default=dict)
    pii_status = models.CharField(max_length=30, default='pending')
    anonymization_status = models.CharField(max_length=30, default='pending')
    human_review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    approved_for_training = models.BooleanField(default=False)
    dataset_version = models.CharField(max_length=50, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_training_candidates',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)


class EvaluationRun(BaseModel):
    class Status(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        RUNNING = 'running', 'Running'
        PASSED = 'passed', 'Passed'
        FAILED = 'failed', 'Failed'

    name = models.CharField(max_length=160)
    dataset_version = models.CharField(max_length=50)
    provider = models.CharField(max_length=20, choices=AIProvider.choices)
    model_name = models.CharField(max_length=160)
    prompt_version = models.ForeignKey(
        PromptVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evaluation_runs',
    )
    code_commit = models.CharField(max_length=64, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)
