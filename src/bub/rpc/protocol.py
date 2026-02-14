"""JSON-RPC 2.0 framework implementation.

Provides a direction-agnostic, transport-agnostic JSON-RPC framework.
Supports both sending requests/notifications AND receiving/handling them.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import Callable
from typing import Protocol

from bub.rpc.types import (
    ErrorData,
    JSONRPCError,
    JSONRPCMessage,
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    RequestId,
    jsonrpc_message_adapter,
)


class JSONRPCErrorException(Exception):
    """Exception with JSON-RPC error code."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


class JSONRPCTransport(Protocol):
    """Bidirectional JSON message transport."""

    async def send_message(self, message: str) -> None:
        """Send a JSON message."""
        ...

    async def receive_message(self) -> str:
        """Receive a JSON message. Blocks until message available."""
        ...


class JSONRPCFramework:
    """Direction-agnostic JSON-RPC 2.0 framework.

    The same instance can act as:
    - Caller: send_request(), send_notification()
    - Responder: register_method(), on_notification(), listen()
    - Both: simultaneously send and receive messages

    The framework handles:
    - Request/response correlation with pending_requests
    - Fire-and-forget notifications
    - Method registration and dispatch
    """

    def __init__(self, transport: JSONRPCTransport) -> None:
        self._transport = transport
        self._pending_requests: dict[RequestId, asyncio.Future[dict[str, object]]] = {}
        self._method_handlers: dict[str, Callable[[dict[str, object]], dict[str, object] | None]] = {}
        self._notification_handlers: dict[str, list[Callable[[dict[str, object]], None]]] = {}
        self._running = False
        self._stop_event = asyncio.Event()

    async def send_request(self, method: str, params: dict[str, object]) -> dict[str, object]:
        """Send JSON-RPC request and await response.

        Creates a request with unique ID, sends it, waits for response.
        """
        request_id = str(uuid.uuid4())
        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=request_id,
            method=method,
            params=params,
        )

        future: asyncio.Future[dict[str, object]] = asyncio.Future()
        self._pending_requests[request_id] = future

        await self._send_message(request)

        try:
            result = await future
            return result
        finally:
            self._pending_requests.pop(request_id, None)

    async def send_notification(self, method: str, params: dict[str, object]) -> None:
        """Send JSON-RPC notification (fire-and-forget).

        Creates a notification (no ID), sends it. No response expected.
        """
        notification = JSONRPCNotification(
            jsonrpc="2.0",
            method=method,
            params=params,
        )

        await self._send_message(notification)

    async def _send_message(self, message: JSONRPCMessage) -> None:
        """Send a JSON-RPC message via transport.

        Uses Layer 1 types, serializes to JSON.
        """
        json_str = message.model_dump_json(by_alias=True)
        await self._transport.send_message(json_str)

    async def listen(self) -> None:
        """Start listening for incoming messages.

        Loops calling transport.receive_message(), dispatches to handlers.
        """
        self._running = True
        self._stop_event.clear()

        while self._running:
            try:
                raw_message = await asyncio.wait_for(self._transport.receive_message(), timeout=0.1)
                await self._process_message(raw_message)
            except TimeoutError:
                if self._stop_event.is_set():
                    break
                continue
            except Exception:
                if not self._running:
                    break
                raise

    async def _process_message(self, raw_message: str) -> None:
        """Process incoming JSON message.

        1. Deserialize using jsonrpc_message_adapter
        2. If request: call method handler, send response
        3. If notification: call notification handlers
        4. If response: match to pending request, complete future
        5. If error: match to pending request, complete future with exception
        """
        message = jsonrpc_message_adapter.validate_json(raw_message)

        if isinstance(message, JSONRPCRequest):
            await self._handle_request(message)
        elif isinstance(message, JSONRPCNotification):
            await self._handle_notification(message)
        elif isinstance(message, JSONRPCResponse):
            self._handle_response(message)
        elif isinstance(message, JSONRPCError):
            self._handle_error(message)

    async def _handle_request(self, request: JSONRPCRequest) -> None:
        """Handle incoming JSON-RPC request."""
        handler = self._method_handlers.get(request.method)

        if handler is None:
            error_response = JSONRPCError(
                jsonrpc="2.0",
                id=request.id,
                error=ErrorData(code=-32601, message="Method not found"),
            )
            await self._send_message(error_response)
            return

        try:
            params = request.params or {}
            result = handler(params)

            if isinstance(result, dict):
                response = JSONRPCResponse(
                    jsonrpc="2.0",
                    id=request.id,
                    result=result,
                )
                await self._send_message(response)
        except Exception as e:
            # Extract error code and message if available
            code = getattr(e, "code", -32603)
            message = str(e) if str(e) else "Internal error"
            error_response = JSONRPCError(
                jsonrpc="2.0",
                id=request.id,
                error=ErrorData(code=code, message=message),
            )
            await self._send_message(error_response)

    async def _handle_notification(self, notification: JSONRPCNotification) -> None:
        """Handle incoming JSON-RPC notification."""
        handlers = self._notification_handlers.get(notification.method, [])
        params = notification.params or {}

        for handler in handlers:
            with contextlib.suppress(Exception):
                handler(params)

    def _handle_response(self, response: JSONRPCResponse) -> None:
        """Handle incoming JSON-RPC response."""
        if response.id is None:
            return
        future = self._pending_requests.get(response.id)

        if future is not None and not future.done():
            future.set_result(response.result)

    def _handle_error(self, error: JSONRPCError) -> None:
        """Handle incoming JSON-RPC error."""
        if error.id is None:
            return
        future = self._pending_requests.get(error.id)

        if future is not None and not future.done():
            future.set_exception(RuntimeError(f"JSON-RPC error: {error.error.code} - {error.error.message}"))

    def register_method(self, name: str, handler: Callable[[dict[str, object]], dict[str, object]]) -> None:
        """Register handler for incoming JSON-RPC requests.

        Handler takes params dict, returns result dict.
        """
        self._method_handlers[name] = handler

    def on_notification(self, method: str, handler: Callable[[dict[str, object]], None]) -> None:
        """Register handler for incoming JSON-RPC notifications.

        Can register multiple handlers per method.
        """
        if method not in self._notification_handlers:
            self._notification_handlers[method] = []

        self._notification_handlers[method].append(handler)

    async def stop(self) -> None:
        """Stop listening for messages."""
        self._running = False
        self._stop_event.set()


__all__ = [
    "JSONRPCFramework",
    "JSONRPCTransport",
]
