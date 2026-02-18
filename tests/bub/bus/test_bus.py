"""Tests for message bus with protocol-based architecture.

Tests message flow scenarios including deadlock detection and basic routing.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest

from bub.bus import AgentBusServer
from .test_transport import MockPeer


class TestMessageFlow:
    """Test basic message flow scenarios."""

    @pytest.mark.asyncio
    async def test_simple_flow_a_to_b(self):
        """Test: a sends message to b, b receives it.

        Scenario:
        - Client A sends message to address "b:client"
        - Client B is subscribed to "b:*"
        - B receives the message
        """
        server = AgentBusServer(host="localhost", port=0)

        # Create mock peers
        peer_a = MockPeer("client:a")
        peer_b = MockPeer("client:b")
        peer_b.subscribe("b:*")

        received = []

        async def handler(from_addr: str, payload: dict[str, Any]):
            received.append((from_addr, payload))

        peer_b.on_message("b:*", handler)

        # Simulate a sending to b
        message = {
            "messageId": f"msg_{uuid.uuid4().hex}",
            "type": "test_message",
            "from": "client:a",
            "to": "b:client",
            "timestamp": "2026-02-19T00:00:00Z",
            "content": {"text": "Hello from A"},
        }

        # Dispatch message
        await peer_b.receive_message("client:a", "b:client", message)

        # Verify B received it
        assert len(received) == 1
        assert received[0][0] == "client:a"
        assert received[0][1]["content"]["text"] == "Hello from A"

    @pytest.mark.asyncio
    async def test_flow_a_to_b_and_a_to_c(self):
        """Test: a sends messages to both b and c.

        Scenario:
        - Client A sends message to B
        - Client A sends message to C
        - Both B and C receive their respective messages
        """
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

        # A sends to B
        msg_to_b = {"content": {"text": "Hello B"}}
        await peer_b.receive_message("client:a", "b:client", msg_to_b)

        # A sends to C
        msg_to_c = {"content": {"text": "Hello C"}}
        await peer_c.receive_message("client:a", "c:client", msg_to_c)

        # Verify both received
        assert len(received_b) == 1
        assert received_b[0]["content"]["text"] == "Hello B"

        assert len(received_c) == 1
        assert received_c[0]["content"]["text"] == "Hello C"


class TestDeadlockScenarios:
    """Test potential deadlock scenarios in message flows."""

    @pytest.mark.asyncio
    async def test_potential_deadlock_a_to_b_b_to_a(self):
        """Test: a calls b, b responds by calling a.

        This tests if there's potential for deadlock when:
        - A sends message to B
        - B processes and tries to send response back to A
        - Both are waiting for each other

        With async/await and proper task scheduling, this should NOT deadlock
        as each message processing is independent.
        """
        peer_a = MockPeer("client:a")
        peer_b = MockPeer("client:b")

        # Track message flow
        messages_a_to_b = []
        messages_b_to_a = []

        async def b_handler(from_addr: str, payload: dict[str, Any]):
            """B receives message from A and responds back."""
            messages_a_to_b.append(payload)

            # B sends response back to A
            response = {"content": {"text": "Response from B"}}
            await peer_a.receive_message("client:b", "a:client", response)

        async def a_handler(from_addr: str, payload: dict[str, Any]):
            """A receives response from B."""
            messages_b_to_a.append(payload)

        peer_b.on_message("b:*", b_handler)
        peer_a.on_message("a:*", a_handler)

        # A sends to B
        initial_msg = {"content": {"text": "Initial from A"}}
        await peer_b.receive_message("client:a", "b:client", initial_msg)

        # Give async tasks time to complete
        await asyncio.sleep(0.01)

        # Verify the full round-trip
        assert len(messages_a_to_b) == 1, "B should have received message from A"
        assert len(messages_b_to_a) == 1, "A should have received response from B"
        assert messages_a_to_b[0]["content"]["text"] == "Initial from A"
        assert messages_b_to_a[0]["content"]["text"] == "Response from B"

    @pytest.mark.asyncio
    async def test_chain_deadlock_a_to_b_to_c_to_a(self):
        """Test: a -> b -> c -> a chain.

        This creates a cycle:
        - A sends to B
        - B sends to C
        - C sends to A

        This tests if the system can handle message cycles without deadlock.
        """
        peer_a = MockPeer("client:a")
        peer_b = MockPeer("client:b")
        peer_c = MockPeer("client:c")

        # Track the chain
        chain = []

        async def c_handler(from_addr: str, payload: dict[str, Any]):
            """C receives from B and sends to A (completing cycle)."""
            chain.append(("C", from_addr, payload))
            response = {"content": {"text": "C to A", "step": 3}}
            await peer_a.receive_message("client:c", "a:client", response)

        async def b_handler(from_addr: str, payload: dict[str, Any]):
            """B receives from A and sends to C."""
            chain.append(("B", from_addr, payload))
            forward = {"content": {"text": "B to C", "step": 2}}
            await peer_c.receive_message("client:b", "c:client", forward)

        async def a_handler(from_addr: str, payload: dict[str, Any]):
            """A receives from C (cycle complete)."""
            chain.append(("A", from_addr, payload))

        peer_c.on_message("c:*", c_handler)
        peer_b.on_message("b:*", b_handler)
        peer_a.on_message("a:*", a_handler)

        # Start the chain: A sends to B
        initial = {"content": {"text": "A to B", "step": 1}}
        await peer_b.receive_message("client:a", "b:client", initial)

        # Give async tasks time to complete
        await asyncio.sleep(0.05)

        # Verify the full chain executed
        assert len(chain) == 3, f"Expected 3 messages in chain, got {len(chain)}: {chain}"

        # Verify order: B receives from A, C receives from B, A receives from C
        assert chain[0] == ("B", "client:a", {"content": {"text": "A to B", "step": 1}})
        assert chain[1][0] == "C"
        assert chain[2][0] == "A"


class TestServerIntegration:
    """Integration tests with actual AgentBusServer."""

    @pytest.mark.asyncio
    async def test_server_start_stop(self):
        """Test server can start and stop cleanly."""
        server = AgentBusServer(host="localhost", port=0)

        # Note: We don't actually start the server to avoid port binding in tests
        # This is a placeholder for when we have the mock transport integrated
        assert server.server_id.startswith("bus-")
        assert server.url.startswith("ws://")

    @pytest.mark.asyncio
    async def test_address_matching(self):
        """Test address pattern matching logic."""
        server = AgentBusServer(host="localhost", port=0)

        # Test exact match
        assert server.address_matches("agent:worker-1", "agent:worker-1") is True

        # Test wildcard match
        assert server.address_matches("agent:worker-1", "agent:*") is True
        assert server.address_matches("tg:123456", "tg:*") is True

        # Test non-match
        assert server.address_matches("agent:worker-1", "tg:*") is False
        assert server.address_matches("agent:worker-1", "agent:worker-2") is False
