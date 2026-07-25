import json

from rest_framework import serializers

from apps.sources.models import StudentSource, StudentSourceCollection
from apps.subjects.models import Subject

from .models import AIFeedback, AIJob


class AIJobCreateSerializer(serializers.Serializer):
    task_type = serializers.ChoiceField(choices=AIJob.TaskType.choices)
    source = serializers.PrimaryKeyRelatedField(queryset=StudentSource.objects.all(), required=False, allow_null=True)
    collection = serializers.PrimaryKeyRelatedField(queryset=StudentSourceCollection.objects.all(), required=False, allow_null=True)
    subject = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.filter(is_active=True), required=False, allow_null=True)
    input = serializers.JSONField(required=False, default=dict)
    parameters = serializers.JSONField(required=False, default=dict)
    force = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        user = self.context['request'].user
        source = attrs.get('source')
        collection = attrs.get('collection')
        if source and source.user_id != user.id:
            raise serializers.ValidationError({'source': 'You do not own this source.'})
        if collection and collection.user_id != user.id:
            raise serializers.ValidationError({'collection': 'You do not own this collection.'})
        if source and collection:
            raise serializers.ValidationError('Choose either source or collection.')
        task_type = attrs['task_type']
        if task_type in {
            AIJob.TaskType.FAHES_GENERATE_QUIZ,
            AIJob.TaskType.KHOLASA_SUMMARY,
            AIJob.TaskType.SADA_TRANSCRIPTION,
        } and not (source or collection):
            raise serializers.ValidationError('This task requires a source or collection.')
        if task_type == AIJob.TaskType.SADA_TRANSCRIPTION and source and source.source_type != source.SourceType.AUDIO:
            raise serializers.ValidationError({'source': 'Sada requires an audio source.'})
        if source and source.status in {source.Status.PROCESSING, source.Status.FAILED}:
            raise serializers.ValidationError({'source': 'The source is not ready for an AI request.'})
        encoded_size = len(json.dumps({'input': attrs.get('input', {}), 'parameters': attrs.get('parameters', {})}, ensure_ascii=False, default=str).encode('utf-8'))
        if encoded_size > 32 * 1024:
            raise serializers.ValidationError('AI request input and parameters must not exceed 32 KB.')
        return attrs


class AIJobListSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIJob
        fields = (
            'public_id', 'character', 'task_type', 'status', 'source', 'collection', 'subject',
            'result_type', 'result_id', 'error_code', 'submitted_at', 'completed_at',
            'created_at', 'updated_at',
        )
        read_only_fields = fields


class AIJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIJob
        fields = (
            'public_id', 'character', 'task_type', 'status', 'source', 'collection', 'subject',
            'external_job_id', 'input_payload', 'parameters', 'result_payload', 'result_type',
            'result_id', 'error_code', 'error_message', 'credits_reserved', 'credits_committed',
            'submitted_at', 'completed_at', 'created_at', 'updated_at',
        )
        read_only_fields = fields


class AIFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIFeedback
        fields = (
            'id', 'job', 'rating', 'is_helpful', 'feedback_type', 'reason_codes', 'comment',
            'corrected_output', 'training_consent', 'consent_version', 'forwarded_to_ai_service',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'job', 'forwarded_to_ai_service', 'created_at', 'updated_at')

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('Rating must be between 1 and 5.')
        return value
