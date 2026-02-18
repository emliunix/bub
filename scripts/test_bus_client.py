#!/usr/bin/env python3
"""Test client to send messages to the bus."""

import asyncio
import json
import os
import sys

import websockets

# Disable proxy for local connection
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

print(f"HTTP_PROXY: {os.environ.get('HTTP_PROXY', 'NOT SET')}")
print(f"HTTPS_PROXY: {os.environ.get('HTTPS_PROXY', 'NOT SET')}")
print(f"http_proxy: {os.environ.get('http_proxy', 'NOT SET')}")
print(f"https_proxy: {os.environ.get('https_proxy', 'NOT SET')}")

URL = "ws://localhost:7892"


async def main():
    async with websockets.connect(URL) as ws:
        print(f"Connected to {URL}")

        # Initialize
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"clientId": "test-client"},
        }
        await ws.send(json.dumps(init_msg))
        resp = json.loads(await ws.recv())
        print(f"Initialized: {resp}")

        # Subscribe to outbound messages
        sub_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "subscribe",
            "params": {"address": "outbound:*"},
        }
        await ws.send(json.dumps(sub_msg))
        resp = json.loads(await ws.recv())
        print(f"Subscribed: {resp}")

        # Send inbound message using sendMessage (simulating telegram)
        content = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "test from ws"
        inbound_msg = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "sendMessage",
            "params": {
                "to": "inbound:436026689",
                "payload": {
                    "messageId": f"test_{asyncio.get_event_loop().time()}",
                    "type": "tg_message",
                    "from": "tg:436026689",
                    "timestamp": "2026-02-18T00:00:00Z",
                    "content": {"text": content, "channel": "telegram", "chatId": "436026689", "senderId": "436026689"},
                },
            },
        }
        await ws.send(json.dumps(inbound_msg))
        print(f"Sent inbound: {content}")

        timeout = int(os.environ.get("BUS_CLIENT_TIMEOUT", "10"))
        print(f"Listening for messages (timeout={timeout}s)...")
        deadline = asyncio.get_event_loop().time() + timeout
        try:
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                msg = await asyncio.wait_for(ws.recv(), timeout=remaining)
                print(f"Received: {msg[:400]}")
        except TimeoutError:
            pass
        print(f"Done (exiting after {timeout}s)")


if __name__ == "__main__":
    asyncio.run(main())
