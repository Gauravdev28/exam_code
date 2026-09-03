from django.urls import path
from apps.core.consumers import PingConsumer, AuthEchoConsumer
from apps.assessments.consumers import TestAttemptConsumer

websocket_urlpatterns = [
    path('ws/ping/', PingConsumer.as_asgi()),
    path('ws/auth-echo/', AuthEchoConsumer.as_asgi()),
    path('ws/attempts/<uuid:attempt_id>/', TestAttemptConsumer.as_asgi()),
]
