"""Runtime bootstrap helpers."""

from __future__ import annotations

from pathlib import Path

from bub.app.runtime import AgentRuntime
from bub.app.types import TapeStore
from bub.config import AgentSettings, TapeSettings
from bub.integrations.republic_client import build_tape_store


def build_runtime(
    workspace: Path,
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    allowed_tools: set[str] | None = None,
    allowed_skills: set[str] | None = None,
    enable_scheduler: bool = True,
) -> AgentRuntime:
    """Build agent runtime for one workspace."""

    agent_settings = AgentSettings()
    tape_settings = TapeSettings()

    if model:
        agent_settings = agent_settings.model_copy(update={"model": model})
    if max_tokens is not None:
        agent_settings = agent_settings.model_copy(update={"max_tokens": max_tokens})

    store: TapeStore = build_tape_store(agent_settings, tape_settings, workspace)

    return AgentRuntime(
        workspace,
        agent_settings,
        store,
        allowed_tools=allowed_tools,
        allowed_skills=allowed_skills,
    )
