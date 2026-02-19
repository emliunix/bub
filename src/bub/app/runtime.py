"""Application runtime and session management."""

from __future__ import annotations

import asyncio
import contextlib
import signal
from collections.abc import AsyncGenerator, Mapping
from contextlib import suppress
from hashlib import md5
from pathlib import Path
from typing import TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import BaseScheduler
from loguru import logger
from republic import LLM

from bub.app.jobstore import JSONJobStore
from bub.app.types import Session, TapeStore
from bub.config.settings import AgentSettings, TapeSettings
from bub.core import AgentLoop, InputRouter, LoopResult, ModelRunner
from bub.integrations.republic_client import build_llm, read_workspace_agents_prompt
from bub.skills import SkillMetadata, discover_skills, load_skill_body
from bub.tape import TapeService
from bub.tools import ProgressiveToolView, ToolRegistry
from bub.tools.builtin import register_builtin_tools

if TYPE_CHECKING:
    pass


def _session_slug(session_id: str) -> str:
    return md5(session_id.encode("utf-8")).hexdigest()[:16]  # noqa: S324


class SessionRuntime:
    """Runtime state for one deterministic session."""

    def __init__(
        self,
        session_id: str,
        loop: AgentLoop,
        tape: TapeService,
        model_runner: ModelRunner,
        tool_view: ProgressiveToolView,
    ) -> None:
        self.session_id = session_id
        self.loop = loop
        self.tape = tape
        self.model_runner = model_runner
        self.tool_view = tool_view

    async def handle_input(self, text: str) -> LoopResult:
        logger.info("session.handle_input.start session_id={}", self.session_id)
        result = await self.loop.handle_input(text)
        logger.info("session.handle_input.complete session_id={}", self.session_id)
        return result

    def reset_context(self) -> None:
        """Clear volatile in-memory context while keeping the same session identity."""
        self.model_runner.reset_context()
        self.tool_view.reset()


