from django.contrib import admin, messages
from django.utils import timezone

from .models import (
    AIFeedback,
    AIOutput,
    AIRequest,
    EvaluationRun,
    ModelDeployment,
    PromptVersion,
    SourceChunk,
    TrainingDatasetCandidate,
)


@admin.register(AIRequest)
class AIRequestAdmin(admin.ModelAdmin):
    list_display = (
        'public_id', 'user', 'task_type', 'status', 'selected_provider',
        'selected_model', 'estimated_cost', 'created_at',
    )
    list_filter = ('status', 'task_type', 'character', 'requested_provider', 'selected_provider')
    search_fields = ('public_id', 'user__email', 'provider_request_id')
    readonly_fields = (
        'public_id', 'input_hash', 'input_tokens', 'output_tokens',
        'estimated_cost', 'actual_cost', 'latency_ms', 'created_at', 'updated_at',
    )


@admin.register(AIOutput)
class AIOutputAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'request', 'validation_status', 'quality_score',
        'groundedness_score', 'is_accepted', 'created_at',
    )
    list_filter = ('validation_status', 'is_accepted', 'is_used_by_student')


@admin.register(AIFeedback)
class AIFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'output', 'rating', 'is_helpful',
        'feedback_type', 'allow_training', 'created_at',
    )
    list_filter = ('rating', 'is_helpful', 'feedback_type', 'allow_training')


@admin.action(description='Approve selected candidates for a versioned training dataset')
def approve_candidates(modeladmin, request, queryset):
    version = timezone.now().strftime('dataset-%Y%m%d')
    updated = queryset.filter(
        pii_status='filtered',
        anonymization_status='completed',
    ).update(
        human_review_status=TrainingDatasetCandidate.ReviewStatus.APPROVED,
        approved_for_training=True,
        dataset_version=version,
        reviewed_by=request.user,
        reviewed_at=timezone.now(),
    )
    modeladmin.message_user(
        request,
        f'Approved {updated} candidates for {version}. Export and offline evaluation are still required.',
        level=messages.SUCCESS,
    )


@admin.action(description='Reject selected training candidates')
def reject_candidates(modeladmin, request, queryset):
    updated = queryset.update(
        human_review_status=TrainingDatasetCandidate.ReviewStatus.REJECTED,
        approved_for_training=False,
        reviewed_by=request.user,
        reviewed_at=timezone.now(),
    )
    modeladmin.message_user(request, f'Rejected {updated} candidates.', level=messages.WARNING)


@admin.register(TrainingDatasetCandidate)
class TrainingDatasetCandidateAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'output', 'human_review_status', 'approved_for_training',
        'dataset_version', 'reviewed_by', 'created_at',
    )
    list_filter = (
        'human_review_status', 'approved_for_training',
        'pii_status', 'anonymization_status', 'dataset_version',
    )
    readonly_fields = ('anonymized_input', 'expected_output', 'created_at', 'updated_at')
    actions = (approve_candidates, reject_candidates)


@admin.register(ModelDeployment)
class ModelDeploymentAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'provider', 'model_name', 'priority', 'is_active',
        'input_cost_per_million', 'output_cost_per_million',
    )
    list_filter = ('provider', 'is_active')
    search_fields = ('name', 'model_name')


@admin.register(PromptVersion)
class PromptVersionAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'character', 'task_type', 'is_active', 'updated_at')
    list_filter = ('character', 'task_type', 'is_active')
    search_fields = ('name', 'system_prompt', 'prompt_template')


@admin.register(SourceChunk)
class SourceChunkAdmin(admin.ModelAdmin):
    list_display = ('source', 'chunk_index', 'page_number', 'embedding_model', 'token_count')
    search_fields = ('source__title', 'chunk_text', 'topic')


@admin.register(EvaluationRun)
class EvaluationRunAdmin(admin.ModelAdmin):
    list_display = ('name', 'dataset_version', 'provider', 'model_name', 'status', 'created_at')
    list_filter = ('status', 'provider', 'dataset_version')
