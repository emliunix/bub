#!/usr/bin/env python3
"""Integration test for bus protocol with 3 clients.

Tests the core bus protocol with a simple scenario:
- Client A sends messages to B and C
- B and C receive messages
- B and C then send responses back to A
- A receives the responses

Uses test-specific message types (allowed by bus whitelist).
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from bub.bus.bus import AgentBusClient, AgentBusServer


# Use allowed message types from bus whitelist
MSG_TYPE = "agent_event"


def create_test_payload(from_addr: str, content: dict, message_id: str | None = None) -> dict:
    """Create a test payload with required fields."""
    return {
        "messageId": message_id or f"test_{uuid.uuid4().hex[:8]}",
        "type": MSG_TYPE,
        "from": from_addr,
        "timestamp": datetime.now(UTC).isoformat(),
        "content": content,
    }


class TestClient:
    """Test client that can send/receive messages."""

    def __init__(self, client_id: str, bus_url: str = "ws://localhost:7892"):
        self.client_id = client_id
        self.bus_url = bus_url
        self.client: AgentBusClient | None = None
        self.received_messages: list[dict] = []
        self.message_event = asyncio.Event()

    async def start(self) -> bool:
        """Connect to bus and subscribe to own address."""
        logger.info("test.client.starting client_id={}", self.client_id)

        self.client = AgentBusClient(self.bus_url, auto_reconnect=False)
        await self.client.connect()
        await self.client.initialize(self.client_id)

        # Subscribe to receive messages sent to this client
        await self.client.subscribe(self.client_id, self._handle_message)
        logger.info("test.client.started client_id={}", self.client_id)
        return True

    async def stop(self) -> None:
        """Disconnect from bus."""
        if self.client:
            await self.client.disconnect()
        logger.info("test.client.stopped client_id={}", self.client_id)

    async def send_message(self, to: str, payload: dict) -> dict:
        """Send a message to another client."""
        if not self.client:
            raise RuntimeError("Client not connected")

        logger.info("test.client.sending from={} to={}", self.client_id, to)
        result = await self.client.send_message(to=to, payload=payload)
        logger.info("test.client.sent from={} to={} acks={}", self.client_id, to, len(result.acks))
        return result

    async def wait_for_messages(self, count: int = 1, timeout: float = 5.0) -> list[dict]:
        """Wait for messages to arrive."""
        start_len = len(self.received_messages)

        async def _wait():
            while len(self.received_messages) < start_len + count:
                await self.message_event.wait()
                self.message_event.clear()

        try:
            await asyncio.wait_for(_wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass

        # Return the newly received messages
        return self.received_messages[start_len : start_len + count]

    def clear_messages(self) -> None:
        """Clear received messages."""
        self.received_messages.clear()
        self.message_event.clear()

    async def _handle_message(self, to: str, payload: dict) -> None:
        """Handle incoming messages."""
        logger.info("test.client.received client_id={} from={}", self.client_id, payload.get("from"))
        self.received_messages.append(payload)
        self.message_event.set()


async def run_test() -> bool:
    """Run the 3-client integration test."""
    print("=" * 70)
    print("BUS PROTOCOL INTEGRATION TEST - 3 Clients")
    print("=" * 70)
    print()

    # Start bus server on dynamic port
    print("Step 1: Starting bus server...")
    log_path = Path("run/test_bus_integration.sqlite3")
    log_path.parent.mkdir(exist_ok=True)
    server = AgentBusServer(host="localhost", port=0, activity_log_path=log_path)
    await server.start_server()

    # Get the actual port assigned
    actual_port = server._server.sockets[0].getsockname()[1]
    bus_url = f"ws://localhost:{actual_port}"
    print(f"✅ Bus server started on {bus_url}")
    print()

    client_a: TestClient | None = None
    client_b: TestClient | None = None
    client_c: TestClient | None = None

    try:
        # Create clients
        print("Step 2: Creating clients A, B, C...")
        client_a = TestClient("client-a", bus_url=bus_url)
        client_b = TestClient("client-b", bus_url=bus_url)
        client_c = TestClient("client-c", bus_url=bus_url)

        # Connect all clients
        await client_a.start()
        await client_b.start()
        await client_c.start()
        print("✅ All clients connected")
        print()

        # Step 3: A sends messages to B and C
        print("Step 3: Client A sends messages to B and C...")

        # Send to B
        msg_to_b = create_test_payload(from_addr="client-a", content={"message": "Hello B!"})
        result_b = await client_a.send_message("client-b", msg_to_b)
        print(f"   ✅ Message to B: {len(result_b.acks)} ack(s)")

        # Send to C
        msg_to_c = create_test_payload(from_addr="client-a", content={"message": "Hello C!"})
        result_c = await client_a.send_message("client-c", msg_to_c)
        print(f"   ✅ Message to C: {len(result_c.acks)} ack(s)")
        print()

        # Step 4: Verify B and C received messages
        print("Step 4: Verifying B and C received messages...")
        await asyncio.sleep(0.2)  # Brief wait for delivery

        if len(client_b.received_messages) >= 1:
            msg = client_b.received_messages[0]
            print(f"   ✅ B received: {msg.get('type')} from {msg.get('from')}")
        else:
            print(f"   ❌ B expected 1 message, got {len(client_b.received_messages)}")
            return False

        if len(client_c.received_messages) >= 1:
            msg = client_c.received_messages[0]
            print(f"   ✅ C received: {msg.get('type')} from {msg.get('from')}")
        else:
            print(f"   ❌ C expected 1 message, got {len(client_c.received_messages)}")
            return False
        print()

        # Step 5: B and C send responses back to A
        print("Step 5: B and C send responses back to A...")

        # B responds to A
        msg_from_b = create_test_payload(from_addr="client-b", content={"reply": "Hello from B!"})
        result_b_ack = await client_b.send_message("client-a", msg_from_b)
        print(f"   ✅ B response sent: {len(result_b_ack.acks)} ack(s)")

        # C responds to A
        msg_from_c = create_test_payload(from_addr="client-c", content={"reply": "Hello from C!"})
        result_c_ack = await client_c.send_message("client-a", msg_from_c)
        print(f"   ✅ C response sent: {len(result_c_ack.acks)} ack(s)")
        print()

        # Step 6: Verify A received both responses
        print("Step 6: Verifying A received responses from B and C...")
        await asyncio.sleep(0.2)  # Brief wait for delivery

        if len(client_a.received_messages) >= 2:
            print(f"   ✅ A received {len(client_a.received_messages)} response(s)")
            for i, msg in enumerate(client_a.received_messages[:2]):
                print(f"      [{i + 1}] {msg.get('type')} from {msg.get('from')}")
                content = msg.get("content", {})
                print(f"          content: {content}")
        else:
            print(f"   ❌ A expected 2 responses, got {len(client_a.received_messages)}")
            for i, msg in enumerate(client_a.received_messages):
                print(f"      [{i}] from={msg.get('from')} type={msg.get('type')}")
            return False
        print()

        print("=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        return True

    except Exception as e:
        logger.exception("test.error")
        print(f"❌ Test error: {e}")
        return False

    finally:
        # Cleanup
        print()
        print("Cleanup: Disconnecting clients and stopping server...")
        if client_a:
            await client_a.stop()
        if client_b:
            await client_b.stop()
        if client_c:
            await client_c.stop()
        await server.stop_server()
        print("✅ Cleanup complete")


async def main() -> int:
    """Main entry point."""
    success = await run_test()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
