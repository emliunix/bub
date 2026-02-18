"""WebSocket JSON-RPC channel adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from datetime import UTC, datetime
from loguru import logger

from bub.channels.base import BaseChannel
from bub.channels.events import InboundMessage, OutboundMessage
from bub.bus.bus import AgentBusClient
from bub.message.messages import create_tg_reply_payload


@dataclass(frozen=True)
class WebSocketConfig:
    """WebSocket adapter config."""

    url: str


class WebSocketChannel(BaseChannel):
    """WebSocket channel adapter using AgentBusClient."""

    name = "websocket"

    def __init__(self, bus: Any, config: WebSocketConfig) -> None:
        super().__init__(bus)
        self._config = config
        self._client: AgentBusClient | None = None
        self._running = False
        self._unsubscribe_funcs: list[Callable[[], Any]] = []

    async def start(self) -> None:
        """Start WebSocket channel: connect to server and subscribe to messages."""
        if not self._config.url:
            raise RuntimeError("websocket url is empty")

        logger.info("websocket.channel.start url={}", self._config.url)
        self._running = True

        # Create and connect client
        self._client = AgentBusClient(url=self._config.url)
        await self._client.connect()

        # Initialize connection
        client_id = f"ws-channel-{id(self):x}"
        await self._client.initialize(client_id=client_id)

        # Subscribe to all messages and filter in handler
        async def handle_message(address: str, payload: dict[str, Any]) -> None:
            await self._handle_inbound_from_server(address, payload)

        await self._client.subscribe("*:*", handle_message)

        # Store subscription info for cleanup
        self._subscribed_address = "*:*"

        logger.info("websocket.channel.connected url={}", self._config.url)

        # Keep running until stop() is called
        try:
            while self._running:
                await asyncio.sleep(1)
        finally:
            # Clean up subscriptions
            for unsub in self._unsubscribe_funcs:
                unsub()
            self._unsubscribe_funcs.clear()

    async def stop(self) -> None:
        """Stop WebSocket channel: disconnect from server."""
        self._running = False
        if self._client:
            await self._client.disconnect()
            self._client = None
        logger.info("websocket.channel.stopped")

    async def send(self, message: OutboundMessage) -> None:
        """Send outbound message via WebSocket."""
        if not self._client:
            logger.warning("websocket.send.not_connected")
            return

        logger.debug(
            "websocket.send channel={} chat_id={} content_len={}",
            message.channel,
            message.chat_id,
            len(message.content),
        )

        # Send message via WebSocket bus
        original_message_id = message.metadata.get("original_message_id", "") if message.metadata else ""
        payload = create_tg_reply_payload(
            message_id=f"msg_ws_{datetime.now(UTC).timestamp()}",
            from_addr="websocket:client",
            reply_to_message_id=original_message_id,
            timestamp=datetime.now(UTC).isoformat(),
            text=message.content,
            channel=message.channel,
            chat_id=message.chat_id,
        )
        await self._client.send_message(to=f"{message.channel}:{message.chat_id}", payload=payload)

    async def _handle_inbound_from_server(self, address: str, payload: dict[str, Any]) -> None:
        """Handle message received from WebSocket server."""
        if not self._running:
            return

        # Extract message info from payload
        content = payload.get("content", {})
        if not isinstance(content, dict):
            return

        channel = content.get("channel", "websocket")
        chat_id = address.split(":", 1)[1] if ":" in address else ""
        sender_id = content.get("senderId", "")
        text = content.get("text", "")

        logger.debug(
            "websocket.inbound channel={} chat_id={} sender_id={} content_len={}",
            channel,
            chat_id,
            sender_id,
            len(text),
        )

        # Create InboundMessage for the bus
        inbound_msg = InboundMessage(
            channel=str(channel),
            sender_id=str(sender_id),
            chat_id=chat_id,
            content=str(text),
            metadata={k: v for k, v in content.items() if k not in ("text", "senderId", "channel")},
        )

        # Publish to local message bus via parent
        await self.publish_inbound(inbound_msg)        await self.publish_inbound(inbound_msg)        )

        # Publish to local message bus
        await self.bus.publish_inbound(inbound_msg)        if not self._running:
            return

        # Extract message info from payload
        content = payload.get("content", {})
        if not isinstance(content, dict):
            return

        channel = content.get("channel", "websocket")
        chat_id = address.split(":", 1)[1] if ":" in address else ""
        sender_id = content.get("senderId", "")
        text = content.get("text", "")

        logger.debug(
            "websocket.inbound channel={} chat_id={} sender_id={} content_len={}",
            channel,
            chat_id,
            sender_id,
            len(text),
        )

        # Create InboundMessage for the bus
        inbound_msg = InboundMessage(
            channel=str(channel),
            sender_id=str(sender_id),
            chat_id=chat_id,
            content=str(text),
            metadata={k: v for k, v in content.items() if k not in ("text", "senderId", "channel")},
        )

        # Publish to local message bus via parent
        await self.publish_inbound(inbound_msg)
