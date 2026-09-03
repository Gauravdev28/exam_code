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
