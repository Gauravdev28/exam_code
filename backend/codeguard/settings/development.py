"""
CODEGUARD — Development Settings
"""
from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# Add BrowsableAPIRenderer for interactive API inspection during development
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
    'rest_framework.renderers.JSONRenderer',
    'rest_framework.renderers.BrowsableAPIRenderer',
]

# Development CORS allows all local development interfaces
CORS_ALLOW_ALL_ORIGINS = True

# CSRF Trusted Origins for local development frontend (Vite)
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:5174',
    'http://127.0.0.1:5174',
    'http://localhost:5175',
    'http://127.0.0.1:5175',
]

# Development login throttle rate to prevent locking out rapid manual/automated testing
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['login'] = '60/minute'

# In-memory channel layer fallback if Redis is unavailable during local standalone runs
try:
    import redis
    r = redis.from_url(REDIS_URL, socket_timeout=1)
    r.ping()
except Exception:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }
