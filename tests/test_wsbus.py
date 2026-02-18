"""Unit tests for WebSocket message bus."""

import asyncio

import pytest

from typing import Any

from bub.bus.bus import AgentBusClient, AgentBusServer


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

        await client.subscribe("test.*", handler)

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
    async def test_send_message(self):
        server = AgentBusServer(host="localhost", port=7897)
        await server.start_server()

        client = AgentBusClient("ws://127.0.0.1:7897", auto_reconnect=False)
        await client.connect()
        await client.initialize("agent:system")

        received = []

        async def handler(topic: str, payload: dict[str, Any]):
            received.append(payload)

        await client.subscribe("tg:*", handler)

        # Send a message using the new API
        from datetime import UTC, datetime
        from bub.message.messages import create_tg_message_payload

        payload = create_tg_message_payload(
            message_id="msg_test",
            from_addr="tg:123",
            timestamp=datetime.now(UTC).isoformat(),
            text="test message",
            sender_id="456",
            channel="telegram",
        )
        await client.send_message(to="tg:123", payload=payload)

        await asyncio.sleep(0.2)

        assert len(received) == 1
        assert received[0]["type"] == "tg_message"
        assert received[0]["content"]["text"] == "test message"

        await client.disconnect()
        await server.stop_server()
