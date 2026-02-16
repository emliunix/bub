"""Tape context helpers."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from republic import TapeContext, TapeEntry


def default_tape_context() -> TapeContext:
    """Return the default context selection for Bub."""

    return TapeContext(anchor=None, select=_select_messages)


def _select_messages(entries: Sequence[TapeEntry], _context: TapeContext) -> list[dict[str, Any]]:
    """Reconstruct messages from tape entries in standard OpenAI format.

    All messages produced by this function conform to the standard format
    defined in bub.llm.format, ensuring compatibility with all LLM providers
    when proper adapter functions are used.
    """
    messages: list[dict[str, Any]] = []
    pending_calls: list[dict[str, Any]] = []

    for entry in entries:
        if entry.kind == "message":
            _append_message_entry(messages, entry)
            continue

        if entry.kind == "tool_call":
            pending_calls = _append_tool_call_entry(messages, entry)
            continue

        if entry.kind == "tool_result":
            _append_tool_result_entry(messages, pending_calls, entry)
            pending_calls = []

    return messages


def _append_message_entry(messages: list[dict[str, Any]], entry: TapeEntry) -> None:
    payload = entry.payload
    if isinstance(payload, dict):
        messages.append(dict(payload))


def _append_tool_call_entry(messages: list[dict[str, Any]], entry: TapeEntry) -> list[dict[str, Any]]:
    """Append a tool call entry as an assistant message with tool_calls."""
    calls = _normalize_tool_calls(entry.payload.get("calls"))
    if calls:
        messages.append({"role": "assistant", "content": "", "tool_calls": calls})
    return calls


def _append_tool_result_entry(
    messages: list[dict[str, Any]],
    pending_calls: list[dict[str, Any]],
    entry: TapeEntry,
) -> None:
    results = entry.payload.get("results")
    if not isinstance(results, list):
        return
    for index, result in enumerate(results):
        messages.append(_build_tool_result_message(result, pending_calls, index))


def _build_tool_result_message(
    result: object,
    pending_calls: list[dict[str, Any]],
    index: int,
) -> dict[str, Any]:
    """Build a tool result message in standard format.

    Standard format requires 'tool_call_id' for all tool role messages.
    If the corresponding tool_call cannot be found, generates a placeholder ID.
    """
    message: dict[str, Any] = {"role": "tool", "content": _render_tool_result(result)}

    # Determine tool_call_id
    if index < len(pending_calls):
        call = pending_calls[index]
        call_id = call.get("id")
        if isinstance(call_id, str) and call_id:
            message["tool_call_id"] = call_id
        else:
            # Invalid call_id, generate placeholder
            message["tool_call_id"] = f"orphan_call_{index}"

        # Add function name if available
        function = call.get("function")
        if isinstance(function, dict):
            name = function.get("name")
            if isinstance(name, str) and name:
                message["name"] = name
    else:
        # No matching tool_call, generate placeholder ID
        # This should not happen in normal operation but handles edge cases
        message["tool_call_id"] = f"orphan_result_{index}"

    return message


def _normalize_tool_calls(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    calls: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            calls.append(dict(item))
    return calls


def _render_tool_result(result: object) -> str:
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False)
    except TypeError:
        return str(result)
