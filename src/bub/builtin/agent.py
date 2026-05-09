"""Refactored agent using new Republic API (ChatClient + ToolExecutor + AsyncTapeManager).

Key changes from the legacy agent:
- Replaces the deprecated LLM facade with ChatClient + LLMCore
- Tool execution is now the agent's responsibility (via ToolExecutor)
- Uses typed turn results (Finished | ToolCallNeeded) from Republic
- Uses AsyncTapeManager directly instead of LLM.tape()
- Modern Python: match statements, union types, dataclass patterns
"""

from __future__ import annotations

import asyncio
import inspect
import re
import shlex
import time
from collections.abc import AsyncGenerator, AsyncIterator, Collection
from contextlib import AsyncExitStack
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import cached_property
from pathlib import Path
from typing import Any, TypeVar

from loguru import logger
from republic import (
    RepublicError,
    TapeEntry,
)
from republic.auth.openai_codex import openai_codex_oauth_resolver
from republic.clients.chat import ChatClient
from republic.core.errors import ErrorKind
from republic.core.execution import LLMCore
from republic.core.results import (
    AsyncStreamEvents,
    ErrorEvent,
    FinalEvent,
    Finished,
    LLMResult,
    PreparedChat,
    StreamEvent,
    TextEvent,
    ToolCallNeeded,
    TurnResult,
    get_tool_schemas,
)
from republic.tape.session import TapeSession
from republic.tools.context import ToolContext
from republic.tools.executor import ToolExecutor

from bub.builtin.settings import AgentSettings, load_settings
from bub.framework import BubFramework
from bub.skills import discover_skills, render_skills_prompt
from bub.tools import REGISTRY, model_tools, render_tools_prompt
from bub.types import State
from bub.utils import workspace_from_state
from republic.tools.schema import ToolInput

# constants

HINT_RE = re.compile(r"\$([A-Za-z0-9_.-]+)")
_CONTEXT_LENGTH_RE = re.compile(
    r"context.{0,20}(?:length|window)|maximum.{0,20}context"
    r"|token.{0,10}limit|prompt.{0,10}too long|tokens? > \d+ maximum",
    re.IGNORECASE,
)
MAX_AUTO_HANDOFF = 1


