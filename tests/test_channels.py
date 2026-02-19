from __future__ import annotations

import asyncio

import pytest

from bub.channels.base import BaseChannel
from bub.channels.manager import ChannelManager


class _Settings:
    telegram_enabled = False
    discord_enabled = False


class _MockBus:
    async def send_message(self, *, to: str, payload: dict) -> None:
        pass


class _Runtime:
    settings = _Settings()


class _FakeChannel(BaseChannel):
    name = "fake"

    def __init__(self, bus) -> None:
        super().__init__(bus)
        self.started = asyncio.Event()
        self.stopped = False

    async def start(self) -> None:
        self.started.set()

    async def stop(self) -> None:
        self.stopped = True

    async def send(self, message) -> None:
        _ = message


@pytest.mark.asyncio
async def test_channel_manager_starts_and_stops_registered_channels() -> None:
    manager = ChannelManager(_MockBus(), _Runtime())  # type: ignore[arg-type]
    fake_channel = _FakeChannel(_MockBus())
    manager.register(fake_channel)

    await manager.start()
    await asyncio.wait_for(fake_channel.started.wait(), timeout=1.0)
    assert list(manager.enabled_channels()) == ["fake"]

    await manager.stop()
    assert fake_channel.stopped is True
