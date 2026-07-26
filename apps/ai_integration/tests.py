import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.sources.models import StudentSource
from apps.subjects.models import EducationStage, Subject

from .models import AIJob

User = get_user_model()


@override_settings(
    ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'],
    AI_SERVICE_ENABLED=True,
    AI_SERVICE_INTERNAL_API_KEY='i' * 64,
    AI_SERVICE_WEBHOOK_SECRET='w' * 64,
)
class AIIntegrationApiTests(APITestCase):
    def setUp(self):
        self.media_override = override_settings(MEDIA_ROOT=tempfile.mkdtemp())
        self.media_override.enable()
        self.user = User.objects.create_user(email='ai@example.com', password='StrongPass123!', full_name='AI User')
        self.other = User.objects.create_user(email='other-ai@example.com', password='StrongPass123!', full_name='Other AI')
        stage = EducationStage.objects.create(name='Secondary', order=1)
        self.subject = Subject.objects.create(name='Physics', education_stage=stage, grade_level='12')
        self.source = StudentSource.objects.create(
            user=self.user,
            subject=self.subject,
            title='Physics notes',
            source_type=StudentSource.SourceType.TEXT,
            file=SimpleUploadedFile('physics.txt', b'Newton laws', content_type='text/plain'),
            original_filename='physics.txt',
            file_size=11,
            mime_type='text/plain',
            extension='txt',
            extracted_text='Newton laws',
            status=StudentSource.Status.READY,
        )

    def tearDown(self):
        self.media_override.disable()

    def authenticate(self):
        self.client.force_authenticate(user=self.user)

    def test_job_creation_is_idempotent(self):
        self.authenticate()
        payload = {
            'task_type': AIJob.TaskType.FAHES_GENERATE_QUIZ,
            'source': self.source.id,
            'subject': self.subject.id,
            'parameters': {'questions_count': 5},
        }
        first = self.client.post(reverse('ai-job-list'), payload, format='json')
        second = self.client.post(reverse('ai-job-list'), payload, format='json')
        self.assertEqual(first.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data['public_id'], second.data['public_id'])
        self.assertEqual(AIJob.objects.filter(user=self.user).count(), 1)

    def test_user_cannot_submit_another_users_source(self):
        other_source = StudentSource.objects.create(
            user=self.other,
            subject=self.subject,
            title='Other',
            source_type=StudentSource.SourceType.TEXT,
            file='student_sources/other.txt',
            original_filename='other.txt',
            file_size=5,
            mime_type='text/plain',
            extension='txt',
            status=StudentSource.Status.READY,
        )
        self.authenticate()
        response = self.client.post(
            reverse('ai-job-list'),
            {'task_type': AIJob.TaskType.FAHES_GENERATE_QUIZ, 'source': other_source.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_internal_manifest_requires_service_key(self):
        missing = self.client.get(reverse('ai-source-manifest', args=[self.source.id]))
        self.assertEqual(missing.status_code, status.HTTP_403_FORBIDDEN)
        allowed = self.client.get(
            reverse('ai-source-manifest', args=[self.source.id]),
            HTTP_X_BARAQ_INTERNAL_KEY='i' * 64,
        )
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertEqual(allowed.data['id'], self.source.id)

    def test_internal_manifest_validates_requested_owner(self):
        allowed = self.client.get(
            reverse('ai-source-manifest', args=[self.source.id]),
            {'user_id': self.user.id},
            HTTP_X_BARAQ_INTERNAL_KEY='i' * 64,
        )
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertIn(f'user_id={self.user.id}', allowed.data['download_url'])

        denied = self.client.get(
            reverse('ai-source-manifest', args=[self.source.id]),
            {'user_id': self.other.id},
            HTTP_X_BARAQ_INTERNAL_KEY='i' * 64,
        )
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)

    def test_sada_rejects_collection_even_when_it_contains_audio(self):
        from apps.sources.models import StudentSourceCollection

        collection = StudentSourceCollection.objects.create(user=self.user, name='Audio folder')
        audio = StudentSource.objects.create(
            user=self.user,
            title='Lecture recording',
            source_type=StudentSource.SourceType.AUDIO,
            file=SimpleUploadedFile('lecture.mp3', b'ID3audio', content_type='audio/mpeg'),
            original_filename='lecture.mp3',
            file_size=8,
            mime_type='audio/mpeg',
            extension='mp3',
            collection=collection,
            status=StudentSource.Status.UPLOADED,
        )
        self.authenticate()
        response = self.client.post(
            reverse('ai-job-list'),
            {'task_type': AIJob.TaskType.SADA_TRANSCRIPTION, 'collection': collection.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        accepted = self.client.post(
            reverse('ai-job-list'),
            {'task_type': AIJob.TaskType.SADA_TRANSCRIPTION, 'source': audio.id},
            format='json',
        )
        # The test account does not have the Sada subscription feature, so a
        # 403 proves the audio source passed request validation and reached
        # the entitlement layer (rather than being rejected as malformed).
        self.assertEqual(accepted.status_code, status.HTTP_403_FORBIDDEN)

    def test_feedback_requires_completed_job(self):
        self.authenticate()
        create = self.client.post(
            reverse('ai-job-list'),
            {'task_type': AIJob.TaskType.FAHES_GENERATE_QUIZ, 'source': self.source.id},
            format='json',
        )
        response = self.client.post(
            reverse('ai-job-feedback', args=[create.data['public_id']]),
            {'rating': 5, 'is_helpful': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_unsigned_webhook_is_rejected(self):
        response = self.client.post(
            reverse('ai-webhook-jobs'),
            {'event_id': 'event-1', 'job_id': 'job-1', 'status': 'completed'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
