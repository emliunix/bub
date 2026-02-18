"""Test transport implementations.

Provides mock transports that don't require actual WebSocket connections,
enabling fast, deterministic tests of message bus logic.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from bub.rpc.types import Transport


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
    "MockPeer",
    "PairedTransport",
]
