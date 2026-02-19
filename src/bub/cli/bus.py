"""Bus CLI commands."""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated

import typer
from loguru import logger

from bub.bus.bus import AgentBusClient
from bub.bus.protocol import AgentBusClientCallbacks, ProcessMessageParams, ProcessMessageResult
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
    from bub.bus.bus import AgentBusServer

    configure_logging(profile="chat")
    bus_settings = BusSettings()

    logger.info("bus.serve starting host={} port={}", bus_settings.host, bus_settings.port)

    server = AgentBusServer.create(server=(bus_settings.host, bus_settings.port))

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
    address: Annotated[
        str, typer.Option("--address", "-a", help="Address for responses (e.g., 'tg:123')")
    ] = f"tg:{DEFAULT_CHAT_ID}",
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
    asyncio.run(_send_and_listen(url, content, chat_id, channel, address, timeout))


async def _send_and_listen(
    url: str, content: str, chat_id: str, channel: str, response_address: str, timeout: int
) -> None:
    received: list[str] = []
    client: AgentBusClient | None = None

    class Callbacks(AgentBusClientCallbacks):
        async def process_message(self, params: ProcessMessageParams) -> ProcessMessageResult:
            msg_content = params.payload.get("content", "")
            received.append(str(msg_content))
            typer.echo(f"\n--- response ---")
            typer.echo(msg_content)
            typer.echo("---")
            return ProcessMessageResult(
                success=True, message="Received", should_retry=False, retry_seconds=0, payload={}
            )

    try:
        client = await AgentBusClient.connect(url, Callbacks())
        # Framework.run() already started by connect()

        await client.initialize(f"bus-send-{chat_id}")
        await client.subscribe(response_address)

        # Send the message
        from datetime import UTC

        message_payload = {
            "messageId": f"msg_{chat_id}_{uuid.uuid4().hex[:8]}",
            "type": "tg_message",
            "from": f"{channel}:{chat_id}",
            "timestamp": datetime.now(UTC).isoformat(),
            "content": {
                "text": content,
                "channel": channel,
                "chat_id": chat_id,
            },
        }

        # Send to a broadcast address that capture will receive
        await client.send_message(to="tg:436026689", payload=message_payload)
        typer.echo(f"Sent: {content}")
        typer.echo(f"Listening on address={response_address} (timeout={timeout}s)...")

        try:
            await asyncio.wait_for(_wait_forever(), timeout=timeout)
        except TimeoutError:
            if not received:
                typer.echo("No response received.", err=True)
    except (ConnectionRefusedError, OSError) as e:
        typer.echo(f"Cannot connect to bus at {url}: {e}", err=True)
        raise typer.Exit(1) from None
    finally:
        if client is not None:
            await client.disconnect()


@bus_app.command("recv")
def bus_recv(
    address: Annotated[str | None, typer.Argument(help="Address pattern to subscribe (e.g., 'tg:*')")] = None,
    bus_url: Annotated[str | None, typer.Option("--bus-url", "-u", envvar="BUB_BUS_URL", help="Bus URL")] = None,
    to: Annotated[
        list[str] | None,
        typer.Option("--to", "-t", help="Address pattern(s) to subscribe to (can be used multiple times)"),
    ] = None,
) -> None:
    """Subscribe to topic(s) and print messages until Ctrl-C.

    Examples:
        bub bus recv "tg:*"                    # Single address
        bub bus recv --to "tg:*" --to "*"     # Multiple addresses
        bub bus recv "*"                       # Wildcard (all messages)
    """
    configure_logging(profile="chat")
    url = bus_url or _resolve_bus_url()

    # Build address list from positional arg and --to options
    addresses: list[str] = []
    if address:
        addresses.append(address)
    if to:
        addresses.extend(to)

    # Default if no addresses specified
    if not addresses:
        addresses = ["tg:*"]

    asyncio.run(_recv_multi(url, addresses))


