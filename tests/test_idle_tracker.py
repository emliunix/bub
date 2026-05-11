"""Tests for IdleTracker."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from bub.channels.idle_tracker import AsyncIOTimer, IdleTracker, Timer


class ManualTimerHandle:
    """Test double for asyncio.TimerHandle."""

    def __init__(self, callback: Any) -> None:
        self._callback = callback
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def fire(self) -> None:
        if not self._cancelled:
            self._callback()


class ManualTimer:
    """Test double for Timer. Manually controlled time."""

    def __init__(self) -> None:
        self._scheduled: list[tuple[float, Any, ManualTimerHandle]] = []
        self._time = 0.0

    async def call_later(self, delay: float, callback: Any) -> ManualTimerHandle:
        handle = ManualTimerHandle(callback)
        self._scheduled.append((self._time + delay, callback, handle))
        return handle

    def advance(self, seconds: float) -> None:
        self._time += seconds
        for when, callback, handle in list(self._scheduled):
            if when <= self._time and not handle.cancelled:
                handle.fire()
                self._scheduled.remove((when, callback, handle))

    @property
    def scheduled_count(self) -> int:
        return sum(1 for _, _, h in self._scheduled if not h.cancelled)


@pytest.fixture
def manual_timer() -> ManualTimer:
    return ManualTimer()


class TestIdleTrackerRegister:
    """Tests for IdleTracker.register()."""

    @pytest.mark.asyncio
    async def test_does_not_schedule_timer(self, manual_timer: ManualTimer) -> None:
        tracker = IdleTracker.create_with_timer(manual_timer)
        callback = AsyncMock()

        await tracker.register("s1", callback, 60.0)

        assert manual_timer.scheduled_count == 0
        assert not callback.called

    @pytest.mark.asyncio
    async def test_stores_session(self, manual_timer: ManualTimer) -> None:
        tracker = IdleTracker.create_with_timer(manual_timer)
        callback = AsyncMock()

        await tracker.register("s1", callback, 60.0)

        assert tracker.is_registered("s1")


class TestIdleTrackerHeartbeat:
    """Tests for IdleTracker.heartbeat()."""

    @pytest.mark.asyncio
    async def test_schedules_timer_on_first_heartbeat(self, manual_timer: ManualTimer) -> None:
        tracker = IdleTracker.create_with_timer(manual_timer)
        callback = AsyncMock()

        await tracker.register("s1", callback, 60.0)
        await tracker.heartbeat("s1")

        assert manual_timer.scheduled_count == 1

    @pytest.mark.asyncio
    async def test_callback_fires_after_advance(self, manual_timer: ManualTimer) -> None:
        tracker = IdleTracker.create_with_timer(manual_timer)
        callback = AsyncMock()

        await tracker.register("s1", callback, 60.0)
        await tracker.heartbeat("s1")
        manual_timer.advance(60.0)

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_resets_timer(self, manual_timer: ManualTimer) -> None:
        tracker = IdleTracker.create_with_timer(manual_timer)
        callback = AsyncMock()

        await tracker.register("s1", callback, 60.0)
        await tracker.heartbeat("s1")
        manual_timer.advance(30.0)
        await tracker.heartbeat("s1")
        manual_timer.advance(30.0)

        callback.assert_not_called()
        manual_timer.advance(30.0)
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_noop_if_not_registered(self, manual_timer: ManualTimer) -> None:
        tracker = IdleTracker.create_with_timer(manual_timer)

        await tracker.heartbeat("s1")

        assert manual_timer.scheduled_count == 0

    @pytest.mark.asyncio
    async def test_different_sessions_independent(self, manual_timer: ManualTimer) -> None:
        tracker = IdleTracker.create_with_timer(manual_timer)
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        await tracker.register("s1", callback1, 30.0)
        await tracker.register("s2", callback2, 60.0)
        await tracker.heartbeat("s1")
        await tracker.heartbeat("s2")
        manual_timer.advance(45.0)

        callback1.assert_called_once()
        assert not callback2.called


class TestIdleTrackerUnregister:
    """Tests for IdleTracker.unregister()."""

    @pytest.mark.asyncio
    async def test_cancels_timer(self, manual_timer: ManualTimer) -> None:
        tracker = IdleTracker.create_with_timer(manual_timer)
        callback = AsyncMock()

        await tracker.register("s1", callback, 60.0)
        await tracker.heartbeat("s1")
        tracker.unregister("s1")
        manual_timer.advance(60.0)

        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_noop_if_not_registered(self, manual_timer: ManualTimer) -> None:
        tracker = IdleTracker.create_with_timer(manual_timer)

        tracker.unregister("s1")

        assert manual_timer.scheduled_count == 0


class TestIdleTrackerShutdown:
    """Tests for IdleTracker.shutdown()."""

    @pytest.mark.asyncio
    async def test_cancels_all_timers(self, manual_timer: ManualTimer) -> None:
        tracker = IdleTracker.create_with_timer(manual_timer)
        callback = AsyncMock()

        await tracker.register("s1", callback, 60.0)
        await tracker.heartbeat("s1")
        await tracker.shutdown()
        manual_timer.advance(60.0)

        callback.assert_not_called()
        assert manual_timer.scheduled_count == 0


class TestAsyncIOTimer:
    """Tests for AsyncIOTimer production implementation."""

    @pytest.mark.asyncio
    async def test_call_later_returns_timer_handle(self) -> None:
        timer = AsyncIOTimer()
        called = asyncio.Event()

        handle = await timer.call_later(0.01, called.set)

        assert isinstance(handle, asyncio.TimerHandle)
        await asyncio.wait_for(called.wait(), timeout=0.1)
