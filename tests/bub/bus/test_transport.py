"""Test transport implementations.

Provides mock transports that don't require actual WebSocket connections,
enabling fast, deterministic tests of message bus logic.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from bub.bus.protocol import (
    AgentBusClientCallbacks,
    ProcessMessageParams,
    ProcessMessageResult,
)
from bub.bus.types import Closable
from bub.rpc.types import Transport


class _PairedTransportImpl(Transport, Closable):
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

    async def close(self) -> None:
        """Close the transport (async to match Closable protocol)."""
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

        self.a = _PairedTransportImpl("A", self._b_to_a, self._a_to_b)
        self.b = _PairedTransportImpl("B", self._a_to_b, self._b_to_a)


class MockListener:
    """Mock listener for testing that implements the Listener protocol.

    Creates paired transports for each client connection, allowing tests
    to exercise the full message bus routing without real WebSockets.
    """

    def __init__(self):
        self._handler: Callable[[Transport], Awaitable[None]] | None = None
        self._pairs: list[PairedTransport] = []
        self._server_tasks: list[asyncio.Task[None]] = []

    async def start(self, handler: Callable[[Transport], Awaitable[None]]) -> None:
        """Start the listener (non-blocking).

        Stores the handler for use when clients connect.
        """
        self._handler = handler

    async def connect_client(self) -> _PairedTransportImpl:
        """Create a new client connection to the server.

        Returns the client-side transport. The server-side is handled
        automatically by calling the stored handler.

        Returns:
            Client-side transport for creating AgentBusClient.
        """
        if self._handler is None:
            raise RuntimeError("Listener not started")

        pair = PairedTransport()
        self._pairs.append(pair)

        # Start server-side handling in background
        task = asyncio.create_task(self._handler(pair.a))
        self._server_tasks.append(task)

        return pair.b

    async def stop(self) -> None:
        """Stop all connections and cleanup."""
        # Cancel all server tasks
        for task in self._server_tasks:
            task.cancel()

        if self._server_tasks:
            await asyncio.gather(*self._server_tasks, return_exceptions=True)

        self._server_tasks.clear()
        self._pairs.clear()


class TestClientCallbacks(AgentBusClientCallbacks):
    """Test implementation of client callbacks for receiving messages.

    Captures all received messages for verification in tests.
    """

    def __init__(self):
        self.received: list[ProcessMessageParams] = []
        self._response: ProcessMessageResult = ProcessMessageResult(
            success=True,
            message="received",
            should_retry=False,
            retry_seconds=0,
            payload={},
        )

    async def process_message(self, params: ProcessMessageParams) -> ProcessMessageResult:
        """Handle incoming message from the bus.

        Captures the message and returns a success response.
        """
        self.received.append(params)
        return self._response

    def set_response(self, response: ProcessMessageResult) -> None:
        """Set the response to return for future messages."""
        self._response = response

    def clear(self) -> None:
        """Clear all captured messages."""
        self.received.clear()


class MockActivityLogWriter:
    """Mock activity log writer for testing.

    Implements the same interface as ActivityLogWriter but does nothing.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or Path("/dev/null")
        self._started = False

    async def start(self) -> None:
        """Initialize (no-op)."""
        self._started = True

    async def stop(self) -> None:
        """Stop (no-op)."""
        self._started = False

    async def log(
        self,
        *,
        event: str,
        message_id: str,
        rpc_id: str | None = None,
        actor: str | None = None,
        to: str | None = None,
        status: str | None = None,
        payload: dict[str, object] | None = None,
        error: str | None = None,
    ) -> None:
        """Queue a log entry (no-op)."""
        pass


__all__ = [
    "MockActivityLogWriter",
    "MockListener",
    "PairedTransport",
    "TestClientCallbacks",
]
