#!/usr/bin/env python3
"""Test MiniMax tool calling directly."""

import os

from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("MINIMAX_API_KEY", os.environ.get("BUB_AGENT_API_KEY")),
    base_url="https://api.minimaxi.com/v1",
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g., San Francisco, CA",
                    }
                },
                "required": ["location"],
            },
        },
    }
]

# Test 1: Simple call without tools
print("=== Test 1: Simple call ===")
resp = client.chat.completions.create(
    model="MiniMax-M2.5",
    messages=[{"role": "user", "content": "Hello"}],
)
print(f"Response: {resp.choices[0].message.content}")

# Test 2: Call with tools - model should return tool_calls
print("\n=== Test 2: Model makes tool call ===")
resp = client.chat.completions.create(
    model="MiniMax-M2.5",
    messages=[{"role": "user", "content": "What's the weather in San Francisco?"}],
    tools=TOOLS,
)
print(f"Has tool_calls: {resp.choices[0].message.tool_calls is not None}")
if resp.choices[0].message.tool_calls:
    for tc in resp.choices[0].message.tool_calls:
        print(f"Tool: {tc.function.name}, Args: {tc.function.arguments}")

# Test 3: Send tool result back - OpenAI format (role: tool)
print("\n=== Test 3: Tool result with role='tool' (OpenAI format) ===")
messages = [
    {"role": "user", "content": "What's the weather in San Francisco?"},
]
resp = client.chat.completions.create(
    model="MiniMax-M2.5",
    messages=messages,
    tools=TOOLS,
)
if resp.choices[0].message.tool_calls:
    messages.append({
        "role": resp.choices[0].message.role,
        "content": resp.choices[0].message.content,
        "tool_calls": [tc.model_dump() for tc in resp.choices[0].message.tool_calls],
    })
    tool_call = resp.choices[0].message.tool_calls[0]
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call.id,
        "name": tool_call.function.name,
        "content": "25 degrees, sunny",
    })
    print(f"Messages to send: {len(messages)}")
    for i, m in enumerate(messages):
        print(f"  [{i}] role={m.get('role')}, keys={list(m.keys())}")

    try:
        resp2 = client.chat.completions.create(
            model="MiniMax-M2.5",
            messages=messages,
            tools=TOOLS,
        )
        print(f"Success! Response: {resp2.choices[0].message.content}")
    except Exception as e:
        print(f"Error: {e}")

# Test 4: Send tool result back - MiniMax format (role: user with array)
print("\n=== Test 4: Tool result with role='user' + array content (MiniMax format) ===")
messages = [
    {"role": "user", "content": "What's the weather in San Francisco?"},
]
resp = client.chat.completions.create(
    model="MiniMax-M2.5",
    messages=messages,
    tools=TOOLS,
)
if resp.choices[0].message.tool_calls:
    messages.append({
        "role": resp.choices[0].message.role,
        "content": resp.choices[0].message.content,
        "tool_calls": [tc.model_dump() for tc in resp.choices[0].message.tool_calls],
    })
    tool_call = resp.choices[0].message.tool_calls[0]
    messages.append({
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": tool_call.id, "content": "25 degrees, sunny"}],
    })
    print(f"Messages to send: {len(messages)}")
    for i, m in enumerate(messages):
        print(f"  [{i}] role={m.get('role')}, content type={type(m.get('content'))}")

    try:
        resp2 = client.chat.completions.create(
            model="MiniMax-M2.5",
            messages=messages,
            tools=TOOLS,
        )
        print(f"Success! Response: {resp2.choices[0].message.content}")
    except Exception as e:
        print(f"Error: {e}")
