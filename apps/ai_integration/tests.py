import tempfile
import time

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from apps.sources.models import StudentSource
from apps.subscriptions.models import UsageLedgerEntry
from apps.subscriptions.services import reserve_character_request
from apps.subjects.models import EducationStage, Subject

from .models import AIJob
from .security import make_service_signature
from .services import build_service_payload, complete_job, update_job_progress

User = get_user_model()


@override_settings(
    ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'],
    AI_SERVICE_ENABLED=True,
    BARAQ_SERVICE_ID='baraq-django',
    BARAQ_HMAC_CURRENT_KEY_ID='django-current',
    BARAQ_HMAC_KEYS_JSON='{"django-current":"test-hmac-secret"}',
    BARAQ_HMAC_ALLOWED_SERVICES=['baraq-ai-service'],
    BARAQ_HMAC_MAX_CLOCK_SKEW_SECONDS=300,
    BARAQ_HMAC_NONCE_TTL_SECONDS=600,
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
        cache.clear()
        self.media_override.disable()

    def internal_headers(self, method, target, body=b'', *, nonce='nonce-for-test-0001'):
        headers = make_service_signature(
            method=method,
            target=target,
            body=body,
            timestamp=int(time.time()),
            nonce=nonce,
            service='baraq-ai-service',
            key_id='django-current',
        )
        return {f"HTTP_{name.upper().replace('-', '_')}": value for name, value in headers.items()}

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
        self.assertEqual(first.data['input_payload']['source_ids'], [str(self.source.id)])
        self.assertEqual(first.data['input_payload']['question_count'], 5)

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

    def test_internal_manifest_requires_hmac_v2_signature(self):
        missing = self.client.get(reverse('ai-source-manifest', args=[self.source.id]))
        self.assertEqual(missing.status_code, status.HTTP_403_FORBIDDEN)
        target = f'/api/internal/v1/ai/sources/{self.source.id}/manifest/?user_id={self.user.id}'
        allowed = self.client.get(
            f"{reverse('ai-source-manifest', args=[self.source.id])}?user_id={self.user.id}",
            **self.internal_headers('GET', target),
        )
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertEqual(allowed.data['source_id'], str(self.source.id))
        self.assertEqual(allowed.data['owner_user_id'], str(self.user.id))
        self.assertEqual(allowed.data['size_bytes'], self.source.file_size)
        self.assertEqual(len(allowed.data['content_sha256']), 64)

    def test_internal_manifest_validates_requested_owner(self):
        target = f'/api/internal/v1/ai/sources/{self.source.id}/manifest/?user_id={self.user.id}'
        allowed = self.client.get(
            reverse('ai-source-manifest', args=[self.source.id]),
            {'user_id': self.user.id},
            **self.internal_headers('GET', target),
        )
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

        denied_target = f'/api/internal/v1/ai/sources/{self.source.id}/manifest/?user_id={self.other.id}'
        denied = self.client.get(
            reverse('ai-source-manifest', args=[self.source.id]),
            {'user_id': self.other.id},
            **self.internal_headers('GET', denied_target, nonce='nonce-for-test-0002'),
        )
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)

    def test_internal_manifest_rejects_replayed_nonce_and_tampered_query(self):
        target = f'/api/internal/v1/ai/sources/{self.source.id}/manifest/?user_id={self.user.id}'
        headers = self.internal_headers('GET', target, nonce='nonce-for-test-0003')
        allowed = self.client.get(f"{reverse('ai-source-manifest', args=[self.source.id])}?user_id={self.user.id}", **headers)
        replayed = self.client.get(f"{reverse('ai-source-manifest', args=[self.source.id])}?user_id={self.user.id}", **headers)
        tampered = self.client.get(
            f"{reverse('ai-source-manifest', args=[self.source.id])}?user_id={self.other.id}",
            **self.internal_headers('GET', target, nonce='nonce-for-test-0004'),
        )
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertEqual(replayed.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(tampered.status_code, status.HTTP_403_FORBIDDEN)

    def test_shared_hmac_v2_vector_matches_ai_service(self):
        headers = make_service_signature(
            method='POST',
            target='/api/ai/v1/jobs?b=2&a=1',
            body=b'{"a":1}',
            timestamp=1_700_000_000,
            nonce='nonce-for-test-0001',
            service='baraq-django',
            key_id='django-current',
        )
        self.assertEqual(
            headers['X-Content-SHA256'],
            '015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862',
        )
        self.assertEqual(
            headers['X-Baraq-Signature'],
            '5e41ddc5b38525cac1fe8c1e44d2d5fbbcae5a0a2788dba6e9021c76eb276f99',
        )

    def test_service_payload_is_the_strict_v2_contract(self):
        self.authenticate()
        created = self.client.post(
            reverse('ai-job-list'),
            {'task_type': AIJob.TaskType.FAHES_GENERATE_QUIZ, 'source': self.source.id},
            format='json',
        )
        job = AIJob.objects.get(public_id=created.data['public_id'])
        payload = build_service_payload(job)
        self.assertEqual(payload['contract_version'], '2.0')
        self.assertEqual(payload['task_type'], AIJob.TaskType.FAHES_GENERATE_QUIZ)
        self.assertEqual(payload['input']['source_ids'], [str(self.source.id)])
        self.assertEqual(payload['model_policy'], {'tier': 'balanced', 'allow_fallback': True})
        self.assertEqual(
            set(payload),
            {
                'contract_version', 'client_job_id', 'user_id', 'project_id',
                'task_type', 'input', 'model_policy', 'trace_context',
            },
        )

    def test_completed_job_requires_a_materialized_result_in_the_database(self):
        with self.assertRaises(IntegrityError):
            AIJob.objects.create(
                user=self.user,
                character=AIJob.Character.FAHES,
                task_type=AIJob.TaskType.FAHES_GENERATE_QUIZ,
                status=AIJob.Status.COMPLETED,
                idempotency_key='completed-without-result',
            )

    def test_progress_updates_cannot_mark_a_job_completed(self):
        job = AIJob.objects.create(
            user=self.user,
            character=AIJob.Character.FAHES,
            task_type=AIJob.TaskType.FAHES_GENERATE_QUIZ,
            status=AIJob.Status.QUEUED,
            idempotency_key='progress-does-not-complete',
        )
        with self.assertRaises(ValidationError):
            update_job_progress(job, AIJob.Status.COMPLETED)
        job.refresh_from_db()
        self.assertEqual(job.status, AIJob.Status.QUEUED)

    def test_completion_materializes_once_then_commits_usage_and_notifies_once(self):
        job = AIJob.objects.create(
            user=self.user,
            source=self.source,
            subject=self.subject,
            character=AIJob.Character.FAHES,
            task_type=AIJob.TaskType.FAHES_GENERATE_QUIZ,
            status=AIJob.Status.QUEUED,
            idempotency_key='complete-job-once',
        )
        reserve_character_request(self.user, job.character, job=job)
        job.credits_reserved = True
        job.save(update_fields=['credits_reserved', 'updated_at'])

        output = {
            'questions': [{
                'question': 'What does Newton\'s first law describe?',
                'choices': ['Inertia', 'Photosynthesis'],
                'correct_answer_index': 0,
            }],
        }
        completed = complete_job(job, output)
        repeated = complete_job(completed, output)

        self.assertEqual(completed.status, AIJob.Status.COMPLETED)
        self.assertEqual(completed.result_type, 'quiz')
        self.assertEqual(repeated.pk, completed.pk)
        self.assertEqual(
            UsageLedgerEntry.objects.filter(
                user=self.user,
                idempotency_key=job.idempotency_key,
                operation=UsageLedgerEntry.Operation.COMMIT,
            ).count(),
            1,
        )
        from apps.notifications.models import Notification

        self.assertEqual(
            Notification.objects.filter(
                user=self.user,
                idempotency_key=f'ai-job:{job.public_id}:completed',
            ).count(),
            1,
        )

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
            {'task_type': AIJob.TaskType.SADA_TRANSCRIBE_AUDIO, 'collection': collection.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        accepted = self.client.post(
            reverse('ai-job-list'),
            {'task_type': AIJob.TaskType.SADA_TRANSCRIBE_AUDIO, 'source': audio.id},
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
