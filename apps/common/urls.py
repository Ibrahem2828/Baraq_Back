from django.urls import path

from .views import HealthCheckView, ProjectMetaView

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health-check'),
    path('meta/', ProjectMetaView.as_view(), name='project-meta'),
]