class AgentRuntime:
    """Agent runtime that manages multiple session loops."""

    def __init__(
        self,
        workspace: Path,
        agent_settings: AgentSettings,
        tape_store: TapeStore,
        *,
        allowed_tools: set[str] | None = None,
        allowed_skills: set[str] | None = None,
        tape_settings: TapeSettings | None = None,
        workspace_prompt: str | None = None,
        scheduler: BaseScheduler | None = None,
        llm: LLM | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self._agent_settings = agent_settings
        self._allowed_skills = _normalize_name_set(allowed_skills)
        self._allowed_tools = _normalize_name_set(allowed_tools)
        self._store = tape_store
        self.workspace_prompt = workspace_prompt or read_workspace_agents_prompt(self.workspace)
        self._tape_settings = tape_settings or TapeSettings()
        self.scheduler = scheduler or self._default_scheduler()
        self._llm = llm or build_llm(agent_settings, self._store)
        self._sessions: dict[str, SessionRuntime] = {}
        self._active_inputs: set[asyncio.Task[LoopResult]] = set()

    def _default_scheduler(self) -> BaseScheduler:
        job_store = JSONJobStore(self._tape_settings.resolve_home() / "jobs.json")
        return BackgroundScheduler(daemon=True, jobstores={"default": job_store})

    def __enter__(self) -> AgentRuntime:
        if not self.scheduler.running:
            self.scheduler.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.scheduler.running:
            with suppress(Exception):
                self.scheduler.shutdown()

    @property
    def settings(self) -> AgentSettings:
        return self._agent_settings

    @property
    def tape_settings(self) -> TapeSettings:
        return self._tape_settings

    def discover_skills(self) -> list[SkillMetadata]:
        discovered = discover_skills(self.workspace)
        if self._allowed_skills is None:
            return discovered
        return [skill for skill in discovered if skill.name.casefold() in self._allowed_skills]

    def load_skill_body(self, skill_name: str) -> str | None:
        if self._allowed_skills is not None and skill_name.casefold() not in self._allowed_skills:
            return None
        return load_skill_body(skill_name, self.workspace)

    def get_session(self, session_id: str) -> SessionRuntime:
        existing = self._sessions.get(session_id)
        if existing is not None:
            return existing

        logger.info("runtime.get_session.creating_tape session_id={}", session_id)
        tape_name = f"{self._tape_settings.tape_name}:{_session_slug(session_id)}"
        tape = TapeService(self._llm, tape_name, store=self._store)
        logger.info("runtime.get_session.tape_created session_id={}", session_id)
        tape.ensure_bootstrap_anchor()
        logger.info("runtime.get_session.handoff_done session_id={}", session_id)

        logger.info("runtime.get_session.registering_tools session_id={}", session_id)
        registry = ToolRegistry(self._allowed_tools)
        register_builtin_tools(
            registry,
            workspace=self.workspace,
            tape=tape,
            runtime=self,
            session_id=session_id,
        )
        logger.info("runtime.get_session.tools_registered session_id={}", session_id)

        logger.info("runtime.get_session.creating_tool_view session_id={}", session_id)
        tool_view = ProgressiveToolView(registry)
        logger.info("runtime.get_session.tool_view_created session_id={}", session_id)

        logger.info("runtime.get_session.creating_router session_id={}", session_id)
        router = InputRouter(registry, tool_view, tape, self.workspace)
        logger.info("runtime.get_session.router_created session_id={}", session_id)

        logger.info("runtime.get_session.creating_model_runner session_id={}", session_id)
        runner = ModelRunner(
            tape=tape,
            router=router,
            tool_view=tool_view,
            tools=registry.model_tools(),
            list_skills=self.discover_skills,
            load_skill_body=self.load_skill_body,
            model=self._agent_settings.model,
            max_steps=self._agent_settings.max_steps,
            max_tokens=self._agent_settings.max_tokens,
            model_timeout_seconds=self._agent_settings.model_timeout_seconds,
            base_system_prompt=self._agent_settings.system_prompt,
            get_workspace_system_prompt=lambda: self.workspace_prompt,
        )
        logger.info("runtime.get_session.model_runner_created session_id={}", session_id)

        logger.info("runtime.get_session.creating_loop session_id={}", session_id)
        loop = AgentLoop(router=router, model_runner=runner, tape=tape, session_id=session_id)
        logger.info("runtime.get_session.loop_created session_id={}", session_id)

        logger.info("runtime.get_session.creating_session_runtime session_id={}", session_id)
        runtime = SessionRuntime(
            session_id=session_id,
            loop=loop,
            tape=tape,
            model_runner=runner,
            tool_view=tool_view,
        )
        logger.info("runtime.get_session.session_runtime_created session_id={}", session_id)

        self._sessions[session_id] = runtime
        logger.info("runtime.get_session.complete session_id={}", session_id)
        return runtime

    async def handle_input(self, session_id: str, text: str) -> LoopResult:
        logger.info("runtime.handle_input.start session_id={}", session_id)
        session = self.get_session(session_id)
        logger.info("runtime.handle_input.got_session session_id={}", session_id)
        task = asyncio.create_task(session.handle_input(text))
        self._active_inputs.add(task)
        logger.info("runtime.handle_input.task_created session_id={}", session_id)
        try:
            result = await task
            logger.info("runtime.handle_input.complete session_id={}", session_id)
            return result
        finally:
            self._active_inputs.discard(task)

    async def _cancel_active_inputs(self) -> int:
        """Cancel all in-flight input tasks and return canceled count."""
        count = 0
        while self._active_inputs:
            task = self._active_inputs.pop()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            count += 1
        return count

    def reset_session_context(self, session_id: str) -> None:
        """Reset volatile context for an already-created session."""
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.reset_context()

    @contextlib.asynccontextmanager
    async def graceful_shutdown(self) -> AsyncGenerator[asyncio.Event, None]:
        """Async context manager for graceful shutdown.

        Cancels active input tasks and yields an event for shutdown coordination.
        Usage:
            async with runtime.graceful_shutdown() as shutdown_event:
                # ... do work ...
                shutdown_event.set()  # Signal shutdown complete
        """
        canceled = await self._cancel_active_inputs()
        logger.info("runtime.graceful_shutdown canceled={} tasks", canceled)

        shutdown_event = asyncio.Event()
        try:
            yield shutdown_event
        finally:
            if not shutdown_event.is_set():
                shutdown_event.set()

    async def sigterm_handler(self, signal_num: int) -> None:
        """Handle SIGTERM by initiating graceful shutdown."""
        logger.info("runtime.sigterm received signal={}", signal_num)
        asyncio.get_event_loop().stop()

    def setup_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.sigterm_handler(s)))


def _normalize_name_set(values: set[str] | None) -> set[str] | None:
    """Normalize a set of names to lowercase for case-insensitive comparison."""
    if values is None:
        return None
    return {v.casefold() for v in values}


def reset_session_context(sessions: Mapping[str, Session], session_id: str) -> None:
    """Reset volatile context for an already-created session."""
    session = sessions.get(session_id)
    if session is None:
        return
    session.reset_context()


async def cancel_active_inputs(active_inputs: set[asyncio.Task[Any]]) -> int:
    """Cancel all in-flight input tasks and return canceled count."""
    count = 0
    while active_inputs:
        task = active_inputs.pop()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        count += 1
    return count
