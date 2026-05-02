from uuid import uuid4

from .client import AIServiceClient
from .schemas import (
    GenerateQuizRequest,
    GenerateQuizResponse,
    GenerateRecommendationsRequest,
    GenerateRecommendationsResponse,
    GenerateStudyPlanRequest,
    GenerateStudyPlanResponse,
    SummarizeTextRequest,
    SummarizeTextResponse,
    TranscribeAudioRequest,
    TranscribeAudioResponse,
)

AVAILABLE_OPERATIONS = [
    'generate_study_plan',
    'generate_quiz',
    'summarize_text',
    'transcribe_audio',
    'generate_recommendations',
]


def _coerce_schema(payload, schema_class):
    if isinstance(payload, schema_class):
        return payload
    return schema_class(**payload)


def get_gateway_status():
    client = AIServiceClient()
    return {
        'enabled': client.is_enabled(),
        'base_url_configured': bool(client.base_url),
        'mode': 'remote' if client.is_enabled() else 'mock',
        'available_operations': AVAILABLE_OPERATIONS,
    }


def generate_study_plan(payload):
    request_payload = _coerce_schema(payload, GenerateStudyPlanRequest)
    client = AIServiceClient()

    if client.is_enabled():
        response_data = client.request(
            '/generate-study-plan',
            payload=request_payload.to_dict(),
        )
        return GenerateStudyPlanResponse(
            plan_title=response_data.get(
                'plan_title',
                f'{request_payload.subject} study plan',
            ),
            tasks=response_data.get('tasks', []),
        )

    tasks = []
    tasks_per_day = 1 if request_payload.daily_minutes <= 90 else 2
    for day_number in range(1, request_payload.days + 1):
        if tasks_per_day == 1:
            tasks.append(
                {
                    'day_number': day_number,
                    'title': f'Review {request_payload.subject} fundamentals',
                    'description': request_payload.goal
                    or f'Focused revision for {request_payload.subject}.',
                    'estimated_minutes': request_payload.daily_minutes,
                    'priority': 'medium',
                    'order': 1,
                }
            )
            continue

        first_block = max(request_payload.daily_minutes // 2, 1)
        second_block = max(request_payload.daily_minutes - first_block, 1)
        tasks.extend(
            [
                {
                    'day_number': day_number,
                    'title': f'Review a key topic in {request_payload.subject}',
                    'description': request_payload.goal
                    or f'Revise core concepts in {request_payload.subject}.',
                    'estimated_minutes': first_block,
                    'priority': 'medium',
                    'order': 1,
                },
                {
                    'day_number': day_number,
                    'title': f'Practice {request_payload.subject} exercises',
                    'description': f'Apply the reviewed concepts in {request_payload.subject}.',
                    'estimated_minutes': second_block,
                    'priority': 'high'
                    if request_payload.difficulty_level == 'hard'
                    else 'medium',
                    'order': 2,
                },
            ]
        )

    # TODO: Replace this mock response with the external AI service response.
    return GenerateStudyPlanResponse(
        plan_title=f'{request_payload.subject} Smart Plan {uuid4().hex[:6]}',
        tasks=tasks,
    )


def generate_quiz(payload):
    request_payload = _coerce_schema(payload, GenerateQuizRequest)
    client = AIServiceClient()

    if client.is_enabled():
        response_data = client.request(
            '/generate-quiz',
            payload=request_payload.to_dict(),
        )
        return GenerateQuizResponse(questions=response_data.get('questions', []))

    normalized_types = request_payload.question_types or ['mcq']
    questions = []
    for index in range(request_payload.questions_count):
        question_type = normalized_types[index % len(normalized_types)]
        order = index + 1
        question_payload = {
            'text': f'Mock AI question {order} about {request_payload.topic or request_payload.subject}.',
            'question_type': question_type,
            'difficulty_level': request_payload.difficulty_level,
            'explanation': (
                f'Mock explanation for question {order} in {request_payload.subject}.'
            ),
            'order': order,
            'points': 1,
            'choices': [],
        }

        if question_type == 'true_false':
            question_payload['choices'] = [
                {'text': 'True', 'is_correct': index % 2 == 0, 'order': 1},
                {'text': 'False', 'is_correct': index % 2 != 0, 'order': 2},
            ]
        else:
            correct_order = (index % 4) + 1
            question_payload['choices'] = [
                {
                    'text': f'Option {choice_order} for question {order}',
                    'is_correct': choice_order == correct_order,
                    'order': choice_order,
                }
                for choice_order in range(1, 5)
            ]

        questions.append(question_payload)

    # TODO: Replace this mock response with the external AI service response.
    return GenerateQuizResponse(questions=questions)


def summarize_text(payload):
    request_payload = _coerce_schema(payload, SummarizeTextRequest)
    client = AIServiceClient()

    if client.is_enabled():
        response_data = client.request(
            '/summarize-text',
            payload=request_payload.to_dict(),
        )
        return SummarizeTextResponse(
            summary=response_data.get('summary', ''),
            key_points=response_data.get('key_points', []),
            flashcards=response_data.get('flashcards', []),
        )

    # TODO: Replace this mock response with the external AI service response.
    return SummarizeTextResponse(
        summary='Mock summary generated by the AI gateway.',
        key_points=[
            f'Mock summary type: {request_payload.summary_type}',
            'Important point one.',
            'Important point two.',
        ],
        flashcards=[
            {'question': 'What is the main idea?', 'answer': 'This is a mock flashcard.'}
        ],
    )


def transcribe_audio(payload):
    request_payload = _coerce_schema(payload, TranscribeAudioRequest)
    client = AIServiceClient()

    if client.is_enabled():
        response_data = client.request(
            '/transcribe-audio',
            payload=request_payload.to_dict(),
        )
        return TranscribeAudioResponse(
            text=response_data.get('text', ''),
            duration_seconds=response_data.get('duration_seconds'),
            segments=response_data.get('segments', []),
        )

    # TODO: Replace this mock response with the external AI service response.
    return TranscribeAudioResponse(
        text='Mock transcription generated by the AI gateway.',
        duration_seconds=30,
        segments=[
            {
                'start': 0,
                'end': 30,
                'text': f'Mock transcription for {request_payload.file_url}.',
            }
        ],
    )


def generate_recommendations(payload):
    request_payload = _coerce_schema(payload, GenerateRecommendationsRequest)
    client = AIServiceClient()

    if client.is_enabled():
        response_data = client.request(
            '/generate-recommendations',
            payload=request_payload.to_dict(),
        )
        return GenerateRecommendationsResponse(
            recommendations=response_data.get('recommendations', [])
        )

    # TODO: Replace this mock response with the external AI service response.
    return GenerateRecommendationsResponse(
        recommendations=[
            'Review the weakest topic first.',
            'Keep study sessions short and consistent.',
            'Retake the quiz after reviewing the mistakes.',
        ]
    )


def ai_health_check():
    client = AIServiceClient()
    if not client.is_enabled():
        return {'status': 'disabled', 'mode': 'mock'}

    response_data = client.health_check()
    return {
        'status': response_data.get('status', 'ok'),
        'mode': 'remote',
    }
