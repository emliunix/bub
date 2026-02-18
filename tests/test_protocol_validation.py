"""Test JSON-RPC 2.0 WebSocket protocol validation."""

import asyncio
import json

import pytest
import websockets

from bub.channels.events import InboundMessage, OutboundMessage
from bub.bus.bus import AgentBusClient, AgentBusServer


def _server_url(server: AgentBusServer) -> str:
    assert server._server is not None
    for sock in server._server.sockets:
        addr = sock.getsockname()
        if len(addr) == 2:
            return f"ws://127.0.0.1:{addr[1]}"
    port = server._server.sockets[0].getsockname()[1]
    return f"ws://localhost:{port}"


@pytest.mark.asyncio
async def test_protocol_full_flow() -> None:
    """Validate full protocol flow: connect, initialize, subscribe, receive all messages."""
    server = AgentBusServer(server=("localhost", 0))
    await server.start_server()

    try:
        server_url = _server_url(server)

        # Client 1: Connects and subscribes to tg topics
        client1 = AgentBusClient(server_url, auto_reconnect=False)
        await client1.connect()

        # Initialize handshake
        init_result = await client1.initialize("agent:system")
        assert init_result.server_id
        assert init_result.server_info.name == "bub-bus"
        assert init_result.capabilities.subscribe is True

        # Subscribe to all tg messages
        sub1 = await client1.subscribe("tg:*")
        assert sub1.success is True

        # Track received messages
        client1_messages: list[tuple[str, dict]] = []

        async def record_handler(topic: str, payload: dict) -> None:
            client1_messages.append((topic, payload))

        await client1.subscribe("tg:*", record_handler)

        # Client 2: Connects as tg peer and sends messages
        client2 = AgentBusClient(server_url, auto_reconnect=False)
        await client2.connect()
        await client2.initialize("tg:chat-bridge")

        await client2.publish_inbound(
            InboundMessage(
                channel="telegram",
                sender_id="user1",
                chat_id="chat1",
                content="hello from telegram",
            )
        )
        await client2.publish_inbound(
            InboundMessage(
                channel="whatsapp",
                sender_id="user2",
                chat_id="chat2",
                content="hello from whatsapp",
            )
        )
        client3 = AgentBusClient(server_url, auto_reconnect=False)
        await client3.connect()
        await client3.initialize("agent:worker-1")

        await client3.publish_outbound(
            OutboundMessage(
                channel="telegram",
                chat_id="chat1",
                content="reply to telegram",
            )
        )

        await asyncio.sleep(0.2)

        assert len(client1_messages) == 3

        topic1, payload1 = client1_messages[0]
        assert topic1 == "tg:chat1"
        assert payload1["type"] == "tg_message"
        assert payload1["content"]["text"] == "hello from telegram"

        topic2, payload2 = client1_messages[1]
        assert topic2 == "tg:chat2"
        assert payload2["type"] == "tg_message"
        assert payload2["content"]["text"] == "hello from whatsapp"

        topic3, payload3 = client1_messages[2]
        assert topic3 == "tg:chat1"
        assert payload3["type"] == "tg_reply"
        assert payload3["content"]["text"] == "reply to telegram"

        await client1.disconnect()
        await client2.disconnect()
        await client3.disconnect()

    finally:
        await server.stop_server()


@pytest.mark.asyncio
async def test_server_rejects_uninitialized_requests() -> None:
    """Server should reject non-initialize requests before handshake."""
    server = AgentBusServer(server=("localhost", 0))
    await server.start_server()

    try:
        server_url = _server_url(server)

        async with websockets.connect(server_url) as ws:
            subscribe_request = {
                "jsonrpc": "2.0",
                "method": "subscribe",
                "params": {"topic": "tg:*"},
                "id": 1,
            }
            await ws.send(json.dumps(subscribe_request))

            response = json.loads(await ws.recv())
            assert "error" in response
            assert response["error"]["code"] == -32001
            assert response["error"]["message"] == "Not initialized"

    finally:
        await server.stop_server()


@pytest.mark.asyncio
async def test_initialize_twice_fails() -> None:
    """Initialize should fail if called twice."""
    server = AgentBusServer(server=("localhost", 0))
    await server.start_server()

    try:
        server_url = _server_url(server)

        client = AgentBusClient(server_url, auto_reconnect=False)
        await client.connect()
        await client.initialize("agent:system")

        with pytest.raises(RuntimeError, match="Already initialized"):
            await client.initialize("agent:system")

        await client.disconnect()

    finally:
        await server.stop_server()


@pytest.mark.asyncio
async def test_wildcard_subscription_receives_all() -> None:
    """Wildcard subscription should receive all messages matching pattern."""
    server = AgentBusServer(server=("localhost", 0))
    await server.start_server()

    try:
        server_url = _server_url(server)

        subscriber = AgentBusClient(server_url, auto_reconnect=False)
        await subscriber.connect()
        await subscriber.initialize("agent:system")

        await subscriber.subscribe("tg:*")

        received: list[tuple[str, dict]] = []

        async def handler(topic: str, payload: dict) -> None:
            received.append((topic, payload))

        await subscriber.subscribe("tg:*", handler)

        publisher = AgentBusClient(server_url, auto_reconnect=False)
        await publisher.connect()
        await publisher.initialize("tg:publisher")

        await publisher.publish_inbound(
            InboundMessage(channel="telegram", sender_id="u1", chat_id="c1", content="msg1")
        )
        await publisher.publish_inbound(
            InboundMessage(channel="telegram", sender_id="u2", chat_id="c2", content="msg2")
        )
        await publisher.publish_inbound(
            InboundMessage(channel="whatsapp", sender_id="u3", chat_id="c3", content="msg3")
        )

        await asyncio.sleep(0.1)

        assert len(received) == 3
        assert received[0][0] == "tg:c1"
        assert received[1][0] == "tg:c2"
        assert received[2][0] == "tg:c3"

        await subscriber.disconnect()
        await publisher.disconnect()

    finally:
        await server.stop_server()


@pytest.mark.asyncio
async def test_client_rejects_subscribe_before_initialize() -> None:
    """Client should reject subscribe before initialize."""
    server = AgentBusServer(server=("localhost", 0))
    await server.start_server()

    try:
        server_url = _server_url(server)

        client = AgentBusClient(server_url, auto_reconnect=False)
        await client.connect()

        with pytest.raises(RuntimeError, match="Not initialized"):
            await client.subscribe("tg:*")

        await client.disconnect()
    finally:
        await server.stop_server()


@pytest.mark.asyncio
async def test_ping_pong() -> None:
    """Ping should return timestamp."""
    server = AgentBusServer(server=("localhost", 0))
    await server.start_server()

    try:
        server_url = _server_url(server)

        client = AgentBusClient(server_url, auto_reconnect=False)
        await client.connect()
        await client.initialize("agent:system")

        async with websockets.connect(server_url) as ws:
            init_req = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {"clientId": "agent:raw"},
                "id": 1,
            }
            await ws.send(json.dumps(init_req))
            await ws.recv()

            ping_req = {"jsonrpc": "2.0", "method": "ping", "params": {}, "id": 2}
            await ws.send(json.dumps(ping_req))

            response = json.loads(await ws.recv())
            assert "result" in response
            assert "timestamp" in response["result"]

        await client.disconnect()

    finally:
        await server.stop_server()
