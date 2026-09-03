from django.urls import path
from apps.core.consumers import PingConsumer, AuthEchoConsumer
from apps.assessments.consumers import TestAttemptConsumer
from apps.invigilation.consumers import InvigilationConsumer, ProctorChatConsumer

websocket_urlpatterns = [
    path('ws/ping/', PingConsumer.as_asgi()),
    path('ws/auth-echo/', AuthEchoConsumer.as_asgi()),
    path('ws/attempts/<uuid:attempt_id>/', TestAttemptConsumer.as_asgi()),
    path('ws/proctor/assessments/<uuid:assessment_id>/', InvigilationConsumer.as_asgi()),
    path('ws/proctor/attempts/<uuid:attempt_id>/chat/', ProctorChatConsumer.as_asgi()),
]
