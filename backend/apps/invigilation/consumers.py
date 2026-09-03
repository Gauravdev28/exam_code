import json
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

from apps.accounts.models import Role
from apps.invigilation.models import ProctorAssignment
from apps.assessments.models import Assessment, TestAttempt

logger = logging.getLogger(__name__)


class InvigilationConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for the real-time proctoring console.
    Provides live risk score telemetry, candidate keyframe mosaic distribution,
    and instantaneous intervention status updates.
    """
    async def connect(self):
        self.assessment_id = str(self.scope['url_route']['kwargs']['assessment_id'])
        self.user = self.scope.get('user')

        # Authentication check
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # Authorization check: Proctor or Admin with assigned access
        is_authorized = await self._verify_proctor_access()
        if not is_authorized:
            await self.close(code=4003)
            return

        self.room_group_name = f"proctor_assessment_{self.assessment_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        await self.send_json({
            "type": "CONNECTED",
            "assessment_id": self.assessment_id,
            "proctor": self.user.email,
            "connected_at": timezone.now().isoformat()
        })

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive_json(self, content, **kwargs):
        action = content.get('action')
        if action == 'PING':
            await self.send_json({
                "type": "PONG",
                "server_time": timezone.now().isoformat()
            })

    async def proctor_event(self, event):
        """
        Handler for group messages pushed via channel_layer.
        """
        await self.send_json({
            "type": "PROCTOR_EVENT",
            "data": event.get("data", {})
        })

    @database_sync_to_async
    def _verify_proctor_access(self) -> bool:
        if getattr(self.user, 'role', None) == Role.ADMIN or self.user.is_staff or self.user.is_superuser:
            return True
        if getattr(self.user, 'role', None) not in ['PROCTOR', Role.ADMIN] and not self.user.is_staff:
            return False
        return ProctorAssignment.objects.filter(
            assessment_id=self.assessment_id,
            proctor=self.user,
            is_active=True
        ).exists()


class ProctorChatConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for bilateral candidate-proctor chat during an examination attempt.
    """
    async def connect(self):
        self.attempt_id = str(self.scope['url_route']['kwargs']['attempt_id'])
        self.user = self.scope.get('user')

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        is_authorized = await self._verify_chat_access()
        if not is_authorized:
            await self.close(code=4003)
            return

        self.room_group_name = f"attempt_{self.attempt_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive_json(self, content, **kwargs):
        action = content.get('action')
        if action == 'PING':
            await self.send_json({
                "type": "PONG",
                "server_time": timezone.now().isoformat()
            })

    async def proctor_event(self, event):
        await self.send_json({
            "type": "EVENT",
            "data": event.get("data", {})
        })

    @database_sync_to_async
    def _verify_chat_access(self) -> bool:
        attempt = TestAttempt.objects.filter(id=self.attempt_id).values('student_id', 'assessment_id').first()
        if not attempt:
            return False

        # Candidate check
        if attempt['student_id'] == self.user.id:
            return True

        # Proctor / Admin check
        if getattr(self.user, 'role', None) == Role.ADMIN or self.user.is_staff or self.user.is_superuser:
            return True

        return ProctorAssignment.objects.filter(
            assessment_id=attempt['assessment_id'],
            proctor=self.user,
            is_active=True
        ).exists()
