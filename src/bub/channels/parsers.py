"""Channel message parsers for WebSocket proxy using Pydantic models.

WebSocket acts as a transport proxy - it receives messages from various
channels (Telegram, Discord, etc.) and parses them using Pydantic models
for automatic validation and type coercion.
"""

from __future__ import annotations

from typing import Protocol

from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from bub.channels.events import InboundMessage


class TelegramMessageContent(BaseModel):
    """Content structure for Telegram messages."""

    text: str = Field(..., description="Message text content")
    sender_id: str = Field(..., alias="senderId", description="Telegram user ID of sender")
    chat_id: str = Field(..., description="Telegram chat ID")
    channel: str = Field(default="telegram", description="Channel identifier")
    username: str | None = Field(default=None, description="Telegram username")
    full_name: str | None = Field(default=None, alias="full_name", description="Full name of sender")
    reply_to_message_id: str | None = Field(
        default=None, alias="reply_to_message_id", description="ID of message being replied to"
    )

    model_config = {"populate_by_name": True}


class TelegramMessagePayload(BaseModel):
    """Full payload structure for Telegram messages."""

    type: str = Field(default="tg_message", description="Message type discriminator")
    from_addr: str = Field(..., alias="from", description="Source address")
    timestamp: str = Field(..., description="ISO8601 timestamp")
    content: TelegramMessageContent = Field(..., description="Message content")

    model_config = {"populate_by_name": True}


class DiscordMessageContent(BaseModel):
    """Content structure for Discord messages."""

    text: str = Field(..., description="Message text content")
    sender_id: str = Field(..., alias="senderId", description="Discord user ID of sender")
    channel_id: str = Field(..., alias="channel_id", description="Discord channel ID")
    guild_id: str | None = Field(default=None, alias="guild_id", description="Discord guild/server ID")
    username: str | None = Field(default=None, description="Discord username")
    global_name: str | None = Field(default=None, alias="global_name", description="Discord global display name")

    model_config = {"populate_by_name": True}


class DiscordMessagePayload(BaseModel):
    """Full payload structure for Discord messages."""

    type: str = Field(default="discord_message", description="Message type discriminator")
    from_addr: str = Field(..., alias="from", description="Source address")
    timestamp: str = Field(..., description="ISO8601 timestamp")
    content: DiscordMessageContent = Field(..., description="Message content")

    model_config = {"populate_by_name": True}


class ChannelMessageParser(Protocol):
    """Protocol for channel-specific message parsers."""

    def parse(self, payload: dict) -> InboundMessage | None:
        """Parse payload into InboundMessage.

        Returns None if message is not recognizable or invalid.
        """
        ...


class TelegramMessageParser:
    """Parser for Telegram messages using Pydantic models."""

    def parse(self, payload: dict) -> InboundMessage | None:
        """Parse Telegram message payload using Pydantic validation."""
        try:
            parsed = TelegramMessagePayload.model_validate(payload)
        except ValidationError as e:
            logger.debug("telegram.parse.validation_error error={}", e)
            return None

        # Extract metadata (everything except core fields)
        content_dict = parsed.content.model_dump(exclude={"text", "sender_id", "chat_id", "channel"}, by_alias=True)
        metadata = {k: v for k, v in content_dict.items() if v is not None}

        # Add envelope fields to metadata
        metadata["message_type"] = parsed.type
        metadata["from_addr"] = parsed.from_addr
        metadata["timestamp"] = parsed.timestamp

        return InboundMessage(
            channel="telegram",
            sender_id=parsed.content.sender_id,
            chat_id=parsed.content.chat_id,
            content=parsed.content.text,
            metadata=metadata,
        )


class DiscordMessageParser:
    """Parser for Discord messages using Pydantic models."""

    def parse(self, payload: dict) -> InboundMessage | None:
        """Parse Discord message payload using Pydantic validation."""
        try:
            parsed = DiscordMessagePayload.model_validate(payload)
        except ValidationError as e:
            logger.debug("discord.parse.validation_error error={}", e)
            return None

        # Extract metadata (everything except core fields)
        content_dict = parsed.content.model_dump(exclude={"text", "sender_id", "channel_id", "guild_id"}, by_alias=True)
        metadata = {k: v for k, v in content_dict.items() if v is not None}

        # Add envelope fields to metadata
        metadata["message_type"] = parsed.type
        metadata["from_addr"] = parsed.from_addr
        metadata["timestamp"] = parsed.timestamp

        return InboundMessage(
            channel="discord",
            sender_id=parsed.content.sender_id,
            chat_id=parsed.content.channel_id,
            content=parsed.content.text,
            metadata=metadata,
        )


# Registry of channel parsers
CHANNEL_PARSERS: dict[str, ChannelMessageParser] = {
    "telegram": TelegramMessageParser(),
    "discord": DiscordMessageParser(),
}


def parse_channel_message(payload: dict) -> InboundMessage | None:
    """Parse a channel message using the appropriate parser.

    Dispatches to the correct parser based on payload.content.channel.
    Returns None if the channel is unknown or parsing fails.
    """
    content = payload.get("content")
    if not isinstance(content, dict):
        return None

    channel = content.get("channel")
    if not channel:
        return None

    parser = CHANNEL_PARSERS.get(channel)
    if not parser:
        logger.debug("parse.unknown_channel channel={}", channel)
        return None

    return parser.parse(payload)
