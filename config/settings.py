from datetime import timedelta
from pathlib import Path
import tempfile

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
SQLITE_FALLBACK_PATH = Path(tempfile.gettempdir()) / 'baraq_backend.sqlite3'

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["127.0.0.1", "localhost"]),
    CORS_ALLOWED_ORIGINS=(
        list,
        [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8081",
            "http://127.0.0.1:8081",
        ],
    ),
    ACCESS_TOKEN_LIFETIME_MINUTES=(int, 60),
    REFRESH_TOKEN_LIFETIME_DAYS=(int, 7),
    TIME_ZONE=(str, "Asia/Damascus"),
    AI_SERVICE_ENABLED=(bool, False),
    AI_SERVICE_BASE_URL=(str, "http://localhost:8001"),
    AI_SERVICE_API_KEY=(str, "change-me"),
    AI_SERVICE_TIMEOUT_SECONDS=(int, 60),
    AI_SERVICE_VERIFY_SSL=(bool, True),
    AI_SERVICE_RETRY_COUNT=(int, 2),
    DATABASE_CONN_MAX_AGE=(int, 60),
    DATABASE_CONN_HEALTH_CHECKS=(bool, True),
    DATABASE_CONNECT_TIMEOUT=(int, 10),
    MEDIA_ROOT=(str, str(BASE_DIR / 'media')),
    MEDIA_URL=(str, '/media/'),
    STUDENT_SOURCE_MAX_UPLOAD_MB=(int, 25),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env(
    "SECRET_KEY",
    default="django-insecure-change-this-before-production",
)
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
CORS_ALLOW_CREDENTIALS = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'apps.common',
    'apps.users',
    'apps.students',
    'apps.subjects',
    'apps.study_plans',
    'apps.quizzes',
    'apps.sources',
    'apps.ai_gateway',
    'apps.subscriptions.apps.SubscriptionsConfig',
    'apps.admin_dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


DATABASES = {
    'default': env.db(
        'DATABASE_URL',
        default=f"sqlite:///{SQLITE_FALLBACK_PATH.as_posix()}",
    ),
}
DATABASES['default']['CONN_MAX_AGE'] = env('DATABASE_CONN_MAX_AGE')
DATABASES['default']['CONN_HEALTH_CHECKS'] = env('DATABASE_CONN_HEALTH_CHECKS')
if DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql':
    DATABASES['default'].setdefault('OPTIONS', {})
    DATABASES['default']['OPTIONS']['connect_timeout'] = env(
        'DATABASE_CONNECT_TIMEOUT'
    )


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'en-us'
TIME_ZONE = env('TIME_ZONE')

USE_I18N = True
USE_TZ = True

APP_NAME = 'Baraq Backend'
APP_PHASE = '3.6'
APP_FEATURES = {
    'auth': True,
    'study_plans': True,
    'quizzes': True,
    'ai_gateway': True,
    'audio': False,
    'summaries': False,
    'analytics': False,
}

AI_SERVICE_ENABLED = env('AI_SERVICE_ENABLED')
AI_SERVICE_BASE_URL = env('AI_SERVICE_BASE_URL')
AI_SERVICE_API_KEY = env('AI_SERVICE_API_KEY')
AI_SERVICE_TIMEOUT_SECONDS = env('AI_SERVICE_TIMEOUT_SECONDS')
AI_SERVICE_VERIFY_SSL = env('AI_SERVICE_VERIFY_SSL')
AI_SERVICE_RETRY_COUNT = env('AI_SERVICE_RETRY_COUNT')

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = env('MEDIA_URL')
MEDIA_ROOT = env('MEDIA_ROOT')
STUDENT_SOURCE_MAX_UPLOAD_MB = env('STUDENT_SOURCE_MAX_UPLOAD_MB')
Path(MEDIA_ROOT).mkdir(parents=True, exist_ok=True)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'users.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'apps.common.exceptions.custom_exception_handler',
    'DEFAULT_PAGINATION_CLASS': 'apps.common.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=env('ACCESS_TOKEN_LIFETIME_MINUTES')
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=env('REFRESH_TOKEN_LIFETIME_DAYS')
    ),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'UPDATE_LAST_LOGIN': True,
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Baraq Backend API',
    'DESCRIPTION': 'Phase 1, 2, 3, 3.5, and 3.6 backend for the Baraq smart learning platform.',
    'VERSION': '3.6.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny'],
    'ENUM_NAME_OVERRIDES': {
        'StudyPlanStatusEnum': 'apps.study_plans.models.StudyPlan.Status',
        'StudyPlanDifficultyLevelEnum': 'apps.study_plans.models.StudyPlan.DifficultyLevel',
        'StudyPlanGenerationTypeEnum': 'apps.study_plans.models.StudyPlan.GenerationType',
        'StudyTaskStatusEnum': 'apps.study_plans.models.StudyTask.Status',
        'StudyTaskPriorityEnum': 'apps.study_plans.models.StudyTask.Priority',
        'QuizTypeEnum': 'apps.quizzes.models.QuizTypeChoices',
        'QuizStatusEnum': 'apps.quizzes.models.QuizStatusChoices',
        'QuestionTypeEnum': 'apps.quizzes.models.QuestionTypeChoices',
        'AttemptStatusEnum': 'apps.quizzes.models.AttemptStatusChoices',
        'QuizProgressActionEnum': 'apps.quizzes.models.QuizLogActionChoices',
        'StudentSourceTypeEnum': 'apps.sources.models.StudentSource.SourceType',
        'StudentSourceStatusEnum': 'apps.sources.models.StudentSource.Status',
        'StudentSourceCollectionStatusEnum': 'apps.sources.models.StudentSourceCollection.Status',
        'SourceCharacterEnum': 'apps.sources.models.StudentSourceInteraction.Character',
        'SourceInteractionActionEnum': 'apps.sources.models.StudentSourceInteraction.Action',
        'SourceInteractionStatusEnum': 'apps.sources.models.StudentSourceInteraction.Status',
        'SubscriptionBillingIntervalEnum': 'apps.subscriptions.models.SubscriptionPlan.BillingInterval',
        'UserSubscriptionStatusEnum': 'apps.subscriptions.models.UserSubscription.Status',
        'SubscriptionProviderEnum': 'apps.subscriptions.models.UserSubscription.Provider',
        'SubscriptionEventTypeEnum': 'apps.subscriptions.models.SubscriptionEvent.EventType',
    },
}

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
