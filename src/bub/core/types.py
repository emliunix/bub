"""Shared core dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from bub.app.runtime import AgentRuntime
    from bub.channels.base import BaseChannel


@dataclass(frozen=True)
class DetectedCommand:
    """Detected command parsed from a line."""

    kind: str  # internal|shell
    raw: str
    name: str
    args_tokens: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedAssistantMessage:
    """Assistant output split between text and command lines."""

    visible_lines: list[str]
    commands: list[DetectedCommand]


class HookContext(Protocol):
    """Context object passed to hooks."""

    runtime: AgentRuntime

    def register_channel(self, channel: type[BaseChannel]) -> None:
        """Register a custom channel."""

    def default_channels(self) -> list[type[BaseChannel]]:
        """Return the default channels to be registered."""
        ...
