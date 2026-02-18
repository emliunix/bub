#!/usr/bin/env python3
"""End-to-end automated test following agent-protocol.md architecture.

This test follows the exact flow documented in docs/agent-protocol.md:
1. Connect mock telegram bridge to bus
2. Request spawn from system agent
3. Receive spawn response with agent_id
4. Send configure to agent (set talkto)
5. Send tg_message to agent
6. Wait for tg_reply response
"""

from __future__ import annotations

import asyncio
import random
import sys
import uuid
from datetime import UTC, datetime

from loguru import logger

from bub.bus.bus import AgentBusClient


class MockTelegramBridge:
    """Mock Telegram bridge following protocol spec."""

    def __init__(self, bus_url: str = "ws://localhost:7892"):
        self.bus_url = bus_url
        self.client: AgentBusClient | None = None
        self.chat_id = str(random.randint(100000000, 999999999))
        self.agent_id: str | None = None
        self.responses: list[dict] = []
        self.spawn_event = asyncio.Event()

    async def start(self) -> bool:
        """Start bridge: connect + subscribe to tg:{chat_id} for responses."""
        logger.info("mock.bridge.starting chat_id={}", self.chat_id)

        self.client = AgentBusClient(self.bus_url, auto_reconnect=True)
        await self.client.connect()
        await self.client.initialize("tg-bridge")

        # Subscribe to receive responses (step 11: agent sends tg_reply to tg:{chat_id})
        await self.client.subscribe(f"tg:{self.chat_id}", self._handle_message)
        logger.info("mock.bridge.subscribed to=tg:{}", self.chat_id)
        return True

    async def stop(self) -> None:
        if self.client:
            await self.client.disconnect()
        logger.info("mock.bridge.stopped")

    async def spawn_agent(self) -> bool:
        """Step 1-8: Request spawn from system agent."""
        logger.info("mock.bridge.spawn_request chat_id={}", self.chat_id)

        self.spawn_event.clear()

        # Step 1: Send spawn_request to system:spawn
        spawn_msg = {
            "messageId": f"spawn_{self.chat_id}_{uuid.uuid4().hex[:8]}",
            "type": "spawn_request",
            "from": f"tg:{self.chat_id}",
            "timestamp": datetime.now(UTC).isoformat(),
            "content": {
                "chat_id": self.chat_id,
                "channel": "telegram",
                "channel_type": "telegram",
            },
        }

        await self.client.send_message(to="system:spawn", payload=spawn_msg)

        logger.info("mock.bridge.spawn_sent to=system:spawn")

        # Wait for spawn_result (step 7: system agent sends to tg:{chat_id})
        try:
            await asyncio.wait_for(self.spawn_event.wait(), timeout=35.0)
        except asyncio.TimeoutError:
            logger.error("mock.bridge.spawn_timeout")
            return False

        if self.agent_id:
            logger.info("mock.bridge.spawn_success agent={}", self.agent_id)
            return True
        return False

    async def send_message(self, content: str) -> bool:
        """Step 10: Send tg_message to agent."""
        if not self.agent_id:
            return False

        logger.info("mock.bridge.send_message agent={}", self.agent_id)

        msg = {
            "messageId": f"msg_{uuid.uuid4().hex}",
            "type": "tg_message",
            "from": f"tg:{self.chat_id}",
            "timestamp": datetime.now(UTC).isoformat(),
            "content": {
                "text": content,
                "senderId": self.chat_id,
                "channel": "telegram",
            },
        }

        await self.client.send_message(to=self.agent_id, payload=msg)

        logger.info("mock.bridge.message_sent to={}", self.agent_id)
        return True

    async def wait_for_response(self, timeout: float = 60.0) -> str | None:
        """Wait for tg_reply from agent (step 11)."""
        logger.info("mock.bridge.waiting_response timeout={}s", timeout)

        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < timeout:
            if self.responses:
                response = self.responses.pop(0)
                text = response.get("content", {}).get("text", "")
                logger.info("mock.bridge.response_received len={}", len(text))
                return text
            await asyncio.sleep(0.5)

        logger.error("mock.bridge.response_timeout")
        return None

    async def _handle_message(self, topic: str, payload: dict) -> None:
        """Handle incoming messages (spawn_result and tg_reply)."""
        msg_type = payload.get("type", "")

        if msg_type == "spawn_result":
            # Step 7: Received agent_id from system agent
            content = payload.get("content", {})
            if content.get("success"):
                self.agent_id = content.get("client_id")
                logger.info("mock.bridge.spawn_result agent={}", self.agent_id)
            else:
                logger.error("mock.bridge.spawn_failed")
            self.spawn_event.set()

        elif msg_type == "tg_reply":
            # Step 11: Received response from agent
            self.responses.append(payload)
            logger.info("mock.bridge.tg_reply_received")


async def run_e2e_test() -> bool:
    """Run complete E2E test following protocol."""
    print("=" * 70)
    print("BUB E2E TEST - Following agent-protocol.md")
    print("=" * 70)
    print()

    bridge = MockTelegramBridge()

    try:
        # Step 0: Connect bridge
        print("Step 0: Connect bridge to bus...")
        if not await bridge.start():
            print("❌ Failed to connect")
            return False
        print("✅ Bridge connected")
        print()

        # Steps 1-8: Spawn agent
        print("Steps 1-8: Request agent spawn...")
        print(f"   Chat ID: {bridge.chat_id}")
        if not await bridge.spawn_agent():
            print("❌ Failed to spawn agent")
            return False
        print(f"✅ Agent spawned: {bridge.agent_id}")
        print()

        # Wait for agent to fully start and subscribe
        print("   Waiting for agent to start...")
        await asyncio.sleep(3.0)
        print("✅ Agent ready")
        print()

        # Step 9-10: Send message (talkto already set via spawn)
        print("Steps 9-10: Send tg_message to agent...")
        test_content = "Hello, this is an E2E test!"
        if not await bridge.send_message(test_content):
            print("❌ Failed to send message")
            return False
        print("✅ Message sent")
        print()

        # Step 11: Wait for response
        print("Step 11: Wait for tg_reply from agent...")
        response = await bridge.wait_for_response(timeout=60.0)

        if response:
            print("✅ Response received!")
            print(f"   Preview: {response[:100]}...")
            return True
        else:
            print("❌ No response received")
            return False

    except Exception as e:
        logger.exception("e2e.test_error")
        print(f"❌ Test error: {e}")
        return False

    finally:
        await bridge.stop()


async def main() -> int:
    success = await run_e2e_test()

    print()
    print("=" * 70)
    if success:
        print("✅ E2E TEST PASSED")
    else:
        print("❌ E2E TEST FAILED")
    print("=" * 70)

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
