from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import permissions, serializers, status
from rest_framework.views import APIView

from apps.common.responses import error_response, success_response

from .exceptions import AIServiceError
from .services import ai_health_check, get_gateway_status


STATUS_DATA_SERIALIZER = inline_serializer(
    name='AIGatewayStatusData',
    fields={
        'enabled': serializers.BooleanField(),
        'base_url_configured': serializers.BooleanField(),
        'mode': serializers.CharField(),
        'available_operations': serializers.ListField(child=serializers.CharField()),
    },
)

HEALTH_DATA_SERIALIZER = inline_serializer(
    name='AIGatewayHealthData',
    fields={
        'status': serializers.CharField(),
        'mode': serializers.CharField(),
    },
)

SUCCESS_WRAPPER_SERIALIZER = inline_serializer(
    name='AIGatewaySuccessResponse',
    fields={
        'success': serializers.BooleanField(),
        'message': serializers.CharField(),
        'data': serializers.JSONField(),
    },
)


@extend_schema(tags=['AI Gateway'])
class AIGatewayStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        description='Return the safe AI gateway configuration status without exposing secrets.',
        responses={200: SUCCESS_WRAPPER_SERIALIZER},
        examples=[
            OpenApiExample(
                'Gateway Status',
                value={
                    'success': True,
                    'message': 'AI Gateway status',
                    'data': {
                        'enabled': False,
                        'base_url_configured': True,
                        'mode': 'mock',
                        'available_operations': [
                            'generate_study_plan',
                            'generate_quiz',
                            'summarize_text',
                            'transcribe_audio',
                            'generate_recommendations',
                        ],
                    },
                },
                response_only=True,
            )
        ],
    )
    def get(self, request):
        return success_response(
            data=get_gateway_status(),
            message='AI Gateway status',
        )


@extend_schema(tags=['AI Gateway'])
class AIGatewayHealthView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        description='Check the AI gateway operating mode and the upstream AI health when enabled.',
        responses={200: SUCCESS_WRAPPER_SERIALIZER, 503: SUCCESS_WRAPPER_SERIALIZER},
    )
    def get(self, request):
        try:
            data = ai_health_check()
        except AIServiceError:
            return error_response(
                message='AI gateway health check failed',
                errors={'status': 'error', 'mode': 'remote'},
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code='ai_gateway_unavailable',
            )

        return success_response(
            data=data,
            message='AI Gateway health',
        )
