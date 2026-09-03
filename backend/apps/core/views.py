import os
import time
from django.db import connection
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.conf import settings
from .responses import APIResponse

class HealthCheckView(APIView):
    """
    System Health Check Endpoint.
    Tests database connectivity and cache responsiveness.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        health_status = {
            "application": "CODEGUARD Assessment Platform",
            "version": "1.0.0-phase1",
            "timestamp": timezone.now().isoformat(),
            "environment": os.getenv('DJANGO_ENV', 'development'),
            "services": {}
        }
        overall_healthy = True

        # 1. Test Database Connectivity
        db_start = time.time()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
            db_duration_ms = round((time.time() - db_start) * 1000, 2)
            health_status["services"]["database"] = {
                "status": "healthy",
                "engine": connection.vendor,
                "latency_ms": db_duration_ms
            }
        except Exception as e:
            overall_healthy = False
            health_status["services"]["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }

        # 2. Test Cache / Channel Layer
        cache_start = time.time()
        channel_backend = settings.CHANNEL_LAYERS.get('default', {}).get('BACKEND', '')
        is_in_memory = 'InMemoryChannelLayer' in channel_backend or getattr(settings, 'TESTING', False)

        if is_in_memory:
            health_status["services"]["redis"] = {
                "status": "healthy",
                "mode": "in-memory (testing/dev)",
                "latency_ms": 0.0
            }
        else:
            try:
                import redis
                redis_client = redis.from_url(settings.REDIS_URL, socket_timeout=1)
                redis_client.ping()
                cache_duration_ms = round((time.time() - cache_start) * 1000, 2)
                health_status["services"]["redis"] = {
                    "status": "healthy",
                    "latency_ms": cache_duration_ms
                }
            except Exception as e:
                if settings.DEBUG:
                    health_status["services"]["redis"] = {
                        "status": "degraded",
                        "message": "Redis unavailable (using development fallback)",
                        "error": str(e)
                    }
                else:
                    overall_healthy = False
                    health_status["services"]["redis"] = {
                        "status": "unhealthy",
                        "error": str(e)
                    }

        http_status = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        health_status["status"] = "healthy" if overall_healthy else "degraded"

        return APIResponse(
            data=health_status,
            message="System is operational" if overall_healthy else "System is experiencing degraded service",
            status_code=http_status
        )


class SystemInfoView(APIView):
    """
    Public system metadata endpoint exposing API capabilities.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return APIResponse(
            data={
                "name": "CODEGUARD API",
                "version": "1.0.0",
                "supported_languages": ["python", "cpp", "java"],
                "phase": "Phase 1: Foundation",
                "docs_url": "/api/docs/"
            },
            message="CODEGUARD API Gateway"
        )