async def _recv_multi(url: str, addresses: list[str]) -> None:
    client: AgentBusClient | None = None
    received_count = 0

    class Callbacks(AgentBusClientCallbacks):
        async def process_message(self, params: ProcessMessageParams) -> ProcessMessageResult:
            nonlocal received_count
            received_count += 1
            import json

            typer.echo(f"\n{'=' * 70}")
            typer.echo(f"[{received_count}] To: {params.to}")
            typer.echo(f"From: {params.from_}")
            typer.echo(f"Payload:")
            typer.echo(json.dumps(params.payload, indent=2, ensure_ascii=False))
            typer.echo(f"{'=' * 70}")
            return ProcessMessageResult(
                success=True, message="Received", should_retry=False, retry_seconds=0, payload={}
            )

    try:
        client = await AgentBusClient.connect(url, Callbacks())
        # Framework.run() already started by connect()

        await client.initialize("bus-recv")

        for addr in addresses:
            await client.subscribe(addr)

        typer.echo(f"Connected to {url}")
        typer.echo(f"Subscribed to: {', '.join(addresses)}")
        typer.echo("Waiting for messages... (Ctrl+C to stop)")

        try:
            await _wait_forever()
        except KeyboardInterrupt:
            typer.echo("\nInterrupted.")
    except (ConnectionRefusedError, OSError) as e:
        typer.echo(f"Cannot connect to bus at {url}: {e}", err=True)
        raise typer.Exit(1) from None
    finally:
        if client is not None:
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


    bot_instance: Bot | None = None
    client: AgentBusClient | None = None

    # Track assigned agents per chat_id
    chat_agents: dict[str, str] = {}  # chat_id -> agent_client_id
    spawn_pending: dict[str, asyncio.Event] = {}  # chat_id -> Event

    async def send_to_telegram(chat_id: str, content: str) -> None:
        logger.info("telegram.bridge.send_to_telegram chat_id={} bot={}", chat_id, bot_instance)
        if bot_instance is None:
            logger.error("telegram.bridge.send_no_bot chat_id={}", chat_id)
            return
        try:
            # Convert markdown to Telegram MarkdownV2 format
            from telegramify_markdown import markdownify as md

            text = md(content)
            await bot_instance.send_message(chat_id=int(chat_id), text=text, parse_mode="MarkdownV2")
            logger.info("telegram.bridge.sent chat_id={}", chat_id)
        except Exception:
            logger.exception("telegram.bridge.send_error chat_id={}", chat_id)

    async def handle_outbound(to: str, payload: dict) -> None:
        """Handle outbound message to Telegram (to="tg:*")."""
        content_obj = payload.get("content", {})
        # Extract text from content dict (content is {"text": "...", "channel": "..."})
        if isinstance(content_obj, dict):
            content = content_obj.get("text", "")
        else:
            content = str(content_obj)
        chat_id = payload.get("chat_id", "")
        logger.info("telegram.bridge.outbound to={} chat_id={} len={}", to, chat_id, len(content))
        await send_to_telegram(chat_id, content)

    async def handle_spawn_response(to: str, payload: dict) -> None:
        """Handle spawn response from system agent (to="telegram-bridge")."""
        msg_type = payload.get("type", "")
        if msg_type != "spawn_result":
            return

        content = payload.get("content", {})
        success = content.get("success", False)
        agent_id = content.get("client_id", "")

        # Find pending spawn and set the result
        for chat_id, event in list(spawn_pending.items()):
            if success and agent_id:
                chat_agents[chat_id] = agent_id
                logger.info("telegram.bridge.spawn_response chat_id={} agent={}", chat_id, agent_id)
            else:
                logger.error(
                    "telegram.bridge.spawn_failed_response chat_id={} error={}",
                    chat_id,
                    content.get("error", "unknown"),
                )

            event.set()
            break

    async def spawn_agent_for_chat(chat_id: str) -> str | None:
        """Spawn an agent for this chat via system agent.

        Note: System agent handles idempotency - if agent already exists and is
        running, it will return success with the existing agent ID.
        """
        if chat_id in spawn_pending:
            # Wait for existing spawn to complete
            logger.info("telegram.bridge.spawn_waiting chat_id={}", chat_id)
            await spawn_pending[chat_id].wait()
            return chat_agents.get(chat_id)

        # Create pending event
        spawn_pending[chat_id] = asyncio.Event()

        try:
            logger.info("telegram.bridge.spawning_agent chat_id={}", chat_id)

            # Send spawn request to system agent
            spawn_msg = {
                "messageId": f"spawn_{chat_id}_{uuid.uuid4().hex[:8]}",
                "type": "spawn_request",
                "from": "telegram-bridge",
                "timestamp": datetime.now(UTC).isoformat(),
                "content": {
                    "chat_id": chat_id,
                    "channel": "telegram",
                    "channel_type": "telegram",
                },
            }

            # Send to system:spawn
            assert client is not None, "client should be initialized"
            await client.send_message(to="system:spawn", payload=spawn_msg)
            logger.info("telegram.bridge.spawn_request_sent chat_id={}", chat_id)

            # Wait for spawn response (timeout after 35 seconds)
            try:
                await asyncio.wait_for(spawn_pending[chat_id].wait(), timeout=35.0)
            except asyncio.TimeoutError:
                logger.error("telegram.bridge.spawn_timeout chat_id={}", chat_id)
                return None

            agent_id = chat_agents.get(chat_id)
            if agent_id:
                logger.info("telegram.bridge.spawn_success chat_id={} agent={}", chat_id, agent_id)
            else:
                logger.error("telegram.bridge.spawn_failed chat_id={}", chat_id)

            return agent_id

        except Exception as e:
            logger.exception("telegram.bridge.spawn_error")
            return None
        finally:
            del spawn_pending[chat_id]

    # Message handlers - pure processing, no dispatch logic
    async def _process_outbound(to: str, payload: dict) -> None:
        """Process outbound message to Telegram."""
        content_obj = payload.get("content", {})
        if isinstance(content_obj, dict):
            content = content_obj.get("text", "")
        else:
            content = str(content_obj)
        chat_id = payload.get("chat_id", "")
        logger.info("telegram.bridge.outbound to={} chat_id={} len={}", to, chat_id, len(content))
        await send_to_telegram(chat_id, content)

    async def _process_spawn_response(to: str, payload: dict) -> None:
        """Process spawn response from system agent."""
        msg_type = payload.get("type", "")
        if msg_type != "spawn_result":
            return

        content = payload.get("content", {})
        success = content.get("success", False)
        agent_id = content.get("client_id", "")

        for chat_id, event in list(spawn_pending.items()):
            if success and agent_id:
                chat_agents[chat_id] = agent_id
                logger.info("telegram.bridge.spawn_response chat_id={} agent={}", chat_id, agent_id)
            else:
                logger.error(
                    "telegram.bridge.spawn_failed_response chat_id={} error={}",
                    chat_id,
                    content.get("error", "unknown"),
                )
            event.set()
            break

    # Dispatch table - maps address patterns to handlers
    _dispatch_table: dict[str, Callable[[str, dict], Awaitable[None]]] = {
        "tg:": _process_outbound,
        "telegram-bridge": _process_spawn_response,
    }

    async def _dispatch_message(to: str, payload: dict) -> None:
        """Dispatch message to appropriate handler based on address."""
        for pattern, handler in _dispatch_table.items():
            if to.startswith(pattern) or to == pattern:
                await handler(to, payload)
                return
        logger.debug("telegram.bridge.unknown_destination to={}", to)

    # Callbacks implementation
    class Callbacks(AgentBusClientCallbacks):
        async def process_message(self, params: ProcessMessageParams) -> ProcessMessageResult:
            """Entry point from bus - dispatch then return result."""
            await _dispatch_message(params.to, params.payload)
            return ProcessMessageResult(
                success=True, message="Processed", should_retry=False, retry_seconds=0, payload={}
            )

    try:
        client = await AgentBusClient.connect(url, Callbacks())
        logger.info("telegram.bridge.message_loop_started")

        # Now initialize (framework.run() already started by connect())
        await client.initialize("telegram-bridge")
        logger.info("telegram.bridge.initialized")

        # Subscribe to tg:* pattern for outbound messages
        await client.subscribe("tg:*")
        logger.info("telegram.bridge.subscribed_tg")

        # Subscribe to telegram-bridge for spawn responses
        await client.subscribe("telegram-bridge")
        logger.info("telegram.bridge.subscribed_bridge")

        logger.info("telegram.bridge.spawn_handler_registered")

        builder = Application.builder().token(token)

        if proxy:
            logger.info("telegram.bridge.using_proxy url={}", proxy)
            builder = builder.proxy(proxy).get_updates_proxy(proxy)
        else:
            logger.info("telegram.bridge.no_proxy")

        app = builder.build()
        bot_instance = app.bot

        async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if update.message is None:
                return
            chat_id = str(update.message.chat_id)
            if allow_chats and chat_id not in allow_chats:
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

            # Ensure we have an agent for this chat
            agent_id = await spawn_agent_for_chat(chat_id)
            if not agent_id:
                logger.error("telegram.bridge.no_agent chat_id={}", chat_id)
                await update.message.reply_text("Failed to start conversation agent. Please try again.")
                return

            with suppress(Exception):
                await context.bot.send_chat_action(chat_id=int(chat_id), action="typing")

            try:
                # Extract Telegram metadata
                telegram_message_id = update.message.message_id
                telegram_chat_id = update.message.chat.id
                is_group = update.message.chat.type in ["group", "supergroup"]
                reply_to_telegram_message_id = (
                    update.message.reply_to_message.message_id if update.message.reply_to_message else None
                )

                # Send directly to the assigned agent
                assert client is not None, "client should be initialized"
                await client.send_message(
                    to=agent_id,
                    payload={
                        "messageId": f"msg_{uuid.uuid4().hex}",
                        "type": "tg_message",
                        "from": f"tg:{chat_id}",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "content": {
                            "text": text,
                            "senderId": str(user.id),
                            "chat_id": chat_id,
                            "channel": "telegram",
                            "username": user.username,
                            "full_name": user.full_name,
                            "telegram_message_id": telegram_message_id,
                            "telegram_chat_id": telegram_chat_id,
                            "is_group": is_group,
                            "reply_to_telegram_message_id": reply_to_telegram_message_id,
                        },
                    },
                )
                logger.info("telegram.bridge.sent_to_agent chat_id={} agent={}", chat_id, agent_id)
            except Exception:
                logger.exception("telegram.bridge.publish_error")

        app.add_handler(CommandHandler("start", on_start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

        await app.initialize()
        await app.start()
        if app.updater is None:
            raise RuntimeError("Telegram updater not initialized")
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("telegram.bridge.started url={}", url)

        # Keep running until interrupted
        try:
            await _wait_forever()
        except KeyboardInterrupt:
            logger.info("telegram.bridge.stopped")
    finally:
        if client is not None:
            await client.disconnect()
