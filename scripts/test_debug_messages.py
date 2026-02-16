#!/usr/bin/env python3
"""Debug script to identify invalid role messages sent to MiniMax."""

import json
import os
from pathlib import Path

# Load .env file first
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key, val)

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "upstream" / "republic" / "src"))

from republic.tools.schema import tool

from bub.config.settings import AgentSettings, TapeSettings, load_settings
from bub.integrations.republic_client import build_llm, build_tape_store


def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny, 72°F"


def validate_message(message: dict, index: int, source: str) -> tuple[bool, str]:
    """Validate a message has a proper role. Returns (is_valid, error_message)."""
    role = message.get("role")

    if role is None:
        return (
            False,
            f"Message {index} from {source}: MISSING 'role' field!\n  Full message: {json.dumps(message, indent=2)}",
        )

    if role == "":
        return (
            False,
            f"Message {index} from {source}: EMPTY 'role' field!\n  Full message: {json.dumps(message, indent=2)}",
        )

    valid_roles = {"system", "user", "assistant", "tool"}
    if role not in valid_roles:
        return (
            False,
            f"Message {index} from {source}: INVALID role '{role}'!\n  Full message: {json.dumps(message, indent=2)}",
        )

    return True, f"Message {index} from {source}: OK (role='{role}')"


