"""
CODEGUARD — Production Settings
"""
from .base import *

DEBUG = False

# Strict Security Headers & Cookies
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Allows frontend client to read CSRF token cookie

# Production REST renderer (JSON only)
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
    'rest_framework.renderers.JSONRenderer',
]

# Phase 9: DSAR Master Key Fail-Closed Production Security (SEC-03)
import re
from django.core.exceptions import ImproperlyConfigured

DEV_DEFAULT_KEY_V1 = '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
v1_key = os.getenv('DSAR_MASTER_KEY_V1')

if not v1_key:
    raise ImproperlyConfigured("DSAR_MASTER_KEY_V1 environment variable is mandatory in production.")

v1_key_clean = v1_key.strip()

if v1_key_clean == DEV_DEFAULT_KEY_V1:
    raise ImproperlyConfigured("DSAR_MASTER_KEY_V1 cannot use the insecure development default key in production.")

if len(v1_key_clean) != 64 or not re.fullmatch(r'[0-9a-fA-F]{64}', v1_key_clean):
    raise ImproperlyConfigured("DSAR_MASTER_KEY_V1 must be a valid 64-character hexadecimal string (32 bytes).")

