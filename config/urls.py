from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

admin.site.site_header = "Baraq Administration"
admin.site.site_title = "Baraq Admin"
admin.site.index_title = "Baraq MVP Control Panel"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path(
        'api/docs/',
        SpectacularSwaggerView.as_view(url_name='api-schema'),
        name='api-docs',
    ),
    path('api/', include('apps.common.urls')),
    path('api/ai-gateway/', include('apps.ai_gateway.urls')),
    path('api/', include('apps.users.urls')),
    path('api/', include('apps.students.urls')),
    path('api/', include('apps.subjects.urls')),
    path('api/', include('apps.study_plans.urls')),
    path('api/', include('apps.quizzes.urls')),
]
