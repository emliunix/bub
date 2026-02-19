#!/usr/bin/env python3
"""End-to-end automated test for Bub system.

This test simulates a Telegram bridge:
1. Generates random chat_id
2. Requests spawn from system agent
3. Sends message with retry
4. Verifies response received
"""

from __future__ import annotations

import asyncio
import random
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from bub.bus.bus import AgentBusClient
from bub.bus.protocol import AgentBusClientCallbacks, ProcessMessageParams, ProcessMessageResult


class MockBridgeCallbacks(AgentBusClientCallbacks):
    """Callbacks for mock telegram bridge."""

    def __init__(self, bridge: MockTelegramBridge) -> None:
        self.bridge = bridge

    async def process_message(self, params: ProcessMessageParams) -> ProcessMessageResult:
        """Handle incoming messages from bus."""
        payload = params.payload
        msg_type = payload.get("type", "")

        if msg_type == "spawn_result":
            await self.bridge._handle_spawn_response(payload)
        elif msg_type == "tg_reply":
            await self.bridge._handle_tg_reply(payload)

        return ProcessMessageResult(success=True, message="Received", should_retry=False, retry_seconds=0, payload={})


class MockTelegramBridge:
    """Mock Telegram bridge for E2E testing."""

    def __init__(self, bus_url: str = "ws://localhost:7892"):
        self.bus_url = bus_url
        self.client: AgentBusClient | None = None
        self.chat_id = str(random.randint(100000000, 999999999))
        self.agent_id: str | None = None
        self.responses: list[dict] = []
        self.spawn_event = asyncio.Event()

    async def start(self) -> bool:
        """Start the mock bridge and connect to bus."""
        logger.info("mock.bridge.starting chat_id={}", self.chat_id)

        callbacks = MockBridgeCallbacks(self)
        self.client = await AgentBusClient.connect(self.bus_url, callbacks)
        await self.client.initialize("mock-telegram-bridge")

        # Subscribe to receive spawn responses (sent to our client_id)
        await self.client.subscribe("mock-telegram-bridge")

        # Also subscribe to tg:{self.chat_id} to receive agent replies
        await self.client.subscribe(f"tg:{self.chat_id}")

        logger.info("mock.bridge.connected chat_id={}", self.chat_id)
        return True

    async def stop(self) -> None:
        """Stop the mock bridge."""
        if self.client:
            await self.client.disconnect()
        logger.info("mock.bridge.stopped")

    async def spawn_agent(self, max_retries: int = 3, timeout: float = 35.0) -> bool:
        """Request system agent to spawn an agent for this chat."""
        logger.info("mock.bridge.spawn_request chat_id={}", self.chat_id)

        for attempt in range(max_retries):
            try:
                self.spawn_event.clear()

                # Send spawn request
                spawn_msg = {
                    "messageId": f"spawn_{self.chat_id}_{uuid.uuid4().hex[:8]}",
                    "type": "spawn_request",
                    "from": "mock-telegram-bridge",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "content": {
                        "chat_id": self.chat_id,
                        "channel": "telegram",
                        "channel_type": "telegram",
                    },
                }

                assert self.client is not None
                await self.client.send_message(to="system:spawn", payload=spawn_msg)

                logger.info(
                    "mock.bridge.spawn_sent attempt={}/{} chat_id={}",
                    attempt + 1,
                    max_retries,
                    self.chat_id,
                )

                # Wait for response
                await asyncio.wait_for(self.spawn_event.wait(), timeout=timeout)

                if self.agent_id:
                    logger.info("mock.bridge.spawn_success chat_id={} agent={}", self.chat_id, self.agent_id)
                    return True
                else:
                    logger.error("mock.bridge.spawn_failed_no_agent chat_id={}", self.chat_id)
                    # Retry after delay
                    await asyncio.sleep(2**attempt)

            except asyncio.TimeoutError:
                logger.error(
                    "mock.bridge.spawn_timeout attempt={}/{} chat_id={}",
                    attempt + 1,
                    max_retries,
                    self.chat_id,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
            except Exception:
                logger.exception("mock.bridge.spawn_error")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)

        return False

    async def send_message(self, content: str, max_retries: int = 3) -> bool:
        """Send message to the agent with retry."""
        if not self.agent_id:
            logger.error("mock.bridge.no_agent chat_id={}", self.chat_id)
            return False

        logger.info(
            "mock.bridge.sending chat_id={} agent={} content={}",
            self.chat_id,
            self.agent_id,
            content[:50],
        )

        for attempt in range(max_retries):
            try:
                msg = {
                    "messageId": f"msg_{uuid.uuid4().hex}",
                    "type": "tg_message",
                    "from": f"tg:{self.chat_id}",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "content": {
                        "text": content,
                        "senderId": self.chat_id,
                        "chat_id": self.chat_id,
                        "channel": "telegram",
                    },
                }

                # Send directly to the assigned agent (not to tg:* broadcast)
                assert self.client is not None
                await self.client.send_message(to=self.agent_id, payload=msg)

                logger.info(
                    "mock.bridge.sent attempt={}/{} chat_id={}",
                    attempt + 1,
                    max_retries,
                    self.chat_id,
                )
                return True

            except Exception:
                logger.exception("mock.bridge.send_error attempt={}/{}", attempt + 1, max_retries)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)

        return False

    async def wait_for_response(self, timeout: float = 60.0) -> str | None:
        """Wait for agent response."""
        logger.info("mock.bridge.waiting_response chat_id={} timeout={}s", self.chat_id, timeout)

        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            if self.responses:
                response = self.responses.pop(0)
                text = response.get("content", {}).get("text", "")
                logger.info("mock.bridge.received_response chat_id={} content_len={}", self.chat_id, len(text))
                return text
            await asyncio.sleep(0.5)

        logger.error("mock.bridge.response_timeout chat_id={}", self.chat_id)
        return None

    async def _handle_spawn_response(self, payload: dict[str, Any]) -> None:
        """Handle spawn result response."""
        content = payload.get("content", {})
        if content.get("success"):
            self.agent_id = content.get("client_id")
            logger.info("mock.bridge.spawn_response_received agent={}", self.agent_id)
        else:
            logger.error("mock.bridge.spawn_failed_response error={}", content.get("error", "unknown"))
        self.spawn_event.set()

    async def _handle_tg_reply(self, payload: dict[str, Any]) -> None:
        """Handle tg_reply from agent."""
        self.responses.append(payload)
        logger.info(
            "mock.bridge.response_received chat_id={} content_len={}",
            self.chat_id,
            len(payload.get("content", {}).get("text", "")),
        )


