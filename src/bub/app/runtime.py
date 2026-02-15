"""Application runtime and session management."""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import os
import signal
from collections.abc import AsyncGenerator, Mapping
from contextlib import suppress
from hashlib import md5
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import BaseScheduler
from loguru import logger
from republic import LLM

from bub.app.jobstore import JSONJobStore
from bub.app.types import Session, TapeStore
from bub.config.settings import AgentSettings, BusSettings, TapeSettings
from bub.core import AgentLoop, InputRouter, LoopResult, ModelRunner
from bub.integrations.republic_client import build_llm, read_workspace_agents_prompt
from bub.skills import SkillMetadata, discover_skills, load_skill_body
from bub.tape import TapeService
from bub.tools import ProgressiveToolView, ToolRegistry
from bub.tools.builtin import register_builtin_tools

if TYPE_CHECKING:
    from bub.channels.manager import ChannelManager
    from bub.types import MessageBus


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
        bus: MessageBus,
    ) -> None:
        self.session_id = session_id
        self.loop = loop
        self.tape = tape
        self.model_runner = model_runner
        self.tool_view = tool_view
        self._bus = bus

    async def handle_input(self, text: str) -> LoopResult:
        return await self.loop.handle_input(text)

    def reset_context(self) -> None:
        """Clear volatile in-memory context while keeping the same session identity."""
        self.model_runner.reset_context()
        self.tool_view.reset()

    async def run_loop(self) -> None:
        """Run the session loop indefinitely with proper lifecycle management."""
        await self._start()
        try:
            await asyncio.Event().wait()
        finally:
            await self._stop()

    async def _start(self) -> None:
        """Start the session: connect to bus and start listening."""
        await self.loop.start()
        logger.info("session.start session_id={}", self.session_id)

    async def _stop(self) -> None:
        """Stop the session: stop listening and disconnect from bus."""
        await self.loop.stop()
        logger.info("session.stop session_id={}", self.session_id)


def reset_session_context(sessions: Mapping[str, Session], session_id: str) -> None:
    """Reset volatile context for an already-created session."""
    session = sessions.get(session_id)
    if session is None:
        return
    session.reset_context()


async def cancel_active_inputs(active_inputs: set[asyncio.Task[None]]) -> int:
    """Cancel all in-flight input tasks and return canceled count."""
    count = 0
    while active_inputs:
        task = active_inputs.pop()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        count += 1
    return count


class AgentRuntime:
    """Agent runtime that manages multiple session loops."""

    def __init__(
        self,
        workspace: Path,
        agent_settings: AgentSettings,
        tape_store: TapeStore,
        bus: MessageBus | None = None,
        *,
        allowed_tools: set[str] | None = None,
        allowed_skills: set[str] | None = None,
        tape_settings: TapeSettings | None = None,
        workspace_prompt: str | None = None,
        scheduler: BaseScheduler | None = None,
        llm: LLM | None = None,
    ) -> None:
        if bus is None:
            raise ValueError("bus is required for AgentRuntime")
        self.workspace = workspace.resolve()
        self._agent_settings = agent_settings
        self._allowed_skills = _normalize_name_set(allowed_skills)
        self._allowed_tools = _normalize_name_set(allowed_tools)
        self._store = tape_store
        self.workspace_prompt = workspace_prompt or read_workspace_agents_prompt(self.workspace)
        self.bus = bus
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
    def bus_settings(self) -> BusSettings | None:
        return None

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

        tape_name = f"{self._tape_settings.tape_name}:{_session_slug(session_id)}"
        tape = TapeService(self._llm, tape_name, store=self._store)
        tape.ensure_bootstrap_anchor()

        registry = ToolRegistry(self._allowed_tools)
        register_builtin_tools(
            registry,
            workspace=self.workspace,
            tape=tape,
            runtime=self,
            session_id=session_id,
        )
        tool_view = ProgressiveToolView(registry)
        router = InputRouter(registry, tool_view, tape, self.workspace)
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
        loop = AgentLoop(router=router, model_runner=runner, tape=tape, session_id=session_id, bus=self.bus)
        runtime = SessionRuntime(
            session_id=session_id,
            loop=loop,
            tape=tape,
            model_runner=runner,
            tool_view=tool_view,
            bus=self.bus,
        )
        self._sessions[session_id] = runtime
        return runtime

    async def handle_input(self, session_id: str, text: str) -> LoopResult:
        session = self.get_session(session_id)
        task = asyncio.create_task(session.handle_input(text))
        self._active_inputs.add(task)
        try:
            return await task
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
        """Run the runtime indefinitely with graceful shutdown."""
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        handled_signals: list[signal.Signals] = []
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop_event.set)
                handled_signals.append(sig)
            except (NotImplementedError, RuntimeError):
                continue
        current_task = asyncio.current_task()
        future = asyncio.ensure_future(stop_event.wait())
        future.add_done_callback(lambda _, task=current_task: task and task.cancel())  # type: ignore[misc]
        try:
            yield stop_event
        finally:
            future.cancel()
            cancelled = await self._cancel_active_inputs()
            if cancelled:
                logger.info("runtime.cancel_inflight count={}", cancelled)
            for sig in handled_signals:
                with suppress(NotImplementedError, RuntimeError):
                    loop.remove_signal_handler(sig)

    def install_hooks(self, channel_manager: ChannelManager) -> None:
        """Install hooks for cross-cutting concerns like channel integration."""
        hooks_module_str = os.getenv("BUB_HOOKS_MODULE")
        if not hooks_module_str:
            return
        try:
            module = importlib.import_module(hooks_module_str)
        except ImportError as e:
            raise ImportError(f"Failed to import hooks module '{hooks_module_str}'") from e
        if not hasattr(module, "install"):
            raise AttributeError(f"Hooks module '{hooks_module_str}' does not have an 'install' function")
        hooks_context = SimpleNamespace(
            runtime=self,
            register_channel=channel_manager.register,
            default_channels=channel_manager.default_channels,
        )
        module.install(hooks_context)


def _normalize_name_set(values: set[str] | None) -> set[str] | None:
    if values is None:
        return None
    return {v.casefold().strip() for v in values}
