"""End-to-end test with mock Telegram messages.

This test uses PairedTransport to simulate the bus without real WebSocket connections.
Tests the complete flow: Telegram message -> bus -> agent -> response.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from bub.bus.protocol import (
    AgentBusClientApi,
    AgentBusServerApi,
    InitializeParams,
    ProcessMessageParams,
    SubscribeParams,
)
from bub.rpc.framework import JSONRPCFramework
from bub.rpc.types import Transport


class PairedTransport:
    """Creates two connected transports for testing."""

    def __init__(self):
        self._a_to_b: asyncio.Queue[str] = asyncio.Queue()
        self._b_to_a: asyncio.Queue[str] = asyncio.Queue()
        self.a = self._PairedTransportImpl("A", self._b_to_a, self._a_to_b)
        self.b = self._PairedTransportImpl("B", self._a_to_b, self._b_to_a)

    class _PairedTransportImpl(Transport):
        def __init__(self, name: str, recv_queue: asyncio.Queue[str], send_queue: asyncio.Queue[str]):
            self._name = name
            self._recv_queue = recv_queue
            self._send_queue = send_queue
            self._closed = False

        @property
        def name(self) -> str:
            return self._name

        async def send_message(self, message: str) -> None:
            if self._closed:
                raise RuntimeError("Transport closed")
            await self._send_queue.put(message)

        async def receive_message(self) -> str:
            if self._closed:
                raise RuntimeError("Transport closed")
            return await self._recv_queue.get()

        def close(self) -> None:
            self._closed = True


import pytest


@pytest.mark.asyncio
async def test_telegram_flow():
    """Test Telegram message flow with mocks."""
    print("=" * 70)
    print("E2E TEST: Telegram Message Flow")
    print("=" * 70)
    print()

    # Setup: Create paired transports
    # Server listens on 'a', client connects on 'b'
    paired = PairedTransport()

    # Server side
    server_framework = JSONRPCFramework(paired.a)
    server_api = AgentBusServerApi(server_framework)

    # Client side (simulates both Telegram bridge and Agent)
    client_framework = JSONRPCFramework(paired.b)
    client_api = AgentBusClientApi(client_framework, client_id="test-client")

    # Track received messages
    received_messages: list[dict] = []
    response_event = asyncio.Event()

    # Server handlers
    async def handle_initialize(params: dict[str, Any]) -> dict[str, Any]:
        return {
            "serverId": "bus-test",
            "serverInfo": {"name": "bub-bus", "version": "1.0.0"},
            "capabilities": {
                "subscribe": True,
                "processMessage": True,
                "addresses": ["tg:*", "agent:*", "system:*"],
            },
        }

    async def handle_subscribe(params: dict[str, Any]) -> dict[str, Any]:
        return {"success": True, "subscriptionId": f"sub_{uuid.uuid4().hex[:8]}"}

    async def handle_send_message(params: dict[str, Any]) -> dict[str, Any]:
        """Handle sendMessage - route to appropriate handler."""
        to = params.get("to", "")
        payload = params.get("payload", {})
        from_addr = params.get("from", "")
        message_id = params.get("messageId", "unknown")

        print(f"  Server: received sendMessage to={to}, type={payload.get('type')}")

        acks = []

        if to == "system:spawn":
            # Handle spawn request
            content = payload.get("content", {})
            chat_id = content.get("chat_id", "")
            agent_id = f"agent:worker-{chat_id[:8]}"

            # Create spawn result
            spawn_result = {
                "success": True,
                "client_id": agent_id,
                "status": "running",
            }

            # Send spawn_result back via processMessage
            spawn_payload = {
                "messageId": f"spawn_result_{uuid.uuid4().hex[:8]}",
                "type": "spawn_result",
                "from": "agent:system",
                "timestamp": datetime.now(UTC).isoformat(),
                "content": spawn_result,
            }

            try:
                result = await server_api.process_message(
                    ProcessMessageParams(
                        from_="agent:system",
                        to=from_addr,
                        message_id=spawn_payload["messageId"],
                        payload=spawn_payload,
                    )
                )
                acks.append({"success": result.success, "message": "Spawned", "payload": {}})
            except Exception as e:
                print(f"  Server: error sending spawn result: {e}")
                acks.append({"success": False, "message": str(e), "payload": {}})

        elif to.startswith("agent:"):
            # Simulate agent processing and responding
            content = payload.get("content", {})
            text = content.get("text", "")

            # Create reply
            reply_payload = {
                "messageId": f"reply_{uuid.uuid4().hex[:8]}",
                "type": "tg_reply",
                "from": to,
                "timestamp": datetime.now(UTC).isoformat(),
                "content": {
                    "text": f"Echo: {text}",
                    "channel": "telegram",
                },
            }

            # Send reply back to sender (Telegram bridge)
            try:
                result = await server_api.process_message(
                    ProcessMessageParams(
                        from_=to,
                        to=from_addr,
                        message_id=reply_payload["messageId"],
                        payload=reply_payload,
                    )
                )
                acks.append({"success": result.success, "message": "Replied", "payload": {}})
            except Exception as e:
                print(f"  Server: error sending reply: {e}")
                acks.append({"success": False, "message": str(e), "payload": {}})

        else:
            acks.append({"success": True, "message": "Received", "payload": {}})

        return {
            "accepted": True,
            "messageId": message_id,
            "acks": acks,
        }

    server_framework.register_method("initialize", handle_initialize)
    server_framework.register_method("subscribe", handle_subscribe)
    server_framework.register_method("sendMessage", handle_send_message)

    # Client handlers (to receive processMessage calls)
    async def handle_process_message(params: dict[str, Any]) -> dict[str, Any]:
        """Handle processMessage from server."""
        payload = params.get("payload", {})
        msg_type = payload.get("type", "")

        print(f"  Client: received processMessage type={msg_type}")
        received_messages.append(payload)
        response_event.set()

        return {
            "success": True,
            "message": "Received",
            "shouldRetry": False,
            "retrySeconds": 0,
            "payload": {},
        }

    client_framework.register_method("processMessage", handle_process_message)

    # Start frameworks
    server_task = asyncio.create_task(server_framework.run())
    client_task = asyncio.create_task(client_framework.run())

    try:
        await asyncio.sleep(0.1)

        # Step 1: Client initializes
        print("Step 1: Initialize connection...")
        result = await client_api.initialize(InitializeParams(client_id="telegram-bridge"))
        assert result.server_id == "bus-test"
        print("✓ Connected to bus")

        # Step 2: Subscribe to tg:*
        print("Step 2: Subscribe to tg:*...")
        result = await client_api.subscribe(SubscribeParams(address="tg:*"))
        assert result.success is True
        print("✓ Subscribed")

        # Step 3: Send spawn request
        print("Step 3: Send spawn_request...")
        chat_id = "436026689"
        spawn_payload = {
            "messageId": f"spawn_{uuid.uuid4().hex[:8]}",
            "type": "spawn_request",
            "from": f"tg:{chat_id}",
            "timestamp": datetime.now(UTC).isoformat(),
            "content": {
                "chat_id": chat_id,
                "channel": "telegram",
                "channel_type": "telegram",
            },
        }

        response_event.clear()
        result = await client_api.send_message2(
            from_=f"tg:{chat_id}",
            to="system:spawn",
            payload=spawn_payload,
        )
        print(f"✓ Spawn request sent (accepted={result.accepted})")

        # Wait for spawn result
        print("Step 4: Wait for spawn_result...")
        try:
            await asyncio.wait_for(response_event.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            print("❌ Timeout waiting for spawn result")
            return False

        # Check spawn result
        if not received_messages:
            print("❌ No messages received")
            return False

        msg = received_messages.pop(0)
        if msg.get("type") != "spawn_result":
            print(f"❌ Expected spawn_result, got {msg.get('type')}")
            return False

        agent_id = msg.get("content", {}).get("client_id")
        print(f"✓ Agent spawned: {agent_id}")

        # Step 5: Send tg_message
        print("Step 5: Send tg_message to agent...")
        test_message = "Hello, this is a test!"
        message_payload = {
            "messageId": f"msg_{uuid.uuid4().hex}",
            "type": "tg_message",
            "from": f"tg:{chat_id}",
            "timestamp": datetime.now(UTC).isoformat(),
            "content": {
                "text": test_message,
                "senderId": chat_id,
                "channel": "telegram",
            },
        }

        response_event.clear()
        result = await client_api.send_message2(
            from_=f"tg:{chat_id}",
            to=agent_id,
            payload=message_payload,
        )
        print(f"✓ Message sent (accepted={result.accepted})")

        # Step 6: Wait for response
        print("Step 6: Wait for tg_reply...")
        try:
            await asyncio.wait_for(response_event.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            print("❌ Timeout waiting for response")
            return False

        # Check response
        if not received_messages:
            print("❌ No response received")
            return False

        response = received_messages.pop(0)
        if response.get("type") != "tg_reply":
            print(f"❌ Expected tg_reply, got {response.get('type')}")
            return False

        response_text = response.get("content", {}).get("text", "")
        if test_message not in response_text:
            print(f"❌ Expected echo of '{test_message}', got '{response_text}'")
            return False

        print(f"✓ Response received: {response_text}")
        print()
        print("=" * 70)
        print("✅ E2E TEST PASSED")
        print("=" * 70)
        return True

    except AssertionError as e:
        print(f"❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"❌ TEST ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        # Cleanup
        await client_framework.stop()
        await server_framework.stop()

        for task in [client_task, server_task]:
            try:
                await task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    result = asyncio.run(test_telegram_flow())
    exit(0 if result else 1)
