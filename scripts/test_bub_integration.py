#!/usr/bin/env python3
"""Debug test to isolate tool call handling breakdown in Bub integration."""

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

from republic import Tool
from republic.tools.schema import normalize_tools

from bub.config.settings import AgentSettings, TapeSettings, load_settings
from bub.integrations.republic_client import build_llm, build_tape_store
from bub.tools.registry import ToolRegistry


def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny, 72°F"


def test_tool_normalization():
    """Test that tools are properly normalized."""
    print("=" * 70)
    print("Test 1: Tool Normalization")
    print("=" * 70)

    # Create a Tool from callable
    tool = Tool.from_callable(get_weather, name="get_weather", description="Get weather for a city")

    print(f"\nTool: {tool}")
    print(f"Tool name: {tool.name}")
    print(f"Tool handler: {tool.handler}")
    print(f"Tool has handler: {tool.handler is not None}")

    # Test normalization
    toolset = normalize_tools([tool])
    print("\nNormalized ToolSet:")
    print(f"  Schemas: {len(toolset.schemas)}")
    print(f"  Runnable: {len(toolset.runnable)}")
    print(f"  Payload: {toolset.payload}")

    # Test require_runnable
    try:
        toolset.require_runnable()
        print("\n✅ require_runnable() passed")
    except ValueError as e:
        print(f"\n❌ require_runnable() failed: {e}")


def test_registry_tools():
    """Test ToolRegistry tool creation."""
    print("\n" + "=" * 70)
    print("Test 2: ToolRegistry Tool Creation")
    print("=" * 70)

    registry = ToolRegistry()

    # Register a test tool
    @registry.register(name="test_weather", short_description="Get weather", model=None, context=False)
    def test_weather(city: str) -> str:
        return f"Weather in {city}: Sunny"

    # Get model_tools
    tools = registry.model_tools()
    print(f"\nRegistered tools: {len(tools)}")

    for tool in tools:
        print(f"\nTool: {tool.name}")
        print(f"  Handler: {tool.handler}")
        print(f"  Has handler: {tool.handler is not None}")

    # Test normalization of registry tools
    if tools:
        toolset = normalize_tools(tools)
        print("\nNormalized ToolSet:")
        print(f"  Schemas: {len(toolset.schemas)}")
        print(f"  Runnable: {len(toolset.runnable)}")

        try:
            toolset.require_runnable()
            print("\n✅ require_runnable() passed for registry tools")
        except ValueError as e:
            print(f"\n❌ require_runnable() failed: {e}")


def test_with_tape():
    """Test tool calls with tape storage."""
    print("\n" + "=" * 70)
    print("Test 3: Tool Calls With Tape")
    print("=" * 70)

    workspace = Path(__file__).parent.parent
    settings = load_settings(workspace)
    tape_settings = TapeSettings()
    agent_settings = AgentSettings()
    store = build_tape_store(agent_settings, tape_settings, workspace)
    llm = build_llm(agent_settings, store)

    # Create tool
    tool = Tool.from_callable(get_weather, name="get_weather", description="Get weather for a city")

    print("\n--- Testing tool_calls (no execution) ---")
    try:
        calls = llm.tool_calls(prompt="What's the weather in Paris?", tools=[tool], tape="test_tool_calls")
        print(f"Tool calls: {json.dumps(calls, indent=2)}")
        print("✅ tool_calls() succeeded")
    except Exception as e:
        print(f"❌ tool_calls() failed: {e}")

    print("\n--- Testing run_tools (with execution) ---")
    try:
        result = llm.run_tools(prompt="What's the weather in Paris?", tools=[tool], tape="test_run_tools")
        print(f"Result kind: {result.kind}")
        print(f"Result text: {result.text}")
        print(f"Result tool_calls: {result.tool_calls}")
        print(f"Result tool_results: {result.tool_results}")
        print(f"Result error: {result.error}")

        if result.error:
            print("\n❌ run_tools() returned error")
        else:
            print("\n✅ run_tools() succeeded")
    except Exception as e:
        print(f"❌ run_tools() failed with exception: {e}")
        import traceback

        traceback.print_exc()


def test_schema_only_tools():
    """Test what happens with schema-only (dict) tools."""
    print("\n" + "=" * 70)
    print("Test 4: Schema-Only (Dict) Tools")
    print("=" * 70)

    # Schema-only tool (dict)
    schema_tool = {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a city",
            "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
        },
    }

    print(f"\nSchema-only tool: {json.dumps(schema_tool, indent=2)}")

    toolset = normalize_tools([schema_tool])
    print("\nNormalized ToolSet:")
    print(f"  Schemas: {len(toolset.schemas)}")
    print(f"  Runnable: {len(toolset.runnable)}")

    try:
        toolset.require_runnable()
        print("\n✅ require_runnable() passed (unexpected!)")
    except ValueError as e:
        print(f"\n❌ require_runnable() failed as expected: {e}")


def test_tape_message_reconstruction():
    """Test how tool calls are reconstructed from tape entries."""
    print("\n" + "=" * 70)
    print("Test 5: Tape Message Reconstruction")
    print("=" * 70)

    workspace = Path(__file__).parent.parent
    settings = load_settings(workspace)
    tape_settings = TapeSettings()
    agent_settings = AgentSettings()
    store = build_tape_store(agent_settings, tape_settings, workspace)
    llm = build_llm(agent_settings, store)

    tool = Tool.from_callable(get_weather, name="get_weather", description="Get weather for a city")

    tape_name = "test_reconstruction"

    # First, make a tool call to populate the tape
    print("\n--- Making tool call to populate tape ---")
    try:
        result = llm.run_tools(prompt="What's the weather in Paris?", tools=[tool], tape=tape_name)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error (expected if schema-only): {e}")

    # Read raw tape entries
    print(f"\n--- Reading tape entries from '{tape_name}' ---")
    entries = llm.read_entries(tape_name)
    print(f"Number of entries: {len(entries)}")

    for i, entry in enumerate(entries):
        print(f"\nEntry {i}:")
        print(f"  ID: {entry.id}")
        print(f"  Kind: {entry.kind}")
        print(f"  Payload keys: {list(entry.payload.keys()) if isinstance(entry.payload, dict) else 'N/A'}")
        if isinstance(entry.payload, dict):
            for key, value in entry.payload.items():
                if key in ["calls", "results", "tool_calls", "messages"]:
                    print(f"  {key}: {json.dumps(value, indent=4)[:500]}")

    # Read messages via context
    print("\n--- Reading messages via context ---")
    messages = llm.read_messages(tape_name)
    print(f"Number of messages: {len(messages)}")

    for i, msg in enumerate(messages):
        print(f"\nMessage {i}:")
        print(f"  Role: {msg.get('role')}")
        print(f"  Content: {msg.get('content', '')[:100]}")
        if "tool_calls" in msg:
            print(f"  Tool calls: {json.dumps(msg['tool_calls'], indent=2)[:500]}")
        if "tool_call_id" in msg:
            print(f"  Tool call ID: {msg['tool_call_id']}")


if __name__ == "__main__":
    test_tool_normalization()
    test_registry_tools()
    test_schema_only_tools()
    test_with_tape()
    test_tape_message_reconstruction()

    print("\n" + "=" * 70)
    print("All tests completed")
    print("=" * 70)
