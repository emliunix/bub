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
import functools
import inspect
import re
import shlex
import time
from collections.abc import AsyncGenerator, AsyncIterator, Collection, Coroutine
from contextlib import AsyncExitStack
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import cached_property
from pathlib import Path
from typing import Any, Callable, TypeVar

from loguru import logger
from republic import (
    RepublicError,
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
from republic.tape.context import ReasoningStrategy
from republic.tape.entries import TapeEntry
from republic.tape.session import TapeSession, prompt_entry
from republic.tools.context import ToolContext
from republic.tools.executor import ToolExecutor

from bub.builtin.settings import AgentSettings, load_settings
from bub.framework import BubFramework
from bub.skills import discover_skills, render_skills_prompt
from bub.tools import REGISTRY, model_tools, render_tools_prompt
from bub.types import State
from bub.utils import workspace_from_state
from republic.tools.schema import Tool, ToolInput
from republic.utils import ensure_drained

# constants

HINT_RE = re.compile(r"\$([A-Za-z0-9_.-]+)")
_CONTEXT_LENGTH_RE = re.compile(
    r"context.{0,20}(?:length|window)|maximum.{0,20}context"
    r"|token.{0,10}limit|prompt.{0,10}too long|tokens? > \d+ maximum",
    re.IGNORECASE,
)
MAX_AUTO_HANDOFF = 1


T = TypeVar("T")

# Prompt can be multi modal, where it's [{type: text, content: "xxx"}]

type Prompt = str | list[dict[str, Any]]


CONTEXT_EXCEEDED_HAND_OFF_PROMPT = """
The context length limit has been exceeded. An auto handoff anchor was inserted and context truncated.
"""


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
        prompt: Prompt,
        steering: asyncio.Queue[Prompt] | None,
        state: State,
        model: str | None = None,
        allowed_skills: Collection[str] | None = None,
        allowed_tools: Collection[str] | None = None,
    ) -> str:
        """Run the agent loop (non-streaming). Returns the final text."""

        get_prompts = mk_get_prompts(prompt, steering)

        return await self._loop(
            tape_name, get_prompts, state, model,
            allowed_skills, allowed_tools,
        )

    async def run_stream(
        self,
        *,
        tape_name: str,
        prompt: Prompt,
        steering: asyncio.Queue[Prompt] | None,
        state: State,
        model: str | None = None,
        allowed_skills: Collection[str] | None = None,
        allowed_tools: Collection[str] | None = None,
    ) -> AsyncStreamEvents[Finished]:
        """Run the agent loop (streaming). Returns a stream of events."""

        stack = AsyncExitStack()

        get_prompts = mk_get_prompts(prompt, steering)

        inner = self._loop_stream_gen(
            tape_name, get_prompts, state, model,
            allowed_skills, allowed_tools,
        )
        return inner

    # command handling

    async def run_command(
        self, tape_name: str, prompt: Prompt, state: State,
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
        self, tape_name: str, prompt: Prompt, state: State,
    ) -> AsyncStreamEvents[Finished] | None:
        """Execute a command and wrap the result in a stream. None if not a command."""
        try:
            if (result := await self.run_command(tape_name, prompt, state)) is not None:
                return AsyncStreamEvents.from_iter([TextEvent(content=result)])
        except Exception as exc:
            return AsyncStreamEvents.from_iter([ErrorEvent(error=RepublicError(ErrorKind.TEMPORARY, str(exc)))])

    # agent loop (non-streaming)

    async def _loop(
        self,
        tape_name: str,
        get_prompts: Callable[[], Coroutine[Any, Any, list[str]]],
        state: State,
        model: str | None,
        allowed_skills: Collection[str] | None,
        allowed_tools: Collection[str] | None,
    ) -> str:

        tools = model_tools(self._resolve_tools(allowed_tools))
        mk_chat = self._prepare_turn(state, model, allowed_skills, tools)
        handoffs_left = MAX_AUTO_HANDOFF
        
        async def _step(session: TapeSession, start: float, step: int, chat: PreparedChat) -> str | PreparedChat:
            nonlocal handoffs_left
            try:
                async with asyncio.timeout(self.settings.model_timeout_seconds):
                    turn_result = await session.run(self._chat, chat)
            except Exception as exc:
                if _is_context_length_error(str(exc)):
                    if handoffs_left <= 0:
                        raise RepublicError(ErrorKind.TEMPORARY, "max auto handoffs reached", details={"exc": exc})
                    handoffs_left -= 1
                    logger.warning("auto_handoff tape={} step={}", tape_name, step)
                    return await self._auto_handoff(functools.partial(mk_chat, session), exc, **chat.metas)
                else:
                    await self._log_step(session, step, start, "error", error=str(exc), **chat.metas)
                    return str(exc)
            else:
                match turn_result:
                    case Finished(result):
                        await self._log_step(session, step, start, "ok", **chat.metas)
                        return result.text or ""

                    case ToolCallNeeded() as tool_call:
                        chat = await self._tool_call(
                            state, tools, start, session, step, tool_call,
                        )
                        return chat

        async with self.tapes.session(tape_name, wait=False) as session:
            prompts = await get_prompts()
            if not prompts:
                raise ValueError("no prompt provided")
            chat = await mk_chat(session, [prompt_entry(p) for p in prompts])

            step = 1
            while step <= self.settings.max_steps:
                start = time.monotonic()
                logger.info("agent.step step={} tape={}", step, session.name)
                await self._log_step_start(session, step, chat, prompts[0])
                match await _step(session, start, step, chat):
                    case PreparedChat() as chat_:
                        chat = chat_
                        await self._log_step(session, step, start, "continue", **chat.metas)
                        steering_msgs = [prompt_entry(p) for p in await get_prompts()]
                        if steering_msgs:
                            step = 1  # reset step count on new steering input
                            chat.entries.extend(steering_msgs)
                    case res:
                        return res
                step += 1

            raise RuntimeError(f"max_steps_reached={self.settings.max_steps}")

    # agent loop (streaming)

    def _loop_stream_gen(
        self,
        tape_name: str,
        get_prompts: Callable[[], Coroutine[Any, Any, list[str]]],
        state: State,
        model: str | None,
        allowed_skills: Collection[str] | None,
        allowed_tools: Collection[str] | None,
    ) -> AsyncStreamEvents[Finished]:
        """Returns an AsyncStreamEvents wrapping the multi-step streaming loop."""
        tools = model_tools(self._resolve_tools(allowed_tools))
        mk_chat = self._prepare_turn(state, model, allowed_skills, tools)
        handoffs_left = MAX_AUTO_HANDOFF

        async def _step(session: TapeSession, start: float, step: int, chat: PreparedChat, res: list[PreparedChat | None]) -> AsyncIterator[StreamEvent[Finished]]:
            nonlocal handoffs_left
            async with asyncio.timeout(self.settings.model_timeout_seconds):
                stream = await session.stream(self._chat, chat)

            result_event = None
            async with ensure_drained(stream) as stream:
                async for event in stream:
                    match event:
                        case TextEvent():
                            yield event
                        case FinalEvent():
                            result_event = event
                            break
                        case ErrorEvent(error=err):
                            if _is_context_length_error(str(err)):
                                if handoffs_left <= 0:
                                    raise RepublicError(ErrorKind.TEMPORARY, "max auto handoffs reached", details={"error": err})
                                handoffs_left -= 1
                                logger.warning("auto_handoff tape={} step={}", tape_name, step)
                                chat = await self._auto_handoff(functools.partial(mk_chat, session), Exception(err), **chat.metas)
                                res[0] = chat
                                return

            if result_event is None:
                raise RuntimeError("stream ended without final event")

            match result_event.result:
                case ToolCallNeeded() as needed:
                    chat_ = await self._tool_call(
                        state, tools, start, session, step, needed
                    )
                    res[0] = chat_

        async def generator() -> AsyncGenerator[StreamEvent[Finished], None]:
            prompts = await get_prompts()
            if not prompts:
                raise ValueError("no prompt provided")
            async with self.tapes.session(tape_name, wait=False) as session:
                chat = await mk_chat(session, [prompt_entry(p) for p in prompts])
                step = 1
                while step <= self.settings.max_steps:
                    start = time.monotonic()
                    logger.info("agent.step step={} tape={}", step, session.name)
                    await self._log_step_start(session, step, chat, prompts[0])
                    try: 
                        res: list[PreparedChat | None] = [None]
                        async with ensure_drained(_step(session, start, step, chat, res)) as event_stream:
                            async for event in event_stream:
                                yield event
                    except Exception as exc:
                        await self._log_step(session, step, start, "error", error=str(exc), **chat.metas)
                        raise
                    else:
                        match res[0]:
                            case PreparedChat() as chat_:
                                chat = chat_
                                await self._log_step(session, step, start, "continue", **chat.metas)
                                steering_msgs = [prompt_entry(p) for p in await get_prompts()]
                                if steering_msgs:
                                    step = 1  # reset step count on new steering input
                                    chat.entries.extend(steering_msgs)
                                    continue
                            case _:
                                return
                    step += 1
                raise RuntimeError(f"max_steps_reached={self.settings.max_steps}")
        return AsyncStreamEvents(generator())

    async def _tool_call(
        self, 
        state: dict[str, Any], tools: list, start: float, 
        session: TapeSession, step: int, tool_call: ToolCallNeeded,
    ) -> PreparedChat:
        try:
            execution = await self._executor.execute_async(
                tool_call.tool_calls, tools,
                context=ToolContext(tape=session.name, run_id=tool_call.result.request.run_id, state=state),
            )
            next_chat = await session.add_tool_results(tool_call, execution.tool_results)
            await self._log_step(session, step, start, "continue", **tool_call.metas)
            return next_chat
        except Exception as exc:
            await self._log_step(session, step, start, "error", error=str(exc), **tool_call.metas)
            raise

    async def _auto_handoff(
        self,
        create_chat: Callable[[list[TapeEntry]], Coroutine[Any, Any, PreparedChat]],
        exc: Exception,
        **metas,
        ) -> PreparedChat:
        entries = [
            TapeEntry.handoff(
                "auto_handoff/context_overflow",
                anchor_state={
                    "reason": "context_length_exceeded",
                    "error": str(exc),
                },
                **metas,
            ),
            TapeEntry.system(CONTEXT_EXCEEDED_HAND_OFF_PROMPT, **metas),
        ]
        return await create_chat(entries)

    # tape logging

    async def _log_step_start(
        self, session: TapeSession, step: int, prepared: PreparedChat, prompt: Any,
    ) -> None:
        await session.append_event(
            "loop.step.start",
            {"step": step, "prompt": prompt},
            **prepared.metas,
        )

    async def _log_step(
        self,
        session: TapeSession,
        step: int,
        start: float,
        status: str,
        *,
        error: str | None = None,
        **metas: Any,
    ) -> None:
        data: dict[str, Any] = {
            "step": step,
            "elapsed_ms": int((time.monotonic() - start) * 1000),
            "status": status,
            "date": datetime.now(UTC).isoformat(),
        }
        if error:
            data["error"] = error
        await session.append_event("loop.step", data, **metas)

    # prompt building

    def _system_prompt(
        self, state: State, allowed: set[str] | None,
    ) -> str:
        blocks: list[str] = []
        if sys_prompt := self.framework.get_system_prompt(state=state):
            blocks.append(sys_prompt)
        if tools_prompt := render_tools_prompt(REGISTRY.values()):
            blocks.append(tools_prompt)
        workspace = workspace_from_state(state)
        if skills_prompt := self._load_skills(workspace, allowed):
            blocks.append(skills_prompt)
        return "\n\n".join(blocks)

    def _load_skills(
        self, workspace: Path, allowed: set[str] | None = None,
    ) -> str:
        index = {
            s.name.casefold(): s
            for s in discover_skills(workspace)
            if allowed is None or s.name.casefold() in allowed
        }
        return render_skills_prompt(list(index.values()))

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

    # def _resolve_reasoning_strategy(self, provider: str) -> ReasoningStrategy:
    #     setting = self.settings.reasoning_strategy
    #     provider = provider.lower()
    #     if isinstance(setting, dict):
    #         strategy = setting.get(provider) or setting.get("default")
    #     else:
    #         strategy = setting
    #     try:
    #         return ReasoningStrategy(strategy) if strategy else ReasoningStrategy.PRUNE
    #     except ValueError:
    #         return ReasoningStrategy.PRUNE

    def _resolve_transport_args(self, provider: str) -> dict[str, Any]:
        setting = self.settings.transport_args
        if not setting:
            return {}
        if "default" in setting or provider in setting:
            return setting.get(provider, setting.get("default", {}))
        return setting

    def _prepare_turn(
        self,
        state: State,
        model: str | None,
        allowed_skills: Collection[str] | None,
        tools: list[Tool],
    ) -> Callable[[TapeSession, list[TapeEntry]], Coroutine[Any, Any, PreparedChat]]:

        provider, model_id = self._resolve_model(model)
        skills = self._skills_set(allowed_skills)
        system_prompt = self._system_prompt(state, skills)
        # TODO: check build_tape_context correctly source reasoning strategy
        # which in turn needs to extend hook build_tape_context to take provider as arg
        # or we should defer the potential prunning strategy to chat client
        # or the read_messages should take the building params supplied by chat client (This is reasonable)
        # session._context = replace(
        #     session._context,
        #     reasoning_strategy=self._resolve_reasoning_strategy(provider),
        # )
        transport_args = self._resolve_transport_args(provider)

        async def _mk(session: TapeSession, entries: list[TapeEntry]) -> PreparedChat:
            chat = await session.prepare(
                provider=provider,
                model=model_id,
                system_prompt=system_prompt,
                tools=get_tool_schemas(tools),
                max_tokens=self.settings.max_tokens,
                reasoning_effort=self.settings.reasoning_effort,
                **transport_args,
            )
            chat.entries.extend(entries)
            return chat
        
        return _mk


