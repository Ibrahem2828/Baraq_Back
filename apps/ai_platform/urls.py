from django.urls import path

from .views import (
    AICapabilitiesView,
    AIFeedbackCreateView,
    AIDataPrivacyView,
    AITrainingConsentRevokeView,
    AIOutputDetailView,
    AIRequestCancelView,
    AIRequestDetailView,
    AIRequestListCreateView,
)

app_name = 'ai_platform'

urlpatterns = [
    path('capabilities/', AICapabilitiesView.as_view(), name='capabilities'),
    path('privacy/', AIDataPrivacyView.as_view(), name='privacy'),
    path('privacy/revoke-training-consent/', AITrainingConsentRevokeView.as_view(), name='revoke-training-consent'),
    path('requests/', AIRequestListCreateView.as_view(), name='request-list-create'),
    path('requests/<uuid:public_id>/', AIRequestDetailView.as_view(), name='request-detail'),
    path('requests/<uuid:public_id>/cancel/', AIRequestCancelView.as_view(), name='request-cancel'),
    path('outputs/<int:pk>/', AIOutputDetailView.as_view(), name='output-detail'),
    path('outputs/<int:output_id>/feedback/', AIFeedbackCreateView.as_view(), name='feedback-create'),
]
