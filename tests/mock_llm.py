"""Mock LLM provider that always triggers tool calls.

Injects a fake AnyLLM client into Republic's LLM so that every
``run_tools_async`` call returns a tool-call response. The tool handlers
are executed by Republic's real ToolExecutor, exercising the full
tool routing and execution path.
"""

from __future__ import annotations

import json
from collections import deque
from types import SimpleNamespace
from typing import Any

from republic import LLM
from republic.tape import TapeStore


class _FakeAnyLLMClient:
    """Minimal fake that replays queued responses."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._queue: deque[Any] = deque()

    def queue(self, *items: Any) -> None:
        self._queue.extend(items)

    def completion(self, **kwargs: Any) -> Any:
        self.calls.append(dict(kwargs))
        return self._next()

    async def acompletion(self, **kwargs: Any) -> Any:
        self.calls.append(dict(kwargs))
        return self._next()

    def _next(self) -> Any:
        if not self._queue:
            raise AssertionError("MockLLM: no queued responses left")
        item = self._queue.popleft()
        if isinstance(item, Exception):
            raise item
        return item


def _make_tool_call_response(
    name: str,
    arguments: dict[str, Any] | str,
    *,
    call_id: str = "call_1",
) -> Any:
    if isinstance(arguments, dict):
        arguments = json.dumps(arguments)
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id=call_id,
                            type="function",
                            function=SimpleNamespace(name=name, arguments=arguments),
                        )
                    ],
                )
            )
        ],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15),
    )


def _make_text_response(text: str) -> Any:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text, tool_calls=[]),
            )
        ],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15),
    )


class MockLLMProvider:
    """A mock LLM provider that injects fake responses into Republic's LLM.

    Usage::

        mock = MockLLMProvider()
        mock.queue_tool_call("fs_read", {"path": "/tmp/test.txt"})
        mock.queue_text("Done reading the file.")

        llm = mock.build()
        result = await llm.run_tools_async(prompt="read the file", tools=tools)
    """

    def __init__(self) -> None:
        self._client = _FakeAnyLLMClient()

    @property
    def client(self) -> _FakeAnyLLMClient:
        return self._client

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self._client.calls

    def queue_tool_call(
        self,
        name: str,
        arguments: dict[str, Any] | str,
        *,
        call_id: str = "call_1",
    ) -> MockLLMProvider:
        self._client.queue(_make_tool_call_response(name, arguments, call_id=call_id))
        return self

    def queue_text(self, text: str) -> MockLLMProvider:
        self._client.queue(_make_text_response(text))
        return self

    def queue_raw(self, response: Any) -> MockLLMProvider:
        self._client.queue(response)
        return self

    def build(
        self,
        *,
        tape_store: TapeStore | None = None,
        model: str = "openai:mock-model",
    ) -> LLM:
        llm = LLM(
            model,
            api_key="mock-key",
            tape_store=tape_store,
        )
        client = self._client
        llm._core.get_client = lambda provider: client
        return llm
