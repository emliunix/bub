#!/usr/bin/env python3
"""Test multi-turn conversation with tool calls to verify context handling."""

import os
import sys
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
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "upstream" / "republic" / "src"))

from republic import Tool

from bub.config.settings import AgentSettings, TapeSettings
from bub.integrations.republic_client import build_llm
from bub.tape.context import _select_messages
from bub.tape.store import FileTapeStore


def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny, 25°C"


def get_time(city: str) -> str:
    """Get current time for a city."""
    return f"Current time in {city}: 14:30"


def test_multi_turn_conversation():
    """Test that tool call context is properly maintained across turns."""

    print("=" * 70)
    print("Test: Multi-Turn Conversation with Tool Calls")
    print("=" * 70)

    # Setup
    workspace = Path(__file__).parent.parent
    tape_settings = TapeSettings()
    agent_settings = AgentSettings()
    store = FileTapeStore(tape_settings.resolve_home(), workspace)
    llm = build_llm(agent_settings, store)

    tape_name = "test_multi_turn"
    tape = llm.tape(tape_name)
    tape.reset()

    # Create tools
    weather_tool = Tool.from_callable(get_weather, name="get_weather", description="Get weather")
    time_tool = Tool.from_callable(get_time, name="get_time", description="Get time")
    tools = [weather_tool, time_tool]

    print("\n--- Turn 1: Ask about Paris weather ---")
    result1 = llm.run_tools(prompt="What's the weather in Paris?", tools=tools, tape=tape_name)
    print(f"Result: {result1.tool_calls}")
    print(f"Results: {result1.tool_results}")

    print("\n--- Turn 2: Ask about London time (should see Paris weather in context) ---")
    result2 = llm.run_tools(prompt="What time is it in London?", tools=tools, tape=tape_name)
    print(f"Result: {result2.tool_calls}")
    print(f"Results: {result2.tool_results}")

    print("\n--- Turn 3: Ask follow-up about Paris (model should know we already checked) ---")
    result3 = llm.run_tools(prompt="Is it warm in Paris?", tools=tools, tape=tape_name)
    print(f"Result: {result3.tool_calls}")
    print(f"Results: {result3.tool_results}")

    # Check tape entries
    print("\n--- Checking tape state ---")
    entries = tape.read_entries()
    print(f"Total entries: {len(entries)}")

    # Get messages that would be sent
    messages = _select_messages(entries, None)
    print(f"\nTotal messages: {len(messages)}")

    # Verify message structure
    print("\n--- Message sequence ---")
    for i, msg in enumerate(messages):
        role = msg.get("role")
        content = msg.get("content", "")[:50]

        if role == "user":
            print(f"{i}. [USER] {content}")
        elif role == "assistant":
            if "tool_calls" in msg:
                calls = msg["tool_calls"]
                call_names = [c.get("function", {}).get("name", "unknown") for c in calls]
                print(f"{i}. [ASSISTANT] Tool calls: {call_names}")
            else:
                print(f"{i}. [ASSISTANT] {content}")
        elif role == "tool":
            tool_call_id = msg.get("tool_call_id", "N/A")
            print(f"{i}. [TOOL] id={tool_call_id[:20]}... content={content[:50]}")

    # Verify all tool results have tool_call_id
    tool_results = [m for m in messages if m.get("role") == "tool"]
    results_with_id = [m for m in tool_results if "tool_call_id" in m]

    print("\n--- Verification ---")
    print(f"Total tool result messages: {len(tool_results)}")
    print(f"Tool results with tool_call_id: {len(results_with_id)}")

    if len(tool_results) == len(results_with_id):
        print("✅ All tool results have tool_call_id")
    else:
        print("❌ Some tool results missing tool_call_id")

    # Check for message ordering issues
    print("\n--- Checking message ordering ---")
    for i in range(len(messages) - 1):
        curr = messages[i]
        next_msg = messages[i + 1]

        # Check that tool result follows assistant message with tool_calls
        if curr.get("role") == "assistant" and "tool_calls" in curr:
            if next_msg.get("role") != "tool":
                print(f"⚠️  Warning: Message {i} has tool_calls but message {i + 1} is not a tool result")
                print(f"   Message {i + 1} role: {next_msg.get('role')}")


if __name__ == "__main__":
    test_multi_turn_conversation()
