"""Mock Telegram client for testing WebSocket bus pub/sub.

This simulates a Telegram channel that connects to a WebSocket server
and publishes inbound messages.
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
from typing import Any

from bub.channels.events import InboundMessage
from bub.channels.wsbus import AgentBusClient


class MockTelegramClient:
    """Mock Telegram client that publishes to WebSocket bus."""

    def __init__(self, url: str, bot_name: str = "MockBot") -> None:
        self._url = url
        self._bot_name = bot_name
        self._client: AgentBusClient | None = None
        self._running = False
        self._chat_ids = ["1001", "1002", "1003"]  # Mock chat IDs

    async def connect(self) -> None:
        """Connect to WebSocket bus server."""
        self._client = AgentBusClient(self._url)
        await self._client.connect()
        await self._client.initialize(f"mock-telegram-{id(self):x}")
        print(f"✅ {self._bot_name} connected to {self._url}")

    async def disconnect(self) -> None:
        """Disconnect from WebSocket bus server."""
        self._running = False
        if self._client:
            await self._client.disconnect()
            print(f"🔌 {self._bot_name} disconnected")

    async def start(self, delay: float = 0.5) -> None:
        """Start publishing messages periodically."""
        self._running = True
        print(f"📱 {self._bot_name} started publishing messages every {delay}s")

        message_count = 0
        while self._running:
            await self._publish_random_message(message_count)
            message_count += 1
            await asyncio.sleep(delay)

    def stop(self) -> None:
        """Stop publishing messages."""
        self._running = False
        print(f"⏸️ {self._bot_name} stopped")

    async def _publish_random_message(self, count: int) -> None:
        """Publish a random message to WebSocket bus."""
        if not self._client:
            return

        chat_id = random.choice(self._chat_ids)
        message_type = random.choice(["text", "command", "question"])
        sender_id = f"user_{random.randint(1000, 9999)}"

        # Generate different message types
        if message_type == "text":
            content = random.choice([
                "hello from mock telegram",
                "what can you do?",
                "help me with coding",
                "how are you?",
            ])
        elif message_type == "command":
            content = random.choice([
                ",help",
                ",tools",
                ",tape.info",
                ",anchors",
            ])
        else:
            content = f"question #{count}: {random.choice(['python', 'async', 'websocket', 'testing'])}?"

        # Create inbound message
        message = InboundMessage(
            channel="telegram",
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            metadata={
                "username": f"mock_user_{random.randint(100, 999)}",
                "message_id": random.randint(100000, 999999),
            },
        )

        # Publish to WebSocket server
        await self._client.publish_inbound(message)

        print(f"📤 Published to chat {chat_id}: {content}")

    async def send_message(self, chat_id: str, content: str) -> None:
        """Send a specific message to a chat."""
        if not self._client:
            return

        message = InboundMessage(
            channel="telegram",
            sender_id="mock_telegram_bot",
            chat_id=chat_id,
            content=content,
            metadata={"username": "MockBot", "message_id": 0},
        )

        await self._client.publish_inbound(message)
        print(f"📤 Sent to chat {chat_id}: {content}")


async def main() -> None:
    """Run mock Telegram client."""
    url = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:7892"
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0

    print(f"🚀 Mock Telegram Client")
    print(f"   Connecting to: {url}")
    print(f"   Message delay: {delay}s")
    print(f"   Press Ctrl+C to stop\n")

    client = MockTelegramClient(url, bot_name="MockTelegram")

    try:
        await client.connect()
        await client.start(delay=delay)
    except KeyboardInterrupt:
        client.stop()
        await client.disconnect()
    except Exception:
        import traceback

        traceback.print_exc()
        client.stop()
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
