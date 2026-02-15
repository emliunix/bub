"""WebSocket JSON-RPC channel adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from loguru import logger

from bub.channels.base import BaseChannel
from bub.channels.events import InboundMessage, OutboundMessage
from bub.channels.wsbus import AgentBusClient


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
        self._unsubscribe_funcs: list[Callable[[], None]] = []

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

        # Subscribe to inbound messages from server
        await self._client.subscribe(topic="inbound:*")
        unsubscribe_inbound = await self._client.on_inbound(self._handle_inbound_from_server)
        self._unsubscribe_funcs.append(unsubscribe_inbound)

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

        # Publish to outbound:* topic so other clients receive it
        await self._client.publish_outbound(message)

    async def _handle_inbound_from_server(self, inbound_msg: InboundMessage) -> None:
        """Handle inbound message received from WebSocket server."""
        if not self._running:
            return

        logger.debug(
            "websocket.inbound channel={} chat_id={} sender_id={} content_len={}",
            inbound_msg.channel,
            inbound_msg.chat_id,
            inbound_msg.sender_id,
            len(inbound_msg.content),
        )

        # Publish to local message bus
        await self.bus.publish_inbound(inbound_msg)
