"""Agent Communication Protocol over WebSocket.

This module implements the JSON-RPC 2.0 protocol defined in docs/agent-protocol.md.
Uses JSONRPCFramework and AgentProtocol for typed API.

Follows typed API pattern from MCP Python SDK.
"""

from __future__ import annotations

import asyncio
import inspect
import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Protocol, cast, runtime_checkable

import websockets
import websockets.asyncio.client
import websockets.asyncio.server
from loguru import logger
from websockets.asyncio.server import ServerConnection

from bub.rpc.framework import JSONRPCErrorException, JSONRPCFramework
from bub.bus.log import ActivityLogWriter
from bub.bus.protocol import (
    AgentBusClientApi,
    AgentBusServerApi,
    InitializeParams,
    InitializeResult,
    MessageAck,
    PingParams,
    PingResult,
    ProcessMessageParams,
    ProcessMessageResult,
    SendMessageParams,
    SendMessageResult,
    ServerCapabilities,
    ServerInfo,
    SubscribeParams,
    SubscribeResult,
    UnsubscribeParams,
    UnsubscribeResult,
    register_client_callbacks,
    register_server_callbacks,
)
from bub.bus.types import Transport

background_tasks: set[asyncio.Task[Any]] = set()


class WebSocketTransport:
    """WebSocket transport adapter for JSON-RPC framework."""

    def __init__(
        self,
        ws: websockets.asyncio.server.ServerConnection | websockets.asyncio.client.ClientConnection,
    ) -> None:
        self._ws = ws

    async def send_message(self, message: str) -> None:
        await self._ws.send(message)

    async def receive_message(self) -> str:
        data = await self._ws.recv()
        if isinstance(data, (bytes, bytearray)):
            data = data.decode("utf-8")
        if isinstance(data, memoryview):
            data = data.tobytes().decode("utf-8")
        return data


