"""
Base Django settings shared by development and production.

All secrets and environment-specific values come from environment
variables (see .env.example at the project root). Nothing sensitive
is hard-coded here.
"""
from pathlib import Path
import ssl

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
env_file = BASE_DIR.parent / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-dev-key-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    # Local apps
    "apps.common",
    "apps.users",
    "apps.identities",
    "apps.registration",
    "apps.browser",
    "apps.email_service",
    "apps.ai_agent",
    "apps.accounts",
    "apps.audit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Database ---------------------------------------------------------------
DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://postgres:postgres@localhost:5432/temp_identity_agent")
}

# --- Auth --------------------------------------------------------------------
AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- I18N ---------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Static --------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF -----------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "user": "60/min",
        "anon": "10/min",
        # Tighter limit on auth endpoints specifically — register/login are
        # the most attractive targets for credential stuffing / abuse.
        "auth": "5/min",
        # Job creation launches a real browser + AI agent run — needs its
        # own, much tighter cap independent of general API usage.
        "registration_jobs": "10/hour",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# --- JWT (djangorestframework-simplejwt) --------------------------------------
from datetime import timedelta  # noqa: E402

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=28),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# --- CORS ------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"])

# --- Celery ------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

# Upstash / rediss:// — must use ssl module constants, NOT the string "CERT_REQUIRED"
if REDIS_URL.startswith("rediss://"):
    CELERY_BROKER_USE_SSL = {
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
    }
    CELERY_REDIS_BACKEND_USE_SSL = {
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
    }

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = env.int("MAX_JOB_DURATION_SECONDS", default=300)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# --- Celery beat schedule (periodic cleanup) ----------------------------------
CELERY_BEAT_SCHEDULE = {
    "expire-temporary-identities": {
        "task": "apps.identities.tasks.expire_temporary_identities",
        "schedule": 900.0,  # every 15 minutes
    },
    "expire-stale-registration-jobs": {
        "task": "apps.identities.tasks.expire_stale_registration_jobs",
        "schedule": 1800.0,  # every 30 minutes
    },
    "close-orphaned-browser-sessions": {
        "task": "apps.identities.tasks.close_orphaned_browser_sessions",
        "schedule": 1800.0,
    },
}

# --- Credential encryption ----------------------------------------------------
# Fernet key. Generate with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
CREDENTIAL_ENCRYPTION_KEY = env("CREDENTIAL_ENCRYPTION_KEY", default=None)

# --- AI provider ---------------------------------------------------------------
# Options:
#   openrouter  – OpenRouter only (default model: openrouter/free)
#   groq        – Groq only
#   fallback    – try OpenRouter first; on 429 / 5xx / network error → Groq
# If left empty, "fallback" is used when both OPENROUTER_API_KEY and
# GROQ_API_KEY are set; otherwise whichever one is configured.
AI_PROVIDER = env("AI_PROVIDER", default="fallback")

# OpenRouter (primary). `openrouter/free` auto-selects an available free model.
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY", default="")
OPENROUTER_BASE_URL = env("OPENROUTER_BASE_URL", default="https://openrouter.ai/api/v1")
OPENROUTER_MODEL = env("OPENROUTER_MODEL", default="openrouter/free")
# Optional attribution headers sent to OpenRouter.
OPENROUTER_SITE_URL = env("OPENROUTER_SITE_URL", default="")
OPENROUTER_APP_NAME = env("OPENROUTER_APP_NAME", default="Temporary Identity Agent")

# Groq (fallback or primary)
GROQ_API_KEY = env("GROQ_API_KEY", default="")
GROQ_BASE_URL = env("GROQ_BASE_URL", default="https://api.groq.com/openai/v1")
GROQ_MODEL = env("GROQ_MODEL", default="llama-3.3-70b-versatile")

MAX_AGENT_STEPS = env.int("MAX_AGENT_STEPS", default=30)
MAX_JOB_DURATION_SECONDS = env.int("MAX_JOB_DURATION_SECONDS", default=300)

# --- Email provider --------------------------------------------------------
EMAIL_PROVIDER = env("EMAIL_PROVIDER", default="mailtm")
EMAIL_API_KEY = env("EMAIL_API_KEY", default="")
EMAIL_API_BASE_URL = env("EMAIL_API_BASE_URL", default="https://api.mail.tm")

# --- Retention / abuse prevention ------------------------------------------
TEMP_ACCOUNT_RETENTION_DAYS = env.int("TEMP_ACCOUNT_RETENTION_DAYS", default=7)
MAX_CONCURRENT_JOBS = env.int("MAX_CONCURRENT_JOBS", default=3)
MAX_JOBS_PER_USER_PER_DAY = env.int("MAX_JOBS_PER_USER_PER_DAY", default=20)

# --- Temporary identity generation ------------------------------------------
# Password policy for generated temporary identities. Enforced by
# apps.identities.password_generator using the `secrets` module — never
# Python's `random`.
IDENTITY_PASSWORD_LENGTH = env.int("IDENTITY_PASSWORD_LENGTH", default=20)
IDENTITY_PASSWORD_MIN_UPPER = env.int("IDENTITY_PASSWORD_MIN_UPPER", default=2)
IDENTITY_PASSWORD_MIN_LOWER = env.int("IDENTITY_PASSWORD_MIN_LOWER", default=2)
IDENTITY_PASSWORD_MIN_DIGITS = env.int("IDENTITY_PASSWORD_MIN_DIGITS", default=2)
IDENTITY_PASSWORD_MIN_SYMBOLS = env.int("IDENTITY_PASSWORD_MIN_SYMBOLS", default=2)

# --- Structured logging ------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}