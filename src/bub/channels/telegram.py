"""Telegram channel adapter."""

from __future__ import annotations

import asyncio
import html
import re
from dataclasses import dataclass
from typing import Any, ClassVar

from loguru import logger
from telegram import Message, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegramify_markdown import markdownify as md

from bub.channels.base import BaseChannel
from bub.channels.events import InboundMessage, OutboundMessage


def exclude_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _message_type(message: Message) -> str:
    if getattr(message, "text", None):
        return "text"
    if getattr(message, "photo", None):
        return "photo"
    if getattr(message, "audio", None):
        return "audio"
    if getattr(message, "sticker", None):
        return "sticker"
    if getattr(message, "video", None):
        return "video"
    if getattr(message, "voice", None):
        return "voice"
    if getattr(message, "document", None):
        return "document"
    if getattr(message, "video_note", None):
        return "video_note"
    return "unknown"


class BubMessageFilter(filters.MessageFilter):
    GROUP_CHAT_TYPES: ClassVar[set[str]] = {"group", "supergroup"}

    def _content(self, message: Message) -> str:
        return (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()

    def filter(self, message: Message) -> bool | dict[str, list[Any]] | None:
        msg_type = _message_type(message)
        if msg_type == "unknown":
            return False

        # Private chat: process all non-command messages and bot commands.
        if message.chat.type == "private":
            return True

        # Group chat: only process when explicitly addressed to the bot.
        if message.chat.type in self.GROUP_CHAT_TYPES:
            bot = message.get_bot()
            bot_id = bot.id
            bot_username = (bot.username or "").lower()

            mentions_bot = self._mentions_bot(message, bot_id, bot_username)
            reply_to_bot = self._is_reply_to_bot(message, bot_id)

            if msg_type != "text" and not getattr(message, "caption", None):
                return reply_to_bot

            return mentions_bot or reply_to_bot

        return False

    def _mentions_bot(self, message: Message, bot_id: int, bot_username: str) -> bool:
        content = self._content(message).lower()
        mentions_by_keyword = "bub" in content or bool(bot_username and f"@{bot_username}" in content)

        entities = [*(getattr(message, "entities", None) or ()), *(getattr(message, "caption_entities", None) or ())]
        for entity in entities:
            if entity.type == "mention" and bot_username:
                mention_text = content[entity.offset : entity.offset + entity.length]
                if mention_text.lower() == f"@{bot_username}":
                    return True
                continue
            if entity.type == "text_mention" and entity.user and entity.user.id == bot_id:
                return True
        return mentions_by_keyword

    @staticmethod
    def _is_reply_to_bot(message: Message, bot_id: int) -> bool:
        reply_to_message = message.reply_to_message
        if reply_to_message is None or reply_to_message.from_user is None:
            return False
        return reply_to_message.from_user.id == bot_id


@dataclass(frozen=True)
class TelegramConfig:
    """Telegram adapter config."""

    token: str
    allow_from: set[str]
    allow_chats: set[str]
    proxy: str | None = None


class TelegramChannel(BaseChannel):
    """Telegram adapter using long polling mode."""

    name = "telegram"

    def __init__(self, bus: Any, config: TelegramConfig) -> None:
        super().__init__(bus)
        self._config = config
        self._app: Application | None = None
        self._typing_tasks: dict[str, asyncio.Task[None]] = {}

    async def start(self) -> None:
        if not self._config.token:
            raise RuntimeError("telegram token is empty")
        logger.info(
            "telegram.channel.start allow_from_count={} allow_chats_count={} proxy={}",
            len(self._config.allow_from),
            len(self._config.allow_chats),
            self._config.proxy,
        )
        self._running = True
        builder = Application.builder().token(self._config.token)
        if self._config.proxy:
            builder = builder.proxy(self._config.proxy).get_updates_proxy(self._config.proxy)
        self._app = builder.build()
        self._app.add_handler(CommandHandler("start", self._on_start))
        self._app.add_handler(CommandHandler("bub", self._on_text, has_args=True, block=False))
        self._app.add_handler(MessageHandler(BubMessageFilter() & ~filters.COMMAND, self._on_text, block=False))
        await self._app.initialize()
        await self._app.start()
        updater = self._app.updater
        if updater is None:
            return
        await updater.start_polling(drop_pending_updates=True, allowed_updates=["message"])
        logger.info("telegram.channel.polling")

    async def stop(self) -> None:
        self._running = False
        for task in self._typing_tasks.values():
            task.cancel()
        self._typing_tasks.clear()
        if self._app is None:
            return
        updater = self._app.updater
        if updater is not None and updater.running:
            await updater.stop()
        await self._app.stop()
        await self._app.shutdown()
        self._app = None
        logger.info("telegram.channel.stopped")

    async def send(self, message: OutboundMessage) -> None:
        if self._app is None:
            return
        self._stop_typing(message.chat_id)

        # Use expandable blockquote for long messages (over 140 chars)
        MAX_COLLAPSE_LENGTH = 140
        raw_content = message.content
        if len(raw_content) > MAX_COLLAPSE_LENGTH:
            # Long message: wrap in expandable blockquote
            # Telegram HTML mode only supports limited tags: b, strong, i, em, u, ins, s, strike, del, code, pre, a, blockquote
            # For simplicity, escape HTML special chars and use plain text in blockquote
            text = html.escape(raw_content)
            # Convert markdown-style bold/italic/code to HTML tags (basic support)
            # Bold: **text** or __text__
            text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
            text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
            # Italic: *text* or _text_
            text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
            text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)
            # Code block
            text = re.sub(r"```(.+?)```", r"<pre>\1</pre>", text, flags=re.DOTALL)
            # Inline code: `text`
            text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
            text = f"<blockquote expandable>{text}</blockquote>"
            parse_mode = "HTML"
        else:
            # Short message: use MarkdownV2 format
            text = md(raw_content)
            parse_mode = "MarkdownV2"

        # In group chats, reply to original message if reply_to_message_id is provided
        if message.reply_to_message_id is not None:
            await self._app.bot.send_message(
                chat_id=int(message.chat_id),
                text=text,
                parse_mode=parse_mode,
                reply_to_message_id=message.reply_to_message_id,
            )
        else:
            await self._app.bot.send_message(
                chat_id=int(message.chat_id),
                text=text,
                parse_mode=parse_mode,
            )

    async def _on_start(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is None:
            return
        if self._config.allow_chats and str(update.message.chat_id) not in self._config.allow_chats:
            await update.message.reply_text(
                "You are not allowed to chat with me. Please deploy your own instance of Bub"
            )
            return
        await update.message.reply_text("Bub is online. Send text to start.")

    async def _on_text(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is None or update.effective_user is None:
            return
        chat_id = str(update.message.chat_id)
        if self._config.allow_chats and chat_id not in self._config.allow_chats:
            return
        user = update.effective_user
        sender_tokens = {str(user.id)}
        if user.username:
            sender_tokens.add(user.username)
        if self._config.allow_from and sender_tokens.isdisjoint(self._config.allow_from):
            await update.message.reply_text("Access denied.")
            return

        text = update.message.text or ""
        if text.startswith("/bot ") or text.startswith("/bub "):
            text = text[5:]

        logger.info(
            "telegram.channel.inbound chat_id={} sender_id={} username={} content={}",
            chat_id,
            user.id,
            user.username or "",
            text[:100],
        )

        self._start_typing(chat_id)
        try:
            await self.publish_inbound(
                InboundMessage(
                    channel=self.name,
                    sender_id=str(user.id),
                    chat_id=chat_id,
                    content=text,
                    metadata=exclude_none({
                        "username": user.username,
                        "full_name": user.full_name,
                        "message_id": update.message.message_id,
                    }),
                )
            )
        except (asyncio.CancelledError, Exception):
            self._stop_typing(chat_id)
            raise

    def _start_typing(self, chat_id: str) -> None:
        self._stop_typing(chat_id)
        self._typing_tasks[chat_id] = asyncio.create_task(self._typing_loop(chat_id))

    def _stop_typing(self, chat_id: str) -> None:
        task = self._typing_tasks.pop(chat_id, None)
        if task is not None:
            task.cancel()

    async def _typing_loop(self, chat_id: str) -> None:
        try:
            while self._app is not None:
                await self._app.bot.send_chat_action(chat_id=int(chat_id), action="typing")
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("telegram.channel.typing_loop.error chat_id={}", chat_id)
            return
