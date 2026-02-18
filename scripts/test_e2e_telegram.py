#!/usr/bin/env python3
"""Automated end-to-end test simulating Telegram message flow."""

import asyncio
import sys
import time
from datetime import UTC, datetime

from bub.channels.events import InboundMessage
from bub.bus.bus import AgentBusClient


async def test_telegram_message_flow():
    """Test the complete flow: simulate Telegram user -> agent -> response."""
    print("=" * 70)
    print("AUTOMATED E2E TEST: Telegram Message Flow")
    print("=" * 70)
    print()

    # Simulate Telegram bridge sending user message
    telegram_bridge = AgentBusClient("ws://localhost:7892", auto_reconnect=False)
    received_responses = []

    try:
        await telegram_bridge.connect()
        await telegram_bridge.initialize("telegram-bridge")
        print("✓ Telegram bridge connected")

        # Subscribe to receive agent responses
        async def handle_response(msg):
            received_responses.append(msg)
            print(f"✓ Telegram bridge received response: {msg.content[:50]}...")

        await telegram_bridge.on_outbound(handle_response)
        print("✓ Telegram bridge subscribed to outbound messages")
        print()

        # Simulate user sending message from Telegram
        chat_id = "436026689"
        user_message = "Hello Bub! This is an automated test message."

        print(f"→ Sending message from user (chat_id={chat_id}):")
        print(f"  Content: {user_message}")
        print()

        await telegram_bridge.publish_inbound(
            InboundMessage(
                channel="telegram",
                sender_id=chat_id,
                chat_id=chat_id,
                content=user_message,
            )
        )
        print("✓ Message published to bus")
        print()

        # Wait for agent to process and respond
        print("⏳ Waiting for agent response (max 60 seconds)...")
        for i in range(60):
            await asyncio.sleep(1)
            if received_responses:
                break
            if i % 10 == 0:
                print(f"  ... {i}s elapsed, still waiting...")

        print()

        if received_responses:
            print("=" * 70)
            print("✅ TEST PASSED")
            print("=" * 70)
            print()
            print("Summary:")
            print(f"  - Message sent: ✓")
            print(f"  - Agent processed: ✓")
            print(f"  - Response received: ✓ ({len(received_responses)} responses)")
            print()
            print("Response content:")
            for i, resp in enumerate(received_responses, 1):
                print(f"  {i}. {resp.content[:100]}...")
            return True
        else:
            print("=" * 70)
            print("❌ TEST FAILED")
            print("=" * 70)
            print()
            print("Issue: No response received from agent")
            print()
            print("Possible causes:")
            print("  - Agent not subscribed to tg:*")
            print("  - Agent session filtering blocking the message")
            print("  - Agent error during processing")
            print("  - Response routing issue")
            return False

    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        await telegram_bridge.disconnect()


if __name__ == "__main__":
    result = asyncio.run(test_telegram_message_flow())
    sys.exit(0 if result else 1)
