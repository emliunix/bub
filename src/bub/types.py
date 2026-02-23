"""Shared type definitions for Bub."""

from __future__ import annotations

from typing import Any, Protocol


class MessageBus(Protocol):
    """Protocol for message bus implementations."""

    async def send_message(self, to: str, payload: dict[str, Any]) -> Any: ...
