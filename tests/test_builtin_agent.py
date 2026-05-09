from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from republic import AsyncStreamEvents, StreamEvent
from republic.core.results import ErrorEvent, Finished, LLMResult, PreparedChat, TextEvent
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
        self.name = name
        self.last_prepared: PreparedChat | None = None

    async def prepare(self, *, prompt: str, provider: str, model: str, **kwargs: Any) -> PreparedChat:
        self.last_prepared = PreparedChat(model=model, provider=provider)
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
