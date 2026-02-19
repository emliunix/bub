"""WebSocket JSON-RPC channel adapter.

WebSocket acts as a transport proxy - it receives messages from various
channels (Telegram, Discord, etc.) and parses them using channel-specific
parsers. It does not have its own message format.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from bub.bus.bus import AgentBusClient
from bub.bus.protocol import (
    AgentBusClientCallbacks,
    ProcessMessageParams,
    ProcessMessageResult,
)
from bub.channels.base import BaseChannel
from bub.channels.events import OutboundMessage
from bub.channels.parsers import parse_channel_message


@dataclass(frozen=True)
class WebSocketConfig:
    """WebSocket adapter config."""

    url: str


class WebSocketChannel(BaseChannel, AgentBusClientCallbacks):
    """WebSocket channel adapter using AgentBusClient.

    Acts as a transport proxy - receives messages from various channels
    (telegram, discord, etc.) and parses them using channel-specific parsers.
    """

    name = "websocket"

    def __init__(self, bus: Any, config: WebSocketConfig) -> None:
        super().__init__(bus)
        self._config = config
        self._client: AgentBusClient | None = None
        self._running = False

    async def start(self) -> None:
        """Start WebSocket channel: connect to server and subscribe to messages."""
        if not self._config.url:
            raise RuntimeError("websocket url is empty")

        logger.info("websocket.channel.start url={}", self._config.url)
        self._running = True

        # Create and connect client (pass self as callbacks)
        self._client = await AgentBusClient.connect(self._config.url, self)

        # Initialize connection
        client_id = f"ws-channel-{id(self):x}"
        await self._client.initialize(client_id=client_id)

        logger.info("websocket.channel.connected url={}", self._config.url)

        # Keep running until stop() is called
        while self._running:
            await self._client.run()

    async def process_message(self, params: ProcessMessageParams) -> ProcessMessageResult:
        """Process message from bus (implements AgentBusClientCallbacks).

        WebSocket is a transport proxy - we parse the message using the
        appropriate channel parser based on payload.content.channel.
        Returns generic OK response (protocol-level ack).
        """
        payload = params.payload

        # Parse using channel-specific parser
        # Returns InboundMessage or None if not recognizable
        inbound_msg = parse_channel_message(payload)

        if inbound_msg is None:
            logger.debug("websocket.unrecognizable_message payload_type={}", payload.get("type"))
            return ProcessMessageResult(
                success=True,  # Acknowledge receipt even if unrecognizable
                message="Unrecognizable message format",
                should_retry=False,
                retry_seconds=0,
                payload={},
            )

        logger.debug(
            "websocket.inbound channel={} chat_id={} sender_id={} content_len={}",
            inbound_msg.channel,
            inbound_msg.chat_id,
            inbound_msg.sender_id,
            len(inbound_msg.content),
        )

        # Publish to local message bus via parent
        await self.publish_inbound(inbound_msg)

        # Return generic OK response - the actual response is sent separately
        # via the reply channel
        return ProcessMessageResult(
            success=True,
            message="Processed",
            should_retry=False,
            retry_seconds=0,
            payload={},  # Empty payload - response sent via separate message
        )

    async def stop(self) -> None:
        """Stop WebSocket channel: disconnect from server."""
        self._running = False
        if self._client:
            await self._client.disconnect()
            self._client = None
        logger.info("websocket.channel.stopped")

    async def send(self, message: OutboundMessage) -> None:
        """Send outbound message via WebSocket.

        Creates a generic bus message format (not channel-specific).
        The recipient is responsible for formatting it for their channel.
        """
        if not self._client:
            logger.warning("websocket.send.not_connected")
            return

        logger.debug(
            "websocket.send channel={} chat_id={} content_len={}",
            message.channel,
            message.chat_id,
            len(message.content),
        )

        # Create generic bus message (not Telegram-specific)
        # The recipient will format it appropriately for their channel
        payload = {
            "messageId": f"msg_ws_{datetime.now(UTC).timestamp()}",
            "type": "outbound_message",
            "from": "websocket:client",
            "timestamp": datetime.now(UTC).isoformat(),
            "to": f"{message.channel}:{message.chat_id}",
            "content": {
                "text": message.content,
                "channel": message.channel,
                "chat_id": message.chat_id,
                "reply_to_message_id": message.reply_to_message_id,
            },
        }

        await self._client.send_message(
            to=f"{message.channel}:{message.chat_id}",
            payload=payload,
        )
