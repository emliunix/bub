"""Bus CLI commands."""

from __future__ import annotations

import asyncio
import sys
from typing import Annotated

import typer
from loguru import logger

from bub.channels.events import InboundMessage, OutboundMessage
from bub.channels.wsbus import AgentBusClient
from bub.config import BusSettings
from bub.logging_utils import configure_logging

bus_app = typer.Typer(help="Bus operations")

DEFAULT_CHAT_ID = "cli"
DEFAULT_CHANNEL = "cli"
DEFAULT_TIMEOUT = 30


def _resolve_bus_url() -> str:
    bus_settings = BusSettings()
    return f"ws://{bus_settings.host}:{bus_settings.port}"


async def _wait_forever() -> None:
    await asyncio.Event().wait()


@bus_app.command("serve")
def bus_serve() -> None:
    """Start the WebSocket bus server."""
    from bub.channels.wsbus import AgentBusServer

    configure_logging(profile="chat")
    bus_settings = BusSettings()

    logger.info("bus.serve starting host={} port={}", bus_settings.host, bus_settings.port)

    server = AgentBusServer(host=bus_settings.host, port=bus_settings.port)

    async def _run() -> None:
        await server.start_server()

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("bus.serve stopped")
        finally:
            await server.stop_server()

    asyncio.run(_run())


@bus_app.command("send")
def bus_send(
    message: Annotated[list[str] | None, typer.Argument(help="Message to send")] = None,
    chat_id: Annotated[str, typer.Option("--chat-id", "-c", help="Chat ID")] = DEFAULT_CHAT_ID,
    channel: Annotated[str, typer.Option("--channel", help="Channel name")] = DEFAULT_CHANNEL,
    topic: Annotated[str, typer.Option("--topic", help="Topic for responses")] = f"tg:{DEFAULT_CHAT_ID}",
    timeout: Annotated[int, typer.Option("--timeout", "-t", help="Receive timeout in seconds")] = DEFAULT_TIMEOUT,
    bus_url: Annotated[str | None, typer.Option("--bus-url", "-u", envvar="BUB_BUS_URL", help="Bus URL")] = None,
) -> None:
    """Send a message to the bus and print responses."""
    configure_logging(profile="chat")
    content = " ".join(message) if message else None
    if not content:
        content = sys.stdin.read().strip()
    if not content:
        typer.echo("No message provided.", err=True)
        raise typer.Exit(1)

    url = bus_url or _resolve_bus_url()
    asyncio.run(_send_and_listen(url, content, chat_id, channel, topic, timeout))


async def _send_and_listen(url: str, content: str, chat_id: str, channel: str, topic: str, timeout: int) -> None:
    client = AgentBusClient(url, auto_reconnect=False)
    received: list[str] = []

    try:
        await client.connect()
        await client.initialize(f"bus-send-{chat_id}")

        async def on_outbound(msg: OutboundMessage) -> None:
            received.append(msg.content)
            typer.echo(f"\n--- response (chat_id={msg.chat_id}) ---")
            typer.echo(msg.content)
            typer.echo("---")

        await client.on_outbound(on_outbound)

        await client.publish_inbound(
            InboundMessage(
                channel=channel,
                sender_id=chat_id,
                chat_id=chat_id,
                content=content,
            )
        )
        typer.echo(f"Sent: {content}")
        typer.echo(f"Listening on topic={topic} (timeout={timeout}s)...")

        try:
            await asyncio.wait_for(_wait_forever(), timeout=timeout)
        except TimeoutError:
            if not received:
                typer.echo("No response received.", err=True)
    except (ConnectionRefusedError, OSError) as e:
        typer.echo(f"Cannot connect to bus at {url}: {e}", err=True)
        raise typer.Exit(1) from None
    finally:
        await client.disconnect()


@bus_app.command("recv")
def bus_recv(
    topic: Annotated[str, typer.Argument(help="Topic pattern to subscribe (e.g., 'tg:*')")] = "tg:*",
    bus_url: Annotated[str | None, typer.Option("--bus-url", "-u", envvar="BUB_BUS_URL", help="Bus URL")] = None,
) -> None:
    """Subscribe to a topic and print messages until Ctrl-C."""
    configure_logging(profile="chat")
    url = bus_url or _resolve_bus_url()
    asyncio.run(_recv(url, topic))


async def _recv(url: str, topic: str) -> None:
    client = AgentBusClient(url, auto_reconnect=False)

    try:
        await client.connect()
        await client.initialize("bus-recv")
        await client.subscribe(topic)
        typer.echo(f"Connected to {url}")
        typer.echo(f"Subscribed to: {topic}")

        async def on_message(topic_pattern: str, payload: dict) -> None:
            import json

            typer.echo(f"\n--- {topic_pattern} ---")
            typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
            typer.echo("---")

        client.on_notification(topic, on_message)

        try:
            await _wait_forever()
        except KeyboardInterrupt:
            typer.echo("\nInterrupted.")
    except (ConnectionRefusedError, OSError) as e:
        typer.echo(f"Cannot connect to bus at {url}: {e}", err=True)
        raise typer.Exit(1) from None
    finally:
        await client.disconnect()


