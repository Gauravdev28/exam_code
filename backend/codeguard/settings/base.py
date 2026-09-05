"""
CODEGUARD — Base Django Settings
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# BASE_DIR points to backend/ root directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables
ROOT_DIR = BASE_DIR.parent
env_path = ROOT_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

SECRET_KEY = os.getenv('SECRET_KEY', 'insecure-default-codeguard-key-must-change-in-prod')

DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')

ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if host.strip()]

# Application definition
INSTALLED_APPS = [
    'daphne',  # Must precede django.contrib.staticfiles for Channels ASGI handling
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party libraries
    'rest_framework',
    'corsheaders',
    'channels',

    # CODEGUARD local apps
    'apps.core',
    'apps.accounts',
    'apps.questions',
    'apps.assessments',
    'apps.evaluator',
    'apps.proctoring',
    'apps.results',
    'apps.retention',
    'apps.invigilation',
]

AUTH_USER_MODEL = 'accounts.User'

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

ROOT_URLCONF = 'codeguard.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'codeguard.wsgi.application'
ASGI_APPLICATION = 'codeguard.asgi.application'

# Database Configuration
DB_ENGINE = os.getenv('DB_ENGINE', 'django.db.backends.mysql')
USE_SQLITE_DEV = os.getenv('USE_SQLITE_DEV', 'False').lower() in ('true', '1', 't')

if USE_SQLITE_DEV:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': os.getenv('DB_NAME', 'codeguard_db'),
            'USER': os.getenv('DB_USER', 'codeguard_user'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'codeguard_secure_password'),
            'HOST': os.getenv('DB_HOST', '127.0.0.1'),
            'PORT': os.getenv('DB_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            }
        }
    }

# Password validation & Modern Secure Hashers (Argon2 priority)
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/minute',
        'user': '180/minute',
        'login': '10/minute',
        'user_burst': '60/minute',
    },
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
    'DEFAULT_PAGINATION_CLASS': 'apps.core.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',')
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True

# Redis and Channel Layers
REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [REDIS_URL],
        },
    },
}

# Celery Broker & Results
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/1')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/2')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Judge0 Execution Engine Configuration
JUDGE0_URL = os.getenv('JUDGE0_URL', 'http://127.0.0.1:2358')
JUDGE0_API_KEY = os.getenv('JUDGE0_API_KEY', '')
JUDGE0_CALLBACK_URL = os.getenv('JUDGE0_CALLBACK_URL', '')
JUDGE0_POLL_INTERVAL_SEC = float(os.getenv('JUDGE0_POLL_INTERVAL_SEC', '0.5'))
JUDGE0_MAX_POLL_TIMEOUT_SEC = int(os.getenv('JUDGE0_MAX_POLL_TIMEOUT_SEC', '30'))
JUDGE0_TIMEOUT_SECONDS = int(os.getenv('JUDGE0_TIMEOUT_SECONDS', '10'))

# Phase 9: Automated Data Retention & DSAR Configuration
RETENTION_DEFAULT_DETAILED_DATA_TTL_DAYS = int(os.getenv('RETENTION_DEFAULT_DETAILED_DATA_TTL_DAYS', '30'))
RETENTION_DEFAULT_PROCTORING_EVIDENCE_TTL_DAYS = int(os.getenv('RETENTION_DEFAULT_PROCTORING_EVIDENCE_TTL_DAYS', '30'))
RETENTION_DEFAULT_REPORT_TTL_DAYS = int(os.getenv('RETENTION_DEFAULT_REPORT_TTL_DAYS', '7'))
RETENTION_CHUNK_SIZE = int(os.getenv('RETENTION_CHUNK_SIZE', '100'))
DSAR_SNAPSHOT_PENDING_TIMEOUT = int(os.getenv('DSAR_SNAPSHOT_PENDING_TIMEOUT', '900'))  # 15 minutes
DSAR_ARCHIVE_TTL_DAYS = int(os.getenv('DSAR_ARCHIVE_TTL_DAYS', '7'))
ACTIVE_DSAR_KEY_VERSION = os.getenv('ACTIVE_DSAR_KEY_VERSION', 'v1')
DSAR_MASTER_KEYS = {
    'v1': os.getenv('DSAR_MASTER_KEY_V1', '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'),
    'v2': os.getenv('DSAR_MASTER_KEY_V2', 'fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210'),
}