# helpers


def _is_context_length_error(msg: str) -> bool:
    return bool(_CONTEXT_LENGTH_RE.search(msg))


def _ensure_text_prompt(prompt: Prompt):
    if isinstance(prompt, list):
        return _extract_text_from_parts(prompt)
    return prompt


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


class NeedHandOffError(Exception):
    """Raised when the agent needs to hand off to a human (e.g. due to context overflow)."""

    def __init__(self, reason: str, *, error: Exception, anchor_state: dict[str, Any] | None = None) -> None:
        super().__init__(f"need_handoff: {reason}")
        self.reason = reason
        self.error = error
        self.anchor_state = anchor_state or {}


def _assert_not_none(value: T | None) -> T:
    if value is None:
        raise RuntimeError("unexpected None value")
    return value


async def _drain_prompts(queue: asyncio.Queue[Prompt]) -> list[str]:
    prompts: list[str] = []
    try:
        while True:
            p = queue.get_nowait()
            prompts.append(_ensure_text_prompt(p))
    except asyncio.QueueEmpty:
        pass
    return prompts


def mk_get_prompts(prompt: Prompt, steering: asyncio.Queue[Prompt] | None) -> Callable[[], Coroutine[Any, Any, list[str]]]:
    first_message = [_ensure_text_prompt(prompt)]
    async def _get_prompts() -> list[str]:
        msgs = []
        if first_message:
            msgs.append(first_message[0])
            first_message.clear()
        if steering:
            msgs.extend(await _drain_prompts(steering))
        return msgs
    return _get_prompts
