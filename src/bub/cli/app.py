"""Typer CLI entrypoints."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger

from bub.app import build_runtime
from bub.app.runtime import AgentRuntime
from bub.channels import ChannelManager
from bub.channels.bus import MessageBus
from bub.channels.telegram import TelegramChannel, TelegramConfig
from bub.channels.wsbus import AgentBusClient
from bub.cli.bus import bus_app
from bub.cli.interactive import InteractiveCli
from bub.cli.tape import tape_app
from bub.config import BusSettings
from bub.config.settings import AgentSettings, load_settings
from bub.core import LoopResult
from bub.logging_utils import configure_logging

app = typer.Typer(name="bub", help="Tape-first coding agent CLI", add_completion=False)
TELEGRAM_DISABLED_ERROR = "telegram is disabled; set BUB_BUS_TELEGRAM_ENABLED=true"
TELEGRAM_TOKEN_ERROR = "missing telegram token; set BUB_BUS_TELEGRAM_TOKEN"  # noqa: S105
WEBSOCKET_DISABLED_ERROR = "websocket is disabled; set BUB_BUS_WEBSOCKET_ENABLED=true"
WEBSOCKET_URL_ERROR = "missing websocket url; set BUB_BUS_WEBSOCKET_URL"

app.add_typer(tape_app, name="tape")
app.add_typer(bus_app, name="bus")


def _parse_subset(values: list[str] | None) -> set[str] | None:
    if values is None:
        return None

    names: set[str] = set()
    for raw in values:
        for part in raw.split(","):
            name = part.strip()
            if name:
                names.add(name)
    return names or None


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        chat()


@app.command()
def chat(
    workspace: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
    model: Annotated[str | None, typer.Option("--model")] = None,
    max_tokens: Annotated[int | None, typer.Option("--max-tokens")] = None,
    session_id: Annotated[str, typer.Option("--session-id", envvar="BUB_SESSION_ID")] = "cli",
    disable_scheduler: Annotated[bool, typer.Option("--disable-scheduler", envvar="BUB_DISABLE_SCHEDULER")] = False,
) -> None:
    """Run interactive CLI."""

    configure_logging(profile="chat")
    resolved_workspace = (workspace.expanduser() if workspace else Path.cwd()).resolve()
    logger.info(
        "chat.start workspace={} model={} max_tokens={}",
        str(resolved_workspace),
        model or "<default>",
        max_tokens if max_tokens is not None else "<default>",
    )
    with build_runtime(
        resolved_workspace, model=model, max_tokens=max_tokens, enable_scheduler=not disable_scheduler
    ) as runtime:
        cli = InteractiveCli(runtime, session_id=session_id)
        asyncio.run(cli.run())


@app.command()
def idle(
    workspace: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
    model: Annotated[str | None, typer.Option("--model")] = None,
    max_tokens: Annotated[int | None, typer.Option("--max-tokens")] = None,
) -> None:
    """Start the scheduler only, this is a good option for running a completely autonomous agent."""
    from apscheduler.schedulers.blocking import BlockingScheduler

    from bub.app.jobstore import JSONJobStore

    configure_logging(profile="chat")
    resolved_workspace = (workspace or Path.cwd()).resolve()
    logger.info(
        "idle.start workspace={} model={} max_tokens={}",
        str(resolved_workspace),
        model or "<default>",
        max_tokens if max_tokens is not None else "<default>",
    )
    settings = load_settings(resolved_workspace)
    job_store = JSONJobStore(settings.resolve_home() / "jobs.json")
    scheduler = BlockingScheduler(jobstores={"default": job_store})
    try:
        scheduler.start()
    finally:
        logger.info("idle.stop workspace={}", str(resolved_workspace))


@app.command()
def run(
    message: Annotated[str, typer.Argument()],
    workspace: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
    model: Annotated[str | None, typer.Option("--model")] = None,
    max_tokens: Annotated[int | None, typer.Option("--max-tokens")] = None,
    session_id: Annotated[str, typer.Option("--session-id", envvar="BUB_SESSION_ID")] = "cli",
    tools: Annotated[
        list[str] | None,
        typer.Option(
            "--tools",
            help="Allowed tool names (repeatable or comma-separated, supports command and model names).",
        ),
    ] = None,
    skills: Annotated[
        list[str] | None,
        typer.Option(
            "--skills",
            help="Allowed skill names (repeatable or comma-separated).",
        ),
    ] = None,
    disable_scheduler: Annotated[bool, typer.Option("--disable-scheduler", envvar="BUB_DISABLE_SCHEDULER")] = False,
) -> None:
    """Run a single message and exit, useful for quick testing or one-off commands."""

    configure_logging()
    resolved_workspace = (workspace.expanduser() if workspace else Path.cwd()).resolve()
    allowed_tools = _parse_subset(tools)
    allowed_skills = _parse_subset(skills)
    logger.info(
        "run.start workspace={} model={} max_tokens={} allowed_tools={} allowed_skills={}",
        str(resolved_workspace),
        model or "<default>",
        max_tokens if max_tokens is not None else "<default>",
        ",".join(sorted(allowed_tools)) if allowed_tools else "<all>",
        ",".join(sorted(allowed_skills)) if allowed_skills else "<all>",
    )
    with build_runtime(
        resolved_workspace,
        model=model,
        max_tokens=max_tokens,
        allowed_tools=allowed_tools,
        allowed_skills=allowed_skills,
        enable_scheduler=not disable_scheduler,
    ) as runtime:
        asyncio.run(_run_once(runtime, session_id, message))


async def _run_once(runtime: AgentRuntime, session_id: str, message: str) -> None:
    import rich

    async with runtime.graceful_shutdown():
        try:
            result = await runtime.handle_input(session_id, message)
            if result.error:
                rich.print(f"[red]Error:[/red] {result.error}", file=sys.stderr)
            else:
                rich.print(result.assistant_output or result.immediate_output or "")
        except asyncio.CancelledError:
            rich.print("[yellow]Operation interrupted.[/yellow]", file=sys.stderr)


@app.command()
def agent(
    workspace: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
    model: Annotated[str | None, typer.Option("--model")] = None,
    max_tokens: Annotated[int | None, typer.Option("--max-tokens")] = None,
    session_id: Annotated[str, typer.Option("--session-id", envvar="BUB_SESSION_ID")] = "bus",
    bus_url: Annotated[str | None, typer.Option("--bus-url", envvar="BUB_BUS_URL")] = None,
) -> None:
    """Run agent connected to WebSocket message bus.

    This starts an agent that:
    1. Connects to WebSocket bus server
    2. Listens for inbound messages from Telegram
    3. Processes with AgentRuntime
    4. Publishes responses back to bus

    Example:
        # Terminal 1: Start bus server with Telegram
        BUB_BUS_TELEGRAM_ENABLED=true BUB_BUS_TELEGRAM_TOKEN=xxx bub bus serve

        # Terminal 2: Start agent
        BUB_BUS_URL=ws://localhost:7892 bub agent
    """
    configure_logging()
    resolved_workspace = (workspace or Path.cwd()).resolve()

    # Get bus URL from param or env
    url = bus_url or AgentSettings().bus_url
    if not url:
        logger.error("agent.bus_url_required")
        raise typer.BadParameter("bus URL required; set --bus-url or BUB_BUS_URL")

    logger.info(
        "agent.start workspace={} bus_url={} session_id={}",
        str(resolved_workspace),
        url,
        session_id,
    )

    with build_runtime(
        resolved_workspace,
        model=model,
        max_tokens=max_tokens,
        enable_scheduler=False,
    ) as runtime:
        asyncio.run(_run_agent_client(url, runtime, session_id))


async def _run_agent_client(bus_url: str, runtime: AgentRuntime, session_id: str) -> None:
    """Run WebSocket client that processes messages with AgentRuntime."""
    from bub.channels.events import InboundMessage, OutboundMessage

    client = AgentBusClient(bus_url)

    try:
        # Connect to server
        await client.connect()
        await client.initialize(f"agent-{session_id}")
        logger.info("agent.connected url={}", bus_url)

        # Subscribe to inbound messages
        async def handle_inbound(message: InboundMessage) -> None:
            """Process inbound message and send response."""
            logger.info(
                "agent.processing chat_id={} content={}",
                message.chat_id,
                message.content[:50],
            )

            # Process with AgentRuntime
            result: LoopResult = await runtime.handle_input(f"{message.channel}:{message.chat_id}", message.content)

            # Build response
            parts = []
            if result.immediate_output:
                parts.append(result.immediate_output)
            if result.assistant_output:
                parts.append(result.assistant_output)
            if result.error:
                parts.append(f"Error: {result.error}")

            content = "\n\n".join(parts).strip()
            if not content:
                content = "(no response)"

            # Publish outbound message
            await client.publish_outbound(
                OutboundMessage(
                    channel=message.channel,
                    chat_id=message.chat_id,
                    content=content,
                )
            )

            logger.info("agent.responded chat_id={} content_len={}", message.chat_id, len(content))

        # Subscribe to inbound messages
        unsub = await client.on_inbound(handle_inbound)
        logger.info("agent.listening session_id={}", session_id)

        # Keep running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("agent.interrupted")
        finally:
            unsub()

    except Exception:
        logger.exception("agent.error")
        raise
    finally:
        await client.disconnect()
        logger.info("agent.disconnected")


@app.command()
def telegram(
    workspace: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
    model: Annotated[str | None, typer.Option("--model")] = None,
    max_tokens: Annotated[int | None, typer.Option("--max-tokens")] = None,
) -> None:
    """Run Telegram channel with the same agent loop runtime."""

    configure_logging()
    resolved_workspace = (workspace or Path.cwd()).resolve()
    logger.info(
        "telegram.start workspace={} model={} max_tokens={}",
        str(resolved_workspace),
        model or "<default>",
        max_tokens if max_tokens is not None else "<default>",
    )

    bus_settings = BusSettings()

    if not bus_settings.telegram_enabled:
        logger.error("telegram.disabled workspace={}", str(resolved_workspace))
        raise typer.BadParameter(TELEGRAM_DISABLED_ERROR)
    if not bus_settings.telegram_token:
        logger.error("telegram.missing_token workspace={}", str(resolved_workspace))
        raise typer.BadParameter(TELEGRAM_TOKEN_ERROR)

    with build_runtime(resolved_workspace, model=model, max_tokens=max_tokens) as runtime:
        bus = MessageBus()
        manager = ChannelManager(bus, runtime)
        manager.register(
            TelegramChannel(
                bus,
                TelegramConfig(
                    token=bus_settings.telegram_token,
                    allow_from=set(bus_settings.telegram_allow_from),
                    allow_chats=set(bus_settings.telegram_allow_chats),
                    proxy=bus_settings.telegram_proxy,
                ),
            )
        )
        try:
            asyncio.run(_serve_channels(manager))
        except KeyboardInterrupt:
            logger.info("telegram.interrupted")
        except Exception:
            logger.exception("telegram.crash")
            raise
        finally:
            logger.info("telegram.stop workspace={}", str(resolved_workspace))


async def _serve_channels(manager: ChannelManager) -> None:
    channels = sorted(manager.enabled_channels())
    logger.info("channels.start enabled={}", channels)
    await manager.start()
    try:
        async with manager.runtime.graceful_shutdown() as stop_event:
            await stop_event.wait()
    finally:
        await manager.stop()
        logger.info("channels.stop")


if __name__ == "__main__":
    app()