class AgentConnection:
    """Server-side connection handler for a single client connection.

    Implements the BusPeer protocol for message processing.
    """

    def __init__(self, conn_id: str, server: AgentBusServer, api: AgentBusServerApi) -> None:
        self._conn_id = conn_id
        self._server = server
        self._api = api
        self._initialized = False
        self._client_id: str | None = None
        self._subscriptions: set[str] = set()

    @property
    def client_id(self) -> str | None:
        """The client's identifier (set after initialization)."""
        return self._client_id

    @property
    def connection_id(self) -> str:
        """The unique connection identifier."""
        return self._conn_id

    @property
    def is_initialized(self) -> bool:
        """Whether the peer has completed initialization."""
        return self._initialized

    @property
    def subscriptions(self) -> set[str]:
        """Set of address patterns this peer is subscribed to."""
        return self._subscriptions

    async def handle_initialize(self, params: InitializeParams) -> InitializeResult:
        """Handle initialize request."""
        if self._initialized:
            raise JSONRPCErrorException(-32001, "Already initialized")
        self._client_id = params.client_id
        self._initialized = True

        server_info = ServerInfo(name="bub-bus", version="0.2.0")
        capabilities = ServerCapabilities(
            subscribe=True,
            process_message=True,
            addresses=["tg:*", "agent:*", "system:*"],
        )
        result = InitializeResult(
            server_id=self._server._server_id,
            server_info=server_info,
            capabilities=capabilities,
        )

        self._subscriptions.add(self._client_id)
        logger.info(
            "wsbus.server.initialize_success client_id={} auto_subscribed={}",
            self._client_id,
            self._client_id,
        )
        return result

    async def handle_subscribe(self, params: SubscribeParams) -> SubscribeResult:
        """Handle subscribe request."""
        self._check_initialized()
        address = params.address
        if not address:
            logger.warning("wsbus.server.subscribe_missing_address client_id={}", self._client_id)
            raise RuntimeError("Address is required")

        self._subscriptions.add(address)

        logger.info(
            "wsbus.server.subscribe client_id={} address={} total_subs={}",
            self._client_id,
            address,
            len(self._subscriptions),
        )

        return SubscribeResult(success=True)

    async def handle_unsubscribe(self, params: UnsubscribeParams) -> UnsubscribeResult:
        """Handle unsubscribe request."""
        self._check_initialized()
        if params.address not in self._subscriptions:
            raise JSONRPCErrorException(-32003, "Subscription not found")
        self._subscriptions.remove(params.address)

        logger.info(
            "wsbus.server.unsubscribe client_id={} address={}",
            self._client_id,
            params.address,
        )

        return UnsubscribeResult(success=True)

    async def handle_ping(self, params: PingParams) -> PingResult:
        """Handle ping request."""
        self._check_initialized()
        return PingResult(timestamp=datetime.now(UTC).isoformat())

    def _check_initialized(self) -> None:
        """Check if connection is initialized before handling non-initialize requests."""
        if not self._initialized:
            raise JSONRPCErrorException(-32001, "Not initialized")

    async def send_message(self, params: SendMessageParams) -> SendMessageResult:
        """Handle send message request - broadcast to all subscribers."""
        self._check_initialized()
        payload = cast(dict[str, object], params.payload)
        sender = params.from_ or self._client_id
        assert sender is not None, "impossible"
        self._server.validate_send_message(
            sender=sender,
            to=params.to,
            payload=payload,
        )
        acks = await self._server._dispatch_process_message(
            params.to,
            payload,
            message_id=params.message_id,
            sender=sender,
        )
        return SendMessageResult(
            accepted=True,
            message_id=params.message_id,
            acks=acks,
        )

    async def process_message(self, from_addr: str, to: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Process an incoming message from the bus.

        This implements the BusPeer protocol method.
        """
        process_params = ProcessMessageParams(
            from_=from_addr,  # type: ignore[call-arg]
            to=to,
            message_id=payload.get("messageId", ""),
            payload=payload,
        )
        result = await self._api.process_message(process_params)
        return {
            "success": result.success,
            "message": result.message,
            "payload": result.payload,
        }


class AgentBusServer:
    """WebSocket server that manages multiple agent connections."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 7892,
        activity_log_path: Path | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._server_id = f"bus-{uuid.uuid4().hex}"
        self._connections: dict[str, AgentConnection] = {}
        self._connections_lock = asyncio.Lock()
        self._server: websockets.Server | None = None
        self._activity_log = ActivityLogWriter(activity_log_path or Path("run/wsbus_activity.sqlite3"))

    @property
    def server_id(self) -> str:
        """Unique server identifier."""
        return self._server_id

    @property
    def url(self) -> str:
        return f"ws://{self._host}:{self._port}"

    async def start_server(self) -> None:
        """Start WebSocket server."""
        await self._activity_log.start()
        self._server = await websockets.serve(self._handle_client, self._host, self._port)
        logger.info("wsbus.server.started url={}", self.url)

    async def stop_server(self) -> None:
        """Stop WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        await self._activity_log.stop()
        logger.info("wsbus.server.stopped")

    async def _handle_client(self, websocket: ServerConnection) -> None:
        """Handle incoming client connection."""
        conn_id = uuid.uuid4().hex

        transport = WebSocketTransport(websocket)
        framework = JSONRPCFramework(transport)
        api = AgentBusServerApi(framework)

        async with self._connections_lock:
            self._connections[conn_id] = AgentConnection(conn_id=conn_id, server=self, api=api)
        conn = self._connections[conn_id]
        logger.info("wsbus.client.connected conn_id={}", conn_id)

        register_server_callbacks(framework, conn)

        try:
            await framework.run()
        except websockets.ConnectionClosed:
            pass
        finally:
            async with self._connections_lock:
                self._connections.pop(conn_id, None)
            logger.info("wsbus.client.disconnected conn_id={}", conn_id)

    def address_matches(self, address: str, pattern: str) -> bool:
        """Check if an address matches a pattern (supports wildcards)."""
        return fnmatch(address, pattern)

    def _address_matches_set(self, address: str, patterns: set[str]) -> bool:
        """Check if address matches any wildcard pattern in the set."""
        return any(fnmatch(address, pattern) for pattern in patterns)

    def validate_send_message(self, *, sender: str, to: str, payload: dict[str, object]) -> None:
        """Validate payload and sender role constraints for sendMessage."""
        required_fields = ("messageId", "type", "from", "timestamp", "content")
        missing = [field for field in required_fields if field not in payload]
        if missing:
            raise JSONRPCErrorException(-32602, f"Missing required payload fields: {', '.join(missing)}")

        msg_type = payload.get("type")
        if not isinstance(msg_type, str) or not msg_type.strip():
            raise JSONRPCErrorException(-32602, "payload.type must be a non-empty string")
        if not isinstance(payload.get("content"), dict):
            raise JSONRPCErrorException(-32602, "payload.content must be an object")

        allowed_types = self._allowed_types_for_sender(sender)
        if msg_type not in allowed_types:
            raise JSONRPCErrorException(
                -32602,
                f"Sender '{sender}' is not allowed to send type '{msg_type}' to '{to}'",
            )

    def _allowed_types_for_sender(self, sender: str) -> set[str]:
        """Return allowed message types for a sender."""
        return {
            "tg_message",
            "tg_reply",
            "spawn_request",
            "spawn_result",
        }

    async def _dispatch_process_message(
        self,
        to: str,
        payload: dict[str, object],
        *,
        message_id: str,
        sender: str,
        rpc_id: str | None = None,
        timeout: float = 30.0,
    ) -> list[MessageAck]:
        """Dispatch processMessage to all matching subscribers and return stripped acks."""
        logger.info("wsbus.server.publish to={} payload_keys={}", to, list(payload.keys()))
        await self._activity_log.log(
            event="send_start",
            message_id=message_id,
            rpc_id=rpc_id,
            actor=sender,
            to=to,
            status="start",
            payload=payload,
        )

        matched_peers: list[str] = []
        async with self._connections_lock:
            connections_snapshot = list(self._connections.values())

        tasks: list[asyncio.Task[ProcessMessageResult]] = []
        for other_conn in connections_snapshot:
            if other_conn.is_initialized and self._address_matches_set(to, other_conn.subscriptions):
                peer_id = other_conn.client_id or other_conn.connection_id
                matched_peers.append(peer_id)
                logger.info("wsbus.server.publish sending to peer={}", peer_id)

                task = asyncio.create_task(
                    self._process_message_for_peer(
                        other_conn, to, payload, message_id, rpc_id, peer_id, sender, timeout
                    )
                )
                tasks.append(task)

        acks: list[MessageAck] = []
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, BaseException):
                    acks.append(
                        MessageAck(
                            success=False,
                            message=str(result),
                            payload={"error": str(result)},
                        )
                    )
                else:
                    # Strip retry fields from ProcessMessageResult
                    acks.append(
                        MessageAck(
                            success=result.success,
                            message=result.message,
                            payload=result.payload,
                        )
                    )

        if matched_peers:
            logger.info(
                "wsbus.publish to={} peers={} matched={}",
                to,
                len(matched_peers),
                matched_peers,
            )
        else:
            logger.info("wsbus.publish to={} peers=0 (no subscribers)", to)

        await self._activity_log.log(
            event="send_finish",
            message_id=message_id,
            rpc_id=rpc_id,
            actor=sender,
            to=to,
            status="ok",
            payload=payload,
        )
        return acks

    async def _process_message_for_peer(
        self,
        other_conn: AgentConnection,
        to: str,
        payload: dict[str, object],
        message_id: str,
        rpc_id: str | None,
        peer_id: str,
        sender: str,
        timeout: float,
    ) -> ProcessMessageResult:
        """Process message for a single peer and return result."""
        await self._activity_log.log(
            event="process_start",
            message_id=message_id,
            rpc_id=rpc_id,
            actor=peer_id,
            to=to,
            status="start",
            payload=payload,
        )
        try:
            process_params = ProcessMessageParams(from_=sender, to=to, message_id=message_id, payload=payload)  # type: ignore[call-arg]
            result = await asyncio.wait_for(
                other_conn._api.process_message(process_params),
                timeout=timeout,
            )
            await self._activity_log.log(
                event="process_finish",
                message_id=message_id,
                rpc_id=rpc_id,
                actor=peer_id,
                to=to,
                status="ok" if result.success else "error",
                payload=payload,
            )
            return result
        except asyncio.TimeoutError:
            await self._activity_log.log(
                event="process_finish",
                message_id=message_id,
                rpc_id=rpc_id,
                actor=peer_id,
                to=to,
                status="timeout",
                payload=payload,
                error=f"Timeout after {timeout}s",
            )
            logger.error(
                "wsbus.publish.process_timeout peer={} to={} timeout={}s",
                peer_id,
                to,
                timeout,
            )
            return ProcessMessageResult(
                success=False,
                message=f"Timeout after {timeout}s",
                should_retry=False,
                retry_seconds=0,
                payload={"error": f"Timeout after {timeout}s"},
            )
        except Exception as exc:
            await self._activity_log.log(
                event="process_finish",
                message_id=message_id,
                rpc_id=rpc_id,
                actor=peer_id,
                to=to,
                status="error",
                payload=payload,
                error=str(exc),
            )
            logger.exception("wsbus.publish.process_error peer={} to={}", peer_id, to)
            return ProcessMessageResult(
                success=False,
                message=str(exc),
                should_retry=False,
                retry_seconds=0,
                payload={"error": str(exc)},
            )


class AgentBusClient:
    """WebSocket client for peers to connect to the bus with auto-reconnect support."""

    def __init__(
        self,
        url: str,
        *,
        auto_reconnect: bool = True,
        max_reconnect_delay: float = 30.0,
    ) -> None:
        self._client_id = f"client-{uuid.uuid4().hex}"
        self._url = url
        self._ws: websockets.asyncio.client.ClientConnection | None = None
        self._framework: JSONRPCFramework | None = None
        self._api: AgentBusClientApi | None = None
        self._run_task: asyncio.Task | None = None
        self._handlers: dict[str, list[Callable[[str, dict[str, Any]], Any]]] = {}
        self._handlers_lock = asyncio.Lock()
        self._initialized = False
        self._auto_reconnect = auto_reconnect
        self._max_reconnect_delay = max_reconnect_delay
        self._reconnect_delay = 1.0
        self._reconnect_attempts = 0
        self._subscribed_addresses: set[str] = set()
        self._subscription_refcounts: dict[str, int] = {}
        self._stop_event = asyncio.Event()
        self._initialized_client_id: str | None = None
        self._message_counter = 0
        self._message_counter_lock = asyncio.Lock()

    @property
    def url(self) -> str:
        return self._url

    async def connect(self) -> None:
        """Connect to server with auto-reconnect support."""
        while not self._stop_event.is_set():
            try:
                await self._connect_once()
                self._reconnect_delay = 1.0
                self._reconnect_attempts = 0
                return
            except (
                websockets.exceptions.WebSocketException,
                ConnectionRefusedError,
                OSError,
            ) as e:
                if not self._auto_reconnect:
                    raise
                self._reconnect_attempts += 1
                logger.warning(
                    "wsbus.client.connect_failed attempt={} delay={:.1f}s error={}",
                    self._reconnect_attempts,
                    self._reconnect_delay,
                    e,
                )
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self._reconnect_delay)
                    return
                except TimeoutError:
                    pass
                self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)

    async def _connect_once(self) -> None:
        """Single connection attempt."""
        self._ws = await websockets.connect(self._url)

        transport = WebSocketTransport(self._ws)
        self._framework = JSONRPCFramework(transport)
        self._api = AgentBusClientApi(self._framework)

        register_client_callbacks(self._framework, self)

        self._run_task = asyncio.create_task(self._run_with_reconnect())
        await asyncio.sleep(0.01)

        logger.info("wsbus.client.connected url={}", self._url)

    async def _run_with_reconnect(self) -> None:
        """Run framework and handle disconnections."""
        try:
            if self._framework:
                await self._framework.run()
        except websockets.exceptions.ConnectionClosed:
            logger.warning("wsbus.client.connection_closed")
        except Exception as e:
            logger.error("wsbus.client.run_error error={}", e)
        finally:
            if self._auto_reconnect and not self._stop_event.is_set():
                logger.info("wsbus.client.triggering_reconnect")
                self._initialized = False
                self._api = None
                self._framework = None
                self._ws = None
                asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        """Reconnect and restore subscriptions."""
        if self._stop_event.is_set():
            return

        logger.info(
            "wsbus.client.reconnecting subscriptions={}",
            len(self._subscribed_addresses),
        )

        if self._framework:
            await self._framework.stop()
        if self._ws:
            await self._ws.close()
        if self._run_task:
            self._run_task.cancel()
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass
        logger.info("wsbus.client.disconnected_for_reconnect")

        self._initialized = False
        self._api = None
        self._framework = None
        self._ws = None

        await self.connect()

        if self._stop_event.is_set():
            return

        if self._initialized_client_id:
            try:
                await self.initialize(self._initialized_client_id)
                logger.debug(
                    "wsbus.client.reinitialized client_id={}",
                    self._initialized_client_id,
                )
            except Exception as e:
                logger.error("wsbus.client.reinitialize_failed error={}", e)
                return

        if self._api is None:
            logger.error("wsbus.client.reconnect_failed _api is None")
            return

        for address in self._subscribed_addresses:
            try:
                await self._api.subscribe(SubscribeParams(address=address))
                logger.debug("wsbus.client.resubscribed address={}", address)
            except Exception as e:
                logger.error(
                    "wsbus.client.resubscribe_failed address={} error={}",
                    address,
                    e,
                )

        logger.info("wsbus.client.reconnect_complete")

    async def disconnect(self) -> None:
        """Disconnect from server."""
        self._stop_event.set()
        if self._framework:
            await self._framework.stop()
        if self._ws:
            await self._ws.close()
        if self._run_task:
            self._run_task.cancel()
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass
        logger.info("wsbus.client.disconnected")

    async def initialize(self, client_id: str) -> InitializeResult:
        """Initialize connection with server."""
        if not self._api:
            raise RuntimeError("Not connected")
        if self._initialized:
            raise RuntimeError("Already initialized")
        result = await self._api.initialize(InitializeParams(client_id=client_id))
        self._initialized = True
        self._initialized_client_id = client_id
        return result

    async def subscribe(
        self,
        address: str,
        handler: Callable[[str, dict[str, Any]], Any] | None = None,
    ) -> SubscribeResult:
        """Subscribe to an address pattern."""
        if not self._api:
            raise RuntimeError("Not connected")
        count = self._subscription_refcounts.get(address, 0)
        if count == 0:
            result = await self._api.subscribe(SubscribeParams(address=address))
            self._subscribed_addresses.add(address)
        else:
            result = SubscribeResult(success=True)
        if handler is not None:
            async with self._handlers_lock:
                if address not in self._handlers:
                    self._handlers[address] = []
                self._handlers[address].append(handler)
        self._subscription_refcounts[address] = count + 1
        return result

    async def unsubscribe(self, address: str) -> UnsubscribeResult:
        """Unsubscribe from an address pattern."""
        if not self._api:
            raise RuntimeError("Not connected")
        count = self._subscription_refcounts.get(address, 0)
        if count <= 1:
            async with self._handlers_lock:
                self._handlers.pop(address, None)
            self._subscribed_addresses.discard(address)
            self._subscription_refcounts.pop(address, None)
            return await self._api.unsubscribe(UnsubscribeParams(address=address))

        self._subscription_refcounts[address] = count - 1
        return UnsubscribeResult(success=True)

    async def process_message(self, params: ProcessMessageParams) -> ProcessMessageResult:
        """Handle processMessage request from bus."""
        payload = cast(dict[str, Any], params.payload)
        matched = await self._dispatch_message(params.to, payload)
        if matched == 0:
            return ProcessMessageResult(
                success=False,
                message="No matching handlers",
                should_retry=False,
                retry_seconds=0,
                payload={"message": "No matching handlers"},
            )
        return ProcessMessageResult(
            success=True,
            message="Processed",
            should_retry=False,
            retry_seconds=0,
            payload={"message": "Processed"},
        )

    def _address_matches(self, address: str, pattern: str) -> bool:
        """Check if address matches wildcard pattern."""
        return fnmatch(address, pattern)

    async def _dispatch_message(self, to: str, payload: dict[str, Any]) -> int:
        """Dispatch one routed message to matching handlers."""
        logger.debug(
            "wsbus.client.dispatch_message to={} handlers_count={} payload_keys={}",
            to,
            len(self._handlers),
            list(payload.keys()) if isinstance(payload, dict) else [],
        )

        matched_patterns = []
        matched_count = 0
        async with self._handlers_lock:
            handlers_snapshot = [(pattern, list(handlers)) for pattern, handlers in self._handlers.items()]
        for pattern, handlers in handlers_snapshot:
            if self._address_matches(to, pattern):
                matched_patterns.append(pattern)
                for handler in handlers:
                    matched_count += 1
                    try:
                        if inspect.iscoroutinefunction(handler):
                            await handler(to, payload)
                        else:
                            handler(to, payload)
                    except Exception:
                        logger.exception("wsbus.client.handler_error to={}", to)

        logger.debug(
            "wsbus.client.notification_matched to={} patterns={}",
            to,
            matched_patterns,
        )
        return matched_count

    async def _next_message_id(self) -> str:
        """Generate next sequential message ID."""
        async with self._message_counter_lock:
            self._message_counter += 1
            return f"msg_{self._client_id}_{self._message_counter:010d}"

    async def send_message(self, to: str, payload: dict[str, Any]) -> SendMessageResult:
        """Send a message to the bus with auto-generated message ID."""
        if not self._api:
            raise RuntimeError("Not connected")
        message_id = await self._next_message_id()
        return await self._api.send_message(
            SendMessageParams(from_=self._client_id, to=to, message_id=message_id, payload=payload)  # type: ignore[call-arg]
        )


__all__ = [
    "ActivityLogWriter",
    "AgentBusClient",
    "AgentBusServer",
    "AgentConnection",
    "WebSocketTransport",
]
