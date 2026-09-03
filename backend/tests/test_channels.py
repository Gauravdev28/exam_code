import pytest
import json
from channels.testing import WebsocketCommunicator
from codeguard.asgi import application

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_websocket_ping_connection_and_echo():
    """
    Verify Channels ASGI WebSocket transport:
    1. Connect to /ws/ping/ with valid host/origin headers
    2. Transmit JSON payload
    3. Receive JSON response
    4. Cleanly disconnect
    """
    communicator = WebsocketCommunicator(
        application,
        "/ws/ping/",
        headers=[
            (b"host", b"localhost"),
            (b"origin", b"http://localhost"),
        ]
    )
    connected, subprotocol = await communicator.connect()
    
    assert connected is True
    
    # Send ping action
    await communicator.send_json_to({"action": "ping"})
    
    # Receive response
    response = await communicator.receive_json_from(timeout=5)
    assert response == {
        "status": "success",
        "response": "pong"
    }
    
    # Close connection
    await communicator.disconnect()