def debug_tape_message_reconstruction():
    """Debug how messages are reconstructed from tape entries."""

    print("=" * 80)
    print("DEBUG: Tape Message Reconstruction for MiniMax")
    print("=" * 80)

    workspace = Path(__file__).parent.parent
    settings = load_settings(workspace)
    tape_settings = TapeSettings()
    agent_settings = AgentSettings()
    store = build_tape_store(agent_settings, tape_settings, workspace)
    llm = build_llm(agent_settings, store)

    tape_name = "debug_minimax_roles"

    # Clean up any existing tape
    try:
        store.reset(tape_name)
        print(f"\n✓ Reset tape: {tape_name}")
    except Exception as e:
        print(f"\n⚠ Could not reset tape: {e}")

    # Step 1: Make a tool call to populate the tape
    print("\n" + "-" * 80)
    print("STEP 1: Making initial tool_calls() to populate tape")
    print("-" * 80)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a city",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string", "description": "City name"}},
                    "required": ["city"],
                },
            },
        }
    ]

    try:
        calls = llm.tool_calls(prompt="What's the weather in Paris?", tools=tools, tape=tape_name)
        print(f"✓ tool_calls() succeeded with {len(calls)} call(s)")
        print(f"  Calls: {json.dumps(calls, indent=2)}")
    except Exception as e:
        print(f"✗ tool_calls() failed: {e}")
        return

    # Step 2: Read raw tape entries
    print("\n" + "-" * 80)
    print("STEP 2: Examining raw tape entries")
    print("-" * 80)

    entries = llm.read_entries(tape_name)
    print(f"\nTotal entries: {len(entries)}")

    for i, entry in enumerate(entries):
        print(f"\n--- Entry {i} ---")
        print(f"  ID: {entry.id}")
        print(f"  Kind: {entry.kind}")
        print(f"  Meta: {entry.meta}")

        if isinstance(entry.payload, dict):
            print(f"  Payload keys: {list(entry.payload.keys())}")

            # Check if payload has a role (for message entries)
            if "role" in entry.payload:
                print(f"  Payload role: '{entry.payload['role']}'")

            # Pretty print payload
            payload_str = json.dumps(entry.payload, indent=4, ensure_ascii=False)
            if len(payload_str) > 500:
                payload_str = payload_str[:500] + "..."
            print(f"  Payload:\n{payload_str}")
        else:
            print(f"  Payload: {entry.payload}")

    # Step 3: Reconstruct messages step-by-step
    print("\n" + "-" * 80)
    print("STEP 3: Step-by-step message reconstruction")
    print("-" * 80)

    messages: list[dict] = []
    pending_calls: list[dict] = []

    print("\nProcessing entries one by one:\n")

    for i, entry in enumerate(entries):
        print(f"Processing entry {i} (kind='{entry.kind}')...")

        if entry.kind == "message":
            # This is what _append_message_entry does
            payload = entry.payload
            if isinstance(payload, dict):
                msg = dict(payload)
                messages.append(msg)
                is_valid, msg_info = validate_message(msg, len(messages) - 1, "message entry")
                print(f"  → Added message: {msg_info}")

        elif entry.kind == "tool_call":
            # This is what _append_tool_call_entry does
            from bub.tape.context import _normalize_tool_calls

            calls = _normalize_tool_calls(entry.payload.get("calls"))
            if calls:
                msg = {"role": "assistant", "content": "", "tool_calls": calls}
                messages.append(msg)
                pending_calls = calls
                is_valid, msg_info = validate_message(msg, len(messages) - 1, "tool_call entry")
                print(f"  → Added assistant message with tool_calls: {msg_info}")
            else:
                print("  ⚠ No calls found in tool_call entry")

        elif entry.kind == "tool_result":
            # This is what _append_tool_result_entry does
            from bub.tape.context import _build_tool_result_message

            results = entry.payload.get("results")
            if isinstance(results, list):
                for index, result in enumerate(results):
                    msg = _build_tool_result_message(result, pending_calls, index)
                    messages.append(msg)
                    is_valid, msg_info = validate_message(msg, len(messages) - 1, "tool_result entry")
                    print(f"  → Added tool result message [{index}]: {msg_info}")
                pending_calls = []
            else:
                print("  ⚠ No results found in tool_result entry")

        elif entry.kind == "system":
            # System entries are special - they create message entries
            content = entry.payload.get("content")
            if content:
                msg = {"role": "system", "content": content}
                messages.append(msg)
                is_valid, msg_info = validate_message(msg, len(messages) - 1, "system entry")
                print(f"  → Added system message: {msg_info}")

        else:
            print(f"  → Skipped (kind='{entry.kind}')")

    # Step 4: Validate final messages
    print("\n" + "-" * 80)
    print("STEP 4: Validating reconstructed messages")
    print("-" * 80)

    print(f"\nTotal reconstructed messages: {len(messages)}")

    invalid_found = False
    for i, msg in enumerate(messages):
        is_valid, msg_info = validate_message(msg, i, "final validation")
        if not is_valid:
            print(f"\n❌ {msg_info}")
            invalid_found = True
        else:
            print(f"  ✓ {msg_info}")

    # Step 5: Test with a second tool call (this is where the error occurs)
    print("\n" + "-" * 80)
    print("STEP 5: Testing second tool_calls() with existing tape (where error occurs)")
    print("-" * 80)

    # First show what messages would be sent
    history_messages = llm.read_messages(tape_name)
    user_message = {"role": "user", "content": "What's the weather in London?"}

    full_payload = []
    full_payload.extend(history_messages)
    full_payload.append(user_message)

    print(f"\nFull payload to be sent ({len(full_payload)} messages):")
    for i, msg in enumerate(full_payload):
        role = msg.get("role", "MISSING!")
        content_preview = str(msg.get("content", ""))[:50]
        tool_calls = "[tool_calls]" if "tool_calls" in msg else ""
        print(f"  [{i}] role='{role}' {tool_calls} content='{content_preview}...'")

    print("\nValidating full payload:")
    for i, msg in enumerate(full_payload):
        is_valid, msg_info = validate_message(msg, i, "payload")
        if not is_valid:
            print(f"\n❌ {msg_info}")
            invalid_found = True

    if invalid_found:
        print("\n" + "=" * 80)
        print("🔴 ROOT CAUSE IDENTIFIED: Invalid role found in messages!")
        print("=" * 80)
        print("\nFull message dump:")
        for i, msg in enumerate(full_payload):
            role = msg.get("role", "!!!MISSING!!!")
            print(f"\nMessage {i}:")
            print(f"  role: {role!r}")
            print(f"  content: {repr(msg.get('content', 'N/A'))[:100]}")
            if "tool_calls" in msg:
                print(f"  tool_calls: {json.dumps(msg['tool_calls'], indent=2)[:200]}...")
            if "tool_call_id" in msg:
                print(f"  tool_call_id: {msg['tool_call_id']!r}")
        return

    # Try the actual call
    print("\n  Attempting second tool_calls()...")
    try:
        calls = llm.tool_calls(prompt="What's the weather in London?", tools=tools, tape=tape_name)
        print(f"  ✅ Second tool_calls() succeeded with {len(calls)} call(s)")
    except Exception as e:
        print(f"  ❌ Second tool_calls() failed: {e}")
        print(f"\n  Error details: {type(e).__name__}")
        import traceback

        traceback.print_exc()

    # Step 6: Check if there are any other entry types we're missing
    print("\n" + "-" * 80)
    print("STEP 6: Checking for edge cases")
    print("-" * 80)

    # Re-read entries after second call
    entries_after = llm.read_entries(tape_name)
    print(f"\nEntries after second call: {len(entries_after)}")

    # Check for any message entries without role
    print("\nChecking all message entries for missing roles:")
    for entry in entries_after:
        if entry.kind == "message":
            role = entry.payload.get("role") if isinstance(entry.payload, dict) else None
            if not role:
                print("  ⚠ Found message entry without role!")
                print(f"    Entry: {json.dumps(entry.payload, indent=2)}")


