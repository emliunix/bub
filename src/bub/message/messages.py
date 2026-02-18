"""Message payload definitions for the agent communication protocol.

This module defines all message payloads discriminated by the 'type' field.
All messages follow the structure defined in docs/agent-protocol.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, NotRequired, TypedDict


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
    telegram_message_id: int
    telegram_chat_id: int
    is_group: NotRequired[bool]
    reply_to_telegram_message_id: NotRequired[int | None]


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
    reply_to_message_id: str
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
    telegram_message_id: int = 0
    telegram_chat_id: int = 0
    is_group: bool = False
    reply_to_telegram_message_id: int | None = None

    @property
    def type(self) -> str:
        return "tg_message"


@dataclass
class TgReply:
    """Runtime dataclass for tg_reply."""

    message_id: str
    from_addr: str
    reply_to_message_id: str
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
    telegram_message_id: int = 0,
    telegram_chat_id: int = 0,
    is_group: bool = False,
    reply_to_telegram_message_id: int | None = None,
) -> dict[str, object]:
    """Create a tg_message payload dict."""
    content: dict[str, object] = {
        "text": text,
        "senderId": sender_id,
        "channel": channel,
        "telegram_message_id": telegram_message_id,
        "telegram_chat_id": telegram_chat_id,
        "is_group": is_group,
        "reply_to_telegram_message_id": reply_to_telegram_message_id,
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
    reply_to_message_id: str,
    timestamp: str,
    text: str,
    channel: str,
    chat_id: str,
) -> dict[str, object]:
    """Create a tg_reply payload dict."""
    return {
        "messageId": message_id,
        "type": "tg_reply",
        "from": from_addr,
        "reply_to_message_id": reply_to_message_id,
        "timestamp": timestamp,
        "chat_id": chat_id,
        "content": {
            "text": text,
            "channel": channel,
        },
    }


def make_reply(request: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Factory function to create a reply based on request message type.

    Args:
        request: The incoming message payload (tg_message, etc.)
        data: Additional data for the reply (text, etc.)

    Returns:
        Reply payload appropriate for the message type
    """
    msg_type = request.get("type", "")

    if msg_type == "tg_message":
        return make_telegram_reply(request, data)

    raise ValueError(f"Unknown message type for reply: {msg_type}")


