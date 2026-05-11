"""Idle detection for per-session auto-compaction."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, Callable, Protocol


class TimerHandle(Protocol):
    """Handle for a scheduled timer."""

    def cancel(self) -> None:
        """Cancel the timer."""
        ...


class Timer(Protocol):
    """Timer service. Production: AsyncIOTimer. Tests: ManualTimer."""

    async def call_later(self, delay: float, callback: Callable[[], Any]) -> TimerHandle:
        """Schedule callback after delay seconds. Returns handle for cancellation."""
        ...


class AsyncIOTimer:
    """Production timer using asyncio event loop."""

    async def call_later(self, delay: float, callback: Callable[[], None]) -> asyncio.TimerHandle:
        loop = asyncio.get_running_loop()
        return loop.call_later(delay, callback)


class IdleTracker:
    """Tracks per-session idle state and fires async callbacks."""

    def __init__(self, timer: Timer) -> None:
        self._timer = timer
        self._timers: dict[str, TimerHandle] = {}
        self._sessions: dict[str, tuple[Callable[[], Coroutine[None, None, None]], float]] = {}

    @staticmethod
    def create() -> "IdleTracker":
        """Create IdleTracker with default AsyncIOTimer."""
        return IdleTracker(AsyncIOTimer())

    @staticmethod
    def create_with_timer(timer: Timer) -> "IdleTracker":
        """Create IdleTracker with custom timer (for testing)."""
        return IdleTracker(timer)

    async def register(
        self,
        session_id: str,
        callback: Callable[[], Coroutine[None, None, None]],
        idle_duration: float,
    ) -> None:
        """Register callback for session. Does NOT schedule timer.

        Timer is only scheduled on first heartbeat().
        """
        self.unregister(session_id)
        self._sessions[session_id] = (callback, idle_duration)

    async def heartbeat(self, session_id: str) -> None:
        """Cancel existing timer and reschedule with same duration.

        No-op if session not registered.
        """
        if session_id not in self._sessions:
            return
        callback, duration = self._sessions[session_id]
        if (handle := self._timers.pop(session_id, None)) is not None:
            handle.cancel()
        self._timers[session_id] = await self._timer.call_later(duration, lambda: asyncio.create_task(callback()))

    def unregister(self, session_id: str) -> None:
        """Cancel timer and remove session."""
        if (handle := self._timers.pop(session_id, None)) is not None:
            handle.cancel()
        self._sessions.pop(session_id, None)

    def is_registered(self, session_id: str) -> bool:
        """Check if session is registered."""
        return session_id in self._sessions

    async def start(self) -> None:
        """Async initialization."""

    async def shutdown(self) -> None:
        """Cancel all timers."""
        for handle in self._timers.values():
            handle.cancel()
        self._timers.clear()
        self._sessions.clear()
