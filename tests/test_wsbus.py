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

        client = AgentBusClient("ws://127.0.0.1:7895", auto_reconnect=False)
        await client.connect()

        await client.initialize("agent:system")

        await client.disconnect()
        await server.stop_server()

    @pytest.mark.asyncio
    async def test_subscribe_and_notify(self):
        server = AgentBusServer(host="localhost", port=7896)
        await server.start_server()

        client = AgentBusClient("ws://127.0.0.1:7896", auto_reconnect=False)
        await client.connect()
        await client.initialize("agent:system")

        notification_received = []

        async def handler(topic: str, payload: dict):
            notification_received.append({"topic": topic, "payload": payload})

        client.on_notification("test.*", handler)

        await client.subscribe("test.*")

        await server.publish(
            "test.topic",
            {
                "messageId": "msg_test",
                "type": "agent_event",
                "from": "agent:system",
                "timestamp": "2026-02-17T00:00:00Z",
                "content": {"hello": "world"},
            },
            message_id="msg_test",
            sender="agent:system",
        )

        await asyncio.sleep(0.2)

        assert len(notification_received) == 1
        assert notification_received[0]["topic"] == "test.topic"
        assert notification_received[0]["payload"]["content"]["hello"] == "world"

        await client.disconnect()
        await server.stop_server()

    @pytest.mark.asyncio
    async def test_inbound_message_convenience(self):
        server = AgentBusServer(host="localhost", port=7897)
        await server.start_server()

        client = AgentBusClient("ws://127.0.0.1:7897", auto_reconnect=False)
        await client.connect()
        await client.initialize("agent:system")

        received = []

        async def handler(topic: str, payload: dict):
            received.append(payload)

        client.on_notification("tg:*", handler)

        await client.subscribe("tg:*")

        msg = InboundMessage(channel="telegram", sender_id="123", chat_id="456", content="test message")
        await server.publish_inbound(msg)

        await asyncio.sleep(0.2)

        assert len(received) == 1
        assert received[0]["type"] == "tg_message"
        assert received[0]["content"]["text"] == "test message"

        await client.disconnect()
        await server.stop_server()
