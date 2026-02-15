"""Typer CLI entrypoints."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger

from bub.app import build_runtime
from bub.app.runtime import AgentRuntime
from bub.channels import ChannelManager, MessageBus, TelegramChannel, TelegramConfig
from bub.cli.bus import bus_app
from bub.cli.interactive import InteractiveCli
from bub.cli.tape import tape_app
from bub.config import AgentSettings, BusSettings
from bub.config.settings import load_settings
from bub.logging_utils import configure_logging

app = typer.Typer(name="bub", help="Tape-first coding agent CLI", add_completion=False)
TELEGRAM_DISABLED_ERROR = "telegram is disabled; set BUB_BUS_TELEGRAM_ENABLED=true"
TELEGRAM_TOKEN_ERROR = "missing telegram token; set BUB_BUS_TELEGRAM_TOKEN"  # noqa: S105

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
    resolved_workspace = (workspace or Path.cwd()).resolve()
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
    resolved_workspace = (workspace or Path.cwd()).resolve()
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
) -> None:
    """Run agent loop connected to the WebSocket message bus.

    This starts an agent that listens for inbound messages on the bus
    and publishes responses back. Requires BUB_BUS_URL to be set.
    """
    configure_logging()
    resolved_workspace = (workspace or Path.cwd()).resolve()
    logger.info(
        "agent.start workspace={} model={} max_tokens={} session_id={}",
        str(resolved_workspace),
        model or "<default>",
        max_tokens if max_tokens is not None else "<default>",
        session_id,
    )

    agent_settings = AgentSettings()
    if not agent_settings.bus_url:
        logger.error("agent.bus_url_required set BUB_BUS_URL")
        raise typer.BadParameter("bus URL required; set BUB_BUS_URL")

    with build_runtime(
        resolved_workspace,
        model=model,
        max_tokens=max_tokens,
        enable_scheduler=False,
    ) as runtime:
        session = runtime.get_session(session_id)
        asyncio.run(session.run_loop())


@app.command()
def telegram(
    workspace: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
    model: Annotated[str | None, typer.Option("--model")] = None,
    max_tokens: Annotated[int | None, typer.Option("--max-tokens")] = None,
) -> None:
    """Run Telegram adapter with the same agent loop runtime."""

    configure_logging()
    os.environ["BUB_MESSAGE_CHANNEL"] = "telegram"
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
