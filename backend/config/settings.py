"""Django settings. All deployment-specific values come from the environment."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8080,http://localhost:8000"
).split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.accounts",
    "apps.projects",
    "apps.surveys",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

if os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.environ["POSTGRES_HOST"],
            "NAME": os.environ.get("POSTGRES_DB", "rampa"),
            "USER": os.environ.get("POSTGRES_USER", "rampa"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    # Local test/dev fallback: this feature stores no geometry columns yet, so
    # sqlite keeps the suite runnable without PostGIS.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "dev.sqlite3",
        }
    }

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "apps.common.errors.api_exception_handler",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

# Object storage (S3-compatible; MinIO in dev). Files never live in the DB.
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://localhost:9000")
S3_PUBLIC_ENDPOINT = os.environ.get("S3_PUBLIC_ENDPOINT", S3_ENDPOINT)
S3_BUCKET = os.environ.get("S3_BUCKET", "rampa")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "rampa")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "rampasecret")
PRESIGN_EXPIRY_SECONDS = int(os.environ.get("PRESIGN_EXPIRY_SECONDS", "3600"))

# Resumable uploads (tusd) / tiles (titiler)
TUS_PUBLIC_URL = os.environ.get("TUS_PUBLIC_URL", "http://localhost:1080/files/")
TUS_INTERNAL_URL = os.environ.get("TUS_INTERNAL_URL", "http://tusd:1080/files/")
TUSD_HOOK_SECRET = os.environ.get("TUSD_HOOK_SECRET", "dev-hook-secret")
TITILER_PUBLIC_URL = os.environ.get("TITILER_PUBLIC_URL", "http://localhost:8081")

# Ingest limits (FR-001/FR-002)
MAX_UPLOAD_BYTES = 50 * 1024**3
SUPPORTED_EXTENSIONS = (".las", ".laz")
UPLOAD_EXPIRY_DAYS = 7
DEM_RESOLUTION_M = 0.20

# Celery
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BEAT_SCHEDULE = {
    "purge-expired-uploads": {
        "task": "apps.surveys.tasks_maintenance.purge_expired_upload_sessions",
        "schedule": 3600.0,
    }
}

LANGUAGE_CODE = "es"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "pipeline": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "pipeline"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
