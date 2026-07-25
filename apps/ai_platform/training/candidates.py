from __future__ import annotations

from django.db import transaction

from apps.ai_platform.models import AIFeedback, SourceChunk, TrainingDatasetCandidate

from .anonymizer import anonymize_value


MAX_TRAINING_CONTEXT_CHARS = 24000


def _training_input(feedback: AIFeedback) -> dict:
    request = feedback.output.request
    payload = {
        'task_type': request.task_type,
        'character': request.character,
        'parameters': request.parameters,
        'input_payload': request.input_payload,
        'source_context': [],
    }
    references = feedback.output.source_references or []
    remaining = MAX_TRAINING_CONTEXT_CHARS
    for reference in references:
        source_id = reference.get('source_id')
        chunk_index = reference.get('chunk_index')
        if source_id is None or chunk_index is None or remaining <= 0:
            continue
        chunk = SourceChunk.objects.filter(
            source_id=source_id,
            chunk_index=chunk_index,
        ).only('source_id', 'chunk_index', 'page_number', 'chunk_text').first()
        if chunk is None:
            continue
        text = chunk.chunk_text[:remaining]
        remaining -= len(text)
        payload['source_context'].append(
            {
                'source_id': chunk.source_id,
                'chunk_index': chunk.chunk_index,
                'page_number': chunk.page_number,
                'text': text,
            }
        )
    return anonymize_value(payload)


@transaction.atomic
def create_or_update_training_candidate(feedback: AIFeedback) -> TrainingDatasetCandidate | None:
    request = feedback.output.request
    if not (request.consent_to_dataset and feedback.allow_training):
        return None

    # A negative rating is valuable for evaluation, but it is not a supervised
    # target unless the user supplied a correction. This prevents training on
    # a model output that the same user marked as incorrect or unhelpful.
    if not feedback.is_helpful and not feedback.corrected_output:
        TrainingDatasetCandidate.objects.filter(output=feedback.output).delete()
        return None

    expected = feedback.corrected_output or feedback.output.output_json
    candidate, _ = TrainingDatasetCandidate.objects.update_or_create(
        output=feedback.output,
        defaults={
            'feedback': feedback,
            'anonymized_input': _training_input(feedback),
            'expected_output': anonymize_value(expected),
            'pii_status': 'filtered',
            'anonymization_status': 'completed',
            # Deliberately pending: no automatic training approval from a user rating.
            'human_review_status': TrainingDatasetCandidate.ReviewStatus.PENDING,
            'approved_for_training': False,
        },
    )
    return candidate