def make_telegram_reply(request: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Create a telegram_reply from a tg_message request.

    Args:
        request: The tg_message payload
        data: Dict with 'text' (required) and optionally other fields

    Returns:
        tg_reply payload with proper metadata binding
    """
    from datetime import UTC, datetime
    import uuid

    content = request.get("content", {})
    chat_id = str(content.get("senderId", ""))  # senderId is chat_id in private chats

    return {
        "messageId": f"msg_{uuid.uuid4().hex}",
        "type": "tg_reply",
        "from": data.get("from", "agent"),
        "reply_to_message_id": request.get("messageId", ""),
        "timestamp": datetime.now(UTC).isoformat(),
        "chat_id": chat_id,
        "content": {
            "text": data.get("text", ""),
            "channel": "telegram",
            "telegram_reply_to_message_id": content.get("telegram_message_id"),  # For Telegram reply threading
        },
    }


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
    telegram_message_id: int
    telegram_chat_id: int
    is_group: NotRequired[bool]
    reply_to_telegram_message_id: NotRequired[int | None]


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
    reply_to_message_id: str
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
    telegram_message_id: int = 0
    telegram_chat_id: int = 0
    is_group: bool = False
    reply_to_telegram_message_id: int | None = None

    @property
    def type(self) -> str:
        return "tg_message"


@dataclass
class TgReply:
    """Runtime dataclass for tg_reply."""

    message_id: str
    from_addr: str
    reply_to_message_id: str
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
    telegram_message_id: int = 0,
    telegram_chat_id: int = 0,
    is_group: bool = False,
    reply_to_telegram_message_id: int | None = None,
) -> dict[str, object]:
    """Create a tg_message payload dict."""
    content: dict[str, object] = {
        "text": text,
        "senderId": sender_id,
        "channel": channel,
        "telegram_message_id": telegram_message_id,
        "telegram_chat_id": telegram_chat_id,
        "is_group": is_group,
        "reply_to_telegram_message_id": reply_to_telegram_message_id,
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
    reply_to_message_id: str,
    timestamp: str,
    text: str,
    channel: str,
    chat_id: str,
) -> dict[str, object]:
    """Create a tg_reply payload dict."""
    return {
        "messageId": message_id,
        "type": "tg_reply",
        "from": from_addr,
        "reply_to_message_id": reply_to_message_id,
        "timestamp": timestamp,
        "chat_id": chat_id,
        "content": {
            "text": text,
            "channel": channel,
        },
    }


def make_reply(request: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Factory function to create a reply based on request message type.

    Args:
        request: The incoming message payload (tg_message, etc.)
        data: Additional data for the reply (text, etc.)

    Returns:
        Reply payload appropriate for the message type
    """
    msg_type = request.get("type", "")

    if msg_type == "tg_message":
        return make_telegram_reply(request, data)

    raise ValueError(f"Unknown message type for reply: {msg_type}")


def make_telegram_reply(request: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Create a telegram_reply from a tg_message request.

    Args:
        request: The tg_message payload
        data: Dict with 'text' (required) and optionally other fields

    Returns:
        tg_reply payload with proper metadata binding
    """
    from datetime import UTC, datetime
    import uuid

    content = request.get("content", {})
    chat_id = str(content.get("senderId", ""))  # senderId is chat_id in private chats

    return {
        "messageId": f"msg_{uuid.uuid4().hex}",
        "type": "tg_reply",
        "from": data.get("from", "agent"),
        "reply_to_message_id": request.get("messageId", ""),
        "timestamp": datetime.now(UTC).isoformat(),
        "chat_id": chat_id,
        "content": {
            "text": data.get("text", ""),
            "channel": "telegram",
            "telegram_reply_to_message_id": content.get("telegram_message_id"),  # For Telegram reply threading
        },
    }

def create_tg_reply_payload(
    message_id: str,
    from_addr: str,
    reply_to_message_id: str,
    timestamp: str,
    text: str,
    channel: str,
    chat_id: str,
) -> dict[str, object]:
    """Create a tg_reply payload dict."""
    return {
        "messageId": message_id,
        "type": "tg_reply",
        "from": from_addr,
        "reply_to_message_id": reply_to_message_id,
        "timestamp": timestamp,
        "chat_id": chat_id,
        "content": {
            "text": text,
            "channel": channel,
        },
    }


def make_reply(request: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Factory function to create a reply based on request message type.

    Args:
        request: The incoming message payload (tg_message, etc.)
        data: Additional data for the reply (text, etc.)

    Returns:
        Reply payload appropriate for the message type
    """
    msg_type = request.get("type", "")

    if msg_type == "tg_message":
        return make_telegram_reply(request, data)

    raise ValueError(f"Unknown message type for reply: {msg_type}")


def make_telegram_reply(request: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Create a telegram_reply from a tg_message request.

    Args:
        request: The tg_message payload
        data: Dict with 'text' (required) and optionally other fields

    Returns:
        tg_reply payload with proper metadata binding
    """
    from datetime import UTC, datetime
    import uuid

    content = request.get("content", {})
    # Use explicit chat_id from content, fallback to senderId for backwards compatibility
    chat_id = str(content.get("chat_id", content.get("senderId", "")))

    return {
        "messageId": f"msg_{uuid.uuid4().hex}",
        "type": "tg_reply",
        "from": data.get("from", "agent"),
        "reply_to_message_id": request.get("messageId", ""),
        "timestamp": datetime.now(UTC).isoformat(),
        "chat_id": chat_id,
        "content": {
            "text": data.get("text", ""),
            "channel": "telegram",
            "telegram_reply_to_message_id": content.get("telegram_message_id"),  # For Telegram reply threading
        },
    }    sender_id: str
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
