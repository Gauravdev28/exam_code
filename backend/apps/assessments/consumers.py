import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

from .models import TestAttempt, AttemptStatus
from .services import AttemptService, AttemptTimerService


class TestAttemptConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time timer synchronization, autosave acknowledgments,
    and attempt lifecycle events.
    Strictly authenticates attempt ownership and utilizes authoritative domain services.
    """
    async def connect(self):
        self.attempt_id = self.scope['url_route']['kwargs']['attempt_id']
        self.user = self.scope.get('user')

        # Authentication check
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # Ownership & Authorization check
        attempt_valid = await self._verify_attempt_access()
        if not attempt_valid:
            await self.close(code=4003)
            return

        self.room_group_name = f"attempt_{self.attempt_id}"

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Send initial sync payload
        sync_data = await self._get_sync_data()
        await self.send_json({
            "type": "SYNC_STATE",
            "data": sync_data
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
            sync_data = await self._get_sync_data()
            await self.send_json({
                "type": "PONG",
                "server_time": timezone.now().isoformat(),
                "remaining_seconds": sync_data.get('remaining_seconds', 0),
                "status": sync_data.get('status')
            })

        elif action == 'SAVE_ANSWER':
            question_id = content.get('question_id')
            answer_data = content.get('answer_data', {})
            revision = content.get('revision', 1)

            save_res = await self._save_answer_via_service(question_id, answer_data, revision)
            await self.send_json({
                "type": "SAVE_ACK",
                "question_id": question_id,
                "data": save_res
            })

        elif action == 'SUBMIT':
            submit_res = await self._submit_attempt_via_service()
            await self.send_json({
                "type": "SUBMIT_ACK",
                "data": submit_res
            })

    # --- Database Helper Methods ---

    @database_sync_to_async
    def _verify_attempt_access(self) -> bool:
        attempt = TestAttempt.objects.filter(id=self.attempt_id).first()
        if not attempt:
            return False
        # Allow student owner or Admin
        if attempt.student_id == self.user.id or getattr(self.user, 'role', '') == 'ADMIN':
            return True
        return False

    @database_sync_to_async
    def _get_sync_data(self):
        attempt = TestAttempt.objects.filter(id=self.attempt_id).first()
        if not attempt:
            return {}
        AttemptTimerService.check_and_expire_attempt_if_needed(attempt)
        remaining = AttemptTimerService.get_remaining_seconds(attempt)
        return {
            "attempt_id": str(attempt.id),
            "status": attempt.status,
            "remaining_seconds": remaining,
            "server_time": timezone.now().isoformat()
        }

    @database_sync_to_async
    def _save_answer_via_service(self, question_id, answer_data, revision):
        try:
            return AttemptService.save_answer(
                student=self.user,
                attempt_id=str(self.attempt_id),
                snapshot_question_id=str(question_id),
                answer_data=answer_data,
                client_revision=revision,
                actor=self.user
            )
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    @database_sync_to_async
    def _submit_attempt_via_service(self):
        try:
            attempt = AttemptService.submit_attempt(
                student=self.user,
                attempt_id=str(self.attempt_id),
                actor=self.user
            )
            return {"status": attempt.status, "submitted_at": attempt.submitted_at.isoformat()}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    async def attempt_event(self, event):
        """
        Handler for real-time evaluator events pushed by CodeSubmissionService.
        """
        await self.send_json(event.get('message', {}))

