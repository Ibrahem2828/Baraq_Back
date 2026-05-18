from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import MySubscriptionView, PublicSubscriptionPlanViewSet

router = SimpleRouter(use_regex_path=False)
router.register(r'plans', PublicSubscriptionPlanViewSet, basename='subscription-plan-public')

urlpatterns = [
    path('me/', MySubscriptionView.as_view(), name='my-subscription'),
]
urlpatterns += router.urls
