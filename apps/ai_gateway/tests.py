import json
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.subjects.models import EducationStage, Subject

from .client import AIServiceClient
from .exceptions import AIServiceTimeoutError
from .services import (
    generate_quiz,
    generate_recommendations,
    generate_study_plan,
    summarize_text,
    transcribe_audio,
)

User = get_user_model()


@override_settings(
    ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'],
    AI_SERVICE_ENABLED=False,
    AI_SERVICE_BASE_URL='http://localhost:8001',
    AI_SERVICE_API_KEY='super-secret-key',
    AI_SERVICE_TIMEOUT_SECONDS=60,
    AI_SERVICE_VERIFY_SSL=True,
    AI_SERVICE_RETRY_COUNT=2,
)
class AIGatewayAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='ai-gateway-user@example.com',
            password='StrongPass123',
            full_name='AI Gateway User',
        )
        self.stage = EducationStage.objects.create(
            name='AI Stage',
            description='Stage',
            order=50,
        )
        self.subject = Subject.objects.create(
            name='AI Physics',
            education_stage=self.stage,
            grade_level='Grade 12',
            description='AI physics subject',
        )

    def authenticate(self):
        self.client.force_authenticate(self.user)

    def test_status_endpoint_returns_200_for_authenticated_user(self):
        self.authenticate()
        response = self.client.get(reverse('ai-gateway-status'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertFalse(response.data['data']['enabled'])
        self.assertEqual(response.data['data']['mode'], 'mock')

    def test_status_endpoint_does_not_leak_api_key(self):
        self.authenticate()
        response = self.client.get(reverse('ai-gateway-status'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_text = json.dumps(response.data)
        self.assertNotIn('super-secret-key', response_text)
        self.assertNotIn('api_key', response_text)

    def test_health_endpoint_returns_mock_mode_when_ai_is_disabled(self):
        self.authenticate()
        response = self.client.get(reverse('ai-gateway-health'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['status'], 'disabled')
        self.assertEqual(response.data['data']['mode'], 'mock')

    def test_generate_study_plan_returns_mock_response_when_disabled(self):
        response = generate_study_plan(
            {
                'student_level': 'Grade 12',
                'subject': 'Physics',
                'days': 3,
                'daily_minutes': 120,
                'difficulty_level': 'medium',
                'goal': 'Revise the core lessons',
            }
        )

        self.assertTrue(response.plan_title)
        self.assertGreaterEqual(len(response.tasks), 3)

    def test_generate_quiz_returns_mock_questions_when_disabled(self):
        response = generate_quiz(
            {
                'subject': 'Physics',
                'topic': 'Newton Laws',
                'difficulty_level': 'medium',
                'questions_count': 5,
                'question_types': ['mcq', 'true_false'],
            }
        )

        self.assertEqual(len(response.questions), 5)
        self.assertIn('choices', response.questions[0])

    def test_summarize_text_returns_mock_summary(self):
        response = summarize_text(
            {
                'text': 'Long educational text',
                'summary_type': 'short',
            }
        )

        self.assertTrue(response.summary)
        self.assertGreaterEqual(len(response.key_points), 1)

    def test_transcribe_audio_returns_mock_transcription(self):
        response = transcribe_audio({'file_url': 'https://example.com/audio.mp3'})

        self.assertIn('Mock transcription', response.text)
        self.assertEqual(response.duration_seconds, 30)

    def test_generate_recommendations_returns_mock_recommendations(self):
        response = generate_recommendations(
            {
                'student_profile': {'level': 'Grade 12'},
                'performance_data': {'score': 60},
            }
        )

        self.assertGreaterEqual(len(response.recommendations), 1)

    def test_client_is_enabled_returns_false_by_default(self):
        client = AIServiceClient()
        self.assertFalse(client.is_enabled())

    @override_settings(
        AI_SERVICE_ENABLED=True,
        AI_SERVICE_BASE_URL='http://ai-service.local',
        AI_SERVICE_API_KEY='super-secret-key',
        AI_SERVICE_TIMEOUT_SECONDS=5,
        AI_SERVICE_VERIFY_SSL=True,
        AI_SERVICE_RETRY_COUNT=0,
    )
    @patch('apps.ai_gateway.client.requests.Session.request', side_effect=requests.Timeout)
    def test_client_timeout_is_wrapped_in_custom_exception(self, mocked_request):
        client = AIServiceClient()

        with self.assertRaises(AIServiceTimeoutError):
            client.request('/generate-quiz', payload={'subject': 'Physics'})

        self.assertEqual(mocked_request.call_count, 1)

    def test_schema_endpoint_still_works(self):
        response = self.client.get(reverse('api-schema'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_ai_study_plan_creation_works_in_mock_mode(self):
        self.authenticate()
        response = self.client.post(
            reverse('study-plan-list'),
            {
                'title': 'AI Study Plan',
                'description': 'AI-generated study plan',
                'subject': self.subject.id,
                'start_date': '2026-05-01',
                'end_date': '2026-05-03',
                'daily_study_minutes': 120,
                'goal': 'Master the subject',
                'difficulty_level': 'medium',
                'generation_type': 'ai',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['generation_type'], 'ai')
        self.assertGreaterEqual(len(response.data['tasks']), 3)

    def test_ai_quiz_creation_works_in_mock_mode(self):
        self.authenticate()
        response = self.client.post(
            reverse('quiz-list'),
            {
                'subject': self.subject.id,
                'title': 'AI Quiz',
                'description': 'AI-generated quiz',
                'topic': 'Physics Basics',
                'difficulty_level': 'medium',
                'quiz_type': 'practice',
                'generation_type': 'ai',
                'questions_count': 5,
                'time_limit_minutes': 15,
                'question_types': ['mcq', 'true_false'],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['generation_type'], 'ai')
        self.assertEqual(len(response.data['questions']), 5)
