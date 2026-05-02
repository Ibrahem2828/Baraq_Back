from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.subjects.models import EducationStage, Subject

from .models import (
    AttemptStatusChoices,
    QuestionBankItem,
    Quiz,
    QuizAttempt,
    QuizStatusChoices,
)

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'])
class QuizAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='quiz-student-1@example.com',
            password='StrongPass123',
            full_name='Quiz Student One',
        )
        self.other_user = User.objects.create_user(
            email='quiz-student-2@example.com',
            password='StrongPass123',
            full_name='Quiz Student Two',
        )
        self.stage = EducationStage.objects.create(
            name='Quiz Stage',
            description='Stage',
            order=10,
        )
        self.subject = Subject.objects.create(
            name='Physics',
            education_stage=self.stage,
            grade_level='Grade 12',
            description='Physics subject',
        )
        self.other_subject = Subject.objects.create(
            name='Chemistry',
            education_stage=self.stage,
            grade_level='Grade 12',
            description='Chemistry subject',
        )

    def authenticate(self, user=None):
        self.client.force_authenticate(user or self.user)

    def create_quiz_via_api(self, user=None, **overrides):
        self.authenticate(user or self.user)
        payload = {
            'subject': self.subject.id,
            'title': 'Newton Laws Quiz',
            'description': 'Short physics practice quiz',
            'topic': 'Newton Laws',
            'difficulty_level': 'medium',
            'quiz_type': 'practice',
            'generation_type': 'manual',
            'questions_count': 5,
            'time_limit_minutes': 15,
            'question_types': ['mcq', 'true_false'],
        }
        payload.update(overrides)
        return self.client.post(reverse('quiz-list'), payload, format='json')

    def start_attempt(self, quiz_id, user=None):
        self.authenticate(user or self.user)
        return self.client.post(reverse('quiz-start', args=[quiz_id]), format='json')

    def submit_attempt(self, attempt_id, answers, user=None):
        self.authenticate(user or self.user)
        return self.client.post(
            reverse('quiz-attempt-submit', args=[attempt_id]),
            {'answers': answers},
            format='json',
        )

    def test_quizzes_list_requires_authentication(self):
        response = self.client.get(reverse('quiz-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_create_quiz(self):
        response = self.create_quiz_via_api()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Quiz.objects.filter(user=self.user).count(), 1)
        self.assertEqual(response.data['status'], QuizStatusChoices.PUBLISHED)

    def test_creating_quiz_generates_requested_number_of_questions(self):
        response = self.create_quiz_via_api(questions_count=5)
        quiz = Quiz.objects.get(user=self.user)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(quiz.questions.count(), 5)
        self.assertEqual(response.data['questions_count'], 5)

    def test_quiz_detail_does_not_expose_correct_choices(self):
        create_response = self.create_quiz_via_api()
        quiz_id = create_response.data['id']

        self.authenticate()
        response = self.client.get(reverse('quiz-detail', args=[quiz_id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        first_question = response.data['questions'][0]
        first_choice = first_question['choices'][0]
        self.assertNotIn('is_correct', first_choice)

    def test_user_can_start_attempt(self):
        create_response = self.create_quiz_via_api()
        quiz_id = create_response.data['id']

        response = self.start_attempt(quiz_id)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('attempt_id', response.data)
        self.assertEqual(response.data['status'], AttemptStatusChoices.IN_PROGRESS)

    def test_user_can_submit_attempt_and_get_result(self):
        create_response = self.create_quiz_via_api()
        quiz = Quiz.objects.get(id=create_response.data['id'])
        start_response = self.start_attempt(quiz.id)
        attempt_id = start_response.data['attempt_id']

        questions = list(quiz.questions.prefetch_related('choices').order_by('order'))
        answers = [
            {
                'question': question.id,
                'selected_choice': question.choices.filter(is_correct=True).first().id,
            }
            for question in questions
        ]

        response = self.submit_attempt(attempt_id, answers)
        attempt = QuizAttempt.objects.get(id=attempt_id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(attempt.status, AttemptStatusChoices.SUBMITTED)
        self.assertEqual(attempt.correct_answers_count, 5)
        self.assertEqual(attempt.wrong_answers_count, 0)
        self.assertEqual(attempt.unanswered_count, 0)
        self.assertEqual(attempt.percentage, Decimal('100.00'))

    def test_cannot_submit_same_attempt_twice(self):
        create_response = self.create_quiz_via_api()
        quiz = Quiz.objects.get(id=create_response.data['id'])
        start_response = self.start_attempt(quiz.id)
        attempt_id = start_response.data['attempt_id']
        question = quiz.questions.prefetch_related('choices').order_by('order').first()
        correct_choice = question.choices.filter(is_correct=True).first()
        payload = [{'question': question.id, 'selected_choice': correct_choice.id}]

        first_submit = self.submit_attempt(attempt_id, payload)
        second_submit = self.submit_attempt(attempt_id, payload)

        self.assertEqual(first_submit.status_code, status.HTTP_200_OK)
        self.assertEqual(second_submit.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_cannot_access_other_user_quiz(self):
        other_response = self.create_quiz_via_api(user=self.other_user, title='Other Quiz')
        quiz_id = other_response.data['id']

        self.authenticate(self.user)
        response = self.client.get(reverse('quiz-detail', args=[quiz_id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_access_other_user_attempt(self):
        other_response = self.create_quiz_via_api(user=self.other_user, title='Other Quiz')
        other_quiz = Quiz.objects.get(id=other_response.data['id'])
        start_response = self.start_attempt(other_quiz.id, user=self.other_user)
        attempt_id = start_response.data['attempt_id']

        self.authenticate(self.user)
        response = self.client.get(reverse('quiz-attempt-detail', args=[attempt_id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unanswered_count_is_calculated(self):
        create_response = self.create_quiz_via_api()
        quiz = Quiz.objects.get(id=create_response.data['id'])
        attempt_id = self.start_attempt(quiz.id).data['attempt_id']

        first_question = quiz.questions.prefetch_related('choices').order_by('order').first()
        answer_payload = [
            {
                'question': first_question.id,
                'selected_choice': first_question.choices.filter(is_correct=True).first().id,
            }
        ]

        response = self.submit_attempt(attempt_id, answer_payload)
        attempt = QuizAttempt.objects.get(id=attempt_id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(attempt.correct_answers_count, 1)
        self.assertEqual(attempt.unanswered_count, 4)

    def test_result_endpoint_returns_correction_data(self):
        create_response = self.create_quiz_via_api()
        quiz = Quiz.objects.get(id=create_response.data['id'])
        attempt_id = self.start_attempt(quiz.id).data['attempt_id']

        question = quiz.questions.prefetch_related('choices').order_by('order').first()
        wrong_choice = question.choices.filter(is_correct=False).first()
        self.submit_attempt(
            attempt_id,
            [{'question': question.id, 'selected_choice': wrong_choice.id}],
        )

        self.authenticate()
        response = self.client.get(reverse('quiz-attempt-result', args=[attempt_id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('answers', response.data)
        self.assertIn('correct_choice', response.data['answers'][0])
        self.assertIn('selected_choice', response.data['answers'][0])

    def test_quiz_filters_work_for_subject_and_status(self):
        today = timezone.localdate()
        self.create_quiz_via_api(title='Physics Practice', subject=self.subject.id)
        archived_response = self.create_quiz_via_api(
            title='Chemistry Archived',
            subject=self.other_subject.id,
            topic='Atoms',
        )

        self.authenticate()
        archive_response = self.client.post(
            reverse('quiz-archive', args=[archived_response.data['id']]),
            format='json',
        )
        self.assertEqual(archive_response.status_code, status.HTTP_200_OK)

        response = self.client.get(
            reverse('quiz-list'),
            {'subject': self.other_subject.id, 'status': QuizStatusChoices.ARCHIVED, 'created_at': str(today)},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], 'Chemistry Archived')

    def test_question_bank_returns_user_items(self):
        self.create_quiz_via_api()

        self.authenticate()
        response = self.client.get(reverse('question-bank-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_can_save_single_answer_before_submit(self):
        create_response = self.create_quiz_via_api()
        quiz = Quiz.objects.get(id=create_response.data['id'])
        attempt_id = self.start_attempt(quiz.id).data['attempt_id']
        question = quiz.questions.prefetch_related('choices').order_by('order').first()
        correct_choice = question.choices.filter(is_correct=True).first()

        self.authenticate()
        response = self.client.post(
            reverse('quiz-attempt-answer', args=[attempt_id]),
            {'question': question.id, 'selected_choice': correct_choice.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['answers']), 1)

    def test_schema_endpoint_still_works(self):
        response = self.client.get(reverse('api-schema'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_abandon_attempt_works(self):
        create_response = self.create_quiz_via_api()
        quiz = Quiz.objects.get(id=create_response.data['id'])
        attempt_id = self.start_attempt(quiz.id).data['attempt_id']

        self.authenticate()
        response = self.client.post(reverse('quiz-attempt-abandon', args=[attempt_id]), format='json')
        attempt = QuizAttempt.objects.get(id=attempt_id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(attempt.status, AttemptStatusChoices.ABANDONED)

    def test_public_question_bank_item_is_visible(self):
        QuestionBankItem.objects.create(
            subject=self.subject,
            created_by=None,
            text='Public bank question',
            question_type='mcq',
            difficulty_level='easy',
            is_public=True,
        )

        self.authenticate()
        response = self.client.get(reverse('question-bank-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)
