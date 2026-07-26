from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.quizzes.models import Quiz
from apps.study_plans.models import StudyPlan
from apps.subjects.models import EducationStage, Subject

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'])
class SystemAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='system-user@example.com',
            password='StrongPass123',
            full_name='System User',
        )
        self.other_user = User.objects.create_user(
            email='other-system-user@example.com',
            password='StrongPass123',
            full_name='Other System User',
        )
        self.admin = User.objects.create_superuser(
            email='system-admin@example.com',
            password='StrongPass123',
            full_name='System Admin',
        )

    def authenticate(self, user=None):
        self.client.force_authenticate(user or self.user)

    def seed_data(self):
        call_command('seed_academic_data')

    def test_health_endpoint_returns_200(self):
        response = self.client.get(reverse('health-check'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['status'], 'ready')

    def test_meta_endpoint_returns_200(self):
        response = self.client.get(reverse('project-meta'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['api_version'], 'v1')
        self.assertEqual(response.data['data']['version'], '4.0.0')
        self.assertTrue(response.data['data']['features']['quizzes'])

    def test_seed_academic_data_runs_successfully(self):
        self.seed_data()

        self.assertEqual(EducationStage.objects.count(), 4)
        self.assertEqual(Subject.objects.count(), 22)

    def test_seed_academic_data_is_idempotent(self):
        self.seed_data()
        self.seed_data()

        self.assertEqual(EducationStage.objects.count(), 4)
        self.assertEqual(Subject.objects.count(), 22)

    def test_subject_filters_work_after_seed(self):
        self.seed_data()
        stage = EducationStage.objects.get(name='الابتدائية')

        response = self.client.get(
            reverse('subjects'),
            {'education_stage': stage.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 5)
        self.assertTrue(
            all(item['education_stage'] == stage.id for item in response.data['results'])
        )

    def test_unauthenticated_user_cannot_access_study_plans(self):
        response = self.client.get(reverse('study-plan-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data['success'])

    def test_unauthenticated_user_cannot_access_quizzes(self):
        response = self.client.get(reverse('quiz-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data['success'])

    def test_user_cannot_see_other_user_study_plan(self):
        self.seed_data()
        subject = Subject.objects.filter(name='الرياضيات').order_by('id').first()
        plan = StudyPlan.objects.create(
            user=self.other_user,
            title='Other User Plan',
            subject=subject,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=2),
            daily_study_minutes=60,
            difficulty_level=StudyPlan.DifficultyLevel.MEDIUM,
            generation_type=StudyPlan.GenerationType.MANUAL,
            status=StudyPlan.Status.ACTIVE,
        )

        self.authenticate(self.user)
        response = self.client.get(reverse('study-plan-detail', args=[plan.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_see_other_user_quiz(self):
        self.seed_data()
        subject = Subject.objects.filter(name='الفيزياء').order_by('id').first()
        quiz = Quiz.objects.create(
            user=self.other_user,
            subject=subject,
            title='Other User Quiz',
            topic='Forces',
            difficulty_level='medium',
            quiz_type='practice',
            generation_type='manual',
            status='published',
            questions_count=0,
        )

        self.authenticate(self.user)
        response = self.client.get(reverse('quiz-detail', args=[quiz.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_schema_endpoint_returns_200(self):
        self.authenticate(self.admin)
        response = self.client.get(reverse('api-schema'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_docs_endpoint_returns_200(self):
        self.authenticate(self.admin)
        response = self.client.get(reverse('api-docs'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
