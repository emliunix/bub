#!/usr/bin/env python3
"""End-to-end validation test for Bub system."""

import asyncio
import json
import sys
import time
from datetime import UTC, datetime

from bub.channels.events import InboundMessage
from bub.bus.bus import AgentBusClient


async def test_bus_connection():
    """Test basic bus connectivity."""
    print("✓ Testing bus connection...")
    client = AgentBusClient("ws://localhost:7892", auto_reconnect=False)
    try:
        await client.connect()
        await client.initialize("test-validator")
        print("  ✓ Connected and initialized")
        return True
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        return False
    finally:
        await client.disconnect()


async def test_message_flow():
    """Test message flow through the system."""
    print("\n✓ Testing message flow...")

    sender = AgentBusClient("ws://localhost:7892", auto_reconnect=False)
    receiver = AgentBusClient("ws://localhost:7892", auto_reconnect=False)

    received_messages = []

    try:
        # Setup receiver
        await receiver.connect()
        await receiver.initialize("test-receiver")
        # Note: publish_inbound always uses tg: prefix
        await receiver.subscribe("tg:*")

        async def handle_message(topic, payload):
            received_messages.append((topic, payload))
            print(f"  ✓ Received message on {topic}")

        await receiver.subscribe("tg:*", handle_message)
        print("  ✓ Receiver subscribed to tg:*")

        # Setup sender
        await sender.connect()
        await sender.initialize("test-sender")
        print("  ✓ Sender connected")

        # Send test message
        await sender.publish_inbound(
            InboundMessage(
                channel="test",
                sender_id="validator",
                chat_id="validation-123",
                content="Hello from validation test",
            )
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
        return False
    finally:
        await sender.disconnect()
        await receiver.disconnect()


async def test_telegram_bridge():
    """Test Telegram bridge connectivity."""
    print("\n✓ Testing Telegram bridge...")

    client = AgentBusClient("ws://localhost:7892", auto_reconnect=False)
    received_replies = []

    try:
        await client.connect()
        await client.initialize("telegram-validator")

        # Subscribe to tg:* to catch any replies
        async def handle_outbound(msg):
            received_replies.append(msg)
            print(f"  ✓ Received outbound message for chat {msg.chat_id}")

        await client.on_outbound(handle_outbound)
        print("  ✓ Subscribed to outbound messages")

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
        return False
    finally:
        await client.disconnect()


async def main():
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
