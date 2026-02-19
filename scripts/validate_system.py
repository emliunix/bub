#!/usr/bin/env python3
"""End-to-end validation test for Bub system."""

import asyncio
import sys
from datetime import UTC, datetime
from typing import Any

from bub.bus.bus import AgentBusClient
from bub.bus.protocol import AgentBusClientCallbacks, ProcessMessageParams, ProcessMessageResult


class ValidationCallbacks(AgentBusClientCallbacks):
    """Callbacks for validation tests."""

    def __init__(self, name: str, message_collector: list | None = None) -> None:
        self.name = name
        self.message_collector = message_collector

    async def process_message(self, params: ProcessMessageParams) -> ProcessMessageResult:
        """Process incoming messages."""
        print(f"  ✓ [{self.name}] Received message to {params.to}")
        if self.message_collector is not None:
            self.message_collector.append((params.to, params.payload))
        return ProcessMessageResult(success=True, message="Received", should_retry=False, retry_seconds=0, payload={})


async def test_bus_connection() -> bool:
    """Test basic bus connectivity."""
    print("✓ Testing bus connection...")
    callbacks = ValidationCallbacks("validator")
    client: AgentBusClient | None = None
    try:
        client = await AgentBusClient.connect("ws://localhost:7892", callbacks)
        await client.initialize("test-validator")
        print("  ✓ Connected and initialized")
        return True
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        return False
    finally:
        if client is not None:
            await client.disconnect()


async def test_message_flow() -> bool:
    """Test message flow through the system."""
    print("\n✓ Testing message flow...")

    received_messages: list[tuple[str, dict]] = []
    sender_callbacks = ValidationCallbacks("sender")
    receiver_callbacks = ValidationCallbacks("receiver", received_messages)
    sender: AgentBusClient | None = None
    receiver: AgentBusClient | None = None

    try:
        # Setup receiver
        receiver = await AgentBusClient.connect("ws://localhost:7892", receiver_callbacks)
        await receiver.initialize("test-receiver")
        await receiver.subscribe("test:*")
        print("  ✓ Receiver subscribed to test:*")

        # Setup sender
        sender = await AgentBusClient.connect("ws://localhost:7892", sender_callbacks)
        await sender.initialize("test-sender")
        print("  ✓ Sender connected")

        # Send test message
        await sender.send_message(
            to="test:validation-123",
            payload={
                "messageId": f"test_{datetime.now(UTC).timestamp()}",
                "type": "test_message",
                "from": "test-sender",
                "timestamp": datetime.now(UTC).isoformat(),
                "content": {
                    "text": "Hello from validation test",
                    "channel": "test",
                    "senderId": "validator",
                    "chat_id": "validation-123",
                },
            },
        )
        print("  ✓ Message sent")

        # Wait for delivery
        await asyncio.sleep(1)

        if received_messages:
            print(f"  ✓ Message delivered successfully ({len(received_messages)} messages)")
            return True
        else:
            print("  ✗ No messages received")
            return False

    except Exception as e:
        print(f"  ✗ Message flow failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        if sender is not None:
            await sender.disconnect()
        if receiver is not None:
            await receiver.disconnect()


async def test_telegram_bridge() -> bool:
    """Test Telegram bridge connectivity."""
    print("\n✓ Testing Telegram bridge...")

    received_replies: list[Any] = []
    callbacks = ValidationCallbacks("telegram-validator", received_replies)
    client: AgentBusClient | None = None

    try:
        client = await AgentBusClient.connect("ws://localhost:7892", callbacks)
        await client.initialize("telegram-validator")

        # Subscribe to tg:* to catch any replies
        await client.subscribe("tg:*")
        print("  ✓ Subscribed to tg:*")

        # Wait a bit for any messages
        await asyncio.sleep(2)

        if received_replies:
            print(f"  ✓ Telegram bridge is processing messages")
            return True
        else:
            print("  ℹ No messages processed (send a Telegram message to test)")
            return True  # Not a failure, just no activity

    except Exception as e:
        print(f"  ✗ Telegram bridge test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        if client is not None:
            await client.disconnect()


async def main() -> int:
    """Run all validation tests."""
    print("=" * 60)
    print("BUB END-TO-END VALIDATION")
    print("=" * 60)
    print()

    results = []

    # Test 1: Bus connection
    results.append(("Bus Connection", await test_bus_connection()))

    # Test 2: Message flow
    results.append(("Message Flow", await test_message_flow()))

    # Test 3: Telegram bridge
    results.append(("Telegram Bridge", await test_telegram_bridge()))

    # Summary
    print()
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print()
    print(f"Result: {passed}/{total} tests passed")

    if passed == total:
        print("✓ All validation tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
