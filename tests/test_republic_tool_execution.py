"""Validate Republic tool call execution path.

Uses MockLLMProvider to inject fake LLM responses and verifies that
Republic correctly parses tool calls, resolves the right handler,
executes it, and returns proper ToolAutoResult.
"""

from __future__ import annotations

import pytest
from mock_llm import MockLLMProvider
from republic import tool


@tool
def echo(*, text: str) -> str:
    return f"ECHO:{text}"


@tool
def add(*, a: int, b: int) -> int:
    return a + b


@tool(name="fs_read")
def fs_read(*, path: str) -> str:
    return f"content of {path}"


@tool(name="fs_write")
def fs_write(*, path: str, content: str) -> str:
    return "ok"


@pytest.mark.asyncio
async def test_tool_call_executes_correct_handler() -> None:
    mock = MockLLMProvider()
    mock.queue_tool_call("echo", {"text": "hello"})

    llm = mock.build()
    result = await llm.run_tools_async("say hello", tools=[echo])

    assert result.kind == "tools"
    assert result.tool_results == ["ECHO:hello"]
    assert result.tool_calls[0]["function"]["name"] == "echo"


@pytest.mark.asyncio
async def test_tool_call_with_multiple_tools_picks_right_one() -> None:
    mock = MockLLMProvider()
    mock.queue_tool_call("add", {"a": 3, "b": 4})

    llm = mock.build()
    result = await llm.run_tools_async("add 3 and 4", tools=[echo, add, fs_read])

    assert result.kind == "tools"
    assert result.tool_results == [7]
    assert result.tool_calls[0]["function"]["name"] == "add"


@pytest.mark.asyncio
async def test_tool_call_unknown_tool_returns_error() -> None:
    mock = MockLLMProvider()
    mock.queue_tool_call("nonexistent_tool", {"x": 1})

    llm = mock.build()
    result = await llm.run_tools_async("do something", tools=[echo])

    assert result.kind == "tools"
    assert any("Unknown tool" in str(r) for r in result.tool_results)


@pytest.mark.asyncio
async def test_tool_call_with_underscore_name() -> None:
    mock = MockLLMProvider()
    mock.queue_tool_call("fs_read", {"path": "test/fixture.txt"})

    llm = mock.build()
    result = await llm.run_tools_async("read file", tools=[fs_read, fs_write])

    assert result.kind == "tools"
    assert result.tool_results == ["content of test/fixture.txt"]


@pytest.mark.asyncio
async def test_text_response_returns_text_result() -> None:
    mock = MockLLMProvider()
    mock.queue_text("Here is your answer.")

    llm = mock.build()
    result = await llm.run_tools_async("question", tools=[echo])

    assert result.kind == "text"
    assert result.text == "Here is your answer."


@pytest.mark.asyncio
async def test_tool_call_then_text_response() -> None:
    mock = MockLLMProvider()
    mock.queue_tool_call("echo", {"text": "step1"})

    llm = mock.build()
    result1 = await llm.run_tools_async("first", tools=[echo])
    assert result1.kind == "tools"
    assert result1.tool_results == ["ECHO:step1"]

    mock.queue_text("All done.")
    result2 = await llm.run_tools_async("second", tools=[echo])
    assert result2.kind == "text"
    assert result2.text == "All done."


@pytest.mark.asyncio
async def test_tool_call_string_arguments() -> None:
    mock = MockLLMProvider()
    mock.queue_tool_call("add", '{"a": 10, "b": 20}')

    llm = mock.build()
    result = await llm.run_tools_async("add numbers", tools=[add])

    assert result.kind == "tools"
    assert result.tool_results == [30]


@pytest.mark.asyncio
async def test_async_tool_handler() -> None:
    @tool
    async def async_echo(*, text: str) -> str:
        return f"ASYNC:{text}"

    mock = MockLLMProvider()
    mock.queue_tool_call("async_echo", {"text": "world"})

    llm = mock.build()
    result = await llm.run_tools_async("echo async", tools=[async_echo])

    assert result.kind == "tools"
    assert result.tool_results == ["ASYNC:world"]