class Agent:
    """Refactored agent: ChatClient + ToolExecutor + AsyncTapeManager."""

    def __init__(self, framework: BubFramework) -> None:
        self.settings = load_settings()
        self.framework = framework

    # cached components

    @cached_property
    def _core(self) -> LLMCore:
        provider, model = LLMCore.resolve_model_provider(self.settings.model, None)
        return LLMCore(
            provider=provider,
            model=model,
            fallback_models=self.settings.fallback_models or [],
            max_retries=3,
            api_key=self.settings.api_key,
            api_key_resolver=openai_codex_oauth_resolver(),
            api_base=self.settings.api_base,
            client_args=self.settings.client_args or {},
            api_format=self.settings.api_format,
            verbose=self.settings.verbose,
        )

    @cached_property
    def _chat(self) -> ChatClient:
        return ChatClient(self._core)

    @cached_property
    def _executor(self) -> ToolExecutor:
        return ToolExecutor()

    @cached_property
    def tapes(self):
        from bub.builtin.tape import TapeService
        return TapeService.from_framework(self.framework)

    # public entry points

    async def run(
        self,
        *,
        tape_name: str,
        prompt: str | list[dict],
        state: State,
        model: str | None = None,
        allowed_skills: Collection[str] | None = None,
        allowed_tools: Collection[str] | None = None,
    ) -> str:
        """Run the agent loop (non-streaming). Returns the final text."""
        if not prompt:
            return "error: empty prompt"

        merge = not state.get("session_id", "").startswith("temp/")
        text = prompt if isinstance(prompt, str) else _extract_text_from_parts(prompt)

        async with self.tapes.session(tape_name, merge_back=merge, state=state) as session:
            return await self._loop(
                session, text, state, model,
                allowed_skills, allowed_tools,
            )

    async def run_stream(
        self,
        *,
        tape_name: str,
        prompt: str | list[dict],
        state: State,
        model: str | None = None,
        allowed_skills: Collection[str] | None = None,
        allowed_tools: Collection[str] | None = None,
    ) -> AsyncStreamEvents:
        """Run the agent loop (streaming). Returns a stream of events."""
        if not prompt:
            return _error_stream("error: empty prompt")

        merge = not state.get("session_id", "").startswith("temp/")
        text = prompt if isinstance(prompt, str) else _extract_text_from_parts(prompt)

        stack = AsyncExitStack()
        session = await stack.enter_async_context(self.tapes.session(tape_name, merge_back=merge, state=state))

        inner = self._loop_stream_gen(
            session, text, state, model,
            allowed_skills, allowed_tools,
        )
        return _with_aclose(inner, stack)

    # command handling

    async def run_command(
        self, tape_name: str, prompt: str | list[dict], state: State,
    ) -> str | None:
        """Execute a comma-prefixed internal command. Returns None if not a command."""
        if not isinstance(prompt, str) or not prompt.strip().startswith(","):
            return None

        line = prompt.strip()[1:].strip()
        if not line:
            raise ValueError("empty command")

        name, tokens = _parse_command(line)
        ctx = ToolContext(tape=tape_name, run_id="cmd", state=state)
        start = time.monotonic()
        status, output = "ok", ""

        try:
            match REGISTRY.get(name):
                case None:
                    output = await _await_if_needed(
                        REGISTRY["bash"].run(context=ctx, cmd=line),
                    )
                case tool:
                    args = _parse_args(tokens)
                    kw = dict(args.kwargs)
                    if tool.context:
                        kw["context"] = ctx
                    output = await _await_if_needed(
                        tool.run(*args.positional, **kw),
                    )
            return output if isinstance(output, str) else str(output)
        except Exception as exc:
            status, output = "error", str(exc)
            raise
        finally:
            ms = int((time.monotonic() - start) * 1000)
            await self.tapes.append_event(
                tape_name, "command",
                {
                    "raw": line, "name": name, "status": status,
                    "elapsed_ms": ms, "output": output,
                    "date": datetime.now(UTC).isoformat(),
                },
            )

    async def run_command_stream(
        self, tape_name: str, prompt: str | list[dict], state: State,
    ) -> AsyncStreamEvents | None:
        """Execute a command and wrap the result in a stream. None if not a command."""
        result = await self.run_command(tape_name, prompt, state)
        return None if result is None else _text_stream(result)

    # agent loop (non-streaming)

    async def _loop(
        self,
        session: TapeSession,
        prompt: str,
        state: State,
        model: str | None,
        allowed_skills: Collection[str] | None,
        allowed_tools: Collection[str] | None,
    ) -> str:
        provider, model_id = self._resolve_model(model)
        tools = self._resolve_tools(allowed_tools)
        skills = self._skills_set(allowed_skills)
        renamed = model_tools(tools)
        handoffs_left = MAX_AUTO_HANDOFF

        system_prompt = self._system_prompt(prompt, state, skills)
        prepared = await self._prepare_turn(session, prompt, provider, model_id, system_prompt, renamed)

        for step in range(1, self.settings.max_steps + 1):
            start = time.monotonic()
            logger.info("agent.step step={} tape={}", step, session.name)
            await self._log_step_start(session, step, prepared, prompt)

            try:
                async with asyncio.timeout(self.settings.model_timeout_seconds):
                    turn_result = await session.run(self._chat, prepared)
            except Exception as exc:
                await self._log_step(session, step, start, "error", prepared, error=str(exc))
                raise

            match turn_result:
                case Finished(result):
                    await self._log_step(session, step, start, "ok", prepared)
                    return result.text or ""

                case ToolCallNeeded() as needed:
                    try:
                        prepared = await self._execute_tools(session, needed, renamed, state)
                    except NeedHandOffError as e:
                        if handoffs_left <= 0:
                            raise e.error
                        handoffs_left -= 1
                        logger.warning("auto_handoff tape={} step={}", session.name, step)
                        await session.handoff(e.reason, state=e.state)
                        await self._log_step(
                            session, step, start, "auto_handoff", prepared,
                            error=str(e),
                        )
                        prepared = await self._prepare_turn(session, prompt, provider, model_id, system_prompt, renamed)
                        continue
                    await self._log_step(session, step, start, "continue", prepared)

        raise RuntimeError(f"max_steps_reached={self.settings.max_steps}")

    # agent loop (streaming)

    def _loop_stream_gen(
        self,
        session: TapeSession,
        prompt: str,
        state: State,
        model: str | None,
        allowed_skills: Collection[str] | None,
        allowed_tools: Collection[str] | None,
    ) -> AsyncStreamEvents:
        """Returns an AsyncStreamEvents wrapping the multi-step streaming loop."""

        async def _run_once(prepared: PreparedChat, res: list[TurnResult | None]) -> AsyncIterator[StreamEvent]:

            async with asyncio.timeout(self.settings.model_timeout_seconds):
                stream = await session.stream(self._chat, prepared)

            result_event = None
            async for event in stream:
                match event:
                    case TextEvent():
                        yield event
                    case FinalEvent():
                        result_event = event
                        break
                    case ErrorEvent(error=err):
                        if _is_context_length_error(str(err)):
                            raise NeedHandOffError("auto_handoff/context_overflow",
                                state={
                                    "reason": "context_length_exceeded",
                                    "error": str(err),
                                },
                                error=err)
                        raise err

            if result_event is None:
                raise RuntimeError("stream ended without final event")
            
            res[0] = result_event.result

        async def generator() -> AsyncGenerator[StreamEvent, None]:
            provider, model_id = self._resolve_model(model)
            tools = self._resolve_tools(allowed_tools)
            skills = self._skills_set(allowed_skills)
            renamed = model_tools(tools)
            handoffs_left = MAX_AUTO_HANDOFF

            system_prompt = self._system_prompt(prompt, state, skills)
            prepared = await self._prepare_turn(session, prompt, provider, model_id, system_prompt, renamed)

            for step in range(1, self.settings.max_steps + 1):
                start = time.monotonic()
                logger.info("agent.step step={} tape={}", step, session.name)
                await self._log_step_start(session, step, prepared, prompt)

                try: 
                    res: list[TurnResult | None] = [None]
                    async for event in _run_once(prepared, res):
                        yield event
                    match _assert_not_none(res[0]):
                        case ToolCallNeeded() as needed:
                            prepared = await self._execute_tools(session, needed, renamed, state, run_id=prepared.run_id)
                            await self._log_step(session, step, start, "continue", prepared)
                        case Finished():
                            await self._log_step(session, step, start, "ok", prepared)
                            break

                except NeedHandOffError as e:
                    if handoffs_left > 0:
                        handoffs_left -= 1
                        logger.warning("auto_handoff tape={} step={}", session.name, step)
                        await session.handoff(
                            e.reason,
                            state=e.state,
                        )
                        await self._log_step(
                            session, step, start, "auto_handoff", prepared,
                            error=str(e),
                        )
                        prepared = await self._prepare_turn(session, prompt, provider, model_id, system_prompt, renamed)
                    else:
                        raise e.error
                except Exception as exc:
                    await self._log_step(session, step, start, "error", prepared, error=str(exc))
                    raise
            else:
                raise RuntimeError(f"max_steps_reached={self.settings.max_steps}")
        return AsyncStreamEvents(generator())

    # tape logging

    async def _log_step_start(
        self, session: TapeSession, step: int, prepared: PreparedChat, prompt: Any,
    ) -> None:
        await session.append_event(
            prepared, "loop.step.start",
            {"step": step, "prompt": prompt},
        )

    async def _log_step(
        self,
        session: TapeSession,
        step: int,
        start: float,
        status: str,
        prepared: PreparedChat,
        *,
        error: str | None = None,
    ) -> None:
        data: dict[str, Any] = {
            "step": step,
            "elapsed_ms": int((time.monotonic() - start) * 1000),
            "status": status,
            "date": datetime.now(UTC).isoformat(),
        }
        if error:
            data["error"] = error
        await session.append_event(prepared, "loop.step", data)

    # prompt building

    def _system_prompt(
        self, prompt_text: str, state: State, allowed: set[str] | None,
    ) -> str:
        blocks: list[str] = []
        if sys_prompt := self.framework.get_system_prompt(prompt=prompt_text, state=state):
            blocks.append(sys_prompt)
        if tools_prompt := render_tools_prompt(REGISTRY.values()):
            blocks.append(tools_prompt)
        workspace = workspace_from_state(state)
        if skills_prompt := self._load_skills(prompt_text, workspace, allowed):
            blocks.append(skills_prompt)
        return "\n\n".join(blocks)

    def _load_skills(
        self, prompt: str, workspace: Path, allowed: set[str] | None = None,
    ) -> str:
        index = {
            s.name.casefold(): s
            for s in discover_skills(workspace)
            if allowed is None or s.name.casefold() in allowed
        }
        expanded = set(HINT_RE.findall(prompt)) & set(index)
        return render_skills_prompt(list(index.values()), expanded_skills=expanded)

    # tool / model resolution

    def _resolve_model(self, override: str | None) -> tuple[str, str]:
        """Resolve (provider, model_id) from settings + optional override."""
        return LLMCore.resolve_model_provider(
            override or self.settings.model, None,
        )

    def _resolve_tools(self, allowed: Collection[str] | None) -> list:
        if allowed is None:
            return list(REGISTRY.values())
        names = {n.casefold() for n in allowed}
        return [t for t in REGISTRY.values() if t.name.casefold() in names]

    @staticmethod
    def _skills_set(coll: Collection[str] | None) -> set[str] | None:
        return {s.casefold() for s in coll} if coll else None

    async def _execute_tools(
        self,
        session: TapeSession,
        needed: ToolCallNeeded,
        renamed: list,
        state: State,
        *,
        run_id: str = "",
    ) -> PreparedChat:
        execution = await self._executor.execute_async(
            needed.tool_calls, renamed,
            context=ToolContext(tape=session.name, run_id=run_id, state=state),
        )
        if execution.error and _is_context_length_error(str(execution.error)):
            raise NeedHandOffError(
                "auto_handoff/context_overflow",
                state={
                    "reason": "context_length_exceeded",
                    "error": str(execution.error),
                },
                error=execution.error,
            )
        return await session.add_tool_results(needed, execution.tool_results)

    async def _prepare_turn(
        self,
        session: TapeSession,
        prompt: str,
        provider: str,
        model_id: str,
        system_prompt: str,
        renamed: list,
    ) -> PreparedChat:
        return await session.prepare(
            prompt=prompt,
            provider=provider,
            model=model_id,
            system_prompt=system_prompt,
            tools=get_tool_schemas(renamed),
            max_tokens=self.settings.max_tokens,
            reasoning_effort=self.settings.reasoning_effort,
        )


