"""Channel manager."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

from loguru import logger

from bub.channels.base import BaseChannel
from bub.channels.events import InboundMessage, OutboundMessage

if TYPE_CHECKING:
    from bub.app.runtime import AgentRuntime
    from bub.config.settings import BusSettings


class ChannelManager:
    """Coordinate inbound routing and outbound dispatch for channels."""

    def __init__(self, bus: Any, runtime: AgentRuntime, bus_settings: BusSettings | None = None) -> None:
        self.bus = bus
        self._runtime = runtime
        self._bus_settings = bus_settings
        self._channels: dict[str, BaseChannel] = {}
        self._unsub_inbound: Callable[[], None] | None = None
        self._unsub_outbound: Callable[[], None] | None = None

    @property
    def runtime(self) -> AgentRuntime:
        return self._runtime

    @property
    def bus_settings(self) -> BusSettings | None:
        return self._bus_settings

    def register(self, channel: BaseChannel) -> None:
        self._channels[channel.name] = channel

    @property
    def channels(self) -> dict[str, BaseChannel]:
        return dict(self._channels)

    async def start(self) -> None:
        # TODO: Update for new bus API - on_inbound/on_outbound removed
        # For now, these are disabled - need to use subscribe() pattern
        self._unsub_inbound = None
        self._unsub_outbound = None
        logger.info("channel.manager.start channels={}", sorted(self._channels.keys()))
        for channel in self._channels.values():
            await channel.start()

    async def stop(self) -> None:
        logger.info("channel.manager.stop")
        for channel in self._channels.values():
            await channel.stop()
        if self._unsub_inbound is not None:
            self._unsub_inbound()
            self._unsub_inbound = None
        if self._unsub_outbound is not None:
            self._unsub_outbound()
            self._unsub_outbound = None

    async def _process_inbound(self, message: InboundMessage) -> None:
        try:
            result = await self._runtime.handle_input(message.session_id, message.render())
            parts = [part for part in (result.immediate_output, result.assistant_output) if part]
            if result.error:
                parts.append(f"error: {result.error}")
            output = "\n\n".join(parts).strip()
            if not output:
                return

            # Extract message_id for reply functionality in group chats
            reply_to_message_id = message.metadata.get("message_id")

            # TODO: Update for new bus API - publish_outbound removed
            # Need to construct payload and call send_message()
            # For now, just send to channel directly (which already works)
            channel = self._channels.get(message.channel)
            if channel:
                await channel.send(
                    OutboundMessage(
                        channel=message.channel,
                        chat_id=message.chat_id,
                        content=output,
                        metadata={"session_id": message.session_id},
                        reply_to_message_id=reply_to_message_id,
                    )
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "channel.inbound.error channel={} chat_id={} session_id={}",
                message.channel,
                message.chat_id,
                message.session_id,
            )

    async def _process_outbound(self, message: OutboundMessage) -> None:
        try:
            channel = self._channels.get(message.channel)
            if channel is None:
                return
            await channel.send(message)
        except Exception:
            logger.exception(
                "channel.outbound.error channel={} chat_id={}",
                message.channel,
                message.chat_id,
            )

    def enabled_channels(self) -> Iterable[str]:
        return self._channels.keys()

    def default_channels(self) -> list[type[BaseChannel]]:
        """Return the built-in channels."""

        result: list[type[BaseChannel]] = []
        settings = self._bus_settings

        if settings and settings.telegram_enabled:
            from bub.channels.telegram import TelegramChannel

            result.append(TelegramChannel)
        if settings and settings.discord_enabled:
            from bub.channels.discord import DiscordChannel

            result.append(DiscordChannel)
        if settings and settings.websocket_enabled:
            from bub.channels.websocket import WebSocketChannel

            result.append(WebSocketChannel)
        return result            result.append(DiscordChannel)
        if settings and settings.websocket_enabled:
            from bub.channels.websocket import WebSocketChannel

            result.append(WebSocketChannel)
        return result
