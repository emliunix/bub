#!/usr/bin/env python3
"""Minimal reproducible test for Republic client with MiniMax API tool calling.

This script tests the full flow:
1. Initialize Republic LLM client with MiniMax configuration
2. Send a message that requires a tool
3. Handle the tool call response
4. Send the tool result back to the model
5. Get the final response

Usage:
    uv run python scripts/test_minimal_republic_minimax.py

Requirements:
    - BUB_AGENT_API_KEY or MINIMAX_API_KEY in .env file
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path


def load_env_file() -> None:
    """Load .env file from project root."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        print(f"Loading environment from: {env_path}")
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key, val)
    else:
        print(f"Warning: .env file not found at {env_path}")


def setup_paths() -> None:
    """Add upstream republic to path."""
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root / "upstream" / "republic" / "src"))
    sys.path.insert(0, str(project_root / "src"))


def get_weather(city: str) -> str:
    """Get weather for a city (test tool implementation)."""
    return f"Sunny, 25°C in {city}"


def main() -> None:
    """Run the minimal reproducible test."""
    print("=" * 70)
    print("Minimal Reproducible Test: Republic Client + MiniMax API")
    print("=" * 70)

    # Load environment and setup paths
    load_env_file()
    setup_paths()

    # Import after path setup
    from republic import LLM

    # Get API configuration
    api_key = os.getenv("BUB_AGENT_API_KEY") or os.getenv("MINIMAX_API_KEY")
    api_base = "https://api.minimax.chat/v1"
    model = "minimax:MiniMax-Text-01"

    if not api_key:
        print("\nERROR: API key not found!")
        print("Please set BUB_AGENT_API_KEY or MINIMAX_API_KEY in your .env file")
        sys.exit(1)

    print("\nConfiguration:")
    print(f"  Model: {model}")
    print(f"  API Base: {api_base}")
    print(f"  API Key: {'*' * 10}{api_key[-4:]}")

    # Define test tool
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for a city",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The name of the city to get weather for",
                        }
                    },
                    "required": ["city"],
                },
            },
        }
    ]

    print(f"\n{'=' * 70}")
    print("STEP 1: Initialize Republic LLM client")
    print(f"{'=' * 70}")

    try:
        llm = LLM(
            model=model,
            api_key=api_key,
            api_base=api_base,
            verbose=2,  # Enable verbose logging
        )
        print("✓ LLM client initialized successfully")
        print(f"  Provider: {llm.provider}")
        print(f"  Model: {llm.model}")
    except Exception as e:
        print(f"✗ Failed to initialize LLM client: {e}")
        traceback.print_exc()
        sys.exit(1)

    print(f"\n{'=' * 70}")
    print("STEP 2: Send message to trigger tool call")
    print(f"{'=' * 70}")

    prompt = "What's the weather like in Paris?"
    print(f"User message: '{prompt}'")
    print(f"Available tools: {[t['function']['name'] for t in tools]}")

    try:
        # Get tool calls from the model
        tool_calls = llm.tool_calls(prompt=prompt, tools=tools)
        print("\n✓ Tool calls received:")
        print(json.dumps(tool_calls, indent=2))
    except Exception as e:
        print(f"\n✗ Failed to get tool calls: {e}")
        traceback.print_exc()
        sys.exit(1)

    if not tool_calls:
        print("\n✗ No tool calls returned - model did not request tool execution")
        print("This may indicate an issue with the MiniMax API or tool configuration")
        sys.exit(1)

    print(f"\n{'=' * 70}")
    print("STEP 3: Execute tool and get result")
    print(f"{'=' * 70}")

    # Execute the tool calls
    tool_results = []
    for call in tool_calls:
        call_id = call.get("id", "unknown")
        func_name = call.get("function", {}).get("name", "unknown")
        arguments_str = call.get("function", {}).get("arguments", "{}")

        print("\nProcessing tool call:")
        print(f"  ID: {call_id}")
        print(f"  Function: {func_name}")
        print(f"  Arguments: {arguments_str}")

        try:
            args = json.loads(arguments_str)
        except json.JSONDecodeError:
            print("  ✗ Failed to parse arguments as JSON")
            args = {}

        if func_name == "get_weather":
            city = args.get("city", "unknown")
            result = get_weather(city)
            print(f"  ✓ Tool executed: get_weather({city})")
            print(f"  Result: {result}")
            tool_results.append({
                "tool_call_id": call_id,
                "role": "tool",
                "name": func_name,
                "content": result,
            })
        else:
            print(f"  ✗ Unknown tool: {func_name}")
            tool_results.append({
                "tool_call_id": call_id,
                "role": "tool",
                "name": func_name,
                "content": f"Error: Unknown tool '{func_name}'",
            })

    print(f"\n{'=' * 70}")
    print("STEP 4: Send tool results back to model")
    print(f"{'=' * 70}")

    # Build message history with tool results
    messages = [
        {"role": "user", "content": prompt},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls,
        },
    ]
    for result in tool_results:
        messages.append({
            "role": "tool",
            "tool_call_id": result["tool_call_id"],
            "name": result["name"],
            "content": result["content"],
        })

    print("Messages being sent:")
    for i, msg in enumerate(messages):
        print(f"  [{i}] {msg}")

    try:
        # Get final response after tool results (no tools needed for final response)
        final_response = llm.chat(messages=messages)
        print("\n✓ Final response received:")
        print(f"  {final_response}")
    except Exception as e:
        print(f"\n✗ Failed to get final response: {e}")
        traceback.print_exc()
        sys.exit(1)

    print(f"\n{'=' * 70}")
    print("TEST COMPLETED SUCCESSFULLY")
    print(f"{'=' * 70}")
    print("\nSummary:")
    print("  ✓ LLM client initialized")
    print(f"  ✓ Tool calls received: {len(tool_calls)}")
    print(f"  ✓ Tool results executed: {len(tool_results)}")
    print("  ✓ Final response received")
    print("\nFinal Answer:")
    print(f"  {final_response}")


if __name__ == "__main__":
    main()