# helpers


def _is_context_length_error(msg: str) -> bool:
    return bool(_CONTEXT_LENGTH_RE.search(msg))


def _extract_text_from_parts(parts: list[dict]) -> str:
    """Extract plain text from multimodal parts."""
    return "\n".join(
        p.get("text", "") for p in parts if p.get("type") == "text"
    )


async def _await_if_needed(result: Any) -> Any:
    if inspect.isawaitable(result):
        return await result
    return result


@dataclass(frozen=True)
class _Args:
    positional: list[str]
    kwargs: dict[str, Any]


def _parse_command(line: str) -> tuple[str, list[str]]:
    words = shlex.split(line.strip())
    return (words[0], words[1:]) if words else ("", [])


def _parse_args(tokens: list[str]) -> _Args:
    positional: list[str] = []
    kwargs: dict[str, Any] = {}
    hit_kwarg = False
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            kwargs[key] = value
            hit_kwarg = True
        elif hit_kwarg:
            raise ValueError(f"positional '{token}' after keyword args")
        else:
            positional.append(token)
    return _Args(positional, kwargs)


# stream factory helpers


def _text_stream(text: str) -> AsyncStreamEvents:
    """Create a single-shot stream that yields text then final."""

    async def gen() -> AsyncGenerator[StreamEvent, None]:
        yield TextEvent(content=text)
        yield FinalEvent(result=LLMResult(
            request=PreparedChat(model="", provider=""),
            text=text,
        ))

    return AsyncStreamEvents(gen())


def _error_stream(message: str) -> AsyncStreamEvents:
    """Create a stream that yields a single error event."""

    async def gen() -> AsyncGenerator[StreamEvent, None]:
        yield ErrorEvent(error=RepublicError(ErrorKind.INVALID_INPUT, message))

    return AsyncStreamEvents(gen())


def _with_aclose(
    events: AsyncStreamEvents, stack: AsyncExitStack,
) -> AsyncStreamEvents:
    """Wrap a stream so that ``stack.aclose()`` runs after the last event."""

    async def gen() -> AsyncGenerator[StreamEvent, None]:
        async for e in events:
            yield e
        await stack.aclose()

    return AsyncStreamEvents(gen())


class NeedHandOffError(Exception):
    """Raised when the agent needs to hand off to a human (e.g. due to context overflow)."""

    def __init__(self, reason: str, *, error: Exception, state: dict[str, Any] | None = None) -> None:
        super().__init__(f"need_handoff: {reason}")
        self.reason = reason
        self.error = error
        self.state = state or {}


T = TypeVar("T")


def _assert_not_none(value: T | None) -> T:
    if value is None:
        raise RuntimeError("unexpected None value")
    return value