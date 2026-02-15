"""Discord channel adapter."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, ClassVar

import discord
from discord.ext import commands
from loguru import logger

from bub.channels.base import BaseChannel
from bub.channels.events import InboundMessage, OutboundMessage


def exclude_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


class BubMessageFilter:
    """Message filter for Discord."""

    def __init__(self, config: "DiscordConfig") -> None:
        self._config = config

    def filter(self, message: discord.Message) -> bool:
        # Don't process bot messages
        if message.author.bot:
            return False

        # Check if channel is allowed
        if self._config.allow_channels and str(message.channel.id) not in self._config.allow_channels:
            return False

        # Check if author is allowed
        author_tokens = {str(message.author.id)}
        if message.author.name:
            author_tokens.add(message.author.name)
        if message.author.global_name:
            author_tokens.add(message.author.global_name)

        if self._config.allow_from and author_tokens.isdisjoint(self._config.allow_from):
            return False

        # Process commands starting with the prefix or plain text
        if message.content.startswith(self._config.command_prefix):
            return True

        # In DMs, process all messages
        if isinstance(message.channel, discord.DMChannel):
            return True

        # In guilds, only process messages that mention the bot
        if isinstance(message.channel, (discord.TextChannel, discord.Thread)):
            # Check if bot is mentioned
            if message.mentions:
                for mention in message.mentions:
                    if mention.bot:
                        return True
            # Check for role mentions
            if message.role_mentions:
                return True

        return False


@dataclass(frozen=True)
class DiscordConfig:
    """Discord adapter config."""

    token: str
    allow_from: set[str]
    allow_channels: set[str]
    command_prefix: str = "!"
    proxy: str | None = None


class DiscordChannel(BaseChannel):
    """Discord adapter based on discord.py."""

    name = "discord"

    def __init__(self, bus: Any, config: DiscordConfig) -> None:
        super().__init__(bus)
        self._config = config
        self._bot: commands.Bot | None = None

    async def start(self) -> None:
        if not self._config.token:
            raise RuntimeError("discord token is empty")

        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        intents.guilds = True
        intents.dm_messages = True

        self._bot = commands.Bot(
            command_prefix=self._config.command_prefix,
            intents=intents,
            help_command=None,
        )

        bot = self._bot
        message_filter = BubMessageFilter(self._config)

        @bot.event
        async def on_ready() -> None:
            if bot.user:
                logger.info("discord.ready user={} id={}", str(bot.user), bot.user.id)
            else:
                logger.info("discord.ready user=unknown")

        @bot.event
        async def on_message(message: discord.Message) -> None:
            await bot.process_commands(message)

            if not message_filter.filter(message):
                return

            content = message.content or ""
            # Strip command prefix if present
            if content.startswith(self._config.command_prefix):
                content = content[len(self._config.command_prefix) :].strip()

            logger.info(
                "discord.inbound channel_id={} author_id={} author_name={} content={}",
                message.channel.id,
                message.author.id,
                message.author.name,
                content[:100],
            )

            try:
                await self.publish_inbound(
                    InboundMessage(
                        channel=self.name,
                        sender_id=str(message.author.id),
                        chat_id=str(message.channel.id),
                        content=content,
                        metadata=exclude_none({
                            "username": message.author.name,
                            "global_name": message.author.global_name,
                            "message_id": str(message.id),
                            "guild_id": str(message.guild.id) if message.guild else None,
                        }),
                    )
                )
            except Exception:
                logger.exception("discord.publish_inbound.error")

            content = message.content or ""
            # Strip command prefix if present
            if content.startswith(self._config.command_prefix):
                content = content[len(self._config.command_prefix) :].strip()

            logger.info(
                "discord.inbound channel_id={} author_id={} author_name={} content={}",
                message.channel.id,
                message.author.id,
                message.author.name,
                content[:100],
            )

            try:
                await self.publish_inbound(
                    InboundMessage(
                        channel=self.name,
                        sender_id=str(message.author.id),
                        chat_id=str(message.channel.id),
                        content=content,
                        metadata=exclude_none({
                            "username": message.author.name,
                            "global_name": message.author.global_name,
                            "message_id": str(message.id),
                            "guild_id": str(message.guild.id) if message.guild else None,
                        }),
                    )
                )
            except Exception:
                logger.exception("discord.publish_inbound.error")

        logger.info(
            "discord.start allow_from_count={} allow_channels_count={}",
            len(self._config.allow_from),
            len(self._config.allow_channels),
        )
        try:
            await self._bot.start(self._config.token)
        finally:
            self._bot = None
            logger.info("discord.stopped")

    async def stop(self) -> None:
        self._running = False
        if self._bot is None:
            return
        await self._bot.close()

    async def send(self, message: OutboundMessage) -> None:
        if self._bot is None:
            return

        channel_id = int(message.chat_id)
        channel = self._bot.get_channel(channel_id)
        if channel is None:
            logger.warning("discord.send.channel_not_found channel_id={}", channel_id)
            return

        # Only send to messageable channels (TextChannel, Thread, DMChannel)
        if not isinstance(channel, discord.abc.Messageable):
            logger.warning("discord.send.not_messageable channel_id={} type={}", channel_id, type(channel).__name__)
            return

        # Split long messages (Discord limit is 2000 chars)
        MAX_MESSAGE_LENGTH = 2000
        content = message.content

        for i in range(0, len(content), MAX_MESSAGE_LENGTH):
            chunk = content[i : i + MAX_MESSAGE_LENGTH]
            try:
                await channel.send(chunk)
            except discord.Forbidden:
                logger.warning("discord.send.forbidden channel_id={}", channel_id)
            except discord.HTTPException as e:
                logger.error("discord.send.error channel_id={} error={}", channel_id, e)
