from __future__ import annotations

from typing import Any

from apps.ai_platform.models import AITaskType


def _reference_key(value: Any) -> tuple[int | None, int | None] | None:
    if not isinstance(value, dict):
        return None
    source_id = value.get('source_id')
    chunk_index = value.get('chunk_index')
    try:
        source_id = int(source_id) if source_id is not None else None
        chunk_index = int(chunk_index) if chunk_index is not None else None
    except (TypeError, ValueError):
        return None
    return source_id, chunk_index


def validate_grounding(
    task_type: str,
    data: dict[str, Any],
    retrieved_references: list[dict[str, Any]],
) -> tuple[list[str], float | None]:
    """Validate that generated citations point to retrieved source chunks."""

    if not retrieved_references:
        return [], None
    allowed = {
        (int(item['source_id']), int(item['chunk_index']))
        for item in retrieved_references
        if item.get('source_id') is not None and item.get('chunk_index') is not None
    }
    cited: list[tuple[int | None, int | None] | None] = []
    if task_type == AITaskType.FAHES_GENERATE_QUIZ:
        cited = [_reference_key(item.get('source_reference')) for item in data.get('questions') or []]
    elif task_type == AITaskType.KHOLASA_SUMMARIZE:
        cited = [_reference_key(item) for item in data.get('source_references') or []]
    else:
        return [], None

    errors: list[str] = []
    valid_count = 0
    for index, key in enumerate(cited):
        if key is None or key not in allowed:
            errors.append(f'Citation {index + 1} does not match a retrieved source chunk.')
        else:
            valid_count += 1
    if not cited:
        return ['No source citations were returned.'], 0.0
    return errors, round((valid_count / len(cited)) * 100, 2)
