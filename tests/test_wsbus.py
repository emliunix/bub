"""Unit tests for WebSocket message bus."""

import asyncio

import pytest

from bub.channels.events import InboundMessage
from bub.channels.wsbus import AgentBusClient, AgentBusServer


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


class TestAgentBusServer:
    @pytest.mark.asyncio
    async def test_server_initialization(self):
        server = AgentBusServer(host="localhost", port=7893)
        assert server.url == "ws://localhost:7893"


class TestAgentBusClient:
    @pytest.mark.asyncio
    async def test_client_server_roundtrip(self):
        server = AgentBusServer(host="localhost", port=7895)
        await server.start_server()

        client = AgentBusClient("ws://localhost:7895")
        await client.connect()

        await client.initialize("test-client", {"name": "test", "version": "1.0.0"})

        await client.disconnect()
        await server.stop_server()

    @pytest.mark.asyncio
    async def test_subscribe_and_notify(self):
        server = AgentBusServer(host="localhost", port=7896)
        await server.start_server()

        client = AgentBusClient("ws://localhost:7896")
        await client.connect()
        await client.initialize("test-client")

        notification_received = []

        async def handler(topic: str, payload: dict):
            notification_received.append({"topic": topic, "payload": payload})

        client.on_notification("test.*", handler)

        await client.subscribe("test.*")

        await server.publish("test.topic", {"hello": "world"})

        await asyncio.sleep(0.2)

        assert len(notification_received) == 1
        assert notification_received[0]["topic"] == "test.topic"
        assert notification_received[0]["payload"] == {"hello": "world"}

        await client.disconnect()
        await server.stop_server()

    @pytest.mark.asyncio
    async def test_inbound_message_convenience(self):
        server = AgentBusServer(host="localhost", port=7897)
        await server.start_server()

        client = AgentBusClient("ws://localhost:7897")
        await client.connect()
        await client.initialize("test-client")

        received = []

        async def handler(topic: str, payload: dict):
            received.append(payload)

        client.on_notification("inbound:*", handler)

        await client.subscribe("inbound:*")

        msg = InboundMessage(channel="telegram", sender_id="123", chat_id="456", content="test message")
        await server.publish_inbound(msg)

        await asyncio.sleep(0.2)

        assert len(received) == 1
        assert received[0]["chat_id"] == "456"
        assert received[0]["content"] == "test message"

        await client.disconnect()
        await server.stop_server()
