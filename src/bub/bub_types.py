"""Shared type definitions for Bub."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Protocol

from bub.channels.events import InboundMessage, OutboundMessage


class MessageBus(Protocol):
    """Protocol for message bus implementations."""

    async def send_message(self, to: str, payload: dict[str, Any]) -> Any: ...
