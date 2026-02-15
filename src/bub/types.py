"""Shared type definitions for Bub."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Protocol

from bub.channels.events import InboundMessage, OutboundMessage


class MessageBus(Protocol):
    """Protocol for message bus implementations."""

    async def publish_inbound(self, message: InboundMessage) -> None: ...
    async def publish_outbound(self, message: OutboundMessage) -> None: ...

    async def on_inbound(
        self, handler: Callable[[InboundMessage], Coroutine[Any, Any, None]]
    ) -> Callable[[], None]: ...
    async def on_outbound(
        self, handler: Callable[[OutboundMessage], Coroutine[Any, Any, None]]
    ) -> Callable[[], None]: ...
