from django.conf import settings
from django.db import DatabaseError, connection
from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import permissions, serializers, status
from rest_framework.views import APIView

from .responses import error_response, success_response


SUCCESS_WRAPPER_SERIALIZER = inline_serializer(
    name='SystemSuccessResponse',
    fields={
        'success': serializers.BooleanField(),
        'message': serializers.CharField(),
        'data': serializers.JSONField(),
        'meta': serializers.JSONField(required=False),
    },
)


class HealthCheckView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['System'],
        description='Return backend health information and verify database connectivity.',
        responses={200: SUCCESS_WRAPPER_SERIALIZER, 503: SUCCESS_WRAPPER_SERIALIZER},
        examples=[
            OpenApiExample(
                'Healthy Response',
                value={
                    'success': True,
                    'message': 'Health check completed successfully',
                    'data': {
                        'status': 'ok',
                        'service': 'baraq_backend',
                        'database': 'ok',
                        'version': 'phase-3.6',
                    },
                },
                response_only=True,
            )
        ],
    )
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
        except DatabaseError:
            return error_response(
                message='Health check failed',
                errors={
                    'status': 'degraded',
                    'service': 'baraq_backend',
                    'database': 'error',
                    'version': f'phase-{settings.APP_PHASE}',
                },
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code='service_unavailable',
            )

        return success_response(
            data={
                'status': 'ok',
                'service': 'baraq_backend',
                'database': 'ok',
                'version': f'phase-{settings.APP_PHASE}',
            },
            message='Health check completed successfully',
        )


class ProjectMetaView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['System'],
        description='Return backend metadata and feature flags for local development clients.',
        responses={200: SUCCESS_WRAPPER_SERIALIZER},
        examples=[
            OpenApiExample(
                'Meta Response',
                value={
                    'success': True,
                    'message': 'Project metadata loaded successfully',
                    'data': {
                        'name': 'Baraq Backend',
                        'phase': '3.6',
                        'features': {
                            'auth': True,
                            'study_plans': True,
                            'quizzes': True,
                            'ai_gateway': True,
                            'audio': False,
                            'summaries': False,
                            'analytics': False,
                        },
                    },
                },
                response_only=True,
            )
        ],
    )
    def get(self, request):
        return success_response(
            data={
                'name': settings.APP_NAME,
                'phase': settings.APP_PHASE,
                'features': settings.APP_FEATURES,
            },
            message='Project metadata loaded successfully',
        )
