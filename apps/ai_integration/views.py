from __future__ import annotations

import hashlib
import json

from django.conf import settings
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.quizzes.models import AttemptStatusChoices, QuizAttempt
from apps.sources.models import StudentSource, StudentSourceCollection
from apps.study_plans.models import StudyTask
from apps.students.models import StudentProfile
from apps.subjects.models import UserSubject

from .client import AIServiceClient, AIServiceError
from .models import AIFeedback, AIJob, AIWebhookEvent
from .security import HasInternalServiceKey, verify_webhook
from .serializers import AIFeedbackSerializer, AIJobCreateSerializer, AIJobListSerializer, AIJobSerializer
from .services import cancel_job, complete_job, create_ai_job, fail_job
from .tasks import forward_ai_feedback


@extend_schema(tags=['AI Jobs'])
class AIJobViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'public_id'
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'completed_at']
    ordering = ['-created_at']

    def get_throttles(self):
        self.throttle_scope = 'ai_requests' if self.action == 'create' else None
        return super().get_throttles()

    def get_queryset(self):
        return AIJob.objects.filter(user=self.request.user).select_related('source', 'collection', 'subject')

    def get_serializer_class(self):
        if self.action == 'create':
            return AIJobCreateSerializer
        if self.action == 'list':
            return AIJobListSerializer
        return AIJobSerializer

    def list(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        for field in ('status', 'character', 'task_type'):
            value = request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        page = self.paginate_queryset(queryset)
        serializer = AIJobListSerializer(page or queryset, many=True)
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)

    def create(self, request):
        serializer = AIJobCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        job, created = create_ai_job(
            user=request.user,
            task_type=data['task_type'],
            source=data.get('source'),
            collection=data.get('collection'),
            subject=data.get('subject'),
            input_payload=data.get('input'),
            parameters=data.get('parameters'),
            force=data.get('force', False),
        )
        return Response(AIJobSerializer(job).data, status=status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK)

    def retrieve(self, request, public_id=None):
        return Response(AIJobSerializer(self.get_object()).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, public_id=None):
        return Response(AIJobSerializer(cancel_job(self.get_object())).data)

    @action(detail=True, methods=['post'])
    def refresh(self, request, public_id=None):
        job = self.get_object()
        if not job.external_job_id or job.status in {AIJob.Status.COMPLETED, AIJob.Status.FAILED, AIJob.Status.CANCELED}:
            return Response(AIJobSerializer(job).data)
        try:
            data = AIServiceClient().get_job(job.external_job_id).data
        except AIServiceError as exc:
            return Response({'success': False, 'message': str(exc), 'code': exc.code}, status=exc.status_code or 503)
        remote_status = str(data.get('status') or '').lower()
        if remote_status in dict(AIJob.Status.choices):
            job.status = remote_status
            job.last_synced_at = timezone.now()
            job.service_metadata = {**job.service_metadata, 'last_refresh': data}
            job.save(update_fields=['status', 'last_synced_at', 'service_metadata', 'updated_at'])
        if remote_status == AIJob.Status.COMPLETED and data.get('result'):
            job = complete_job(job, data['result'], {'refresh_response': data})
        elif remote_status == AIJob.Status.FAILED:
            job = fail_job(job, RuntimeError(data.get('error_message') or 'AI job failed.'))
        return Response(AIJobSerializer(job).data)

    @action(detail=True, methods=['post'], url_path='feedback')
    def feedback(self, request, public_id=None):
        job = self.get_object()
        if job.status != AIJob.Status.COMPLETED:
            return Response({'detail': 'Feedback is accepted only for completed AI jobs.'}, status=status.HTTP_409_CONFLICT)
        serializer = AIFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feedback, _ = AIFeedback.objects.update_or_create(
            job=job,
            user=request.user,
            defaults={**serializer.validated_data, 'consent_version': serializer.validated_data.get('consent_version') or settings.AI_DATASET_CONSENT_VERSION},
        )
        transaction.on_commit(lambda: forward_ai_feedback.delay(feedback.pk))
        return Response(AIFeedbackSerializer(feedback).data, status=status.HTTP_201_CREATED)


class AICapabilitiesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({
            'service_enabled': settings.AI_SERVICE_ENABLED,
            'characters': [value for value, _ in AIJob.Character.choices],
            'task_types': [value for value, _ in AIJob.TaskType.choices],
            'phase_one': ['fahes', 'khota', 'rasheed'],
            'phase_two': ['kholasa', 'sada'],
        })


class AIServiceHealthView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        try:
            data = AIServiceClient().health().data
            return Response({'status': 'ok', 'service': data})
        except AIServiceError as exc:
            return Response({'status': 'error', 'message': str(exc), 'code': exc.code}, status=503)


