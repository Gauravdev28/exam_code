"""
CODEGUARD — Test Settings
"""
from .base import *

DEBUG = False
TESTING = True

# Fast password hasher for test execution speed
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Use in-memory SQLite database for deterministic test runs unless configured otherwise
if USE_SQLITE_DEV or os.getenv('CI', 'false').lower() != 'true':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }

# In-memory channel layer for isolated WebSocket tests
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# Eager Celery execution for deterministic testing
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
