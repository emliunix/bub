"""JSON-RPC 2.0 type definitions.

Generic JSON-RPC 2.0 types following the specification.
Used across different RPC implementations.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, TypeAdapter

RequestId = str | int


class JSONRPCRequest(BaseModel):
    """A JSON-RPC request that expects a response."""

    jsonrpc: str
    id: RequestId
    method: str
    params: dict[str, object] | None = None

    model_config = ConfigDict(extra="forbid")


class JSONRPCNotification(BaseModel):
    """A JSON-RPC notification which does not expect a response."""

    jsonrpc: str
    method: str
    params: dict[str, object] | None = None

    model_config = ConfigDict(extra="forbid")


class ErrorData(BaseModel):
    """Error information for JSON-RPC error responses."""

    code: int
    message: str
    data: object = None


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
    result: dict[str, object]

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
    "RequestId",
    "jsonrpc_message_adapter",
]
