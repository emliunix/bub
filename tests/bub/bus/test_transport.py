"""In-memory transport implementation for testing.

Provides mock transport that doesn't require actual WebSocket connections,
enabling fast, deterministic tests of message bus logic.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from typing import Any

from bub.rpc.types import Transport


class InMemoryTransport(Transport):
    """In-memory transport for testing.

    Simulates message sending/receiving without actual network I/O.
    Used to test bus logic in isolation.
    """

    def __init__(self, name: str = "test"):
        self._name = name
        self._incoming: asyncio.Queue[str] = asyncio.Queue()
        self._outgoing: asyncio.Queue[str] = asyncio.Queue()
        self._closed = False
        self._recv_count = 0
        self._send_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def recv_count(self) -> int:
        return self._recv_count

    @property
    def send_count(self) -> int:
        return self._send_count

    async def send_message(self, message: str) -> None:
        """Send a message - puts it in outgoing queue."""
        if self._closed:
            raise RuntimeError("Transport closed")
        self._send_count += 1
        await self._outgoing.put(message)

    async def receive_message(self) -> str:
        """Receive a message - waits on incoming queue."""
        if self._closed:
            raise RuntimeError("Transport closed")
        message = await self._incoming.get()
        self._recv_count += 1
        return message

    def inject_message(self, message: str) -> None:
        """Inject a message into the incoming queue (for testing)."""
        self._incoming.put_nowait(message)

    def inject_json(self, data: dict[str, Any]) -> None:
        """Inject a JSON message into the incoming queue."""
        self.inject_message(json.dumps(data))

    async def receive_outgoing(self) -> str:
        """Receive a message from the outgoing queue (for verification)."""
        return await self._outgoing.get()

    def close(self) -> None:
        """Close the transport."""
        self._closed = True


class PairedTransport:
    """Creates two connected transports for testing client-server scenarios.

    Messages sent on transport A are received on transport B and vice versa.
    """

    def __init__(self):
        # A -> B queue
        self._a_to_b: asyncio.Queue[str] = asyncio.Queue()
        # B -> A queue
        self._b_to_a: asyncio.Queue[str] = asyncio.Queue()

        self.a = self._PairedTransportImpl("A", self._b_to_a, self._a_to_b)
        self.b = self._PairedTransportImpl("B", self._a_to_b, self._b_to_a)

    class _PairedTransportImpl(Transport):
        """Implementation of one side of a paired transport."""

        def __init__(
            self,
            name: str,
            recv_queue: asyncio.Queue[str],
            send_queue: asyncio.Queue[str],
        ):
            self._name = name
            self._recv_queue = recv_queue
            self._send_queue = send_queue
            self._closed = False

        @property
        def name(self) -> str:
            return self._name

        async def send_message(self, message: str) -> None:
            if self._closed:
                raise RuntimeError("Transport closed")
            await self._send_queue.put(message)

        async def receive_message(self) -> str:
            if self._closed:
                raise RuntimeError("Transport closed")
            return await self._recv_queue.get()

        def close(self) -> None:
            self._closed = True


class MockPeer:
    """Mock peer for testing message flows.

    Simulates a client that can subscribe to addresses and receive messages.
    """

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.subscriptions: set[str] = set()
        self.received_messages: list[dict[str, Any]] = []
        self._handlers: dict[str, Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]] = {}

    def subscribe(self, address: str) -> None:
        """Subscribe to an address pattern."""
        self.subscriptions.add(address)

    def on_message(
        self,
        address: str,
        handler: Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """Register a handler for messages matching an address."""
        self._handlers[address] = handler

    async def receive_message(self, from_addr: str, to: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Receive a message and optionally process it."""
        self.received_messages.append({
            "from": from_addr,
            "to": to,
            "payload": payload,
        })

        # Check if we have a handler for this address
        for pattern, handler in self._handlers.items():
            if self._match_pattern(to, pattern):
                await handler(from_addr, payload)
                return {"success": True, "message": "processed"}

        return {"success": True, "message": "received"}

    def _match_pattern(self, address: str, pattern: str) -> bool:
        """Check if address matches pattern (supports * wildcard)."""
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return address.startswith(prefix)
        return address == pattern

    def clear_messages(self) -> None:
        """Clear received message history."""
        self.received_messages.clear()


__all__ = [
    "InMemoryTransport",
    "MockPeer",
    "PairedTransport",
]
