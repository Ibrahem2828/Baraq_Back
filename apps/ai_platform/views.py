from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.responses import success_response

from .models import AIFeedback, AIOutput, AIRequest, AITaskType, SourceChunk, TrainingDatasetCandidate
from .orchestration import cancel_ai_request, execute_ai_request, fail_queued_ai_request
from .serializers import (
    AIFeedbackSerializer,
    AIOutputSerializer,
    AIRequestCreateSerializer,
    AIRequestSerializer,
)
from .tasks import process_ai_request
from .throttles import AIRequestDailyThrottle


class AICapabilitiesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        phase_two = bool(getattr(settings, 'AI_PLATFORM_PHASE_TWO_ENABLED', False))
        return success_response(
            data={
                'phase_one': [
                    AITaskType.FAHES_GENERATE_QUIZ,
                    AITaskType.KHOTA_GENERATE_PLAN,
                    AITaskType.RASHEED_RECOMMEND,
                ],
                'phase_two': [
                    AITaskType.KHOLASA_SUMMARIZE,
                    AITaskType.SADA_TRANSCRIBE,
                ],
                'phase_two_enabled': phase_two,
                'feedback_enabled': True,
                'training_requires_consent': True,
                'automatic_training_approval': False,
            },
            message='AI platform capabilities',
        )


class AIRequestListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        if self.request.method == 'POST':
            return [AIRequestDailyThrottle()]
        return []

    def get_queryset(self):
        return (
            AIRequest.objects.filter(user=self.request.user)
            .select_related('source', 'collection', 'prompt_version')
            .select_related('output')
        )

    def get_serializer_class(self):
        return AIRequestCreateSerializer if self.request.method == 'POST' else AIRequestSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ai_request = serializer.save()

        if ai_request.status == AIRequest.Status.COMPLETED:
            # A validated cache hit is returned immediately without consuming a
            # provider call or creating an unnecessary Celery task.
            pass
        elif getattr(settings, 'AI_PLATFORM_RUN_SYNCHRONOUS', False):
            ai_request = execute_ai_request(ai_request.id)
        else:
            try:
                process_ai_request.delay(ai_request.id)
            except Exception as exc:
                if getattr(settings, 'AI_PLATFORM_QUEUE_FALLBACK_SYNCHRONOUS', False):
                    ai_request = execute_ai_request(ai_request.id)
                else:
                    ai_request = fail_queued_ai_request(
                        ai_request,
                        code='ai_queue_unavailable',
                        message=f'AI worker queue is unavailable: {exc}',
                    )
            else:
                ai_request.refresh_from_db()

        output_serializer = AIRequestSerializer(ai_request, context={'request': request})
        response_status = (
            status.HTTP_200_OK
            if ai_request.status in {AIRequest.Status.COMPLETED, AIRequest.Status.FAILED}
            else status.HTTP_202_ACCEPTED
        )
        return Response(output_serializer.data, status=response_status)


class AIRequestDetailView(generics.RetrieveAPIView):
    serializer_class = AIRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'public_id'

    def get_queryset(self):
        return AIRequest.objects.filter(user=self.request.user).select_related('output')


class AIRequestCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, public_id):
        ai_request = get_object_or_404(AIRequest, public_id=public_id, user=request.user)
        ai_request = cancel_ai_request(ai_request)
        return Response(AIRequestSerializer(ai_request, context={'request': request}).data)


class AIOutputDetailView(generics.RetrieveAPIView):
    serializer_class = AIOutputSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AIOutput.objects.filter(request__user=self.request.user).select_related('request')


class AIFeedbackCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, output_id):
        output = get_object_or_404(AIOutput, pk=output_id, request__user=request.user)
        serializer = AIFeedbackSerializer(
            data=request.data,
            context={'request': request, 'output': output},
        )
        serializer.is_valid(raise_exception=True)
        feedback = serializer.save()
        return Response(AIFeedbackSerializer(feedback).data, status=status.HTTP_201_CREATED)

class AIDataPrivacyView(APIView):
    """Let a user inspect or delete their AI history and derived training data."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        requests = AIRequest.objects.filter(user=request.user)
        outputs = AIOutput.objects.filter(request__user=request.user)
        return success_response(
            data={
                'requests': requests.count(),
                'outputs': outputs.count(),
                'feedback': AIFeedback.objects.filter(user=request.user).count(),
                'training_candidates': TrainingDatasetCandidate.objects.filter(
                    output__request__user=request.user
                ).count(),
                'source_chunks': SourceChunk.objects.filter(source__user=request.user).count(),
                'consented_requests': requests.filter(consent_to_dataset=True).count(),
                'retention_days': int(getattr(settings, 'AI_DATA_RETENTION_DAYS', 180)),
            },
            message='AI data privacy summary',
        )

    @transaction.atomic
    def delete(self, request):
        request_queryset = AIRequest.objects.filter(user=request.user)
        request_count = request_queryset.count()
        chunk_count = SourceChunk.objects.filter(source__user=request.user).count()
        # Cascades remove outputs, feedback, and training candidates, including
        # previously approved candidates, because explicit deletion overrides
        # earlier training consent.
        request_queryset.delete()
        SourceChunk.objects.filter(source__user=request.user).delete()
        return success_response(
            data={
                'deleted_requests': request_count,
                'deleted_source_chunks': chunk_count,
            },
            message='تم حذف سجل الذكاء الاصطناعي والبيانات المشتقة الخاصة بك.',
        )


class AITrainingConsentRevokeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        requests = AIRequest.objects.filter(user=request.user, consent_to_dataset=True)
        updated = requests.update(consent_to_dataset=False)
        candidates = TrainingDatasetCandidate.objects.filter(
            output__request__user=request.user
        )
        deleted_candidates = candidates.count()
        candidates.delete()
        return success_response(
            data={
                'requests_updated': updated,
                'training_candidates_deleted': deleted_candidates,
            },
            message='تم سحب الموافقة وحذف جميع أمثلة التدريب المرشحة المرتبطة بحسابك.',
        )

