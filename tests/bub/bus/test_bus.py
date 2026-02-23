"""Tests for message bus protocol layer.

Tests bus protocol behavior using mock transport, avoiding real WebSocket connections.
Tests focus on protocol semantics rather than transport implementation.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any, cast

import pytest

from bub.bus import AgentBusServer
from bub.bus.bus import AgentBusClient
from bub.bus.log import ActivityLogWriter
from bub.bus.protocol import (
    AgentBusClientApi,
    AgentBusServerApi,
    InitializeParams,
    ProcessMessageParams,
    ProcessMessageResult,
    SubscribeParams,
)
from bub.rpc.framework import JSONRPCFramework
from .test_transport import MockListener, TestClientCallbacks


@pytest.fixture
def make_test_payload():
    """Factory fixture for creating test message payloads."""

    def _make(content: dict[str, Any] | None = None, from_addr: str = "test:sender") -> dict[str, Any]:
        base: dict[str, Any] = {
            "messageId": f"msg_{uuid.uuid4().hex[:8]}",
            "type": "tg_message",
            "from": from_addr,
            "timestamp": "2026-02-19T00:00:00Z",
        }
        if content:
            base["content"] = content
        return base

    return _make


class TestMessageFlow:
    """Test basic message flow scenarios."""

    @pytest.mark.asyncio
    async def test_simple_flow_a_to_b(self, make_test_payload):
        """Test: a sends message to b, b receives it."""
        listener = MockListener()
        server = AgentBusServer(
            listener, ActivityLogWriter(Path("/tmp/test_bus_" + str(uuid.uuid4())[:8] + ".sqlite3"))
        )
        server_task = asyncio.create_task(server.start_server())

        try:
            await asyncio.sleep(0.05)

            transport_a = await listener.connect_client()
            transport_b = await listener.connect_client()

            callbacks_a = TestClientCallbacks()
            callbacks_b = TestClientCallbacks()

            client_a = AgentBusClient(transport_a, callbacks_a)
            client_b = AgentBusClient(transport_b, callbacks_b)

            await client_a._start()
            await client_b._start()

            await client_a.initialize("client:a")
            await client_b.initialize("client:b")

            await client_b.subscribe("agent:b")

            payload = make_test_payload({"text": "Hello from A"})
            result = await client_a.send_message(to="agent:b", payload=payload)

            await asyncio.sleep(0.01)
            assert len(callbacks_b.received) == 1
            assert callbacks_b.received[0].from_ == client_a._client_id
            payload_dict = cast(dict[str, Any], callbacks_b.received[0].payload)
            assert payload_dict["content"]["text"] == "Hello from A"

        finally:
            await server.stop_server()
            await listener.stop()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_flow_a_to_b_and_a_to_c(self, make_test_payload):
        """Test: a sends messages to both b and c."""
        listener = MockListener()
        server = AgentBusServer(
            listener, ActivityLogWriter(Path("/tmp/test_bus_" + str(uuid.uuid4())[:8] + ".sqlite3"))
        )
        server_task = asyncio.create_task(server.start_server())

        try:
            await asyncio.sleep(0.05)

            transport_a = await listener.connect_client()
            transport_b = await listener.connect_client()
            transport_c = await listener.connect_client()

            callbacks_a = TestClientCallbacks()
            callbacks_b = TestClientCallbacks()
            callbacks_c = TestClientCallbacks()

            client_a = AgentBusClient(transport_a, callbacks_a)
            client_b = AgentBusClient(transport_b, callbacks_b)
            client_c = AgentBusClient(transport_c, callbacks_c)

            await client_a._start()
            await client_b._start()
            await client_c._start()

            await client_a.initialize("client:a")
            await client_b.initialize("client:b")
            await client_c.initialize("client:c")

            await client_b.subscribe("agent:b")
            await client_c.subscribe("agent:c")

            payload_b = make_test_payload({"text": "Hello B"})
            await client_a.send_message(to="agent:b", payload=payload_b)

            payload_c = make_test_payload({"text": "Hello C"})
            await client_a.send_message(to="agent:c", payload=payload_c)

            await asyncio.sleep(0.01)

            assert len(callbacks_b.received) == 1
            payload_dict_b = cast(dict[str, Any], callbacks_b.received[0].payload)
            assert payload_dict_b["content"]["text"] == "Hello B"

            assert len(callbacks_c.received) == 1
            payload_dict_c = cast(dict[str, Any], callbacks_c.received[0].payload)
            assert payload_dict_c["content"]["text"] == "Hello C"

        finally:
            await server.stop_server()
            await listener.stop()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass


class TestDeadlockScenarios:
    """Test potential deadlock scenarios in message flows."""

    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self):
        """Test that request handlers run concurrently (no deadlock when responding from handler)."""
        from .test_transport import PairedTransport

        paired = PairedTransport()
        server_transport = paired.a
        client_transport = paired.b

        server_framework = JSONRPCFramework(server_transport)
        client_framework = JSONRPCFramework(client_transport)

        response_received = asyncio.Event()

        # Server handler that sends a request back (would deadlock without concurrent handling)
        async def server_handler(params: dict[str, object]) -> dict[str, object]:
            # Send a message back to the client from within the handler
            client_api = AgentBusClientApi(client_framework, client_id="test-client")
            await client_api.send_message2(
                from_="server:handler",
                to="client:test",
                payload={"type": "response", "content": {"text": "response from handler"}},
            )
            return {
                "success": True,
                "message": "processed",
                "shouldRetry": False,
                "retrySeconds": 0,
                "payload": {},
            }

        async def client_handler(params: dict[str, object]) -> dict[str, object]:
            response_received.set()
            return {
                "success": True,
                "message": "received",
                "shouldRetry": False,
                "retrySeconds": 0,
                "payload": {},
            }

        server_framework.register_method("processMessage", server_handler)
        client_framework.register_method("processMessage", client_handler)

        server_task = asyncio.create_task(server_framework.run())
        client_task = asyncio.create_task(client_framework.run())

        try:
            await asyncio.sleep(0.01)

            server_api = AgentBusServerApi(server_framework)

            # Send message - server handler will try to send back
            await server_api.process_message(
                ProcessMessageParams(  # type: ignore[call-arg]
                    from_="client:test",
                    to="server:handler",
                    message_id="msg-001",
                    payload={"type": "test"},
                )
            )

            # Wait for the response (would timeout if deadlocked)
            await asyncio.wait_for(response_received.wait(), timeout=2.0)

            assert response_received.is_set()

        finally:
            await server_framework.stop()
            await client_framework.stop()
            try:
                await client_task
            except asyncio.CancelledError:
                pass
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_potential_deadlock_a_to_b_b_to_a(self, make_test_payload):
        """Test: a calls b, b responds by calling a."""
        listener = MockListener()
        server = AgentBusServer(
            listener, ActivityLogWriter(Path("/tmp/test_bus_" + str(uuid.uuid4())[:8] + ".sqlite3"))
        )
        server_task = asyncio.create_task(server.start_server())

        try:
            await asyncio.sleep(0.05)

            transport_a = await listener.connect_client()
            transport_b = await listener.connect_client()

            callbacks_a = TestClientCallbacks()
            callbacks_b = TestClientCallbacks()

            client_a = AgentBusClient(transport_a, callbacks_a)
            client_b = AgentBusClient(transport_b, callbacks_b)

            await client_a._start()
            await client_b._start()

            await client_a.initialize("client:a")
            await client_b.initialize("client:b")

            await client_a.subscribe("client:a")
            await client_b.subscribe("agent:b")

            # Set up B's response to send back to A
            original_process_message = callbacks_b.process_message

            async def b_handler_with_response(params: ProcessMessageParams) -> ProcessMessageResult:
                # Send response back to A
                await client_b.send_message(to="client:a", payload=make_test_payload({"text": "Response from B"}))
                return await original_process_message(params)

            callbacks_b.process_message = b_handler_with_response

            payload = make_test_payload({"text": "Initial from A"})
            await client_a.send_message(to="agent:b", payload=payload)

            await asyncio.sleep(0.05)

            # A should receive B's response
            assert len(callbacks_a.received) == 1
            payload_dict = cast(dict[str, Any], callbacks_a.received[0].payload)
            assert payload_dict["content"]["text"] == "Response from B"

            # B should receive A's initial message
            assert len(callbacks_b.received) == 1
            payload_dict_b = cast(dict[str, Any], callbacks_b.received[0].payload)
            assert payload_dict_b["content"]["text"] == "Initial from A"

        finally:
            await server.stop_server()
            await listener.stop()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_chain_deadlock_a_to_b_to_c_to_a(self, make_test_payload):
        """Test: a -> b -> c -> a chain."""
        listener = MockListener()
        server = AgentBusServer(
            listener, ActivityLogWriter(Path("/tmp/test_bus_" + str(uuid.uuid4())[:8] + ".sqlite3"))
        )
        server_task = asyncio.create_task(server.start_server())

        try:
            await asyncio.sleep(0.05)

            transport_a = await listener.connect_client()
            transport_b = await listener.connect_client()
            transport_c = await listener.connect_client()

            callbacks_a = TestClientCallbacks()
            callbacks_b = TestClientCallbacks()
            callbacks_c = TestClientCallbacks()

            client_a = AgentBusClient(transport_a, callbacks_a)
            client_b = AgentBusClient(transport_b, callbacks_b)
            client_c = AgentBusClient(transport_c, callbacks_c)

            await client_a._start()
            await client_b._start()
            await client_c._start()

            await client_a.initialize("client:a")
            await client_b.initialize("client:b")
            await client_c.initialize("client:c")

            await client_a.subscribe("client:a")
            await client_b.subscribe("agent:b")
            await client_c.subscribe("agent:c")

            # Track chain
            chain: list[tuple[str, str, dict[str, Any]]] = []

            # Set up C to send back to A
            original_c_process = callbacks_c.process_message

            async def c_handler(params: ProcessMessageParams) -> ProcessMessageResult:
                chain.append(("C", params.from_, params.payload))
                await client_c.send_message(to="client:a", payload=make_test_payload({"text": "C to A", "step": 3}))
                return await original_c_process(params)

            callbacks_c.process_message = c_handler

            # Set up B to forward to C
            original_b_process = callbacks_b.process_message

            async def b_handler(params: ProcessMessageParams) -> ProcessMessageResult:
                chain.append(("B", params.from_, params.payload))
                await client_b.send_message(to="agent:c", payload=make_test_payload({"text": "B to C", "step": 2}))
                return await original_b_process(params)

            callbacks_b.process_message = b_handler

            # Set up A to receive from C
            original_a_process = callbacks_a.process_message

            async def a_handler(params: ProcessMessageParams) -> ProcessMessageResult:
                chain.append(("A", params.from_, params.payload))
                return await original_a_process(params)

            callbacks_a.process_message = a_handler

            # Start chain
            payload = make_test_payload({"text": "A to B", "step": 1})
            await client_a.send_message(to="agent:b", payload=payload)

            await asyncio.sleep(0.1)

            # Verify chain
            assert len(chain) == 3
            assert chain[0][0] == "B"
            payload_dict_b = cast(dict[str, Any], chain[0][2])
            assert payload_dict_b["content"]["text"] == "A to B"
            assert chain[1][0] == "C"
            assert chain[2][0] == "A"

        finally:
            await server.stop_server()
            await listener.stop()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass


class TestServerProtocol:
    """Test server protocol behavior."""

    @pytest.mark.asyncio
    async def test_address_matching(self):
        """Test address pattern matching logic."""
        listener = MockListener()
        server = AgentBusServer(listener, ActivityLogWriter(Path("/tmp/test_bus_match.sqlite3")))

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
        """Test that send_message returns delivery acks using paired transport."""
        from .test_transport import PairedTransport

        paired = PairedTransport()
        client_transport = paired.a
        server_transport = paired.b

        # Set up server side
        server_framework = JSONRPCFramework(server_transport)
        client_framework = JSONRPCFramework(client_transport)

        # Register server handlers
        async def handle_initialize(params: dict[str, object]) -> dict[str, object]:
            return {
                "serverId": "bus-test",
                "serverInfo": {"name": "bub-bus", "version": "1.0.0"},
                "capabilities": {"subscribe": True, "processMessage": True, "addresses": []},
            }

        async def handle_subscribe(params: dict[str, object]) -> dict[str, object]:
            return {"success": True, "subscriptionId": "sub-001"}

        async def handle_send_message(params: dict[str, object]) -> dict[str, object]:
            return {
                "accepted": True,
                "messageId": params.get("messageId", "unknown"),
                "acks": [{"success": True, "message": "Delivered", "payload": {}}],
            }

        server_framework.register_method("initialize", handle_initialize)
        server_framework.register_method("subscribe", handle_subscribe)
        server_framework.register_method("sendMessage", handle_send_message)

        # Client side
        api = AgentBusClientApi(client_framework, client_id="test-client")

        # Start both frameworks concurrently
        server_task = asyncio.create_task(server_framework.run())
        client_task = asyncio.create_task(client_framework.run())

        try:
            # Wait a bit for frameworks to start
            await asyncio.sleep(0.01)

            # Initialize
            init_result = await api.initialize(InitializeParams(client_id="test-client"))
            assert init_result.server_id == "bus-test"

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

        finally:
            await client_framework.stop()
            await server_framework.stop()
            try:
                await client_task
            except asyncio.CancelledError:
                pass
            try:
                await server_task
            except asyncio.CancelledError:
                pass


class TestMultipleSubscribers:
    """Test fanout to multiple subscribers."""

    @pytest.mark.asyncio
    async def test_multiple_peers_receive_same_message(self, make_test_payload):
        """Test that multiple subscribers receive the same broadcast."""
        listener = MockListener()
        server = AgentBusServer(
            listener, ActivityLogWriter(Path("/tmp/test_bus_" + str(uuid.uuid4())[:8] + ".sqlite3"))
        )
        server_task = asyncio.create_task(server.start_server())

        try:
            await asyncio.sleep(0.05)

            transport_sender = await listener.connect_client()
            transport_sub1 = await listener.connect_client()
            transport_sub2 = await listener.connect_client()

            callbacks_sender = TestClientCallbacks()
            callbacks_sub1 = TestClientCallbacks()
            callbacks_sub2 = TestClientCallbacks()

            client_sender = AgentBusClient(transport_sender, callbacks_sender)
            client_sub1 = AgentBusClient(transport_sub1, callbacks_sub1)
            client_sub2 = AgentBusClient(transport_sub2, callbacks_sub2)

            await client_sender._start()
            await client_sub1._start()
            await client_sub2._start()

            await client_sender.initialize("client:sender")
            await client_sub1.initialize("client:sub1")
            await client_sub2.initialize("client:sub2")

            # Subscribe to the same pattern
            await client_sub1.subscribe("broadcast:*")
            await client_sub2.subscribe("broadcast:*")

            # Send broadcast
            payload = make_test_payload({"text": "hello all"})
            await client_sender.send_message(to="broadcast:all", payload=payload)

            await asyncio.sleep(0.05)

            # Both should receive
            assert len(callbacks_sub1.received) == 1
            assert len(callbacks_sub2.received) == 1
            payload_dict_1 = cast(dict[str, Any], callbacks_sub1.received[0].payload)
            payload_dict_2 = cast(dict[str, Any], callbacks_sub2.received[0].payload)
            assert payload_dict_1["content"]["text"] == "hello all"
            assert payload_dict_2["content"]["text"] == "hello all"

        finally:
            await server.stop_server()
            await listener.stop()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass


class TestProcessMessage:
    """Test process_message protocol."""

    @pytest.mark.asyncio
    async def test_process_message_success(self):
        """Test successful message processing using paired transport."""
        from .test_transport import PairedTransport

        paired = PairedTransport()
        server_transport = paired.a
        client_transport = paired.b

        # Set up server side (bus calling client)
        client_framework = JSONRPCFramework(client_transport)
        server_framework = JSONRPCFramework(server_transport)

        # Register client-side handler for processMessage
        async def handle_process_message(params: dict[str, object]) -> dict[str, object]:
            return {
                "success": True,
                "message": "Processed",
                "shouldRetry": False,
                "retrySeconds": 0,
                "payload": {"message": "Processed"},
            }

        client_framework.register_method("processMessage", handle_process_message)

        # Start both frameworks concurrently
        server_task = asyncio.create_task(server_framework.run())
        client_task = asyncio.create_task(client_framework.run())

        try:
            # Wait a bit for frameworks to start
            await asyncio.sleep(0.01)

            # Server side (bus)
            api = AgentBusServerApi(server_framework)

            # Process a message
            result = await api.process_message(
                ProcessMessageParams(  # type: ignore[call-arg]
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

        finally:
            await server_framework.stop()
            await client_framework.stop()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
            try:
                await client_task
            except asyncio.CancelledError:
                pass


class TestWildcardSubscription:
    """Test wildcard subscription behavior."""

    @pytest.mark.asyncio
    async def test_wildcard_receives_matching_messages(self, make_test_payload):
        """Test that wildcard subscription receives only matching messages."""
        listener = MockListener()
        server = AgentBusServer(
            listener, ActivityLogWriter(Path("/tmp/test_bus_" + str(uuid.uuid4())[:8] + ".sqlite3"))
        )
        server_task = asyncio.create_task(server.start_server())

        try:
            await asyncio.sleep(0.05)

            transport_a = await listener.connect_client()
            transport_b = await listener.connect_client()
            transport_c = await listener.connect_client()

            callbacks_a = TestClientCallbacks()
            callbacks_b = TestClientCallbacks()
            callbacks_c = TestClientCallbacks()

            client_a = AgentBusClient(transport_a, callbacks_a)
            client_b = AgentBusClient(transport_b, callbacks_b)
            client_c = AgentBusClient(transport_c, callbacks_c)

            await client_a._start()
            await client_b._start()
            await client_c._start()

            await client_a.initialize("client:a")
            await client_b.initialize("client:b")
            await client_c.initialize("client:c")

            # Subscribe to wildcard pattern
            await client_b.subscribe("tg:*")

            # Send matching messages
            payload1 = make_test_payload({"text": "msg1"})
            await client_a.send_message(to="tg:chat1", payload=payload1)

            payload2 = make_test_payload({"text": "msg2"})
            await client_a.send_message(to="tg:chat2", payload=payload2)

            # Send non-matching message
            payload3 = make_test_payload({"text": "msg3"})
            await client_c.send_message(to="wa:chat3", payload=payload3)

            await asyncio.sleep(0.05)

            # Should only receive tg:* messages (2 from A)
            assert len(callbacks_b.received) == 2
            payload_dict_0 = cast(dict[str, Any], callbacks_b.received[0].payload)
            payload_dict_1 = cast(dict[str, Any], callbacks_b.received[1].payload)
            assert payload_dict_0["content"]["text"] == "msg1"
            assert payload_dict_1["content"]["text"] == "msg2"

        finally:
            await server.stop_server()
            await listener.stop()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
