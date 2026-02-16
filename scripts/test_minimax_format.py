#!/usr/bin/env python3
"""Test MiniMax tool calling - check exact response format."""

import json
import sys

from openai import OpenAI

# Use the API key from command line arg or env
API_KEY = sys.argv[1] if len(sys.argv) > 1 else None
if not API_KEY:
    import os

    API_KEY = os.environ.get("BUB_AGENT_API_KEY") or os.environ.get("OPENAI_API_KEY")

client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.minimaxi.com/v1",
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        },
    }
]

# Call with tools
resp = client.chat.completions.create(
    model="MiniMax-M2.5",
    messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
    tools=TOOLS,
)

print("=== Full Response ===")
print(json.dumps(resp.model_dump(), indent=2, ensure_ascii=False, default=str))