class AIWebhookView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        raw_body = request._request.body
        if not verify_webhook(request, body=raw_body):
            return Response({'detail': 'Invalid webhook signature.'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            payload = json.loads(raw_body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response({'detail': 'Invalid JSON payload.'}, status=status.HTTP_400_BAD_REQUEST)
        event_id = str(payload.get('event_id') or '')
        external_job_id = str(payload.get('job_id') or payload.get('external_job_id') or '')
        if not event_id or not external_job_id:
            return Response({'detail': 'event_id and job_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
        event, created = AIWebhookEvent.objects.get_or_create(
            event_id=event_id,
            defaults={
                'event_type': str(payload.get('event_type') or 'job.updated'),
                'external_job_id': external_job_id,
                'payload_hash': hashlib.sha256(raw_body).hexdigest(),
            },
        )
        if not created and event.processed:
            return Response({'accepted': True, 'duplicate': True})
        job = AIJob.objects.filter(external_job_id=external_job_id).first()
        if job is None:
            event.error_message = 'Unknown external job.'
            event.save(update_fields=['error_message'])
            return Response({'detail': 'Unknown job.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            remote_status = str(payload.get('status') or '').lower()
            if remote_status == AIJob.Status.COMPLETED:
                complete_job(job, payload.get('result') or {}, {'webhook': payload.get('metadata') or {}})
            elif remote_status == AIJob.Status.FAILED:
                fail_job(job, RuntimeError(payload.get('error_message') or 'AI service job failed.'))
            elif remote_status == AIJob.Status.CANCELED:
                cancel_job(job)
            elif remote_status in dict(AIJob.Status.choices):
                job.status = remote_status
                job.last_synced_at = timezone.now()
                job.save(update_fields=['status', 'last_synced_at', 'updated_at'])
            event.processed = True
            event.processed_at = timezone.now()
            event.save(update_fields=['processed', 'processed_at'])
        except Exception as exc:
            event.error_message = str(exc)[:2000]
            event.save(update_fields=['error_message'])
            raise
        return Response({'accepted': True})


class InternalSourceManifestView(APIView):
    permission_classes = [HasInternalServiceKey]
    authentication_classes = []

    def get(self, request, pk):
        source = get_object_or_404(StudentSource.objects.select_related('subject', 'collection'), pk=pk)
        return Response({
            'id': source.id,
            'user_id': source.user_id,
            'title': source.title,
            'source_type': source.source_type,
            'status': source.status,
            'mime_type': source.mime_type,
            'extension': source.extension,
            'file_size': source.file_size,
            'checksum': source.metadata.get('sha256'),
            'subject_id': source.subject_id,
            'collection_id': source.collection_id,
            'extracted_text': source.extracted_text if source.status == source.Status.READY else None,
            'download_url': request.build_absolute_uri(f'/api/internal/v1/ai/sources/{source.id}/download/'),
        })


class InternalSourceDownloadView(APIView):
    permission_classes = [HasInternalServiceKey]
    authentication_classes = []

    def get(self, request, pk):
        source = get_object_or_404(StudentSource, pk=pk)
        if not source.file:
            raise Http404
        response = FileResponse(source.file.open('rb'), content_type=source.mime_type or 'application/octet-stream')
        extension = f'.{source.extension}' if source.extension else ''
        response['Content-Disposition'] = f'attachment; filename="source-{source.id}{extension}"'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


class InternalCollectionManifestView(APIView):
    permission_classes = [HasInternalServiceKey]
    authentication_classes = []

    def get(self, request, pk):
        collection = get_object_or_404(StudentSourceCollection.objects.prefetch_related('sources'), pk=pk)
        return Response({
            'id': collection.id,
            'user_id': collection.user_id,
            'name': collection.name,
            'subject_id': collection.subject_id,
            'sources': [
                {
                    'id': source.id,
                    'title': source.title,
                    'source_type': source.source_type,
                    'status': source.status,
                    'manifest_url': request.build_absolute_uri(f'/api/internal/v1/ai/sources/{source.id}/manifest/'),
                }
                for source in collection.sources.filter(status__in=[StudentSource.Status.UPLOADED, StudentSource.Status.READY])
            ],
        })


class InternalUserContextView(APIView):
    permission_classes = [HasInternalServiceKey]
    authentication_classes = []

    def get(self, request, pk):
        profile = StudentProfile.objects.select_related('education_stage').filter(user_id=pk).first()
        subjects = UserSubject.objects.filter(user_id=pk).select_related('subject')
        quiz_metrics = QuizAttempt.objects.filter(
            user_id=pk, status=AttemptStatusChoices.SUBMITTED
        ).aggregate(
            attempts=Count('id'),
            average_percentage=Avg('percentage'),
        )
        task_metrics = StudyTask.objects.filter(plan__user_id=pk).aggregate(
            total=Count('id'),
            completed=Count('id', filter=Q(status=StudyTask.Status.COMPLETED)),
            skipped=Count('id', filter=Q(status=StudyTask.Status.SKIPPED)),
        )
        return Response({
            'user_id': pk,
            'profile': {
                'education_stage': getattr(getattr(profile, 'education_stage', None), 'name', None),
                'grade_level': getattr(profile, 'grade_level', ''),
                'specialization': getattr(profile, 'specialization', ''),
                'study_goal': getattr(profile, 'study_goal', ''),
                'daily_study_hours': getattr(profile, 'daily_study_hours', None),
            },
            'subjects': [{'id': item.subject_id, 'name': item.subject.name} for item in subjects],
            'performance': {
                'quiz_attempts': quiz_metrics['attempts'] or 0,
                'average_quiz_percentage': float(quiz_metrics['average_percentage'] or 0),
                'study_tasks_total': task_metrics['total'] or 0,
                'study_tasks_completed': task_metrics['completed'] or 0,
                'study_tasks_skipped': task_metrics['skipped'] or 0,
            },
        })


class AIApiRootView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        base = request.build_absolute_uri('/').rstrip('/')
        return Response({
            'jobs': f'{base}/api/v1/ai/jobs/',
            'capabilities': f'{base}/api/v1/ai/capabilities/',
            'service_health': f'{base}/api/v1/ai/service-health/',
        })
