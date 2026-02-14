"""Test for tape replay with error entries - reproduces minimax API failure."""

from republic import TapeEntry

from bub.tape.context import default_tape_context


def test_tape_replay_with_invalid_tool_arguments_issue() -> None:
    """Reproduce the issue: malformed tool call arguments cause repeated API failures.

    This test reproduces the bug where:
    1. Model generates a tool call with malformed JSON arguments
    2. Tool returns "invalid_input" error
    3. Model retries but sends same malformed args directly to API
    4. API returns 400 error
    5. On tape replay, the same error keeps happening

    The problematic tape entries look like:
    - tool_call with malformed arguments (escaped quotes not valid JSON)
    - tool_result with error: "Tool 'fs_edit' arguments are not valid JSON."
    - error: API 400 error from minimax

    The fix should either:
    1. Filter out tool_call entries that resulted in errors when loading tape
    2. Add a rollback mechanism to skip past errors
    3. Mark certain tool_call IDs as "poisonous" and exclude them from replay
    """
    context = default_tape_context()
    assert context.select is not None

    # This reproduces the actual tape entries from ~/.bub/tapes/
    # The malformed tool call has escaped quotes in arguments - not valid JSON
    entries = [
        TapeEntry.message({"role": "user", "content": "edit the file"}),
        TapeEntry.tool_call([
            {
                "id": "call_function_bekk8zjdtanm_1",
                "type": "function",
                "function": {
                    "name": "fs_edit",
                    # This is malformed - escaped quotes are not valid JSON
                    "arguments": '{"new": "    async def send(self, message: OutboundMessage) -> None:\\n        ...", "path": "src/bub/channels/telegram.py"}',
                },
            },
        ]),
        # Tool returns error for invalid JSON arguments
        TapeEntry.tool_result([
            {"kind": "invalid_input", "message": "Tool 'fs_edit' arguments are not valid JSON."},
        ]),
        # Then the model retries and sends malformed args directly to API
        # API returns 400 error
        TapeEntry(
            371,
            "error",
            {"kind": "invalid_input", "message": "minimax:MiniMax-M2.5: Error code: 400 - invalid function arguments"},
            {"run_id": "ec4e7e1211db4d13b077ea7d1ea4be69"},
        ),
        TapeEntry(
            372, "event", {"name": "run", "data": {"status": "error"}}, {"run_id": "ec4e7e1211db4d13b077ea7d1ea4be69"}
        ),
    ]

    messages = context.select(entries, context)

    # Currently, the context includes the malformed tool_call
    # This causes the same error when replaying
    assert len(messages) == 3

    # The tool call is included with malformed arguments
    tool_call_msg = messages[1]
    assert tool_call_msg["role"] == "assistant"
    assert "tool_calls" in tool_call_msg

    # The arguments are still malformed
    args = tool_call_msg["tool_calls"][0]["function"]["arguments"]
    print(f"Malformed arguments: {args}")

    # This is the bug - these malformed arguments get sent to the API again on replay


def test_error_entries_not_included_in_messages() -> None:
    """Verify that error kind entries are not included in messages."""
    context = default_tape_context()
    assert context.select is not None

    entries = [
        TapeEntry.message({"role": "user", "content": "hello"}),
        TapeEntry(100, "error", {"kind": "invalid_input", "message": "some error"}, {}),
        TapeEntry.message({"role": "assistant", "content": "hi"}),
    ]

    messages = context.select(entries, context)

    # Error entries should be filtered out
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_tool_call_with_error_result_should_be_excluded() -> None:
    """Tool calls that resulted in errors should be excluded from replay.

    This is the proposed fix: when a tool_call is followed by a tool_result
    with an error, the tool_call should not be included in messages for replay.
    """
    context = default_tape_context()
    assert context.select is not None

    # Normal successful tool call - should be included
    successful_entries = [
        TapeEntry.message({"role": "user", "content": "read file"}),
        TapeEntry.tool_call([
            {
                "id": "call-ok",
                "type": "function",
                "function": {"name": "fs.read", "arguments": '{"path":"a.txt"}'},
            },
        ]),
        TapeEntry.tool_result(["file content here"]),
        TapeEntry.message({"role": "assistant", "content": "Here's the file"}),
    ]

    messages_ok = context.select(successful_entries, context)
    assert len(messages_ok) == 4  # user msg, tool_call, tool_result, assistant

    # Failed tool call - currently included (this is the bug)
    failed_entries = [
        TapeEntry.message({"role": "user", "content": "edit file"}),
        TapeEntry.tool_call([
            {
                "id": "call-fail",
                "type": "function",
                "function": {"name": "fs_edit", "arguments": "not valid json"},
            },
        ]),
        TapeEntry.tool_result([{"kind": "invalid_input", "message": "invalid JSON"}]),
    ]

    messages_fail = context.select(failed_entries, context)

    # Current behavior: includes the failed tool_call (BUG)
    # Expected behavior: should exclude it or mark it as failed
    print(f"Failed tool call messages: {messages_fail}")
    # Currently returns 2 messages (user + tool_call)
    # Should ideally return only user message, or user + error info
