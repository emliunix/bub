"""Unit tests for WebSocket message bus."""

import asyncio

import pytest

from bub.channels.wsbus import WebSocketMessageBus, WebSocketMessageBusClient
from bub.channels.events import InboundMessage, OutboundMessage


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


class TestWebSocketBus:
    @pytest.mark.asyncio
    async def test_bus_initialization(self):
        bus = WebSocketMessageBus(host="localhost", port=7893)
        assert bus.url == "ws://localhost:7893"
        assert not bus._running

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        bus = WebSocketMessageBus(host="localhost", port=7894)
        await bus.start_server()

        received = []

        async def handler(payload):
            received.append(payload)

        await bus.subscribe("test.topic", handler)
        await bus.publish("test.topic", {"hello": "world"})

        await asyncio.sleep(0.1)

        assert len(received) == 1
        assert received[0] == {"hello": "world"}

        await bus.stop_server()

    @pytest.mark.asyncio
    async def test_client_server_communication(self):
        server = WebSocketMessageBus(host="localhost", port=7895)
        await server.start_server()

        client = WebSocketMessageBusClient("ws://localhost:7895")
        await client.connect()

        received = []

        async def handler(payload):
            received.append(payload)

        await client.subscribe("chat.message", handler)

        # Publish from server
        await server.publish("chat.message", {"text": "hello"})

        await asyncio.sleep(0.2)

        assert len(received) == 1
        assert received[0]["text"] == "hello"

        await client.disconnect()
        await server.stop_server()

    @pytest.mark.asyncio
    async def test_inbound_message_convenience(self):
        server = WebSocketMessageBus(host="localhost", port=7896)
        await server.start_server()

        received = []

        async def handler(inbound):
            received.append(inbound)

        await server.subscribe("inbound", handler)

        msg = InboundMessage(channel="telegram", sender_id="123", chat_id="456", content="test message")

        await server.publish_inbound(msg)

        await asyncio.sleep(0.1)

        assert len(received) == 1
        assert received[0]["channel"] == "telegram"
        assert received[0]["content"] == "test message"

        await server.stop_server()

    @pytest.mark.asyncio
    async def test_outbound_message_convenience(self):
        server = WebSocketMessageBus(host="localhost", port=7897)
        await server.start_server()

        received = []

        async def handler(outbound):
            received.append(outbound)

        await server.subscribe("outbound", handler)

        msg = OutboundMessage(channel="telegram", chat_id="456", content="response")

        await server.publish_outbound(msg)

        await asyncio.sleep(0.1)

        assert len(received) == 1
        assert received[0]["channel"] == "telegram"
        assert received[0]["content"] == "response"

        await server.stop_server()
