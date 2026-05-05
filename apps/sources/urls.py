from rest_framework.routers import SimpleRouter

from .views import StudentSourceViewSet

router = SimpleRouter(use_regex_path=False)
router.register(r'student-sources', StudentSourceViewSet, basename='student-source')

urlpatterns = router.urls
