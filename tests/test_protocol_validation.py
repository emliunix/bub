"""Test JSON-RPC 2.0 WebSocket protocol validation."""

import asyncio
import json

import pytest
import websockets

from bub.channels.events import InboundMessage, OutboundMessage
from bub.channels.wsbus import AgentBusClient, AgentBusServer


@pytest.mark.asyncio
async def test_protocol_full_flow() -> None:
    """Validate full protocol flow: connect, initialize, subscribe, receive all messages."""
    server = AgentBusServer(host="localhost", port=0)
    await server.start_server()

    try:
        assert server._server is not None
        server_url = f"ws://localhost:{server._server.sockets[0].getsockname()[1]}"

        # Client 1: Connects and subscribes to all topics
        client1 = AgentBusClient(server_url)
        await client1.connect()

        # Initialize handshake
        init_result = await client1.initialize("client-1")
        assert init_result.server_id
        assert init_result.server_info.name == "bub-bus"
        assert init_result.capabilities.subscribe is True

        # Subscribe to all inbound messages
        sub1_inbound = await client1.subscribe("inbound:*")
        assert sub1_inbound.subscription_id.startswith("sub_")

        # Subscribe to all outbound messages
        sub1_outbound = await client1.subscribe("outbound:*")
        assert sub1_outbound.subscription_id.startswith("sub_")

        # Track received messages
        client1_messages: list[tuple[str, dict]] = []

        async def record_handler(topic: str, payload: dict) -> None:
            client1_messages.append((topic, payload))

        client1.on_notification("inbound:*", record_handler)
        client1.on_notification("outbound:*", record_handler)

        # Client 2: Connects and sends messages
        client2 = AgentBusClient(server_url)
        await client2.connect()
        await client2.initialize("client-2")

        # Send inbound message from channel telegram
        await client2.publish_inbound(
            InboundMessage(
                channel="telegram",
                sender_id="user1",
                chat_id="chat1",
                content="hello from telegram",
            )
        )

        # Send inbound message from channel whatsapp
        await client2.publish_inbound(
            InboundMessage(
                channel="whatsapp",
                sender_id="user2",
                chat_id="chat2",
                content="hello from whatsapp",
            )
        )

        # Send outbound message
        await client2.publish_outbound(
            OutboundMessage(
                channel="telegram",
                chat_id="chat1",
                content="reply to telegram",
            )
        )

        # Wait for messages to be delivered
        await asyncio.sleep(0.2)

        # Verify client1 received all messages
        assert len(client1_messages) == 3

        # Check first inbound (telegram)
        topic1, payload1 = client1_messages[0]
        assert topic1 == "inbound:chat1"
        assert payload1["content"] == "hello from telegram"

        # Check second inbound (whatsapp)
        topic2, payload2 = client1_messages[1]
        assert topic2 == "inbound:chat2"
        assert payload2["content"] == "hello from whatsapp"

        # Check outbound
        topic3, payload3 = client1_messages[2]
        assert topic3 == "outbound:chat1"
        assert payload3["content"] == "reply to telegram"

        await client1.disconnect()
        await client2.disconnect()

    finally:
        await server.stop_server()


@pytest.mark.asyncio
async def test_server_rejects_uninitialized_requests() -> None:
    """Server should reject non-initialize requests before handshake."""
    server = AgentBusServer(host="localhost", port=0)
    await server.start_server()

    try:
        assert server._server is not None
        port = server._server.sockets[0].getsockname()[1]
        server_url = f"ws://localhost:{port}"

        # Connect directly with raw websocket
        async with websockets.connect(server_url) as ws:
            # Try to subscribe before initialize
            subscribe_request = {
                "jsonrpc": "2.0",
                "method": "subscribe",
                "params": {"topic": "inbound:*"},
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
    server = AgentBusServer(host="localhost", port=0)
    await server.start_server()

    try:
        assert server._server is not None
        port = server._server.sockets[0].getsockname()[1]
        server_url = f"ws://localhost:{port}"

        client = AgentBusClient(server_url)
        await client.connect()
        await client.initialize("client-1")

        # Try to initialize again - should fail on server side
        with pytest.raises(RuntimeError, match="Already initialized"):
            await client.initialize("client-1")

        await client.disconnect()

    finally:
        await server.stop_server()


@pytest.mark.asyncio
async def test_wildcard_subscription_receives_all() -> None:
    """Wildcard subscription should receive all messages matching pattern."""
    server = AgentBusServer(host="localhost", port=0)
    await server.start_server()

    try:
        assert server._server is not None
        port = server._server.sockets[0].getsockname()[1]
        server_url = f"ws://localhost:{port}"

        subscriber = AgentBusClient(server_url)
        await subscriber.connect()
        await subscriber.initialize("subscriber")

        # Subscribe to wildcard
        await subscriber.subscribe("inbound:*")

        received: list[tuple[str, dict]] = []

        async def handler(topic: str, payload: dict) -> None:
            received.append((topic, payload))

        subscriber.on_notification("inbound:*", handler)

        # Publisher sends messages to different chat IDs
        publisher = AgentBusClient(server_url)
        await publisher.connect()
        await publisher.initialize("publisher")

        # Send to multiple channels/chats
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

        # Verify all messages received
        assert len(received) == 3
        assert received[0][0] == "inbound:c1"
        assert received[1][0] == "inbound:c2"
        assert received[2][0] == "inbound:c3"

        await subscriber.disconnect()
        await publisher.disconnect()

    finally:
        await server.stop_server()


@pytest.mark.asyncio
async def test_client_rejects_subscribe_before_initialize() -> None:
    """Client should reject subscribe before initialize."""
    server = AgentBusServer(host="localhost", port=0)
    await server.start_server()

    try:
        assert server._server is not None
        port = server._server.sockets[0].getsockname()[1]
        server_url = f"ws://localhost:{port}"

        client = AgentBusClient(server_url)
        await client.connect()

        with pytest.raises(RuntimeError, match="Not initialized"):
            await client.subscribe("inbound:*")

        await client.disconnect()
    finally:
        await server.stop_server()


@pytest.mark.asyncio
async def test_ping_pong() -> None:
    """Ping should return timestamp."""
    server = AgentBusServer(host="localhost", port=0)
    await server.start_server()

    try:
        assert server._server is not None
        port = server._server.sockets[0].getsockname()[1]
        server_url = f"ws://localhost:{port}"

        client = AgentBusClient(server_url)
        await client.connect()
        await client.initialize("pinger")

        # Connect with raw websocket to send ping
        async with websockets.connect(server_url) as ws:
            init_req = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {"clientId": "raw-client"},
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
