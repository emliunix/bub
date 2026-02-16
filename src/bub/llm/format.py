"""Standard message format definitions (OpenAI-compatible).

This module defines the standard internal format that Bub uses for all
message storage and processing. Provider-specific adapters convert to/from
this standard format at the API boundary.

Standard Format (OpenAI-compatible):
- system: System instructions
- user: User input
- assistant: Model output (may include tool_calls)
- tool: Tool results (REQUIRES tool_call_id)

Note: The "developer" role from newer OpenAI APIs should be converted to
"system" for storage.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class ToolCallFunction(TypedDict):
    """Function call details within a tool call."""

    name: str
    arguments: str


class ToolCall(TypedDict):
    """A single tool call from the assistant."""

    id: str
    type: Literal["function"]
    function: ToolCallFunction


class StandardMessage(TypedDict, total=False):
    """Standard message format (OpenAI-compatible).

    All messages stored in tape and processed internally use this format.
    Provider adapters convert to/from this format at API boundaries.
    """

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None
    # For assistant messages with tool calls
    tool_calls: list[ToolCall]
    # For tool result messages (REQUIRED when role="tool")
    tool_call_id: str
    # Optional: function name for tool results
    name: str


# Role types for validation
STANDARD_ROLES: set[str] = {"system", "user", "assistant", "tool"}

# Roles that require additional fields
REQUIRED_FIELDS: dict[str, set[str]] = {
    "tool": {"tool_call_id"},
}


def validate_standard_message(msg: dict[str, Any]) -> list[str]:
    """Validate that a message conforms to the standard format.

    Returns a list of validation errors (empty if valid).
    """
    errors: list[str] = []

    # Check role
    role = msg.get("role")
    if not role:
        errors.append("Missing required field: 'role'")
    elif role not in STANDARD_ROLES:
        errors.append(f"Invalid role: '{role}'. Must be one of: {STANDARD_ROLES}")

    # Check required fields for specific roles
    if role in REQUIRED_FIELDS:
        for field in REQUIRED_FIELDS[role]:
            if field not in msg or not msg[field]:
                errors.append(f"Role '{role}' requires field: '{field}'")

    # Check tool_calls format if present
    if "tool_calls" in msg:
        tool_calls = msg["tool_calls"]
        if not isinstance(tool_calls, list):
            errors.append("'tool_calls' must be a list")
        else:
            for i, call in enumerate(tool_calls):
                if not isinstance(call, dict):
                    errors.append(f"tool_calls[{i}] must be an object")
                    continue
                if "id" not in call:
                    errors.append(f"tool_calls[{i}] missing required field: 'id'")
                if "type" not in call:
                    errors.append(f"tool_calls[{i}] missing required field: 'type'")
                if "function" not in call:
                    errors.append(f"tool_calls[{i}] missing required field: 'function'")
                elif not isinstance(call["function"], dict):
                    errors.append(f"tool_calls[{i}].function must be an object")

    return errors


def is_valid_standard_message(msg: dict[str, Any]) -> bool:
    """Check if a message is valid standard format."""
    return len(validate_standard_message(msg)) == 0


def create_system_message(content: str) -> StandardMessage:
    """Create a standard system message."""
    return {"role": "system", "content": content}


def create_user_message(content: str) -> StandardMessage:
    """Create a standard user message."""
    return {"role": "user", "content": content}


def create_assistant_message(content: str, tool_calls: list[ToolCall] | None = None) -> StandardMessage:
    """Create a standard assistant message."""
    msg: StandardMessage = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


def create_tool_message(content: str, tool_call_id: str, name: str | None = None) -> StandardMessage:
    """Create a standard tool result message.

    Note: tool_call_id is REQUIRED for tool role messages.
    """
    msg: StandardMessage = {"role": "tool", "content": content, "tool_call_id": tool_call_id}
    if name:
        msg["name"] = name
    return msg
