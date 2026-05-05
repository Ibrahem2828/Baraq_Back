from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.quizzes.serializers import QuizListSerializer
from apps.study_plans.serializers import StudyPlanListSerializer
from apps.subjects.models import Subject
from apps.subjects.serializers import SubjectSerializer

from .capabilities import get_source_character_capabilities
from .models import StudentSource, StudentSourceInteraction
from .validators import validate_student_source_file


class StudentSourceInteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentSourceInteraction
        fields = (
            'id',
            'source',
            'character',
            'action',
            'status',
            'result_type',
            'result_id',
            'message',
            'metadata',
            'created_at',
        )


class StudentSourceListSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = StudentSource
        fields = (
            'id',
            'title',
            'description',
            'source_type',
            'subject',
            'subject_name',
            'original_filename',
            'file_size',
            'mime_type',
            'extension',
            'status',
            'created_at',
            'updated_at',
            'capabilities',
        )

    @extend_schema_field(serializers.DictField())
    def get_capabilities(self, obj):
        capabilities = get_source_character_capabilities(obj)
        return {
            key: {
                'available': value['available'],
                'actions': value['actions'],
            }
            for key, value in capabilities.items()
        }


class StudentSourceDetailSerializer(StudentSourceListSerializer):
    file_url = serializers.SerializerMethodField()
    extracted_text_preview = serializers.SerializerMethodField()
    has_extracted_text = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()

    class Meta(StudentSourceListSerializer.Meta):
        fields = StudentSourceListSerializer.Meta.fields + (
            'file_url',
            'extracted_text_preview',
            'has_extracted_text',
            'processing_error',
            'metadata',
        )

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get('request')
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url

    @extend_schema_field(serializers.CharField())
    def get_extracted_text_preview(self, obj):
        if not obj.extracted_text:
            return ''
        return obj.extracted_text[:500]

    @extend_schema_field(serializers.BooleanField())
    def get_has_extracted_text(self, obj):
        return bool(obj.extracted_text)

    @extend_schema_field(serializers.DictField())
    def get_capabilities(self, obj):
        return get_source_character_capabilities(obj)


class StudentSourceCreateSerializer(serializers.ModelSerializer):
    subject = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.filter(is_active=True, education_stage__is_active=True),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = StudentSource
        fields = ('id', 'title', 'description', 'subject', 'file')
        read_only_fields = ('id',)

    def validate_file(self, value):
        self.context['file_metadata'] = validate_student_source_file(value)
        return value

    def create(self, validated_data):
        file_metadata = self.context['file_metadata']
        return StudentSource.objects.create(
            user=self.context['request'].user,
            original_filename=file_metadata['original_filename'],
            file_size=file_metadata['file_size'],
            mime_type=file_metadata['mime_type'],
            extension=file_metadata['extension'],
            source_type=file_metadata['source_type'],
            **validated_data,
        )


class StudentSourceUpdateSerializer(serializers.ModelSerializer):
    subject = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.filter(is_active=True, education_stage__is_active=True),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = StudentSource
        fields = ('title', 'description', 'subject')


class UseWithCharacterSerializer(serializers.Serializer):
    character = serializers.ChoiceField(choices=StudentSourceInteraction.Character.choices)
    action = serializers.ChoiceField(
        choices=StudentSourceInteraction.Action.choices,
        required=False,
        allow_blank=True,
    )


class SourceCharacterResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    available = serializers.BooleanField(required=False)
    message = serializers.CharField()
    interaction = StudentSourceInteractionSerializer(required=False)
    advice = serializers.ListField(child=serializers.CharField(), required=False)
    study_plan = StudyPlanListSerializer(required=False)
    quiz = QuizListSerializer(required=False)
