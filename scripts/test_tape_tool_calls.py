#!/usr/bin/env python3
"""Test MiniMax tool calls with tape recording to see what's being stored."""

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

# Add paths
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "upstream" / "republic" / "src"))

from bub.config.settings import AgentSettings, TapeSettings
from bub.integrations.republic_client import build_llm, build_tape_store


def test_tool_calls_with_tape():
    """Test tool calls and check what's recorded on the tape."""

    workspace = Path(__file__).parent.parent

    print("=" * 60)
    print("Test: Tool calls with tape recording")
    print("=" * 60)

    # Setup like Bub does
    tape_settings = TapeSettings()
    agent_settings = AgentSettings()

    store = build_tape_store(agent_settings, tape_settings, workspace)
    llm = build_llm(agent_settings, store)

    # Create a tape
    tape_name = "test_tool_calls"
    tape = llm.tape(tape_name)

    # Clear any existing entries
    tape.reset()

    print("\n--- Initial tape state ---")
    entries = tape.read_entries()
    print(f"Entries: {len(entries)}")

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

    print("\n--- Making tool_calls request ---")
    calls = llm.tool_calls(prompt="What's the weather in Paris?", tools=tools)

    print(f"Returned calls: {json.dumps(calls, indent=2)}")
    print(f"Number of calls: {len(calls)}")

    print("\n--- Tape entries after tool_calls ---")
    entries = tape.read_entries()
    print(f"Total entries: {len(entries)}")

    for i, entry in enumerate(entries):
        print(f"\nEntry {i}:")
        print(f"  ID: {entry.id}")
        print(f"  Kind: {entry.kind}")
        print(f"  Payload: {json.dumps(entry.payload, indent=4)}")
        print(f"  Meta: {entry.meta}")

        if entry.kind == "tool_call":
            print("  >>> TOOL CALL ENTRY FOUND <<<")
            calls_in_entry = entry.payload.get("calls", [])
            print(f"  Number of calls in entry: {len(calls_in_entry)}")

    # Also test with run_tools
    print("\n--- Testing run_tools ---")
    tape.reset()

    from republic.tools.schema import tool

    @tool
    def get_weather(city: str) -> str:
        """Get weather for a city."""
        return f"Weather in {city}: Sunny, 22°C"

    result = llm.run_tools(prompt="What's the weather in London?", tools=[get_weather])

    print(f"Run tools result kind: {result.kind}")
    print(f"Run tools result text: {result.text}")
    print(f"Run tools result tool_calls: {result.tool_calls}")
    print(f"Run tools result tool_results: {result.tool_results}")

    print("\n--- Tape entries after run_tools ---")
    entries = tape.read_entries()
    print(f"Total entries: {len(entries)}")

    for i, entry in enumerate(entries):
        print(f"\nEntry {i}:")
        print(f"  ID: {entry.id}")
        print(f"  Kind: {entry.kind}")
        print(f"  Payload: {json.dumps(entry.payload, indent=4)}")


if __name__ == "__main__":
    test_tool_calls_with_tape()
