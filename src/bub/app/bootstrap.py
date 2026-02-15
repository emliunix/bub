"""Runtime bootstrap helpers."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from bub.app.runtime import AgentRuntime
from bub.app.types import TapeStore
from bub.channels.wsbus import AgentBusClient
from bub.config import AgentSettings, TapeSettings
from bub.integrations.republic_client import build_tape_store
from bub.types import MessageBus


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

    if agent_settings.bus_url:
        logger.info("bus.client.create url={}", agent_settings.bus_url)
        bus: MessageBus = AgentBusClient(agent_settings.bus_url)
    else:
        raise ValueError("bus_url is required")

    return AgentRuntime(
        workspace,
        agent_settings,
        store,
        bus,
        allowed_tools=allowed_tools,
        allowed_skills=allowed_skills,
    )
