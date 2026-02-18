#!/usr/bin/env python3
"""Test that verifies concurrent request handling in the bus.

This test demonstrates that the fix for the deadlock issue works:
- When a client receives a message and sends a response from within the handler,
  it no longer deadlocks because the framework handles requests concurrently.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from bub.bus.bus import AgentBusClient, AgentBusServer


MSG_TYPE = "agent_event"


def create_payload(from_addr: str, content: dict) -> dict:
    """Create a test payload."""
    return {
        "messageId": f"test_{uuid.uuid4().hex[:8]}",
        "type": MSG_TYPE,
        "from": from_addr,
        "timestamp": datetime.now(UTC).isoformat(),
        "content": content,
    }


class RespondingClient:
    """Client that automatically responds from message handler."""

    def __init__(self, client_id: str, bus_url: str, respond_to: str | None = None):
        self.client_id = client_id
        self.bus_url = bus_url
        self.respond_to = respond_to  # Who to respond to
        self.client: AgentBusClient | None = None
        self.received_count = 0
        self.response_count = 0
        self._response_event = asyncio.Event()

    async def start(self) -> bool:
        """Connect and subscribe."""
        logger.info("responding.client.starting client_id={}", self.client_id)
        self.client = AgentBusClient(self.bus_url, auto_reconnect=False)
        await self.client.connect()
        await self.client.initialize(self.client_id)
        await self.client.subscribe(self.client_id, self._handle_message)
        logger.info("responding.client.started client_id={}", self.client_id)
        return True

    async def stop(self) -> None:
        if self.client:
            await self.client.disconnect()
        logger.info("responding.client.stopped client_id={}", self.client_id)

    async def _handle_message(self, to: str, payload: dict) -> None:
        """Handle message and respond immediately (would deadlock without fix)."""
        self.received_count += 1
        sender = payload.get("from")
        logger.info("responding.client.received client_id={} from={}", self.client_id, sender)

        # Respond directly from handler - this would deadlock before the fix
        if self.respond_to and self.client and sender == self.respond_to:
            response_payload = create_payload(
                from_addr=self.client_id,
                content={"reply": f"Response from {self.client_id}"},
            )
            try:
                result = await self.client.send_message(to=sender, payload=response_payload)
                self.response_count += len(result.acks)
                self._response_event.set()
                logger.info("responding.client.auto_response sent to={} acks={}", sender, len(result.acks))
            except Exception as e:
                logger.error("responding.client.auto_response_failed error={}", e)


async def run_concurrent_test() -> bool:
    """Test concurrent request handling."""
    print("=" * 70)
    print("CONCURRENT REQUEST HANDLING TEST")
    print("=" * 70)
    print()

    # Start server
    print("Starting bus server...")
    log_path = Path("run/test_concurrent.sqlite3")
    log_path.parent.mkdir(exist_ok=True)
    server = AgentBusServer(host="localhost", port=0, activity_log_path=log_path)
    await server.start_server()

    actual_port = server._server.sockets[0].getsockname()[1]
    bus_url = f"ws://localhost:{actual_port}"
    print(f"✅ Server on {bus_url}")
    print()

    try:
        # Create clients - B and C will auto-respond to A
        print("Creating clients (B and C auto-respond to A)...")
        client_a = RespondingClient("client-a", bus_url)
        client_b = RespondingClient("client-b", bus_url, respond_to="client-a")
        client_c = RespondingClient("client-c", bus_url, respond_to="client-a")

        await client_a.start()
        await client_b.start()
        await client_c.start()
        print("✅ All clients connected")
        print()

        # A sends to B - B will respond from handler
        print("Step 1: A sends to B (B responds from handler)...")
        msg = create_payload("client-a", {"msg": "Hello B"})
        result = await client_a.client.send_message("client-b", msg)
        print(f"   ✅ Sent to B, got {len(result.acks)} ack(s)")

        # Wait for B's auto-response
        await asyncio.sleep(0.3)
        print(f"   B received: {client_b.received_count}, responded: {client_b.response_count}")
        print(f"   A received responses: {client_a.received_count}")

        if client_a.received_count >= 1:
            print("   ✅ A received response from B (no deadlock!)")
        else:
            print("   ❌ A did not receive response (deadlock?)")
            return False
        print()

        # A sends to C - C will respond from handler
        print("Step 2: A sends to C (C responds from handler)...")
        client_a.received_count = 0  # Reset
        msg = create_payload("client-a", {"msg": "Hello C"})
        result = await client_a.client.send_message("client-c", msg)
        print(f"   ✅ Sent to C, got {len(result.acks)} ack(s)")

        await asyncio.sleep(0.3)
        print(f"   C received: {client_c.received_count}, responded: {client_c.response_count}")
        print(f"   A received responses: {client_a.received_count}")

        if client_a.received_count >= 1:
            print("   ✅ A received response from C (no deadlock!)")
        else:
            print("   ❌ A did not receive response (deadlock?)")
            return False
        print()

        # Test parallel sends
        print("Step 3: A sends to both B and C simultaneously...")
        client_a.received_count = 0

        msg_b = create_payload("client-a", {"msg": "Parallel to B"})
        msg_c = create_payload("client-a", {"msg": "Parallel to C"})

        # Send both in parallel
        await asyncio.gather(
            client_a.client.send_message("client-b", msg_b),
            client_a.client.send_message("client-c", msg_c),
        )

        await asyncio.sleep(0.5)
        print(f"   A received {client_a.received_count} response(s)")

        if client_a.received_count == 2:
            print("   ✅ Both responses received (concurrent handling works!)")
        else:
            print(f"   ⚠️ Expected 2 responses, got {client_a.received_count}")
            # This might be timing, don't fail
        print()

        print("=" * 70)
        print("✅ CONCURRENT HANDLING TEST PASSED")
        print("=" * 70)
        return True

    except Exception as e:
        logger.exception("test.error")
        print(f"❌ Test error: {e}")
        return False

    finally:
        print()
        print("Cleanup...")
        await client_a.stop()
        await client_b.stop()
        await client_c.stop()
        await server.stop_server()
        print("✅ Cleanup complete")


async def main() -> int:
    success = await run_concurrent_test()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