async def run_e2e_test() -> bool:
    """Run complete E2E test."""
    print("=" * 70)
    print("BUB E2E AUTOMATED TEST")
    print("=" * 70)
    print()

    bridge = MockTelegramBridge()

    try:
        # Step 1: Connect to bus
        print("Step 1: Connecting to bus...")
        if not await bridge.start():
            print("❌ Failed to connect to bus")
            return False
        print("✅ Connected to bus")
        print()

        # Step 2: Request agent spawn
        print("Step 2: Requesting agent spawn...")
        print(f"   Chat ID: {bridge.chat_id}")
        if not await bridge.spawn_agent():
            print("❌ Failed to spawn agent")
            return False
        print(f"✅ Agent spawned: {bridge.agent_id}")
        print()

        # Step 3: Send test message
        print("Step 3: Sending test message...")
        test_message = "Hello, this is an automated E2E test!"
        if not await bridge.send_message(test_message):
            print("❌ Failed to send message")
            return False
        print("✅ Message sent")
        print()

        # Step 4: Wait for response
        print("Step 4: Waiting for agent response (max 60s)...")
        response = await bridge.wait_for_response(timeout=60.0)

        if response:
            print("✅ Response received!")
            print(f"   Length: {len(response)} chars")
            print(f"   Preview: {response[:100]}...")
            print()
            return True
        else:
            print("❌ No response received within timeout")
            print()
            return False

    except Exception as e:
        logger.exception("e2e.test_error")
        print(f"❌ Test failed with error: {e}")
        return False

    finally:
        await bridge.stop()


async def main() -> int:
    """Main entry point."""
    success = await run_e2e_test()

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
