"""Channel bus event models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class InboundMessage:
    """Message received from an external channel."""

    channel: str
    sender_id: str
    chat_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def session_id(self) -> str:
        return f"{self.channel}:{self.chat_id}"

    def render(self) -> str:
        data = {"message": self.content, **self.metadata, "sender_id": self.sender_id, "chat_id": self.chat_id}
        return json.dumps(data, ensure_ascii=False)


@dataclass(frozen=True)
class OutboundMessage:
    """Message to be delivered to one external channel."""

    channel: str
    chat_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    reply_to_message_id: int | None = None


@dataclass(frozen=True)
class AgentCompleteEvent:
    """Event emitted when an agent finishes processing."""

    session_id: str
    exit_requested: bool
    steps: int
    error: str | None
    trigger_next: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class AgentSpawnEvent:
    """Event emitted when a new agent session is forked."""

    parent_session_id: str
    child_session_id: str
    from_anchor: str
    intention: dict[str, Any] | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
