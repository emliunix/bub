from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from republic import AsyncStreamEvents
from republic.core.results import ErrorEvent, Finished, LLMResult, PreparedChat, TextEvent
from republic.tape.context import ReasoningStrategy
from republic.tape.session import TapeSession

from bub.builtin.agent import Agent
from bub.builtin.settings import AgentSettings


def _make_agent() -> Agent:
    """Build an Agent with a mocked framework, bypassing real LLM/tape init."""
    framework = MagicMock()
    framework.get_tape_store.return_value = None
    framework.get_system_prompt.return_value = ""

    with patch.object(Agent, "__init__", lambda self, fw: None):
        agent = Agent.__new__(Agent)

    agent.settings = AgentSettings.model_construct(model="test:model", api_key="k", api_base="b")
    agent.framework = framework
    return agent


class _MergeBackCapture:
    """Captures the merge_back kwarg passed to TapeService.session()."""

    def __init__(self) -> None:
        self.merge_back_values: list[bool] = []
        self.sessions: list[MagicMock] = []

    @contextlib.asynccontextmanager
    async def session(
        self, tape_name: str, *, merge_back: bool = True, state: Any = None
    ) -> AsyncGenerator[MagicMock, None]:
        self.merge_back_values.append(merge_back)
        mock_session = MagicMock()
        mock_session.name = tape_name
        self.sessions.append(mock_session)
        yield mock_session


@pytest.mark.asyncio
async def test_agent_run_regular_session_merges_back() -> None:
    """A regular (non-temp) session should merge tape entries back."""
    agent = _make_agent()
    capture = _MergeBackCapture()
    agent.tapes = capture  # type: ignore[assignment]

    # Mock the LLM call path to return immediately
    with patch.object(
        agent,
        "_loop_stream_gen",
        return_value=_error_stream("error: empty prompt"),
    ):
        result = await agent.run_stream(
            tape_name="user/session1",
            prompt="hello",
            state={"session_id": "user/session1", "_runtime_workspace": "/tmp"},  # noqa: S108
        )
        [event async for event in result]

    assert capture.merge_back_values == [True]


@pytest.mark.asyncio
async def test_agent_run_temp_session_does_not_merge_back() -> None:
    """A temp/ session should NOT merge tape entries back."""
    agent = _make_agent()
    capture = _MergeBackCapture()
    agent.tapes = capture  # type: ignore[assignment]

    with patch.object(
        agent,
        "_loop_stream_gen",
        return_value=_error_stream("error: empty prompt"),
    ):
        result = await agent.run_stream(
            tape_name="temp/abc123",
            prompt="hello",
            state={"session_id": "temp/abc123", "_runtime_workspace": "/tmp"},  # noqa: S108
        )
        [event async for event in result]

    assert capture.merge_back_values == [False]


@pytest.mark.asyncio
async def test_agent_run_empty_prompt_returns_error() -> None:
    agent = _make_agent()
    agent.tapes = MagicMock()  # type: ignore[assignment]

    result = await agent.run_stream(tape_name="user/s1", prompt="", state={})
    events = [event async for event in result]

    assert len(events) == 1
    assert isinstance(events[0], ErrorEvent)
    assert events[0].error.message == "error: empty prompt"


# ---------------------------------------------------------------------------
# Model passthrough tests
# ---------------------------------------------------------------------------


class _FakeSession:
    """Minimal fake TapeSession that delegates stream() to the ChatClient."""

    def __init__(self, name: str = "test") -> None:
        from republic.tape.context import TapeContext
        self.name = name
        self._context = TapeContext()
        self.last_prepared: PreparedChat | None = None

    async def prepare(self, *, prompt: str, provider: str, model: str, **kwargs: Any) -> PreparedChat:
        tools = kwargs.pop("tools", None) or []
        max_tokens = kwargs.pop("max_tokens", None)
        reasoning_effort = kwargs.pop("reasoning_effort", None)
        self.last_prepared = PreparedChat(
            model=model,
            provider=provider,
            tools=tools,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
            kwargs=kwargs,
        )
        return self.last_prepared

    async def stream(self, chat: Any, prepared: PreparedChat) -> AsyncStreamEvents:
        return await chat.stream(prepared, [])

    async def run(self, chat: Any, prepared: PreparedChat) -> Any:
        from republic.core.results import Finished, LLMResult
        return Finished(result=LLMResult(request=prepared, text="done"))

    async def add_tool_results(self, needed: Any, results: list[dict]) -> PreparedChat:
        return self.last_prepared or PreparedChat(model="", provider="")

    async def handoff(self, name: str, **kwargs: Any) -> None:
        pass

    async def append_event(self, prepared: PreparedChat, kind: str, payload: dict) -> None:
        pass


class _ChatCapture:
    """Captures PreparedChat passed to ChatClient.stream()."""

    def __init__(self) -> None:
        self.prepared: PreparedChat | None = None

    async def stream(self, prepared: PreparedChat, messages: list[dict]) -> AsyncStreamEvents:
        self.prepared = prepared

        async def iterator():
            yield TextEvent(content="done")
            yield _final_event("done")

        return AsyncStreamEvents(iterator())


