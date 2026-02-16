#!/usr/bin/env python3
"""Test MiniMax tool calls through Republic to trace where calls are lost."""

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

# Add upstream/republic to path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "upstream" / "republic" / "src"))

from republic import LLM


def test_minimax_through_republic():
    """Test MiniMax tool calls using Republic client (sync version)."""

    # Simple weather tool
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

    # Get API key from env (try multiple sources)
    api_key = os.getenv("MINIMAX_API_KEY") or os.getenv("BUB_AGENT_API_KEY")
    api_base = os.getenv("BUB_AGENT_API_BASE") or os.getenv("BUB_API_BASE")
    if not api_key:
        print("ERROR: MINIMAX_API_KEY or BUB_AGENT_API_KEY not set")
        return

    print("=" * 60)
    print("Test: MiniMax through Republic")
    print("=" * 60)

    # Create LLM client
    llm = LLM(
        model="minimax:MiniMax-Text-01",
        api_key=api_key,
        api_base=api_base,
        verbose=2,  # Enable verbose logging
    )

    print("\n--- Test 1: tool_calls method ---")
    try:
        calls = llm.tool_calls(prompt="What's the weather in Paris?", tools=tools)
        print(f"Tool calls returned: {json.dumps(calls, indent=2)}")
        print(f"Number of calls: {len(calls)}")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()

    print("\n--- Test 2: Debug raw response ---")
    try:
        # Access the underlying client to debug
        from any_llm import AnyLLM

        client = AnyLLM.create("minimax", api_key=api_key, api_base=api_base)

        messages = [{"role": "user", "content": "What's the weather in Tokyo?"}]

        response = client.completion(model="MiniMax-Text-01", messages=messages, tools=tools, stream=False)

        print(f"Raw response type: {type(response)}")
        print(f"Raw response: {response}")
        print()

        # Check response structure
        if hasattr(response, "choices"):
            print(f"Number of choices: {len(response.choices)}")
            if response.choices:
                choice = response.choices[0]
                print(f"Choice: {choice}")
                if hasattr(choice, "message"):
                    msg = choice.message
                    print(f"Message: {msg}")
                    print(f"Message type: {type(msg)}")
                    if hasattr(msg, "content"):
                        print(f"Message content: {msg.content}")
                    if hasattr(msg, "tool_calls"):
                        print(f"Message tool_calls: {msg.tool_calls}")
                        if msg.tool_calls:
                            for i, tc in enumerate(msg.tool_calls):
                                print(f"  Tool call {i}: {tc}")
                                print(f"    type: {type(tc)}")
                                print(f"    id: {getattr(tc, 'id', 'N/A')}")
                                print(f"    type attr: {getattr(tc, 'type', 'N/A')}")
                                if hasattr(tc, "function"):
                                    func = tc.function
                                    print(f"    function: {func}")
                                    print(f"    function type: {type(func)}")
                                    print(f"    function.name: {getattr(func, 'name', 'N/A')}")
                                    print(f"    function.arguments: {getattr(func, 'arguments', 'N/A')}")
                    else:
                        print("Message has no tool_calls attribute")
                else:
                    print("Choice has no message attribute")
        else:
            print("Response has no choices attribute")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_minimax_through_republic()
