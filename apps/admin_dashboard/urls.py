from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.subscriptions.views import (
    AdminSubscriptionPlanViewSet,
    AdminSubscriptionUsageViewSet,
    AdminUserSubscriptionViewSet,
)

from .views import (
    AdminCharacterInteractionViewSet,
    AdminMeView,
    AdminOverviewView,
    AdminPermissionViewSet,
    AdminQuizAttemptViewSet,
    AdminQuizViewSet,
    AdminRoleViewSet,
    AdminSourceCollectionViewSet,
    AdminSourceViewSet,
    AdminStudyPlanViewSet,
    AdminUserViewSet,
    AuditLogViewSet,
    ManagedUserViewSet,
    SystemHealthView,
)

router = SimpleRouter(use_regex_path=False)
router.register(r'permissions', AdminPermissionViewSet, basename='admin-permission')
router.register(r'roles', AdminRoleViewSet, basename='admin-role')
router.register(r'admin-users', AdminUserViewSet, basename='admin-user')
router.register(r'users', ManagedUserViewSet, basename='admin-managed-user')
router.register(
    r'source-collections',
    AdminSourceCollectionViewSet,
    basename='admin-source-collection',
)
router.register(r'sources', AdminSourceViewSet, basename='admin-source')
router.register(r'study-plans', AdminStudyPlanViewSet, basename='admin-study-plan')
router.register(r'quizzes', AdminQuizViewSet, basename='admin-quiz')
router.register(r'quiz-attempts', AdminQuizAttemptViewSet, basename='admin-quiz-attempt')
router.register(
    r'character-interactions',
    AdminCharacterInteractionViewSet,
    basename='admin-character-interaction',
)
router.register(r'audit-logs', AuditLogViewSet, basename='admin-audit-log')
router.register(
    r'subscription-plans',
    AdminSubscriptionPlanViewSet,
    basename='admin-subscription-plan',
)
router.register(
    r'user-subscriptions',
    AdminUserSubscriptionViewSet,
    basename='admin-user-subscription',
)
router.register(
    r'subscription-usage',
    AdminSubscriptionUsageViewSet,
    basename='admin-subscription-usage',
)

urlpatterns = [
    path('me/', AdminMeView.as_view(), name='admin-me'),
    path('overview/', AdminOverviewView.as_view(), name='admin-overview'),
    path('system/health/', SystemHealthView.as_view(), name='admin-system-health'),
]
urlpatterns += router.urls