def _final_event(text: str) -> Any:
    from republic.core.results import FinalEvent
    return FinalEvent(result=Finished(result=LLMResult(
        request=PreparedChat(model="", provider=""),
        text=text,
    )))


def _error_stream(message: str) -> AsyncStreamEvents:
    """Create a stream that yields a single error event."""
    from republic.core.errors import ErrorKind, RepublicError
    from republic.core.results import ErrorEvent

    async def gen():
        yield ErrorEvent(error=RepublicError(ErrorKind.INVALID_INPUT, message))

    return AsyncStreamEvents(gen())


class _FakeTapeService:
    """Yields _FakeSession instances."""

    def __init__(self) -> None:
        self.merge_back_values: list[bool] = []
        self.sessions: list[_FakeSession] = []

    @contextlib.asynccontextmanager
    async def session(
        self, tape_name: str, *, merge_back: bool = True, state: Any = None
    ) -> AsyncGenerator[_FakeSession, None]:
        self.merge_back_values.append(merge_back)
        fake = _FakeSession(name=tape_name)
        self.sessions.append(fake)
        yield fake


@pytest.mark.asyncio
async def test_agent_run_passes_model_to_llm() -> None:
    """The model parameter should be forwarded to session.prepare()."""
    agent = _make_agent()
    tapes = _FakeTapeService()
    agent.tapes = tapes  # type: ignore[assignment]

    chat_capture = _ChatCapture()
    agent._chat = chat_capture  # type: ignore[assignment]

    # Patch _resolve_model to avoid real provider lookup
    with patch.object(agent, "_resolve_model", return_value=("openai", "gpt-4o")):
        result = await agent.run_stream(
            tape_name="user/s1",
            prompt="hello",
            state={"session_id": "user/s1", "_runtime_workspace": "/tmp"},  # noqa: S108
            model="openai:gpt-4o",
        )
        [event async for event in result]

    assert chat_capture.prepared is not None
    assert chat_capture.prepared.model == "gpt-4o"
    assert chat_capture.prepared.provider == "openai"


@pytest.mark.asyncio
async def test_agent_run_model_defaults_to_settings_model() -> None:
    """When model is not specified, Agent.settings.model should be used."""
    agent = _make_agent()
    tapes = _FakeTapeService()
    agent.tapes = tapes  # type: ignore[assignment]

    chat_capture = _ChatCapture()
    agent._chat = chat_capture  # type: ignore[assignment]

    with patch.object(agent, "_resolve_model", return_value=("test", "test:model")):
        result = await agent.run_stream(
            tape_name="user/s1",
            prompt="hello",
            state={"session_id": "user/s1", "_runtime_workspace": "/tmp"},  # noqa: S108
        )
        [event async for event in result]

    assert chat_capture.prepared is not None
    assert chat_capture.prepared.model == "test:model"


# ---------------------------------------------------------------------------
# Reasoning strategy resolution tests
# ---------------------------------------------------------------------------


