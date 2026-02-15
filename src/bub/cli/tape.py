"""Tape CLI commands."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger
from rich.console import Console

from bub.config.settings import load_settings
from bub.integrations.republic_client import build_tape_store
from bub.logging_utils import configure_logging

tape_app = typer.Typer(help="Tape operations")


@tape_app.command("list")
def tape_list(
    workspace: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
) -> None:
    """List all tapes."""
    resolved_workspace = (workspace or Path.cwd()).resolve()
    settings = load_settings(resolved_workspace)
    store = build_tape_store(settings, settings, resolved_workspace)

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
    resolved_workspace = (workspace or Path.cwd()).resolve()
    settings = load_settings(resolved_workspace)
    store = build_tape_store(settings, settings, resolved_workspace)

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
    resolved_workspace = (workspace or Path.cwd()).resolve()
    settings = load_settings(resolved_workspace)
    store = build_tape_store(settings, settings, resolved_workspace)

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
    from republic import TapeEntry

    resolved_workspace = (workspace or Path.cwd()).resolve()
    settings = load_settings(resolved_workspace)
    store = build_tape_store(settings, settings, resolved_workspace)

    if not to_tape:
        to_tape = f"{from_tape}_fork_{uuid.uuid4().hex[:8]}"

    entries = store.read(from_tape, from_entry_id=from_entry)
    if not entries:
        console = Console()
        console.print(f"[red]No entries found in '{from_tape}'[/red]")
        return

    for entry in entries:
        new_entry = TapeEntry(
            id=0,
            kind=entry.kind,
            payload=dict(entry.payload),
            meta=dict(entry.meta),
        )
        store.append(to_tape, new_entry)

    store.append(to_tape, TapeEntry.anchor(name="session/start", state={"owner": "forked", "from_tape": from_tape}))

    console = Console()
    console.print(f"[green]Forked '{from_tape}' → '{to_tape}'[/green]")
    console.print(f"  entries: {len(entries)}")
    if from_entry:
        console.print(f"  from entry: {from_entry}")


@tape_app.command("serve")
def tape_serve(
    workspace: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
) -> None:
    """Start the tape server."""
    from bub.config import TapeSettings
    from bub.tape.server import TapeServer

    configure_logging(profile="chat")
    resolved_workspace = (workspace or Path.cwd()).resolve()

    settings = TapeSettings()

    logger.info("tape.serve starting")

    server = TapeServer(host=settings.host, port=settings.port)
    try:
        server.start(settings, resolved_workspace)
    except KeyboardInterrupt:
        logger.info("tape.serve stopped")
