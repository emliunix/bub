#!/usr/bin/env python3
"""Minimal reproduction script to identify test report output during tool execution."""

import os
import sys
from pathlib import Path

# Setup paths
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "upstream" / "republic" / "src"))

# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key, val)

from republic import Tool
from bub.config.settings import AgentSettings, TapeSettings
from bub.integrations.republic_client import build_llm, build_tape_store


def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny, 72°F"


def main():
    print("=" * 70)
    print("Testing tool execution for test report output")
    print("=" * 70)
    print()

    # Check for pytest modules before import
    pytest_modules = [m for m in sys.modules.keys() if "pytest" in m or "conftest" in m]
    if pytest_modules:
        print(f"WARNING: Found pytest modules loaded: {pytest_modules}")
    else:
        print("✓ No pytest modules loaded before test")
    print()

    # Setup minimal Bub environment
    workspace = Path.cwd()
    agent_settings = AgentSettings()
    tape_settings = TapeSettings()

    print(f"Settings loaded:")
    print(f"  Model: {agent_settings.model}")
    print(f"  API Key set: {bool(agent_settings.resolved_api_key)}")
    print()

    # Build tape store and LLM
    store = build_tape_store(agent_settings, tape_settings, workspace)
    llm = build_llm(agent_settings, store)

    print(f"LLM initialized: {llm.model}")
    print()

    # Check for pytest modules after import
    pytest_modules_after = [m for m in sys.modules.keys() if "pytest" in m or "conftest" in m]
    if pytest_modules_after:
        print(f"WARNING: Found pytest modules loaded after setup: {pytest_modules_after}")
        print()

    # Create a tool
    tool = Tool.from_callable(get_weather, name="get_weather", description="Get weather")

    print("Executing tool via llm.tools.execute...")
    print("-" * 70)

    # Execute the tool
    result = llm.tools.execute([{"function": {"name": "get_weather", "arguments": {"city": "Boston"}}}], tools=[tool])

    print("-" * 70)
    print(f"Tool execution result:")
    print(f"  tool_calls: {result.tool_calls}")
    print(f"  tool_results: {result.tool_results}")
    print(f"  error: {result.error}")
    print()

    # Check for pytest modules after execution
    pytest_modules_final = [m for m in sys.modules.keys() if "pytest" in m or "conftest" in m]
    if pytest_modules_final:
        print(f"WARNING: Found pytest modules loaded after execution: {pytest_modules_final}")
    else:
        print("✓ No pytest modules loaded after execution")


if __name__ == "__main__":
    main()
