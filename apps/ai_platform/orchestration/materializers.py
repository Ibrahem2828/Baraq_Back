from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from django.db import transaction

from apps.ai_platform.models import AIRequest, AITaskType
from apps.quizzes.models import (
    Choice,
    GenerationTypeChoices,
    Question,
    QuestionBankItem,
    Quiz,
    QuizStatusChoices,
    QuizTypeChoices,
)
from apps.study_plans.models import StudyPlan, StudyPlanProgressLog, StudyTask
from apps.subjects.models import Subject


def _resolve_subject(request: AIRequest) -> Subject | None:
    if request.source_id and request.source.subject_id:
        return request.source.subject
    if request.collection_id and request.collection.subject_id:
        return request.collection.subject
    subject_id = request.input_payload.get('subject_id')
    if subject_id:
        return Subject.objects.filter(pk=subject_id).first()
    return None


@transaction.atomic
def materialize_fahes(request: AIRequest, data: dict[str, Any]) -> dict[str, Any] | None:
    subject = _resolve_subject(request)
    if subject is None:
        return None
    questions = data.get('questions') or []
    difficulty = str(request.parameters.get('difficulty') or 'medium')
    quiz = Quiz.objects.create(
        user=request.user,
        subject=subject,
        title=str(data.get('quiz_title') or f'اختبار {subject.name}')[:255],
        description='تم إنشاء هذا الاختبار بواسطة فاحص من محتوى الطالب.',
        topic=str(request.parameters.get('topic') or subject.name),
        difficulty_level=difficulty,
        quiz_type=QuizTypeChoices.PRACTICE,
        generation_type=GenerationTypeChoices.AI,
        status=QuizStatusChoices.PUBLISHED,
        questions_count=len(questions),
        time_limit_minutes=request.parameters.get('time_limit_minutes'),
        ai_request_id=str(request.public_id),
    )
    for order, item in enumerate(questions, start=1):
        question = Question.objects.create(
            quiz=quiz,
            text=item['question'],
            question_type=item['question_type'],
            difficulty_level=item.get('difficulty') or difficulty,
            explanation=item.get('explanation') or '',
            order=order,
            points=1,
        )
        choices = []
        correct_index = int(item['correct_answer_index'])
        for choice_index, choice_text in enumerate(item.get('choices') or []):
            choices.append(
                Choice.objects.create(
                    question=question,
                    text=choice_text,
                    is_correct=choice_index == correct_index,
                    order=choice_index + 1,
                )
            )
        QuestionBankItem.objects.create(
            subject=subject,
            created_by=request.user,
            text=question.text,
            question_type=question.question_type,
            difficulty_level=question.difficulty_level,
            explanation=question.explanation,
            metadata={
                'quiz_id': quiz.id,
                'ai_request_id': str(request.public_id),
                'topic': item.get('topic'),
                'source_reference': item.get('source_reference'),
                'choices': [
                    {'text': choice.text, 'order': choice.order, 'is_correct': choice.is_correct}
                    for choice in choices
                ],
            },
            is_public=False,
            is_active=True,
        )
    return {'result_type': 'quiz', 'result_id': quiz.id}


@transaction.atomic
def materialize_khota(request: AIRequest, data: dict[str, Any]) -> dict[str, Any] | None:
    subject = _resolve_subject(request)
    if subject is None:
        return None
    plan_days = data.get('plan_days') or []
    if not plan_days:
        return None
    dates = [date.fromisoformat(day['date']) for day in plan_days]
    start_date = date.fromisoformat(str(request.parameters.get('start_date'))) if request.parameters.get('start_date') else min(dates)
    end_date = date.fromisoformat(str(request.parameters.get('end_date'))) if request.parameters.get('end_date') else max(dates)
    daily_limit = max(15, min(int(request.parameters.get('daily_minutes') or 60), 720))
    plan = StudyPlan.objects.create(
        user=request.user,
        title=str(data.get('plan_title') or f'خطة {subject.name}')[:255],
        description=str(data.get('summary') or ''),
        subject=subject,
        start_date=start_date,
        end_date=end_date,
        daily_study_minutes=daily_limit,
        goal=str(request.input_payload.get('goal') or ''),
        difficulty_level=str(request.parameters.get('difficulty') or 'medium'),
        status=StudyPlan.Status.ACTIVE,
        generation_type=StudyPlan.GenerationType.AI,
        ai_request_id=str(request.public_id),
    )
    per_date_order: defaultdict[date, int] = defaultdict(int)
    for day in plan_days:
        task_date = date.fromisoformat(day['date'])
        if task_date < start_date or task_date > end_date:
            continue
        used_minutes = 0
        for item in day.get('tasks') or []:
            minutes = int(item.get('estimated_minutes') or 0)
            if minutes <= 0 or used_minutes + minutes > daily_limit:
                continue
            used_minutes += minutes
            per_date_order[task_date] += 1
            StudyTask.objects.create(
                plan=plan,
                title=str(item.get('topic') or item.get('subject') or subject.name)[:255],
                description=str(item.get('reason') or ''),
                task_date=task_date,
                estimated_minutes=minutes,
                priority=item.get('priority') or StudyTask.Priority.MEDIUM,
                status=StudyTask.Status.PENDING,
                order=per_date_order[task_date],
            )
    StudyPlanProgressLog.objects.create(
        user=request.user,
        plan=plan,
        action=StudyPlanProgressLog.Action.PLAN_CREATED,
        metadata={'generation_type': 'ai', 'ai_request_id': str(request.public_id), 'source': 'ai_platform'},
    )
    return {'result_type': 'study_plan', 'result_id': plan.id}


def materialize_output(request: AIRequest, data: dict[str, Any]) -> dict[str, Any] | None:
    existing = (request.metadata or {}).get('materialized_result')
    if existing:
        return existing
    if request.task_type == AITaskType.FAHES_GENERATE_QUIZ:
        return materialize_fahes(request, data)
    if request.task_type == AITaskType.KHOTA_GENERATE_PLAN:
        return materialize_khota(request, data)
    return None
