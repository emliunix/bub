"""Republic integration helpers."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from republic import LLM
from republic.tape.context import TapeContext
from republic.tape.entries import TapeEntry

from bub.app.runtime import TapeStore
from bub.config.settings import AgentSettings, TapeSettings
from bub.tape.context import default_tape_context
from bub.tape.remote import RemoteTapeStore
from bub.tape.store import FileTapeStore

AGENTS_FILE = "AGENTS.md"


def _convert_to_minimax_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert messages to MiniMax-compatible format.

    MiniMax rejects messages with empty or null role fields.
    This function ensures all messages have valid roles.
    """
    converted = []
    for msg in messages:
        role = msg.get("role", "")

        # Handle messages with no role or empty string role
        if not role:
            msg = dict(msg)
            msg["role"] = "user"
            converted.append(msg)
            continue

        converted.append(msg)

    return converted


def _create_minimax_compatible_context(base_context: TapeContext) -> TapeContext:
    """Create a TapeContext that converts messages for MiniMax compatibility."""

    # Get the original select function, or use a default one if None
    # We can't easily access _default_messages from here as it's private in republic.tape.context
    # But we can import build_messages which calls it

    from republic.tape.context import _default_messages

    original_select = base_context.select or (lambda entries, _: _default_messages(entries))

    def minimax_select(entries: Sequence[TapeEntry], context: TapeContext) -> list[dict[str, Any]]:
        # Call the original selector
        messages = original_select(entries, context)
        # Convert the results
        converted = _convert_to_minimax_messages(messages)

        # Debug logging
        import logging

        logger = logging.getLogger("bub.integrations.republic")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("minimax.conversion input_count={} output_count={}", len(messages), len(converted))
            for i, msg in enumerate(converted):
                if not msg.get("role"):
                    logger.error("minimax.invalid_role index={} msg={}", i, msg)

        return converted

    return TapeContext(anchor=base_context.anchor, select=minimax_select)


def build_tape_store(
    agent_settings: AgentSettings,
    tape_settings: TapeSettings,
    workspace: Path,
) -> FileTapeStore | RemoteTapeStore:
    """Build tape store for one workspace.

    If tape_server_url is set in agent_settings, connects to remote tape server.
    Otherwise, uses local FileTapeStore.
    """
    if agent_settings.tape_server_url:
        return RemoteTapeStore(agent_settings.tape_server_url, workspace)

    return FileTapeStore(tape_settings.resolve_home(), workspace)


def _is_minimax_model(model: str) -> bool:
    """Check if model is a MiniMax model."""
    return "minimax" in model.lower()


def build_llm(agent_settings: AgentSettings, store: TapeStore) -> LLM:
    """Build Republic LLM client configured for Bub runtime."""

    client_args = None
    if "azure" in agent_settings.model:
        client_args = {"api_version": "2025-01-01-preview"}

    # Use standard tape context - Bub now uses standard OpenAI-compatible format
    # throughout the tape layer. Provider-specific adaptations happen at the
    # API boundary in the LLM client layer (Republic/any-llm).
    base_context = default_tape_context()

    # Wrap context with MiniMax compatibility if using MiniMax model
    if _is_minimax_model(agent_settings.model):
        context = _create_minimax_compatible_context(base_context)
    else:
        context = base_context

    return LLM(
        agent_settings.model,
        api_key=agent_settings.resolved_api_key,
        api_base=agent_settings.api_base,
        tape_store=store,
        context=context,
        client_args=client_args,
    )


def read_workspace_agents_prompt(workspace: Path) -> str:
    """Read workspace AGENTS.md if present."""

    prompt_file = workspace / AGENTS_FILE
    if not prompt_file.is_file():
        return ""
    try:
        return prompt_file.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
