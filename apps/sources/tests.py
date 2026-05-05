import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.quizzes.models import Quiz
from apps.study_plans.models import StudyPlan
from apps.subjects.models import EducationStage, Subject

from .models import StudentSource, StudentSourceInteraction

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'])
class StudentSourceAPITestCase(APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(
            MEDIA_ROOT=self.media_root,
            STUDENT_SOURCE_MAX_UPLOAD_MB=1,
        )
        self.override.enable()

        self.user = User.objects.create_user(
            email='student1@example.com',
            password='StrongPass123',
            full_name='Student One',
        )
        self.other_user = User.objects.create_user(
            email='student2@example.com',
            password='StrongPass123',
            full_name='Student Two',
        )
        self.stage = EducationStage.objects.create(
            name='Secondary',
            description='Secondary stage',
            order=1,
        )
        self.subject = Subject.objects.create(
            name='Mathematics',
            education_stage=self.stage,
            grade_level='Grade 12',
            description='Core subject',
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def authenticate(self, user=None):
        self.client.force_authenticate(user or self.user)

    def upload_source(self, filename='summary.txt', content=None, content_type='text/plain', subject=True):
        self.authenticate()
        file_content = content if content is not None else b'Derivatives help measure change.\nLimits describe behavior near a value.'
        payload = {
            'title': 'Math Summary',
            'description': 'Uploaded class notes',
            'file': SimpleUploadedFile(filename, file_content, content_type=content_type),
        }
        if subject:
            payload['subject'] = self.subject.id
        return self.client.post(reverse('student-source-list'), payload, format='multipart')

    def test_upload_allowed_file(self):
        response = self.upload_source()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['source_type'], StudentSource.SourceType.TEXT)
        self.assertEqual(StudentSource.objects.filter(user=self.user).count(), 1)

    def test_reject_bad_extension(self):
        response = self.upload_source(filename='hack.exe', content=b'bad')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(StudentSource.objects.count(), 0)

    def test_reject_too_large_file(self):
        response = self.upload_source(content=b'a' * (1024 * 1024 + 1))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(StudentSource.objects.count(), 0)

    def test_list_only_own_sources(self):
        own_response = self.upload_source()
        self.assertEqual(own_response.status_code, status.HTTP_201_CREATED)
        StudentSource.objects.create(
            user=self.other_user,
            subject=self.subject,
            title='Other Source',
            source_type=StudentSource.SourceType.TEXT,
            file='student_sources/other.txt',
            original_filename='other.txt',
            file_size=10,
            mime_type='text/plain',
            extension='txt',
        )

        response = self.client.get(reverse('student-source-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'Math Summary')

    def test_cannot_access_other_user_source(self):
        other_source = StudentSource.objects.create(
            user=self.other_user,
            subject=self.subject,
            title='Other Source',
            source_type=StudentSource.SourceType.TEXT,
            file='student_sources/other.txt',
            original_filename='other.txt',
            file_size=10,
            mime_type='text/plain',
            extension='txt',
        )
        self.authenticate()

        response = self.client.get(reverse('student-source-detail', args=[other_source.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_process_txt(self):
        upload = self.upload_source()
        source_id = upload.data['id']

        response = self.client.post(reverse('student-source-process', args=[source_id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['source']['status'], StudentSource.Status.READY)
        self.assertTrue(response.data['source']['has_extracted_text'])

    def test_source_capabilities(self):
        upload = self.upload_source()

        response = self.client.get(reverse('student-source-capabilities', args=[upload.data['id']]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['khota']['available'])
        self.assertFalse(response.data['kholasa']['available'])

    def test_use_with_rasheed(self):
        upload = self.upload_source()

        response = self.client.post(
            reverse('student-source-use-with-character', args=[upload.data['id']]),
            {'character': StudentSourceInteraction.Character.RASHEED},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('advice', response.data)

    def test_use_with_khota_does_not_fail(self):
        upload = self.upload_source()

        response = self.client.post(reverse('student-source-use-with-khota', args=[upload.data['id']]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(StudyPlan.objects.filter(user=self.user).count(), 1)

    def test_use_with_fahes_does_not_fail(self):
        upload = self.upload_source()
        self.client.post(reverse('student-source-process', args=[upload.data['id']]))

        response = self.client.post(reverse('student-source-use-with-fahes', args=[upload.data['id']]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(Quiz.objects.filter(user=self.user).count(), 1)

    def test_kholasa_unavailable(self):
        upload = self.upload_source()

        response = self.client.post(reverse('student-source-use-with-kholasa', args=[upload.data['id']]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['success'])
        self.assertFalse(response.data['available'])

    def test_sada_unavailable(self):
        upload = self.upload_source()

        response = self.client.post(reverse('student-source-use-with-sada', args=[upload.data['id']]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['success'])
        self.assertFalse(response.data['available'])

    def test_delete_source(self):
        upload = self.upload_source()

        response = self.client.delete(reverse('student-source-detail', args=[upload.data['id']]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(StudentSource.objects.filter(user=self.user).count(), 0)