class TestResolveReasoningStrategy:
    """Unit tests for Agent._resolve_reasoning_strategy."""

    def test_global_string_setting(self) -> None:
        agent = _make_agent()
        agent.settings = AgentSettings.model_construct(reasoning_strategy="full")
        assert agent._resolve_reasoning_strategy("openai") == ReasoningStrategy.FULL

    def test_dict_with_matching_provider(self) -> None:
        agent = _make_agent()
        agent.settings = AgentSettings.model_construct(
            reasoning_strategy={"openai": "full", "anthropic": "last_turn_only"}
        )
        assert agent._resolve_reasoning_strategy("openai") == ReasoningStrategy.FULL
        assert agent._resolve_reasoning_strategy("anthropic") == ReasoningStrategy.LAST_TURN_ONLY

    def test_dict_no_match_returns_prune(self) -> None:
        agent = _make_agent()
        agent.settings = AgentSettings.model_construct(
            reasoning_strategy={"openai": "full"}
        )
        assert agent._resolve_reasoning_strategy("deepseek") == ReasoningStrategy.PRUNE

    def test_dict_with_default_fallback(self) -> None:
        agent = _make_agent()
        agent.settings = AgentSettings.model_construct(
            reasoning_strategy={"default": "tool_calls_only", "openai": "full"}
        )
        assert agent._resolve_reasoning_strategy("openai") == ReasoningStrategy.FULL
        assert agent._resolve_reasoning_strategy("deepseek") == ReasoningStrategy.TOOLCALLS_ONLY

    def test_invalid_global_string_returns_prune(self) -> None:
        agent = _make_agent()
        agent.settings = AgentSettings.model_construct(reasoning_strategy="invalid")
        assert agent._resolve_reasoning_strategy("openai") == ReasoningStrategy.PRUNE

    def test_invalid_dict_value_returns_prune(self) -> None:
        agent = _make_agent()
        agent.settings = AgentSettings.model_construct(
            reasoning_strategy={"openai": "bad_value", "default": "full"}
        )
        assert agent._resolve_reasoning_strategy("openai") == ReasoningStrategy.PRUNE
        assert agent._resolve_reasoning_strategy("deepseek") == ReasoningStrategy.FULL

    def test_none_setting_returns_prune(self) -> None:
        agent = _make_agent()
        agent.settings = AgentSettings.model_construct(reasoning_strategy=None)
        assert agent._resolve_reasoning_strategy("openai") == ReasoningStrategy.PRUNE

    def test_provider_case_insensitive(self) -> None:
        agent = _make_agent()
        agent.settings = AgentSettings.model_construct(
            reasoning_strategy={"openai": "full"}
        )
        assert agent._resolve_reasoning_strategy("OpenAI") == ReasoningStrategy.FULL
        assert agent._resolve_reasoning_strategy("OPENAI") == ReasoningStrategy.FULL

    @pytest.mark.asyncio
    async def test_prepare_turn_updates_context(self) -> None:
        agent = _make_agent()
        agent.settings = AgentSettings.model_construct(
            reasoning_strategy={"openai": "full", "default": "prune"}
        )
        session = _FakeSession()

        with patch.object(session, "prepare", new_callable=AsyncMock) as mock_prepare:
            await agent._prepare_turn(
                session, "hello", "openai", "gpt-4o", "sys", []
            )

        assert session._context.reasoning_strategy == ReasoningStrategy.FULL
        mock_prepare.assert_awaited_once()

    def test_zai_provider_last_turn_only(self) -> None:
        agent = _make_agent()
        agent.settings = AgentSettings.model_construct(
            reasoning_strategy={"zai": "last_turn_only", "default": "prune"}
        )
        assert agent._resolve_reasoning_strategy("zai") == ReasoningStrategy.LAST_TURN_ONLY

    def test_zai_client_args_isolated_from_openai(self) -> None:
        agent = _make_agent()
        agent.settings = AgentSettings.model_construct(
            client_args={
                "default": {"timeout": 30},
                "zai": {"thinking": {"type": "enabled"}},
            },
        )
        core = agent._core
        assert core._resolve_client_args("zai") == {"thinking": {"type": "enabled"}}
        assert core._resolve_client_args("openai") == {"timeout": 30}

    def test_resolve_transport_args_provider_specific(self) -> None:
        agent = _make_agent()
        agent.settings = AgentSettings.model_construct(
            transport_args={
                "default": {"temperature": 0.7},
                "zai": {"thinking": {"type": "enabled"}},
            },
        )
        assert agent._resolve_transport_args("zai") == {"thinking": {"type": "enabled"}}
        assert agent._resolve_transport_args("openai") == {"temperature": 0.7}

    def test_resolve_transport_args_global(self) -> None:
        agent = _make_agent()
        agent.settings = AgentSettings.model_construct(
            transport_args={"temperature": 0.5},
        )
        assert agent._resolve_transport_args("zai") == {"temperature": 0.5}
        assert agent._resolve_transport_args("openai") == {"temperature": 0.5}

    @pytest.mark.asyncio
    async def test_prepare_turn_passes_transport_args(self) -> None:
        agent = _make_agent()
        agent.settings = AgentSettings.model_construct(
            transport_args={
                "zai": {"thinking": {"type": "enabled"}},
            },
        )
        session = _FakeSession()

        await agent._prepare_turn(
            session, "hello", "zai", "GLM-5.1", "sys", []
        )

        assert session.last_prepared is not None
        assert session.last_prepared.kwargs.get("thinking") == {"type": "enabled"}

    @pytest.mark.asyncio
    async def test_prepare_turn_updates_context_for_zai(self) -> None:
        agent = _make_agent()
        agent.settings = AgentSettings.model_construct(
            reasoning_strategy={"zai": "last_turn_only", "default": "prune"}
        )
        session = _FakeSession()

        with patch.object(session, "prepare", new_callable=AsyncMock) as mock_prepare:
            await agent._prepare_turn(
                session, "hello", "zai", "GLM-5.1", "sys", []
            )

        assert session._context.reasoning_strategy == ReasoningStrategy.LAST_TURN_ONLY
        mock_prepare.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_prepare_turn_passes_reasoning_effort_for_zai(self) -> None:
        agent = _make_agent()
        agent.settings = AgentSettings.model_construct(
            reasoning_strategy={"zai": "last_turn_only"},
            reasoning_effort="low",
        )
        session = _FakeSession()

        await agent._prepare_turn(
            session, "hello", "zai", "GLM-5.1", "sys", []
        )

        assert session._context.reasoning_strategy == ReasoningStrategy.LAST_TURN_ONLY
        assert session.last_prepared is not None
        assert session.last_prepared.reasoning_effort == "low"
