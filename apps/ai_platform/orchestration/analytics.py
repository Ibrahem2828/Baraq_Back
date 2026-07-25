from __future__ import annotations

from django.db.models import Avg, Count, Q, Sum

from apps.quizzes.models import AttemptStatusChoices, QuizAttempt
from apps.study_plans.models import StudyTask


def _subject_id_for_request(request) -> int | None:
    if request.source_id and request.source and request.source.subject_id:
        return request.source.subject_id
    if request.collection_id and request.collection and request.collection.subject_id:
        return request.collection.subject_id
    value = (request.input_payload or {}).get('subject_id')
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def build_authoritative_student_metrics(request) -> dict:
    """Compute Rasheed inputs in the backend instead of trusting model arithmetic."""

    subject_id = _subject_id_for_request(request)
    attempts = QuizAttempt.objects.filter(
        user=request.user,
        status=AttemptStatusChoices.SUBMITTED,
    )
    tasks = StudyTask.objects.filter(plan__user=request.user)
    if subject_id:
        attempts = attempts.filter(quiz__subject_id=subject_id)
        tasks = tasks.filter(plan__subject_id=subject_id)

    attempt_totals = attempts.aggregate(
        attempts_count=Count('id'),
        average_percentage=Avg('percentage'),
        correct_answers=Sum('correct_answers_count'),
        wrong_answers=Sum('wrong_answers_count'),
        unanswered=Sum('unanswered_count'),
        average_duration_seconds=Avg('duration_seconds'),
    )
    topic_rows = list(
        attempts.values('quiz__topic')
        .annotate(average_percentage=Avg('percentage'), attempts_count=Count('id'))
        .order_by('average_percentage')[:20]
    )
    task_totals = tasks.aggregate(
        tasks_count=Count('id'),
        completed_tasks=Count('id', filter=Q(status=StudyTask.Status.COMPLETED)),
        skipped_tasks=Count('id', filter=Q(status=StudyTask.Status.SKIPPED)),
        pending_tasks=Count('id', filter=Q(status=StudyTask.Status.PENDING)),
    )
    tasks_count = int(task_totals.get('tasks_count') or 0)
    completed = int(task_totals.get('completed_tasks') or 0)

    return {
        'scope': {'subject_id': subject_id},
        'quiz_performance': {
            'attempts_count': int(attempt_totals.get('attempts_count') or 0),
            'average_percentage': _number(attempt_totals.get('average_percentage')),
            'correct_answers': int(attempt_totals.get('correct_answers') or 0),
            'wrong_answers': int(attempt_totals.get('wrong_answers') or 0),
            'unanswered': int(attempt_totals.get('unanswered') or 0),
            'average_duration_seconds': _number(attempt_totals.get('average_duration_seconds')),
            'topics': [
                {
                    'topic': row.get('quiz__topic') or 'غير مصنف',
                    'average_percentage': _number(row.get('average_percentage')),
                    'attempts_count': int(row.get('attempts_count') or 0),
                }
                for row in topic_rows
            ],
        },
        'study_plan_adherence': {
            'tasks_count': tasks_count,
            'completed_tasks': completed,
            'skipped_tasks': int(task_totals.get('skipped_tasks') or 0),
            'pending_tasks': int(task_totals.get('pending_tasks') or 0),
            'completion_rate': round((completed / tasks_count) * 100, 2) if tasks_count else None,
        },
    }


def _number(value):
    if value is None:
        return None
    return round(float(value), 2)
