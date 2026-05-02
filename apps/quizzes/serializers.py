from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.subjects.models import Subject

from .models import (
    AttemptStatusChoices,
    Choice,
    DifficultyLevelChoices,
    GenerationTypeChoices,
    Question,
    QuestionBankItem,
    QuestionTypeChoices,
    Quiz,
    QuizAttempt,
    QuizStatusChoices,
    QuizTypeChoices,
    StudentAnswer,
)
from .services import create_quiz, update_quiz


class QuizSubjectSerializer(serializers.ModelSerializer):
    education_stage_name = serializers.CharField(
        source='education_stage.name',
        read_only=True,
    )

    class Meta:
        model = Subject
        fields = (
            'id',
            'name',
            'education_stage',
            'education_stage_name',
            'grade_level',
            'description',
            'is_active',
        )


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ('id', 'text', 'order')


class ChoiceResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ('id', 'text', 'is_correct', 'order')


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = (
            'id',
            'text',
            'question_type',
            'difficulty_level',
            'order',
            'points',
            'choices',
        )


class QuestionResultSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    text = serializers.CharField()
    question_type = serializers.CharField()
    difficulty_level = serializers.CharField()
    order = serializers.IntegerField()
    points = serializers.IntegerField()
    choices = ChoiceResultSerializer(many=True)
    correct_choice = ChoiceResultSerializer(allow_null=True)
    selected_choice = ChoiceResultSerializer(allow_null=True)
    text_answer = serializers.CharField(allow_blank=True)
    is_correct = serializers.BooleanField()
    explanation = serializers.CharField(allow_blank=True)
    points_awarded = serializers.DecimalField(max_digits=8, decimal_places=2)


class QuizAttemptMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAttempt
        fields = (
            'id',
            'status',
            'started_at',
            'submitted_at',
            'score',
            'max_score',
            'percentage',
        )


class QuizListSerializer(serializers.ModelSerializer):
    subject = QuizSubjectSerializer(read_only=True)

    class Meta:
        model = Quiz
        fields = (
            'id',
            'title',
            'subject',
            'topic',
            'difficulty_level',
            'quiz_type',
            'generation_type',
            'status',
            'questions_count',
            'time_limit_minutes',
            'created_at',
        )


class QuizDetailSerializer(QuizListSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    attempts_count = serializers.SerializerMethodField()
    last_attempt = serializers.SerializerMethodField()

    class Meta(QuizListSerializer.Meta):
        fields = QuizListSerializer.Meta.fields + (
            'description',
            'ai_request_id',
            'updated_at',
            'questions',
            'attempts_count',
            'last_attempt',
        )

    @extend_schema_field(serializers.IntegerField())
    def get_attempts_count(self, obj):
        attempts = getattr(obj, 'attempts', None)
        if attempts is not None and hasattr(attempts, 'all'):
            return attempts.count()
        return obj.attempts.count()

    @extend_schema_field(QuizAttemptMiniSerializer(allow_null=True))
    def get_last_attempt(self, obj):
        attempts = getattr(obj, 'attempts', None)
        if attempts is not None and hasattr(attempts, 'all'):
            last_attempt = attempts.all().first()
        else:
            last_attempt = obj.attempts.order_by('-started_at').first()
        return QuizAttemptMiniSerializer(last_attempt).data if last_attempt else None


class QuizCreateSerializer(serializers.ModelSerializer):
    subject = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.filter(is_active=True, education_stage__is_active=True)
    )
    question_types = serializers.ListField(
        child=serializers.ChoiceField(choices=QuestionTypeChoices.choices),
        required=False,
        allow_empty=False,
    )

    class Meta:
        model = Quiz
        fields = (
            'subject',
            'title',
            'description',
            'topic',
            'difficulty_level',
            'quiz_type',
            'generation_type',
            'questions_count',
            'time_limit_minutes',
            'question_types',
        )

    def validate_questions_count(self, value):
        if value < 1 or value > 50:
            raise serializers.ValidationError('questions_count must be between 1 and 50.')
        return value

    def validate_generation_type(self, value):
        if value not in {GenerationTypeChoices.MANUAL, GenerationTypeChoices.AI}:
            raise serializers.ValidationError('Invalid generation type.')
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        return create_quiz(user, validated_data)


class QuizUpdateSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=QuizStatusChoices.choices, required=False)

    class Meta:
        model = Quiz
        fields = (
            'title',
            'description',
            'topic',
            'difficulty_level',
            'quiz_type',
            'status',
            'time_limit_minutes',
        )

    def update(self, instance, validated_data):
        return update_quiz(instance, validated_data)


class StudentAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAnswer
        fields = (
            'id',
            'question',
            'selected_choice',
            'text_answer',
            'created_at',
            'updated_at',
        )


class QuizAttemptSerializer(serializers.ModelSerializer):
    quiz = QuizListSerializer(read_only=True)

    class Meta:
        model = QuizAttempt
        fields = (
            'id',
            'quiz',
            'status',
            'started_at',
            'submitted_at',
            'score',
            'max_score',
            'percentage',
            'correct_answers_count',
            'wrong_answers_count',
            'unanswered_count',
            'duration_seconds',
        )


class QuizAttemptDetailQuizSerializer(serializers.ModelSerializer):
    subject = QuizSubjectSerializer(read_only=True)
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = (
            'id',
            'title',
            'description',
            'topic',
            'difficulty_level',
            'quiz_type',
            'generation_type',
            'status',
            'questions_count',
            'time_limit_minutes',
            'subject',
            'questions',
        )


class QuizAttemptDetailSerializer(serializers.ModelSerializer):
    quiz = QuizAttemptDetailQuizSerializer(read_only=True)
    answers = StudentAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = QuizAttempt
        fields = (
            'id',
            'quiz',
            'status',
            'started_at',
            'submitted_at',
            'score',
            'max_score',
            'percentage',
            'correct_answers_count',
            'wrong_answers_count',
            'unanswered_count',
            'duration_seconds',
            'answers',
        )


class StartAttemptSerializer(serializers.Serializer):
    pass


class QuizAttemptStartResponseSerializer(serializers.Serializer):
    attempt_id = serializers.IntegerField()
    quiz = QuizAttemptDetailQuizSerializer()
    questions = QuestionSerializer(many=True)
    started_at = serializers.DateTimeField()
    time_limit_minutes = serializers.IntegerField(allow_null=True)
    status = serializers.ChoiceField(choices=AttemptStatusChoices.choices)


class SubmitAnswerSerializer(serializers.Serializer):
    question = serializers.PrimaryKeyRelatedField(queryset=Question.objects.all())
    selected_choice = serializers.PrimaryKeyRelatedField(
        queryset=Choice.objects.all(),
        required=False,
        allow_null=True,
    )
    text_answer = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def validate(self, attrs):
        if not attrs.get('selected_choice') and not attrs.get('text_answer'):
            raise serializers.ValidationError(
                'Either selected_choice or text_answer must be provided.'
            )
        return attrs


class SubmitQuizSerializer(serializers.Serializer):
    answers = SubmitAnswerSerializer(many=True, required=False, default=list)


class QuizResultSerializer(serializers.Serializer):
    attempt = QuizAttemptSerializer()
    quiz = QuizDetailSerializer()
    answers = QuestionResultSerializer(many=True)
    correct_answers_count = serializers.IntegerField()
    wrong_answers_count = serializers.IntegerField()
    unanswered_count = serializers.IntegerField()
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    recommendations = serializers.ListField(child=serializers.CharField())


class QuestionBankItemSerializer(serializers.ModelSerializer):
    subject = QuizSubjectSerializer(read_only=True)

    class Meta:
        model = QuestionBankItem
        fields = (
            'id',
            'subject',
            'text',
            'question_type',
            'difficulty_level',
            'explanation',
            'is_public',
            'created_at',
            'updated_at',
        )
