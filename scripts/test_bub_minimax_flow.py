#!/usr/bin/env python3
"""Test Bub-style MiniMax tool call flow to trace where calls are lost."""

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

from bub.config.settings import AgentSettings, TapeSettings, load_settings
from bub.integrations.republic_client import build_llm, build_tape_store


def test_bub_style_tool_calls():
    """Test tool calls using Bub's actual configuration flow."""

    workspace = Path(__file__).parent.parent

    print("=" * 60)
    print("Test: Bub-style MiniMax tool calls")
    print("=" * 60)

    # Load settings like Bub does
    print(f"\n--- Loading settings for workspace: {workspace}")
    settings = load_settings(workspace)

    print(f"Model: {settings.model}")
    print(f"API Base: {settings.api_base}")
    print(f"API Key (first 20 chars): {settings.resolved_api_key[:20] if settings.resolved_api_key else 'None'}...")

    # Build tape store
    print("\n--- Building tape store")
    tape_settings = TapeSettings()
    agent_settings = AgentSettings()

    print(f"AgentSettings model: {agent_settings.model}")
    print(f"AgentSettings api_base: {agent_settings.api_base}")
    print(
        f"AgentSettings api_key (first 20): {agent_settings.resolved_api_key[:20] if agent_settings.resolved_api_key else 'None'}..."
    )

    store = build_tape_store(agent_settings, tape_settings, workspace)
    print(f"Store type: {type(store)}")

    # Build LLM like Bub does
    print("\n--- Building LLM client")
    llm = build_llm(agent_settings, store)
    print(f"LLM provider: {llm.provider}")
    print(f"LLM model: {llm.model}")

    # Test tool calls
    print("\n--- Testing tool_calls")
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
        calls = llm.tool_calls(prompt="What's the weather in Paris?", tools=tools)
        print(f"Tool calls returned: {json.dumps(calls, indent=2)}")
        print(f"Number of calls: {len(calls)}")

        if calls:
            print("\n✅ SUCCESS: Tool calls are working!")
        else:
            print("\n❌ FAILURE: Tool calls returned empty list")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_bub_style_tool_calls()
