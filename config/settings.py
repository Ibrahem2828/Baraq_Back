from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    ENVIRONMENT=(str, "production"),
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
    TIME_ZONE=(str, "Asia/Damascus"),
    ACCESS_TOKEN_LIFETIME_MINUTES=(int, 30),
    REFRESH_TOKEN_LIFETIME_DAYS=(int, 14),
    DATABASE_CONN_MAX_AGE=(int, 60),
    DATABASE_CONN_HEALTH_CHECKS=(bool, True),
    DATABASE_CONNECT_TIMEOUT=(int, 10),
    STUDENT_SOURCE_MAX_UPLOAD_MB=(int, 25),
    API_DOCS_PUBLIC=(bool, False),
    AI_SERVICE_ENABLED=(bool, True),
    AI_SERVICE_VERIFY_SSL=(bool, True),
    AI_SERVICE_TIMEOUT_SECONDS=(int, 30),
    AI_DATASET_CONSENT_VERSION=(str, "2026-07-01"),
    SECURE_SSL_REDIRECT=(bool, True),
    SECURE_HSTS_SECONDS=(int, 31536000),
    SECURE_HSTS_INCLUDE_SUBDOMAINS=(bool, True),
    SECURE_HSTS_PRELOAD=(bool, False),
    CORS_ALLOW_CREDENTIALS=(bool, False),
    DATABASE_STATEMENT_TIMEOUT_MS=(int, 30000),
)
environ.Env.read_env(BASE_DIR / ".env")

ENVIRONMENT = env("ENVIRONMENT")
DEBUG = env("DEBUG")
SECRET_KEY = env("SECRET_KEY", default="")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[]) or CORS_ALLOWED_ORIGINS
PUBLIC_API_BASE_URL = env("PUBLIC_API_BASE_URL", default="http://localhost:8000").rstrip("/")

if not DEBUG:
    if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure"):
        raise ImproperlyConfigured("A strong SECRET_KEY of at least 50 characters is required in production.")
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured("ALLOWED_HOSTS must be configured in production.")
    if not PUBLIC_API_BASE_URL.startswith("https://"):
        raise ImproperlyConfigured("PUBLIC_API_BASE_URL must use HTTPS in production.")
else:
    SECRET_KEY = SECRET_KEY or "django-insecure-development-only-not-for-production"
    ALLOWED_HOSTS = ALLOWED_HOSTS or ["127.0.0.1", "localhost", "testserver"]

APP_NAME = "Baraq Backend"
APP_VERSION = "4.0.0"
APP_PHASE = "4.0"
API_VERSION = "v1"
LEGACY_API_SUNSET = "Wed, 31 Dec 2026 23:59:59 GMT"
APP_FEATURES = {
    "auth": True,
    "study_plans": True,
    "quizzes": True,
    "sources": True,
    "subscriptions": True,
    "dashboard": True,
    "ai_service_integration": True,
    "fahes": True,
    "khota": True,
    "rasheed": True,
    "kholasa": True,
    "sada": True,
    "notifications": True,
    "support": True,
}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "apps.common",
    "apps.users",
    "apps.students",
    "apps.subjects",
    "apps.study_plans",
    "apps.quizzes",
    "apps.sources",
    "apps.subscriptions.apps.SubscriptionsConfig",
    "apps.ai_integration.apps.AIIntegrationConfig",
    "apps.analytics.apps.AnalyticsConfig",
    "apps.summaries.apps.SummariesConfig",
    "apps.audio.apps.AudioConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.support.apps.SupportConfig",
    "apps.admin_dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.common.middleware.RequestIDMiddleware",
    "apps.common.middleware.APIVersionHeadersMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

DATABASE_URL = env("DATABASE_URL", default=f"sqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}" if DEBUG else "")
if not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL is required in production.")
DATABASES = {"default": env.db("DATABASE_URL", default=DATABASE_URL)}
DATABASES["default"]["CONN_MAX_AGE"] = env("DATABASE_CONN_MAX_AGE")
DATABASES["default"]["CONN_HEALTH_CHECKS"] = env("DATABASE_CONN_HEALTH_CHECKS")
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    options = DATABASES["default"].setdefault("OPTIONS", {})
    options["connect_timeout"] = env("DATABASE_CONNECT_TIMEOUT")
    options["options"] = f"-c statement_timeout={env('DATABASE_STATEMENT_TIMEOUT_MS')}"

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache" if REDIS_URL.startswith("redis") else "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": REDIS_URL if REDIS_URL.startswith("redis") else "baraq-local-cache",
        "TIMEOUT": 300,
        "KEY_PREFIX": "baraq",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTH_USER_MODEL = "users.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "ar"
LANGUAGES = [("ar", "العربية"), ("en", "English")]
TIME_ZONE = env("TIME_ZONE")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
}
MEDIA_URL = env("MEDIA_URL", default="/media/")
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "media")))
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
STUDENT_SOURCE_MAX_UPLOAD_MB = env("STUDENT_SOURCE_MAX_UPLOAD_MB")
FILE_UPLOAD_MAX_MEMORY_SIZE = min(STUDENT_SOURCE_MAX_UPLOAD_MB, 10) * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = (STUDENT_SOURCE_MAX_UPLOAD_MB + 2) * 1024 * 1024

