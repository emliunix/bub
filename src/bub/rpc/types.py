"""JSON-RPC 2.0 type definitions.

Generic JSON-RPC 2.0 types following the specification.
Used across different RPC implementations.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, TypeAdapter

RequestId = str | int


@runtime_checkable
class Transport(Protocol):
    """Protocol for message transport layer.

    Abstracts the underlying transport mechanism (WebSocket, in-memory, etc.)
    This is the only external interface we need to mock for testing.
    """

    async def send_message(self, message: str) -> None:
        """Send a message string through the transport."""
        ...

    async def receive_message(self) -> str:
        """Receive a message string from the transport."""
        ...


@runtime_checkable
class Listener(Protocol):
    """Protocol for server listener to accept incoming connections.

    Abstracts the server creation to enable testing with mock implementations.
    """

    async def start(self, handler: Callable[[Transport], Awaitable[None]]) -> None:
        """Start listening for connections.

        Args:
            handler: Callback to handle new connections with a Transport.
        """
        ...

    async def stop(self) -> None:
        """Stop listening and close all connections."""
        ...

    @property
    def url(self) -> str:
        """Server URL for clients to connect to."""
        ...


class JSONRPCRequest(BaseModel):
    """A JSON-RPC request that expects a response."""

    jsonrpc: str
    id: RequestId
    method: str
    params: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")


class JSONRPCNotification(BaseModel):
    """A JSON-RPC notification which does not expect a response."""

    jsonrpc: str
    method: str
    params: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")


class ErrorData(BaseModel):
    """Error information for JSON-RPC error responses."""

    code: int
    message: str
    data: Any = None


class JSONRPCError(BaseModel):
    """A response to a request that indicates an error occurred."""

    jsonrpc: str
    id: RequestId | None
    error: ErrorData

    model_config = ConfigDict(extra="forbid")


class JSONRPCResponse(BaseModel):
    """A successful (non-error) response to a request."""

    jsonrpc: str
    id: RequestId | None
    result: dict[str, Any]

    model_config = ConfigDict(extra="forbid")


# Union type for all JSON-RPC messages
JSONRPCMessage = JSONRPCRequest | JSONRPCNotification | JSONRPCResponse | JSONRPCError


# Type adapter for validating JSON-RPC messages
jsonrpc_message_adapter: TypeAdapter[JSONRPCMessage] = TypeAdapter(JSONRPCMessage)


__all__ = [
    "ErrorData",
    "JSONRPCError",
    "JSONRPCMessage",
    "JSONRPCNotification",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "Listener",
    "RequestId",
    "Transport",
    "jsonrpc_message_adapter",
]
