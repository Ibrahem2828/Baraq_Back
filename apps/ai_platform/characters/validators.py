from __future__ import annotations

from datetime import date
from typing import Any

from apps.ai_platform.models import AITaskType


class AIOutputValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__('; '.join(errors))
        self.errors = errors


def _require_string(data: dict[str, Any], key: str, errors: list[str]) -> None:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f'{key} must be a non-empty string.')


def validate_fahes(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _require_string(data, 'quiz_title', errors)
    questions = data.get('questions')
    if not isinstance(questions, list) or not questions:
        return errors + ['questions must be a non-empty list.']
    seen_questions: set[str] = set()
    for index, question in enumerate(questions):
        prefix = f'questions[{index}]'
        if not isinstance(question, dict):
            errors.append(f'{prefix} must be an object.')
            continue
        text = str(question.get('question') or '').strip()
        if not text:
            errors.append(f'{prefix}.question is required.')
        normalized = ' '.join(text.lower().split())
        if normalized and normalized in seen_questions:
            errors.append(f'{prefix}.question is duplicated.')
        seen_questions.add(normalized)
        q_type = question.get('question_type')
        choices = question.get('choices')
        expected_count = 2 if q_type == 'true_false' else 4
        if q_type not in {'mcq', 'true_false'}:
            errors.append(f'{prefix}.question_type is unsupported.')
        if not isinstance(choices, list) or len(choices) != expected_count:
            errors.append(f'{prefix}.choices must contain {expected_count} choices.')
            continue
        clean_choices = [' '.join(str(item).lower().split()) for item in choices]
        if any(not item for item in clean_choices):
            errors.append(f'{prefix}.choices cannot contain empty values.')
        if len(set(clean_choices)) != len(clean_choices):
            errors.append(f'{prefix}.choices must be unique.')
        answer_index = question.get('correct_answer_index')
        if not isinstance(answer_index, int) or not 0 <= answer_index < len(choices):
            errors.append(f'{prefix}.correct_answer_index is invalid.')
        _require_string(question, 'explanation', errors)
        _require_string(question, 'topic', errors)
    return errors


def validate_khota(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _require_string(data, 'plan_title', errors)
    days = data.get('plan_days')
    if not isinstance(days, list) or not days:
        return errors + ['plan_days must be a non-empty list.']
    seen_dates: set[str] = set()
    for day_index, day in enumerate(days):
        if not isinstance(day, dict):
            errors.append(f'plan_days[{day_index}] must be an object.')
            continue
        day_value = str(day.get('date') or '')
        try:
            date.fromisoformat(day_value)
        except ValueError:
            errors.append(f'plan_days[{day_index}].date must be ISO date.')
        if day_value in seen_dates:
            errors.append(f'plan_days[{day_index}].date is duplicated.')
        seen_dates.add(day_value)
        tasks = day.get('tasks')
        if not isinstance(tasks, list) or not tasks:
            errors.append(f'plan_days[{day_index}].tasks must be non-empty.')
            continue
        day_total = 0
        for task_index, task in enumerate(tasks):
            if not isinstance(task, dict):
                errors.append(f'plan_days[{day_index}].tasks[{task_index}] must be an object.')
                continue
            minutes = task.get('estimated_minutes')
            if not isinstance(minutes, int) or not 5 <= minutes <= 240:
                errors.append(f'plan_days[{day_index}].tasks[{task_index}].estimated_minutes is invalid.')
            else:
                day_total += minutes
            for field in ('subject', 'topic', 'reason'):
                _require_string(task, field, errors)
        if day_total > 720:
            errors.append(f'plan_days[{day_index}] exceeds the absolute daily safety limit.')
    return errors


def validate_rasheed(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    recommendations = data.get('recommendations')
    if not isinstance(recommendations, list) or not recommendations:
        errors.append('recommendations must be a non-empty list.')
    _require_string(data, 'next_best_action', errors)
    score = data.get('overall_score')
    if score is not None and (not isinstance(score, (int, float)) or not 0 <= score <= 100):
        errors.append('overall_score must be null or between 0 and 100.')
    return errors


def validate_kholasa(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _require_string(data, 'short_summary', errors)
    _require_string(data, 'detailed_summary', errors)
    if not isinstance(data.get('key_points'), list):
        errors.append('key_points must be a list.')
    return errors


def validate_sada(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _require_string(data, 'full_transcript', errors)
    if not isinstance(data.get('segments'), list):
        errors.append('segments must be a list.')
    return errors


VALIDATORS = {
    AITaskType.FAHES_GENERATE_QUIZ: validate_fahes,
    AITaskType.KHOTA_GENERATE_PLAN: validate_khota,
    AITaskType.RASHEED_RECOMMEND: validate_rasheed,
    AITaskType.KHOLASA_SUMMARIZE: validate_kholasa,
    AITaskType.SADA_TRANSCRIBE: validate_sada,
}


def validate_output(task_type: str, data: dict[str, Any]) -> list[str]:
    validator = VALIDATORS.get(task_type)
    if validator is None:
        return ['Unsupported AI task type.']
    return validator(data)
