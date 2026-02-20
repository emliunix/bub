"""Agent Communication Protocol over WebSocket.

This module implements the JSON-RPC 2.0 protocol defined in docs/agent-protocol.md.
Uses JSONRPCFramework and AgentProtocol for typed API.

Follows typed API pattern from MCP Python SDK.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Protocol, cast

import websockets
import websockets.asyncio.client
import websockets.asyncio.server
from loguru import logger

from bub.bus.log import ActivityLogWriter
from bub.bus.protocol import (
    AgentBusClientApi,
    AgentBusClientCallbacks,
    AgentBusServerApi,
    ClientInfo,
    ConnectionInfo,
    GetStatusParams,
    GetStatusResult,
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
from bub.bus.types import Closable, Listener
from bub.rpc.framework import JSONRPCErrorException, JSONRPCFramework
from bub.rpc.types import Transport
from bub.utils import lift_async


class ClosableTransport(Transport, Closable, Protocol):
    pass


class WebSocketListener(Listener):
    """WebSocket-based implementation of the Listener protocol."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._server: websockets.Server | None = None

    @property
    def url(self) -> str:
        return f"ws://{self._host}:{self._port}"

    async def start(self, handler: Callable[[Transport], Awaitable[None]]) -> None:
        """Start WebSocket server and forward connections to handler."""

        async def _ws_handler(websocket: websockets.asyncio.server.ServerConnection) -> None:
            transport = WebSocketTransport(websocket)
            await handler(transport)

        self._server = await websockets.serve(_ws_handler, self._host, self._port)

    async def stop(self) -> None:
        """Stop the WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()


class WebSocketTransport:
    """WebSocket transport adapter for JSON-RPC framework."""

    def __init__(
        self,
        conn: websockets.asyncio.server.ServerConnection | websockets.asyncio.client.ClientConnection,
    ) -> None:
        self._conn = conn

    async def send_message(self, message: str) -> None:
        await self._conn.send(message)

    async def receive_message(self) -> str:
        return await self._conn.recv(True)


class ClientWebSocketTransport:
    def __init__(
        self,
        ctx: websockets.asyncio.client.connect,
        conn: websockets.asyncio.client.ClientConnection,
    ) -> None:
        self._ctx = ctx
        self._conn = conn

    async def send_message(self, message: str) -> None:
        await self._conn.send(message)

    async def receive_message(self) -> str:
        return await self._conn.recv(True)

    async def close(self) -> None:
        await self._ctx.__aexit__(None, None, None)


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
        self._client_info: ClientInfo | None = None
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

    @property
    def client_info(self) -> ClientInfo | None:
        """Client info from initialization."""
        return self._client_info

    async def handle_initialize(self, params: InitializeParams) -> InitializeResult:
        """Handle initialize request."""
        if self._initialized:
            raise JSONRPCErrorException(-32001, "Already initialized")
        self._client_id = params.client_id
        self._client_info = params.client_info
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

    async def handle_get_status(self, params: GetStatusParams) -> GetStatusResult:
        """Handle get status request - delegate to server."""
        self._check_initialized()
        return await self._server.handle_get_status(params)

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
        listener: Listener,
        log_writer: ActivityLogWriter,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        self._server_id = f"bus-{uuid.uuid4().hex}"
        self._connections: dict[str, AgentConnection] = {}
        self._connections_lock = asyncio.Lock()
        self._listener = listener
        self._stop_event = stop_event or asyncio.Event()
        self._activity_log = log_writer

    @staticmethod
    def create(server: tuple[str, int] | Listener, activity_log_path: Path | None = None) -> AgentBusServer:
        """Factory method to create AgentBusServer instance."""
        # Create WebSocketListener from tuple if needed
        if isinstance(server, tuple):
            listener: Listener = WebSocketListener(*server)
        else:
            listener = server
        return AgentBusServer(listener, ActivityLogWriter(activity_log_path or Path("run/wsbus_activity.sqlite3")))

    @property
    def server_id(self) -> str:
        """Unique server identifier."""
        return self._server_id

    async def start_server(self) -> None:
        """Start WebSocket server."""
        await self._activity_log.start()
        await self._listener.start(self._handle_transport)
        logger.info("wsbus.server.started: {}", self._listener)

    async def stop_server(self) -> None:
        """Stop WebSocket server."""
        await self._listener.stop()
        await self._activity_log.stop()
        logger.info("wsbus.server.stopped")

    async def _handle_transport(self, transport: Transport) -> None:
        """Handle incoming client connection."""
        conn_id = uuid.uuid4().hex

        framework = JSONRPCFramework(transport, self._stop_event)
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
        except TimeoutError:
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

    async def handle_get_status(self, params: GetStatusParams) -> GetStatusResult:
        """Handle getStatus request - return server status and connections."""
        connections = []
        async with self._connections_lock:
            for conn in self._connections.values():
                if conn.is_initialized:
                    connections.append(
                        ConnectionInfo(
                            client_id=conn.client_id or "unknown",
                            connection_id=conn.connection_id,
                            subscriptions=list(conn.subscriptions),
                            client_info=conn.client_info,
                        )
                    )
        return GetStatusResult(
            server_id=self._server_id,
            connections=connections,
        )


class ReconnectableTransport:
    def __init__(
        self,
        transport_factory: Callable[[], Awaitable[ClosableTransport]],
        max_reconnect_delay: float,
        stop_event: asyncio.Event,
        on_reconnect: Callable[[], Awaitable[None]],
    ) -> None:
        self.transport_factory = transport_factory
        self.max_reconnect_delay = max_reconnect_delay
        self._transport: ClosableTransport | None = None
        self._reconnect_delay = 1.0
        self._stop_event = stop_event
        self._on_reconnect = on_reconnect
        self._is_first_connection = True

    async def send_message(self, message: str) -> None:
        """Send a message string through the transport."""
        for i in range(2):
            try:
                return await (await self._get_transport()).send_message(message)
            except ConnectionError as e:
                logger.error("Failed to send message, retrying: {}", e)
                self._transport = None

    async def receive_message(self) -> str:
        """Receive a message string from the transport."""
        while not self._stop_event.is_set():
            try:
                return await (await self._get_transport()).receive_message()
            except ConnectionError as e:
                logger.error("Failed to receive message, retrying: {}", e)
                self._transport = None
        raise ConnectionError("Transport is stopped")

    async def _get_transport(self) -> ClosableTransport:
        """Get the current transport, reconnecting if necessary."""
        while not self._stop_event.is_set():
            if self._transport is None:
                try:
                    self._transport = await self.transport_factory()
                    self._reconnect_delay = 1.0
                    logger.info("Transport connected")
                    if self._is_first_connection:
                        self._is_first_connection = False
                    else:
                        await self._on_reconnect()
                except Exception as e:
                    logger.error("Failed to connect transport: {}", e)
                    await asyncio.sleep(self._reconnect_delay)
                    self._reconnect_delay = min(self._reconnect_delay * 2, self.max_reconnect_delay)
            else:
                return self._transport
        raise ConnectionError("Transport is stopped")

    async def close(self) -> None:
        """Close the transport."""
        if self._transport:
            await self._transport.close()
            self._transport = None


class AgentBusClient:
    """WebSocket client for peers to connect to the bus with auto-reconnect support."""

    def __init__(
        self,
        transport: ClosableTransport,
        callbacks: AgentBusClientCallbacks,
    ) -> None:
        self._client_id = f"client-{uuid.uuid4().hex}"
        self._transport = transport
        stop_event = asyncio.Event()
        framework = JSONRPCFramework(transport, stop_event=stop_event)
        register_client_callbacks(framework, callbacks)
        self._api = AgentBusClientApi(framework)
        self._run_task: asyncio.Task | None = None
        self._initialized = False
        self._initialized_client_id: str | None = None
        self._subscription: set[str] = set()
        self._message_id_seed = 0
        self._message_id_seed_lock = asyncio.Lock()
        self._stop_event = stop_event

    @staticmethod
    async def connect(url: str | ClosableTransport, callbacks: AgentBusClientCallbacks) -> AgentBusClient:
        """Connect to server with auto-reconnect support."""

        async def _factory(url: str) -> ClosableTransport:
            ctx = websockets.connect(url)
            return ClientWebSocketTransport(ctx, await ctx.__aenter__())

        if isinstance(url, str):
            transport_factory = lambda: _factory(url)
        else:
            transport_factory = lambda: lift_async(url)

        async def _on_reconnect() -> None:
            if cell and cell[0]:
                await cell[0]._on_reconnect()

        transport = ReconnectableTransport(
            transport_factory=transport_factory,
            max_reconnect_delay=30.0,
            stop_event=asyncio.Event(),
            on_reconnect=_on_reconnect,
        )
        cell = [AgentBusClient(transport, callbacks)]
        client = cell[0]
        # Start the framework run loop automatically
        await client._start()
        return client

    async def _start(self) -> None:
        """Start the framework run loop in background."""
        if self._run_task is None:
            self._run_task = asyncio.create_task(self._api._framework.run())
            # Give the task a moment to start processing messages
            await asyncio.sleep(0.1)

    async def _on_reconnect(self) -> None:
        for address in self._subscription:
            await self.subscribe(address)

    async def initialize(self, client_id: str) -> InitializeResult:
        """Initialize connection with server."""
        if self._initialized:
            raise RuntimeError("Already initialized")
        result = await self._api.initialize(InitializeParams(client_id=client_id))
        self._initialized = True
        return result

    async def subscribe(
        self,
        address: str,
    ) -> SubscribeResult:
        """Subscribe to an address pattern."""
        self._check_initialized()
        if address not in self._subscription:
            result = await self._api.subscribe(SubscribeParams(address=address))
            self._subscription.add(address)
        else:
            result = SubscribeResult(success=True)
        return result

    async def unsubscribe(self, address: str) -> UnsubscribeResult:
        """Unsubscribe from an address pattern."""
        self._check_initialized()
        if address in self._subscription:
            self._subscription.remove(address)
        return await self._api.unsubscribe(UnsubscribeParams(address=address))

    async def send_message(self, to: str, payload: dict[str, Any]) -> SendMessageResult:
        """Send a message to the bus with auto-generated message ID."""
        self._check_initialized()
        message_id = await self._next_message_id()
        return await self._api.send_message(
            SendMessageParams(from_=self._client_id, to=to, message_id=message_id, payload=payload)  # type: ignore[call-arg]
        )

    async def _next_message_id(self) -> str:
        """Generate next sequential message ID."""
        async with self._message_id_seed_lock:
            self._message_id_seed += 1
            return f"msg_{self._client_id}_{self._message_id_seed:010d}"

    def _check_initialized(self) -> None:
        """Check if client is initialized before performing actions."""
        if not self._initialized:
            raise RuntimeError("Client is not initialized yet")

    async def run(self) -> None:
        self._run_task = asyncio.create_task(self._api._framework.run())
        try:
            await self._run_task
        except asyncio.CancelledError:
            pass

    async def disconnect(self) -> None:
        """Disconnect from server."""
        self._stop_event.set()
        if self._run_task:
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass
            await self._transport.close()
        logger.info("wsbus.client.disconnected")


__all__ = [
    "ActivityLogWriter",
    "AgentBusClient",
    "AgentBusServer",
    "AgentConnection",
    "WebSocketTransport",
]
