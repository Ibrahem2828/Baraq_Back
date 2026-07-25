from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ai_platform.models import AIFeedback, AIRequest, TrainingDatasetCandidate
from apps.users.models import User


@override_settings(
    AI_PLATFORM_RUN_SYNCHRONOUS=True,
    AI_PLATFORM_ALLOW_MOCK=True,
    AI_PLATFORM_PHASE_TWO_ENABLED=False,
)
class AIPlatformApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='student-ai@example.com',
            password='StrongPass123!',
            full_name='AI Student',
        )
        self.client.force_authenticate(self.user)

    def test_phase_one_request_is_executed_and_logged(self):
        response = self.client.post(
            reverse('ai_platform:request-list-create'),
            {
                'task_type': 'rasheed_recommend',
                'requested_provider': 'auto',
                'input_payload': {
                    'metrics': {'overall_score': 72, 'weak_topics': ['algebra']},
                    'context': {'language': 'ar'},
                },
                'consent_to_dataset': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], AIRequest.Status.COMPLETED)
        self.assertEqual(response.data['selected_provider'], 'mock')
        self.assertIsNotNone(response.data['output'])

    def test_feedback_creates_pending_training_candidate_only_with_consent(self):
        request_response = self.client.post(
            reverse('ai_platform:request-list-create'),
            {
                'task_type': 'rasheed_recommend',
                'input_payload': {'metrics': {'overall_score': 80}},
                'consent_to_dataset': True,
            },
            format='json',
        )
        output_id = request_response.data['output']['id']
        feedback_response = self.client.post(
            reverse('ai_platform:feedback-create', kwargs={'output_id': output_id}),
            {
                'rating': 5,
                'is_helpful': True,
                'feedback_type': 'general',
                'issue_types': [],
                'comment': 'مفيد',
                'allow_training': True,
            },
            format='json',
        )
        self.assertEqual(feedback_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AIFeedback.objects.count(), 1)
        candidate = TrainingDatasetCandidate.objects.get()
        self.assertFalse(candidate.approved_for_training)
        self.assertEqual(candidate.human_review_status, TrainingDatasetCandidate.ReviewStatus.PENDING)

    def test_phase_two_is_rejected_when_disabled(self):
        response = self.client.post(
            reverse('ai_platform:request-list-create'),
            {
                'task_type': 'kholasa_summarize',
                'input_payload': {'text': 'نص طويل للتلخيص'},
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    def test_negative_feedback_without_correction_is_not_training_ground_truth(self):
        request_response = self.client.post(
            reverse('ai_platform:request-list-create'),
            {
                'task_type': 'rasheed_recommend',
                'input_payload': {'metrics': {'overall_score': 40}},
                'consent_to_dataset': True,
                'parameters': {'force_refresh': True},
            },
            format='json',
        )
        output_id = request_response.data['output']['id']
        response = self.client.post(
            reverse('ai_platform:feedback-create', kwargs={'output_id': output_id}),
            {
                'rating': 1,
                'is_helpful': False,
                'feedback_type': 'incorrect',
                'issue_types': ['incorrect'],
                'allow_training': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(TrainingDatasetCandidate.objects.filter(output_id=output_id).exists())

    def test_completed_request_can_be_reused_from_validated_cache_without_extra_usage(self):
        payload = {
            'task_type': 'rasheed_recommend',
            'input_payload': {'metrics': {'overall_score': 67}},
        }
        first = self.client.post(
            reverse('ai_platform:request-list-create'), payload, format='json'
        )
        second = self.client.post(
            reverse('ai_platform:request-list-create'), payload, format='json'
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        cached = AIRequest.objects.get(public_id=second.data['public_id'])
        self.assertTrue(cached.metadata['cache_hit'])
        self.assertEqual(cached.input_tokens, 0)
        self.assertEqual(cached.output_tokens, 0)
        self.assertNotEqual(first.data['public_id'], second.data['public_id'])

    def test_user_can_revoke_consent_and_delete_ai_history(self):
        request_response = self.client.post(
            reverse('ai_platform:request-list-create'),
            {
                'task_type': 'rasheed_recommend',
                'input_payload': {'metrics': {'overall_score': 90}},
                'consent_to_dataset': True,
                'parameters': {'force_refresh': True},
            },
            format='json',
        )
        output_id = request_response.data['output']['id']
        self.client.post(
            reverse('ai_platform:feedback-create', kwargs={'output_id': output_id}),
            {
                'rating': 5,
                'is_helpful': True,
                'feedback_type': 'general',
                'allow_training': True,
            },
            format='json',
        )
        revoke = self.client.post(reverse('ai_platform:revoke-training-consent'))
        self.assertEqual(revoke.status_code, status.HTTP_200_OK)
        self.assertEqual(TrainingDatasetCandidate.objects.count(), 0)
        self.assertFalse(AIRequest.objects.get(public_id=request_response.data['public_id']).consent_to_dataset)

        delete = self.client.delete(reverse('ai_platform:privacy'))
        self.assertEqual(delete.status_code, status.HTTP_200_OK)
        self.assertEqual(AIRequest.objects.filter(user=self.user).count(), 0)