if env.bool("USE_S3_STORAGE", default=False):
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default=None)
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default=None)
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    AWS_S3_FILE_OVERWRITE = False

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.custom_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ("apps.common.renderers.EnvelopeJSONRenderer",),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", default="60/hour"),
        "user": env("THROTTLE_USER", default="2000/day"),
        "register": env("THROTTLE_REGISTER", default="10/hour"),
        "login": env("THROTTLE_LOGIN", default="10/minute"),
        "password_reset": env("THROTTLE_PASSWORD_RESET", default="5/hour"),
        "uploads": env("THROTTLE_UPLOADS", default="30/hour"),
        "ai_requests": env("THROTTLE_AI", default="100/day"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env("ACCESS_TOKEN_LIFETIME_MINUTES")),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env("REFRESH_TOKEN_LIFETIME_DAYS")),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "LEEWAY": 30,
}

API_DOCS_PUBLIC = env("API_DOCS_PUBLIC")
SPECTACULAR_SETTINGS = {
    "TITLE": "Baraq Backend API",
    "DESCRIPTION": "Production API for Baraq mobile, dashboard, and AI service integration.",
    "VERSION": APP_VERSION,
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny" if API_DOCS_PUBLIC else "rest_framework.permissions.IsAdminUser"],
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "StudyPlanStatusEnum": "apps.study_plans.models.StudyPlan.Status",
        "StudyPlanDifficultyLevelEnum": "apps.study_plans.models.StudyPlan.DifficultyLevel",
        "StudyPlanGenerationTypeEnum": "apps.study_plans.models.StudyPlan.GenerationType",
        "StudyTaskStatusEnum": "apps.study_plans.models.StudyTask.Status",
        "StudyTaskPriorityEnum": "apps.study_plans.models.StudyTask.Priority",
        "QuizTypeEnum": "apps.quizzes.models.QuizTypeChoices",
        "QuizStatusEnum": "apps.quizzes.models.QuizStatusChoices",
        "QuestionTypeEnum": "apps.quizzes.models.QuestionTypeChoices",
        "AttemptStatusEnum": "apps.quizzes.models.AttemptStatusChoices",
    },
}

CORS_ALLOW_CREDENTIALS = env("CORS_ALLOW_CREDENTIALS")
CORS_URLS_REGEX = r"^/api/.*$"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT") if not DEBUG else False
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = env("SECURE_HSTS_SECONDS") if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = env("SECURE_HSTS_INCLUDE_SUBDOMAINS") if not DEBUG else False
SECURE_HSTS_PRELOAD = env("SECURE_HSTS_PRELOAD") if not DEBUG else False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL.replace("/0", "/1"))
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 15 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 14 * 60
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE

AI_SERVICE_ENABLED = env("AI_SERVICE_ENABLED")
AI_SERVICE_BASE_URL = env("AI_SERVICE_BASE_URL", default="http://ai-service:8001")
AI_SERVICE_JOBS_PATH = env("AI_SERVICE_JOBS_PATH", default="/api/ai/v1/jobs")
AI_SERVICE_FEEDBACK_PATH = env("AI_SERVICE_FEEDBACK_PATH", default="/api/ai/v1/feedback")
AI_SERVICE_HEALTH_PATH = env("AI_SERVICE_HEALTH_PATH", default="/api/ai/v1/health/ready")
AI_SERVICE_INTERNAL_API_KEY = env("AI_SERVICE_INTERNAL_API_KEY", default="")
AI_SERVICE_WEBHOOK_SECRET = env("AI_SERVICE_WEBHOOK_SECRET", default="")
AI_SERVICE_VERIFY_SSL = env("AI_SERVICE_VERIFY_SSL")
AI_SERVICE_TIMEOUT_SECONDS = env("AI_SERVICE_TIMEOUT_SECONDS")
AI_DATASET_CONSENT_VERSION = env("AI_DATASET_CONSENT_VERSION")
if AI_SERVICE_ENABLED and not DEBUG and (len(AI_SERVICE_INTERNAL_API_KEY) < 32 or len(AI_SERVICE_WEBHOOK_SECRET) < 32):
    raise ImproperlyConfigured("AI service credentials must be at least 32 characters in production.")

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Baraq <no-reply@baraq.app>")
FRONTEND_PASSWORD_RESET_URL = env("FRONTEND_PASSWORD_RESET_URL", default="baraq://reset-password")
PASSWORD_RESET_TIMEOUT = env.int("PASSWORD_RESET_TIMEOUT", default=3600)

SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=SENTRY_DSN, environment=ENVIRONMENT, traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.05), send_default_pii=False)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "apps.common.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "apps": {"handlers": ["console"], "level": env("APP_LOG_LEVEL", default="INFO"), "propagate": False},
    },
}
