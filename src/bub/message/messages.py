"""Message payload definitions for the agent communication protocol.

This module defines all message payloads discriminated by the 'type' field.
All messages follow the structure defined in docs/agent-protocol.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, NotRequired, TypedDict


# ============================================================================
# Spawn Messages
# ============================================================================


class SpawnRequestContent(TypedDict):
    """Content for spawn_request message."""

    chat_id: str
    channel: str
    channel_type: str  # e.g., "telegram", "discord"


class SpawnRequestPayload(TypedDict):
    """Payload for spawn_request message."""

    messageId: str
    type: Literal["spawn_request"]
    from_: str  # Use from_ to avoid keyword conflict
    timestamp: str
    content: SpawnRequestContent


class SpawnResultContent(TypedDict):
    """Content for spawn_result message."""

    success: bool
    client_id: str
    status: str
    error: NotRequired[str]


class SpawnResultPayload(TypedDict):
    """Payload for spawn_result message."""

    messageId: str
    type: Literal["spawn_result"]
    from_: str
    timestamp: str
    content: SpawnResultContent


# ============================================================================
# Telegram Messages
# ============================================================================


class TgMessageContent(TypedDict):
    """Content for tg_message (incoming from Telegram)."""

    text: str
    senderId: str
    channel: str
    username: NotRequired[str]
    full_name: NotRequired[str]


class TgMessagePayload(TypedDict):
    """Payload for tg_message."""

    messageId: str
    type: Literal["tg_message"]
    from_: str
    timestamp: str
    content: TgMessageContent


class TgReplyContent(TypedDict):
    """Content for tg_reply (outgoing to Telegram)."""

    text: str
    channel: str


class TgReplyPayload(TypedDict):
    """Payload for tg_reply."""

    messageId: str
    type: Literal["tg_reply"]
    from_: str
    timestamp: str
    content: TgReplyContent


# ============================================================================
# Union Type for All Messages
# ============================================================================

MessagePayload = SpawnRequestPayload | SpawnResultPayload | TgMessagePayload | TgReplyPayload


# ============================================================================
# Dataclass versions for runtime use
# ============================================================================


@dataclass
class SpawnRequest:
    """Runtime dataclass for spawn_request."""

    message_id: str
    from_addr: str  # 'from' is reserved
    timestamp: str
    chat_id: str
    channel: str
    channel_type: str  # e.g., "telegram", "discord"

    @property
    def type(self) -> str:
        return "spawn_request"


@dataclass
class SpawnResult:
    """Runtime dataclass for spawn_result."""

    message_id: str
    from_addr: str
    timestamp: str
    success: bool
    client_id: str
    status: str
    error: str | None = None

    @property
    def type(self) -> str:
        return "spawn_result"


@dataclass
class TgMessage:
    """Runtime dataclass for tg_message."""

    message_id: str
    from_addr: str
    timestamp: str
    text: str
    sender_id: str
    channel: str
    username: str | None = None
    full_name: str | None = None

    @property
    def type(self) -> str:
        return "tg_message"


@dataclass
class TgReply:
    """Runtime dataclass for tg_reply."""

    message_id: str
    from_addr: str
    timestamp: str
    text: str
    channel: str

    @property
    def type(self) -> str:
        return "tg_reply"


# ============================================================================
# Construction Helpers
# ============================================================================


def create_tg_message_payload(
    message_id: str,
    from_addr: str,
    timestamp: str,
    text: str,
    sender_id: str,
    channel: str,
    username: str | None = None,
    full_name: str | None = None,
) -> dict[str, object]:
    """Create a tg_message payload dict."""
    content: dict[str, object] = {
        "text": text,
        "senderId": sender_id,
        "channel": channel,
    }
    if username is not None:
        content["username"] = username
    if full_name is not None:
        content["full_name"] = full_name
    return {
        "messageId": message_id,
        "type": "tg_message",
        "from": from_addr,
        "timestamp": timestamp,
        "content": content,
    }


def create_tg_reply_payload(
    message_id: str,
    from_addr: str,
    timestamp: str,
    text: str,
    channel: str,
) -> dict[str, object]:
    """Create a tg_reply payload dict."""
    return {
        "messageId": message_id,
        "type": "tg_reply",
        "from": from_addr,
        "timestamp": timestamp,
        "content": {
            "text": text,
            "channel": channel,
        },
    }
