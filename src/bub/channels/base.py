"""Base channel interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from bub.channels.events import InboundMessage, OutboundMessage
from bub.message.messages import create_tg_message_payload

if TYPE_CHECKING:
    from bub.bub_types import MessageBus


class BaseChannel(ABC):
    """Abstract base class for channel adapters."""

    name = "base"

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        """Start adapter and begin ingesting inbound messages."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop adapter and cleanup resources."""

    @abstractmethod
    async def send(self, message: OutboundMessage) -> None:
        """Send one outbound message to external channel."""

    async def publish_inbound(self, message: InboundMessage) -> None:
        """Publish inbound message to the bus."""
        payload = create_tg_message_payload(
            message_id=message.metadata.get("message_id", "0"),
            from_addr=f"tg:{message.chat_id}",
            timestamp=datetime.now(UTC).isoformat(),
            text=message.content,
            sender_id=message.sender_id,
            channel=message.channel,
            username=message.metadata.get("username"),
            full_name=message.metadata.get("full_name"),
        )
        await self.bus.send_message(to=f"tg:{message.chat_id}", payload=payload)

    @property
    def is_running(self) -> bool:
        return self._running
