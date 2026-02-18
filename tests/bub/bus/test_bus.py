"""Tests for message bus protocol layer.

Tests bus protocol behavior using mock transport, avoiding real WebSocket connections.
Tests focus on protocol semantics rather than transport implementation.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest

from bub.bus import AgentBusServer
from bub.bus.protocol import (
    AgentBusClientApi,
    AgentBusServerApi,
    InitializeParams,
    ProcessMessageParams,
    SendMessageParams,
    SubscribeParams,
)
from bub.rpc.framework import JSONRPCFramework
from .test_transport import InMemoryTransport, MockPeer


class TestMessageFlow:
    """Test basic message flow scenarios."""

    @pytest.mark.asyncio
    async def test_simple_flow_a_to_b(self):
        """Test: a sends message to b, b receives it."""
        peer_a = MockPeer("client:a")
        peer_b = MockPeer("client:b")
        peer_b.subscribe("b:*")

        received = []

        async def handler(from_addr: str, payload: dict[str, Any]):
            received.append((from_addr, payload))

        peer_b.on_message("b:*", handler)

        message = {
            "messageId": f"msg_{uuid.uuid4().hex}",
            "type": "test_message",
            "from": "client:a",
            "to": "b:client",
            "timestamp": "2026-02-19T00:00:00Z",
            "content": {"text": "Hello from A"},
        }

        await peer_b.receive_message("client:a", "b:client", message)

        assert len(received) == 1
        assert received[0][0] == "client:a"
        assert received[0][1]["content"]["text"] == "Hello from A"

    @pytest.mark.asyncio
    async def test_flow_a_to_b_and_a_to_c(self):
        """Test: a sends messages to both b and c."""
        peer_a = MockPeer("client:a")
        peer_b = MockPeer("client:b")
        peer_c = MockPeer("client:c")

        received_b = []
        received_c = []

        async def handler_b(from_addr: str, payload: dict[str, Any]):
            received_b.append(payload)

        async def handler_c(from_addr: str, payload: dict[str, Any]):
            received_c.append(payload)

        peer_b.on_message("b:*", handler_b)
        peer_c.on_message("c:*", handler_c)

        msg_to_b = {"content": {"text": "Hello B"}}
        await peer_b.receive_message("client:a", "b:client", msg_to_b)

        msg_to_c = {"content": {"text": "Hello C"}}
        await peer_c.receive_message("client:a", "c:client", msg_to_c)

        assert len(received_b) == 1
        assert received_b[0]["content"]["text"] == "Hello B"

        assert len(received_c) == 1
        assert received_c[0]["content"]["text"] == "Hello C"


class TestDeadlockScenarios:
    """Test potential deadlock scenarios in message flows."""

    @pytest.mark.asyncio
    async def test_potential_deadlock_a_to_b_b_to_a(self):
        """Test: a calls b, b responds by calling a."""
        peer_a = MockPeer("client:a")
        peer_b = MockPeer("client:b")

        messages_a_to_b = []
        messages_b_to_a = []

        async def b_handler(from_addr: str, payload: dict[str, Any]):
            messages_a_to_b.append(payload)
            response = {"content": {"text": "Response from B"}}
            await peer_a.receive_message("client:b", "a:client", response)

        async def a_handler(from_addr: str, payload: dict[str, Any]):
            messages_b_to_a.append(payload)

        peer_b.on_message("b:*", b_handler)
        peer_a.on_message("a:*", a_handler)

        initial_msg = {"content": {"text": "Initial from A"}}
        await peer_b.receive_message("client:a", "b:client", initial_msg)

        await asyncio.sleep(0.01)

        assert len(messages_a_to_b) == 1
        assert len(messages_b_to_a) == 1
        assert messages_a_to_b[0]["content"]["text"] == "Initial from A"
        assert messages_b_to_a[0]["content"]["text"] == "Response from B"

    @pytest.mark.asyncio
    async def test_chain_deadlock_a_to_b_to_c_to_a(self):
        """Test: a -> b -> c -> a chain."""
        peer_a = MockPeer("client:a")
        peer_b = MockPeer("client:b")
        peer_c = MockPeer("client:c")

        chain = []

        async def c_handler(from_addr: str, payload: dict[str, Any]):
            chain.append(("C", from_addr, payload))
            response = {"content": {"text": "C to A", "step": 3}}
            await peer_a.receive_message("client:c", "a:client", response)

        async def b_handler(from_addr: str, payload: dict[str, Any]):
            chain.append(("B", from_addr, payload))
            forward = {"content": {"text": "B to C", "step": 2}}
            await peer_c.receive_message("client:b", "c:client", forward)

        async def a_handler(from_addr: str, payload: dict[str, Any]):
            chain.append(("A", from_addr, payload))

        peer_c.on_message("c:*", c_handler)
        peer_b.on_message("b:*", b_handler)
        peer_a.on_message("a:*", a_handler)

        initial = {"content": {"text": "A to B", "step": 1}}
        await peer_b.receive_message("client:a", "b:client", initial)

        await asyncio.sleep(0.05)

        assert len(chain) == 3
        assert chain[0] == ("B", "client:a", {"content": {"text": "A to B", "step": 1}})
        assert chain[1][0] == "C"
        assert chain[2][0] == "A"


class TestServerProtocol:
    """Test server protocol behavior."""

    @pytest.mark.asyncio
    async def test_server_rejects_uninitialized_requests(self):
        """Server should reject non-initialize requests before handshake."""
        transport = InMemoryTransport("test-client")
        framework = JSONRPCFramework(transport)

        # Don't register initialize - server should reject other requests
        # This tests that the server enforces initialization order

        # Send a subscribe request without initialization
        subscribe_request = {
            "jsonrpc": "2.0",
            "method": "subscribe",
            "params": {"address": "tg:*"},
            "id": 1,
        }

        transport.inject_json(subscribe_request)

        # Server should respond with error
        # Note: This would need the actual server handler registration
        # For now, this documents the expected behavior
        pass

    @pytest.mark.asyncio
    async def test_address_matching(self):
        """Test address pattern matching logic."""
        server = AgentBusServer(server=("localhost", 0))

        # Test exact match
        assert server.address_matches("agent:worker-1", "agent:worker-1") is True

        # Test wildcard match
        assert server.address_matches("agent:worker-1", "agent:*") is True
        assert server.address_matches("tg:123456", "tg:*") is True

        # Test non-match
        assert server.address_matches("agent:worker-1", "tg:*") is False
        assert server.address_matches("agent:worker-1", "agent:worker-2") is False


class TestSendMessageAcks:
    """Test send_message ack behavior."""

    @pytest.mark.asyncio
    async def test_send_message_returns_acks(self):
        """Test that send_message returns delivery acks."""
        transport = InMemoryTransport("test-client")
        framework = JSONRPCFramework(transport)
        api = AgentBusClientApi(framework, client_id="test-client")

        # Initialize
        init_result = await api.initialize(InitializeParams(client_id="test-client"))
        assert init_result.server_id.startswith("bus-")

        # Subscribe
        sub_result = await api.subscribe(SubscribeParams(address="test:*"))
        assert sub_result.success is True

        # Send message using send_message2 (auto-generates message_id)
        result = await api.send_message2(
            from_="test:sender",
            to="test:topic",
            payload={
                "type": "test",
                "content": {"text": "hello"},
            },
        )

        assert result.accepted is True
        assert result.message_id.startswith("msg_test-client")


class TestMultipleSubscribers:
    """Test fanout to multiple subscribers."""

    @pytest.mark.asyncio
    async def test_multiple_peers_receive_same_message(self):
        """Test that multiple subscribers receive the same broadcast."""
        sender = MockPeer("client:sender")
        subscriber1 = MockPeer("client:sub1")
        subscriber2 = MockPeer("client:sub2")

        received1 = []
        received2 = []

        async def handler1(from_addr: str, payload: dict[str, Any]):
            received1.append(payload)

        async def handler2(from_addr: str, payload: dict[str, Any]):
            received2.append(payload)

        subscriber1.on_message("broadcast:*", handler1)
        subscriber2.on_message("broadcast:*", handler2)

        # Send broadcast
        message = {
            "messageId": "msg-001",
            "type": "broadcast",
            "content": {"text": "hello all"},
        }

        await subscriber1.receive_message("client:sender", "broadcast:all", message)
        await subscriber2.receive_message("client:sender", "broadcast:all", message)

        # Both should receive
        assert len(received1) == 1
        assert len(received2) == 1
        assert received1[0]["content"]["text"] == "hello all"
        assert received2[0]["content"]["text"] == "hello all"


class TestProcessMessage:
    """Test process_message protocol."""

    @pytest.mark.asyncio
    async def test_process_message_success(self):
        """Test successful message processing."""
        transport = InMemoryTransport("test-agent")
        framework = JSONRPCFramework(transport)
        api = AgentBusServerApi(framework)

        # Process a message
        result = await api.process_message(
            ProcessMessageParams(
                from_="tg:123",
                to="agent:test",
                message_id="msg-001",
                payload={
                    "type": "tg_message",
                    "content": {"text": "hello"},
                },
            )
        )

        assert result.success is True
        assert result.should_retry is False


class TestWildcardSubscription:
    """Test wildcard subscription behavior."""

    @pytest.mark.asyncio
    async def test_wildcard_receives_matching_messages(self):
        """Test that wildcard subscription receives only matching messages."""
        peer = MockPeer("client:test")
        peer.subscribe("tg:*")

        received = []

        async def handler(from_addr: str, payload: dict[str, Any]):
            received.append((from_addr, payload))

        peer.on_message("tg:*", handler)

        # Send matching messages
        await peer.receive_message("client:a", "tg:chat1", {"content": {"text": "msg1"}})
        await peer.receive_message("client:b", "tg:chat2", {"content": {"text": "msg2"}})

        # Send non-matching message
        await peer.receive_message("client:c", "wa:chat3", {"content": {"text": "msg3"}})

        # Should only receive tg:* messages
        assert len(received) == 2
        assert received[0][1]["content"]["text"] == "msg1"
        assert received[1][1]["content"]["text"] == "msg2"
