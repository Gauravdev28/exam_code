import json
from channels.generic.websocket import AsyncWebsocketConsumer

class PingConsumer(AsyncWebsocketConsumer):
    """
    Foundational smoke test consumer verifying Channels ASGI WebSocket pipeline,
    handshake negotiation, bidirectional JSON message frame transport, and clean disconnection.
    """
    async def connect(self):
        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or '{}')
        except Exception:
            data = {}

        action = data.get('action', 'ping')
        await self.send(text_data=json.dumps({
            'status': 'success',
            'response': 'pong' if action == 'ping' else action
        }))


class AuthEchoConsumer(AsyncWebsocketConsumer):
    """
    Authenticated WebSocket consumer establishing session-based WebSocket authorization.
    Rejects unauthenticated connections with close code 4001.
    """
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated or not user.is_active:
            await self.close(code=4001)
            return
        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        user = self.scope.get("user")
        await self.send(text_data=json.dumps({
            "status": "success",
            "authenticated_as": user.email,
            "role": getattr(user, 'role', 'STUDENT')
        }))