@bus_app.command("telegram")
def bus_telegram(
    token: Annotated[
        str | None, typer.Option("--token", "-t", envvar="BUB_BUS_TELEGRAM_TOKEN", help="Telegram bot token")
    ] = None,
    bus_url: Annotated[str | None, typer.Option("--bus-url", "-u", envvar="BUB_BUS_URL", help="Bus URL")] = None,
    allow_from: Annotated[list[str] | None, typer.Option("--allow-from", help="Allow users by ID/username")] = None,
    allow_chats: Annotated[list[str] | None, typer.Option("--allow-chats", help="Allow chats by ID")] = None,
    proxy: Annotated[
        str | None, typer.Option("--proxy", envvar="BUB_BUS_TELEGRAM_PROXY", help="Telegram proxy URL")
    ] = None,
) -> None:
    """Run Telegram bridge - receives Telegram messages and forwards to bus."""
    configure_logging(profile="chat")

    if not token:
        typer.echo("Telegram token required. Set --token or BUB_BUS_TELEGRAM_TOKEN", err=True)
        raise typer.Exit(1)

    url = bus_url or _resolve_bus_url()
    allow_from_set = set(allow_from) if allow_from else set()
    allow_chats_set = set(allow_chats) if allow_chats else set()

    asyncio.run(_run_telegram_bridge(url, token, allow_from_set, allow_chats_set, proxy))


async def _run_telegram_bridge(  # noqa: C901
    url: str,
    token: str,
    allow_from: set[str],
    allow_chats: set[str],
    proxy: str | None,
) -> None:
    from contextlib import suppress

    from telegram import Bot, Update
    from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

    from bub.channels.events import InboundMessage

    client = AgentBusClient(url, auto_reconnect=True)
    bot_instance: Bot | None = None

    async def send_to_telegram(chat_id: str, content: str) -> None:
        logger.info("telegram.bridge.send_to_telegram chat_id={} bot={}", chat_id, bot_instance)
        if bot_instance is None:
            logger.error("telegram.bridge.send_no_bot chat_id={}", chat_id)
            return
        try:
            await bot_instance.send_message(chat_id=int(chat_id), text=content)
            logger.info("telegram.bridge.sent chat_id={}", chat_id)
        except Exception:
            logger.exception("telegram.bridge.send_error chat_id={}", chat_id)

    async def handle_outbound(msg: OutboundMessage) -> None:
        logger.info("telegram.bridge.outbound chat_id={} len={}", msg.chat_id, len(msg.content))
        await send_to_telegram(msg.chat_id, msg.content)

    try:
        await client.connect()
        await client.initialize("telegram-bridge")

        await client.on_outbound(handle_outbound)

        builder = Application.builder().token(token)
        if proxy:
            builder = builder.proxy(proxy).get_updates_proxy(proxy)

        app = builder.build()
        bot_instance = app.bot

        async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if update.message is None:
                return
            if allow_chats and str(update.message.chat_id) not in allow_chats:
                await update.message.reply_text("You are not allowed.")
                return
            await update.message.reply_text("Bub is online.")

        async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if update.message is None or update.effective_user is None:
                return
            chat_id = str(update.message.chat_id)
            if allow_chats and chat_id not in allow_chats:
                return
            user = update.effective_user
            sender_tokens = {str(user.id)}
            if user.username:
                sender_tokens.add(user.username)
            if allow_from and sender_tokens.isdisjoint(allow_from):
                await update.message.reply_text("Access denied.")
                return

            text = update.message.text or ""
            if text.startswith("/bot ") or text.startswith("/bub "):
                text = text[5:]

            logger.info("telegram.bridge.inbound chat_id={} content={}", chat_id, text[:50])

            with suppress(Exception):
                await context.bot.send_chat_action(chat_id=int(chat_id), action="typing")

            try:
                await client.publish_inbound(
                    InboundMessage(
                        channel="telegram",
                        sender_id=str(user.id),
                        chat_id=chat_id,
                        content=text,
                        metadata={"username": user.username, "full_name": user.full_name},
                    )
                )
            except Exception:
                logger.exception("telegram.bridge.publish_error")

        app.add_handler(CommandHandler("start", on_start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("telegram.bridge.started url={}", url)

        # Explicitly subscribe to outbound
        sub_result = await client.subscribe("outbound:*")
        logger.info("telegram.bridge.subscribed result={}", sub_result)

        try:
            await _wait_forever()
        except KeyboardInterrupt:
            logger.info("telegram.bridge.stopped")
    finally:
        await client.disconnect()
