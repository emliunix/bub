import asyncio
import contextlib
from types import SimpleNamespace

import pytest

from bub.channels.base import BaseChannel
from bub.channels.manager import ChannelManager
from bub.cli.app import _serve_channels


class _Settings:
    telegram_enabled = False
    discord_enabled = False


class _MockBus:
    async def send_message(self, *, to: str, payload: dict) -> None:
        pass


class _Runtime:
    settings = _Settings()

    @contextlib.asynccontextmanager
    async def graceful_shutdown(self):
        stop_event = asyncio.Event()
        yield stop_event


class _ChannelRaisesOnStop(BaseChannel):
    name = "bad"

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        raise RuntimeError("stop failure")

    async def send(self, message) -> None:
        _ = message


@pytest.mark.asyncio
async def test_channel_manager_shutdown_propagates_channel_stop_error() -> None:
    manager = ChannelManager(_MockBus(), _Runtime())  # type: ignore[arg-type]
    bad_channel = _ChannelRaisesOnStop(_MockBus())
    manager.register(bad_channel)

    await manager.start()
    # Stop should raise RuntimeError
    with pytest.raises(RuntimeError, match="stop failure"):
        await manager.stop()


@pytest.mark.asyncio
async def test_serve_channels_handles_cancelled_error_from_graceful_shutdown() -> None:
    class _DummyRuntime:
        @contextlib.asynccontextmanager
        async def graceful_shutdown(self):
            stop_event = asyncio.Event()
            current_task = asyncio.current_task()
            waiter = asyncio.create_task(stop_event.wait())
            waiter.add_done_callback(lambda _: current_task.cancel() if current_task else None)
            try:
                self.stop_event = stop_event
                yield stop_event
            finally:
                waiter.cancel()

    class _DummyManager:
        def __init__(self) -> None:
            self.runtime = _DummyRuntime()
            self.calls: list[str] = []

        async def start(self) -> None:
            self.calls.append("start")

        async def stop(self) -> None:
            self.calls.append("stop")

        def enabled_channels(self):
            return []

    manager = _DummyManager()
    task = asyncio.create_task(_serve_channels(manager))  # type: ignore[arg-type]
    await asyncio.sleep(0.05)
    assert manager.calls == ["start"]
    manager.runtime.stop_event.set()
    await asyncio.wait_for(task, timeout=1.0)
    assert manager.calls == ["start", "stop"]
