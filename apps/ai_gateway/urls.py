from django.urls import path

from .views import AIGatewayHealthView, AIGatewayStatusView

urlpatterns = [
    path('status/', AIGatewayStatusView.as_view(), name='ai-gateway-status'),
    path('health/', AIGatewayHealthView.as_view(), name='ai-gateway-health'),
]