def test_run_tools_vs_tool_calls():
    """Compare what run_tools stores vs what tool_calls stores."""

    print("\n" + "=" * 80)
    print("COMPARISON: run_tools() vs tool_calls() tape entries")
    print("=" * 80)

    workspace = Path(__file__).parent.parent
    settings = load_settings(workspace)
    tape_settings = TapeSettings()
    agent_settings = AgentSettings()
    store = build_tape_store(agent_settings, tape_settings, workspace)
    llm = build_llm(agent_settings, store)

    # Test run_tools
    print("\n--- Testing run_tools() ---")
    tape_run = "debug_run_tools"
    try:
        store.reset(tape_run)
    except:
        pass

    @tool
    def get_weather(city: str) -> str:
        """Get weather for a city."""
        return f"Weather in {city}: Sunny, 22°C"

    result = llm.run_tools(prompt="What's the weather in Berlin?", tools=[get_weather], tape=tape_run)
    print(f"run_tools result: {result.kind}")

    entries_run = llm.read_entries(tape_run)
    print(f"\nrun_tools() created {len(entries_run)} entries:")
    for i, entry in enumerate(entries_run):
        print(f"  [{i}] {entry.kind}")
        if entry.kind == "message" and isinstance(entry.payload, dict):
            role = entry.payload.get("role", "MISSING!")
            print(f"       role='{role}'")

    messages_run = llm.read_messages(tape_run)
    print(f"\nrun_tools() reconstructed {len(messages_run)} messages:")
    for i, msg in enumerate(messages_run):
        role = msg.get("role", "MISSING!")
        print(f"  [{i}] role='{role}'")

    # Test tool_calls
    print("\n--- Testing tool_calls() ---")
    tape_call = "debug_tool_calls"
    try:
        store.reset(tape_call)
    except:
        pass

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a city",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        }
    ]

    calls = llm.tool_calls(prompt="What's the weather in Madrid?", tools=tools, tape=tape_call)
    print(f"tool_calls result: {len(calls)} call(s)")

    entries_call = llm.read_entries(tape_call)
    print(f"\ntool_calls() created {len(entries_call)} entries:")
    for i, entry in enumerate(entries_call):
        print(f"  [{i}] {entry.kind}")
        if entry.kind == "message" and isinstance(entry.payload, dict):
            role = entry.payload.get("role", "MISSING!")
            print(f"       role='{role}'")

    messages_call = llm.read_messages(tape_call)
    print(f"\ntool_calls() reconstructed {len(messages_call)} messages:")
    for i, msg in enumerate(messages_call):
        role = msg.get("role", "MISSING!")
        print(f"  [{i}] role='{role}'")

    # Compare
    print("\n--- Comparison ---")
    print(f"run_tools entries: {len(entries_run)}, messages: {len(messages_run)}")
    print(f"tool_calls entries: {len(entries_call)}, messages: {len(messages_call)}")


def analyze_root_cause():
    """Analyze and explain the root cause of the issue."""

    print("\n" + "=" * 80)
    print("ROOT CAUSE ANALYSIS")
    print("=" * 80)

    print("""
🔍 ISSUE IDENTIFIED:

When using tool_calls() (not run_tools()), the following happens:

1. First call with tape="test":
   - Entry 0: message (user prompt)
   - Entry 1: tool_call (assistant's tool_calls)
   - Entry 2: tool_result with {"results": []} ← EMPTY ARRAY!
   - Entry 3: event

2. Message reconstruction:
   - Entry 0 (message): Creates role='user' message ✓
   - Entry 1 (tool_call): Creates role='assistant' with tool_calls ✓
   - Entry 2 (tool_result): Creates NO messages because results=[] ✗
   - Result: Missing role='tool' message!

3. Second call with tape="test":
   The reconstructed message sequence is:
   - [0] role='user' (first prompt)
   - [1] role='assistant' with tool_calls (first response)
   - [2] role='user' (second prompt)
   
   MiniMax expects: user → assistant with tool_calls → tool → user
   But we send:     user → assistant with tool_calls → user
   
   Missing the tool result message causes: "invalid role: (2013)"

💡 KEY DIFFERENCE:

run_tools() vs tool_calls():
- run_tools(): Actually executes tools, gets results, stores them in tool_result
  - Creates: user → assistant with tool_calls → tool (with result) ✓
  
- tool_calls(): Only gets tool calls, doesn't execute, stores empty results
  - Creates: user → assistant with tool_calls (missing tool message!) ✗

🎯 THE FIX:

Options:
1. Don't record tool_result entries when results are empty
2. OR reconstruct tool messages even when results are empty (with placeholder)
3. OR make tool_calls() not use tape at all (since it doesn't execute tools)

The cleanest fix is Option 1: Don't record tool_result when there are no results.
This way the tape only contains what actually happened.
""")


if __name__ == "__main__":
    debug_tape_message_reconstruction()
    test_run_tools_vs_tool_calls()
    analyze_root_cause()

    print("\n" + "=" * 80)
    print("Debug script completed")
    print("=" * 80)
