"""Type definitions and protocols for the message bus.

This module defines protocols for transport layer to enable testing with mock implementations.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

# Type aliases
Address = str
ClientId = str
ConnectionId = str
MessagePayload = dict[str, Any]
AckDict = dict[str, Any]

# Handler type
MessageHandler = Callable[[Address, MessagePayload], Awaitable[None]]


@runtime_checkable
class Transport(Protocol):
    """Protocol for message transport layer.

    Abstracts the underlying transport mechanism (WebSocket, in-memory, etc.)
    This is the only external interface we need to mock for testing.
    """

    async def send_message(self, message: str) -> None:
        """Send a message string through the transport."""
        ...

    async def receive_message(self) -> str:
        """Receive a message string from the transport."""
        ...


class TestMessage:
    """Simple test message structure for testing message flows."""

    def __init__(
        self,
        message_id: str,
        from_addr: str,
        to: str,
        payload: MessagePayload,
        message_type: str = "test_message",
    ):
        self.message_id = message_id
        self.from_addr = from_addr
        self.to = to
        self.payload = payload
        self.message_type = message_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "messageId": self.message_id,
            "type": self.message_type,
            "from": self.from_addr,
            "to": self.to,
            "content": self.payload,
        }


__all__ = [
    "Address",
    "AckDict",
    "ClientId",
    "ConnectionId",
    "MessageHandler",
    "MessagePayload",
    "TestMessage",
    "Transport",
]
