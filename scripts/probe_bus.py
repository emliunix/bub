#!/usr/bin/env python3
"""Remote probe to test bus connectivity and spawn functionality."""

import asyncio
import sys
import uuid
from datetime import UTC, datetime

# Add src to path
sys.path.insert(0, "/home/liu/Documents/bub/src")

from bub.bus.bus import AgentBusClient
from bub.bus.protocol import SendMessageParams


async def probe_bus():
    """Probe the bus to test connectivity."""
    print("=== Bus Probe ===")

    client = AgentBusClient("ws://localhost:7892", auto_reconnect=False)
    received_response = False
    agent_id = None

    async def handle_message(topic: str, payload: dict):
        nonlocal received_response, agent_id
        msg_type = payload.get("type", "")
        print(f"[RECV] topic={topic} type={msg_type}")

        if msg_type == "spawn_result":
            content = payload.get("content", {})
            if content.get("success"):
                agent_id = content.get("client_id")
                print(f"[SUCCESS] Agent spawned: {agent_id}")
            else:
                print(f"[FAILED] Error: {content.get('error')}")
            received_response = True

    try:
        # Connect
        print("Connecting...")
        await client.connect()
        await client.initialize("probe-client")
        print(f"Connected as probe-client")

        # Subscribe to receive spawn response
        await client.subscribe("tg:probe123", handle_message)
        print("Subscribed to tg:probe123")

        # Send spawn request
        spawn_msg = {
            "messageId": f"probe_{uuid.uuid4().hex[:8]}",
            "type": "spawn_request",
            "from": "tg:probe123",
            "timestamp": datetime.now(UTC).isoformat(),
            "content": {
                "chat_id": "probe123",
                "channel": "telegram",
                "channel_type": "telegram",
            },
        }

        print(f"Sending spawn_request to system:spawn...")
        await client._api.send_message(SendMessageParams(to="system:spawn", payload=spawn_msg))
        print("Request sent, waiting for response (max 10s)...")

        # Wait for response
        for i in range(20):
            if received_response:
                break
            await asyncio.sleep(0.5)
            if i % 4 == 0:
                print(f"  ... {i // 2}s elapsed")

        if received_response:
            print(f"\n✅ SUCCESS: Agent {agent_id} spawned")
            return True
        else:
            print("\n❌ TIMEOUT: No spawn_result received")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        await client.disconnect()
        print("Disconnected")


if __name__ == "__main__":
    result = asyncio.run(probe_bus())
    sys.exit(0 if result else 1)
