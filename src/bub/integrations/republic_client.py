"""Republic integration helpers."""

from __future__ import annotations

from pathlib import Path

from republic import LLM

from bub.app.runtime import TapeStore
from bub.config.settings import AgentSettings, TapeSettings
from bub.tape.context import default_tape_context
from bub.tape.remote import RemoteTapeStore
from bub.tape.store import FileTapeStore

AGENTS_FILE = "AGENTS.md"


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


def build_llm(agent_settings: AgentSettings, store: TapeStore) -> LLM:
    """Build Republic LLM client configured for Bub runtime."""

    client_args = None
    if "azure" in agent_settings.model:
        client_args = {"api_version": "2025-01-01-preview"}

    return LLM(
        agent_settings.model,
        api_key=agent_settings.resolved_api_key,
        api_base=agent_settings.api_base,
        tape_store=store,
        context=default_tape_context(),
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
