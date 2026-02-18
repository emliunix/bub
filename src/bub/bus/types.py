"""Type definitions and protocols for the message bus.

This module defines bus-specific types.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

# Type aliases
Address = str
ClientId = str
ConnectionId = str
MessagePayload = dict[str, Any]
AckDict = dict[str, Any]

# Handler type
MessageHandler = Callable[[Address, MessagePayload], Awaitable[None]]


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
]
