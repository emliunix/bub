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
from bub.app.runtime import AppRuntime
from bub.channels import ChannelManager, MessageBus, TelegramChannel, TelegramConfig
from bub.cli.interactive import InteractiveCli
from bub.config.settings import load_settings
from bub.integrations.republic_client import build_tape_store
from bub.logging_utils import configure_logging

app = typer.Typer(name="bub", help="Tape-first coding agent CLI", add_completion=False)
TELEGRAM_DISABLED_ERROR = "telegram is disabled; set BUB_TELEGRAM_ENABLED=true"
TELEGRAM_TOKEN_ERROR = "missing telegram token; set BUB_TELEGRAM_TOKEN"  # noqa: S105


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
    from bub.config.settings import load_settings

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


async def _run_once(runtime: AppRuntime, session_id: str, message: str) -> None:
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

    with build_runtime(resolved_workspace, model=model, max_tokens=max_tokens) as runtime:
        if not runtime.settings.telegram_enabled:
            logger.error("telegram.disabled workspace={}", str(resolved_workspace))
            raise typer.BadParameter(TELEGRAM_DISABLED_ERROR)
        if not runtime.settings.telegram_token:
            logger.error("telegram.missing_token workspace={}", str(resolved_workspace))
            raise typer.BadParameter(TELEGRAM_TOKEN_ERROR)

        bus = MessageBus()
        runtime.set_bus(bus)
        manager = ChannelManager(bus, runtime)
        manager.register(
            TelegramChannel(
                bus,
                TelegramConfig(
                    token=runtime.settings.telegram_token,
                    allow_from=set(runtime.settings.telegram_allow_from),
                    allow_chats=set(runtime.settings.telegram_allow_chats),
                    proxy=runtime.settings.telegram_proxy,
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


tape_app = typer.Typer(help="Tape operations")


@tape_app.command("list")
def tape_list(
    workspace: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
) -> None:
    """List all tapes."""
    from rich.console import Console

    resolved_workspace = (workspace or Path.cwd()).resolve()
    settings = load_settings(resolved_workspace)
    store = build_tape_store(settings, resolved_workspace)

    tapes = store.list_tapes()
    console = Console()
    console.print(f"[bold]Tapes in {resolved_workspace}:[/bold]")
    if not tapes:
        console.print("[dim]No tapes found[/dim]")
    for tape_name in tapes:
        entries = store.read(tape_name)
        console.print(f"  {tape_name}: {len(entries or [])} entries")


@tape_app.command("history")
def tape_history(
    name: str = typer.Argument(..., help="Tape name"),
    workspace: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
) -> None:
    """Show tape history."""
    from rich.console import Console

    resolved_workspace = (workspace or Path.cwd()).resolve()
    settings = load_settings(resolved_workspace)
    store = build_tape_store(settings, resolved_workspace)

    entries = store.read(name)
    console = Console()

    if not entries:
        console.print(f"[yellow]No entries in tape '{name}'[/yellow]")
        return

    for entry in entries:
        if entry.kind == "message":
            role = entry.payload.get("role", "?")
            content = entry.payload.get("content", "")[:100]
            console.print(f"[blue]{role}[/blue]: {content}")
        elif entry.kind == "tool_call":
            console.print(f"[yellow]tool_call[/yellow]: {entry.payload.get('calls', [])}")
        elif entry.kind == "tool_result":
            console.print(f"[green]tool_result[/green]: {entry.payload.get('results', [])}")
        elif entry.kind == "anchor":
            console.print(f"[magenta]anchor[/magenta]: {entry.payload.get('name')}")
        elif entry.kind == "event":
            console.print(f"[dim]event[/dim]: {entry.payload.get('name')}")
        elif entry.kind == "error":
            console.print(f"[red]error[/red]: {entry.payload.get('message')}")


@tape_app.command("anchors")
def tape_anchors(
    name: str = typer.Argument(..., help="Tape name"),
    workspace: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
) -> None:
    """List anchors in a tape."""
    from rich.console import Console

    resolved_workspace = (workspace or Path.cwd()).resolve()
    settings = load_settings(resolved_workspace)
    store = build_tape_store(settings, resolved_workspace)

    anchor_list = store.list_anchors()

    console = Console()
    console.print(f"[bold]Anchors in '{name}':[/bold]")
    if not anchor_list:
        console.print("[dim]No anchors found[/dim]")
    for anchor in anchor_list:
        console.print(f"  {anchor.name}: {anchor.state}")


@tape_app.command("fork", hidden=True)
def tape_fork(
    from_tape: str = typer.Argument(..., help="Source tape"),
    to_tape: str = typer.Option(None, "--to", help="New tape name"),
    from_entry: int = typer.Option(None, "--from-entry", help="Fork from entry ID"),
    workspace: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
) -> None:
    """Fork a tape using primitives: create + read + append."""
    import uuid

    from republic import TapeEntry
    from rich.console import Console

    resolved_workspace = (workspace or Path.cwd()).resolve()
    settings = load_settings(resolved_workspace)
    store = build_tape_store(settings, resolved_workspace)

    if not to_tape:
        to_tape = f"{from_tape}_fork_{uuid.uuid4().hex[:8]}"

    # Primitive 1: Read entries from source (with optional entry filter)
    entries = store.read(from_tape, from_entry_id=from_entry)
    if not entries:
        console = Console()
        console.print(f"[red]No entries found in '{from_tape}'[/red]")
        return

    # Primitive 2: Create new tape by appending (auto-creates file)
    for entry in entries:
        # Create new entry with ID starting from 1
        new_entry = TapeEntry(
            id=0,  # Will be assigned by append
            kind=entry.kind,
            payload=dict(entry.payload),
            meta=dict(entry.meta),
        )
        store.append(to_tape, new_entry)

    # Add bootstrap anchor to new tape
    store.append(to_tape, TapeEntry.anchor(name="session/start", state={"owner": "forked", "from_tape": from_tape}))

    console = Console()
    console.print(f"[green]Forked '{from_tape}' → '{to_tape}'[/green]")
    console.print(f"  entries: {len(entries)}")
    if from_entry:
        console.print(f"  from entry: {from_entry}")


app.add_typer(tape_app, name="tape")


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
