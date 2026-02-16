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
from typing import Any, cast

import websockets
import websockets.asyncio.client
import websockets.asyncio.server
from loguru import logger
from websockets.asyncio.server import ServerConnection

from bub.channels.events import InboundMessage, OutboundMessage
from bub.rpc.framework import JSONRPCErrorException, JSONRPCFramework
from bub.rpc.protocol import (
    AgentBusClientApi,
    AgentBusServerApi,
    InitializeParams,
    InitializeResult,
    PingParams,
    PingResult,
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

background_tasks: set[asyncio.Task[Any]] = set()  # Store background tasks to prevent garbage collection


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
    """Represents a connected agent client."""

    def __init__(self, conn_id: str, server: AgentBusServer, api: AgentBusServerApi) -> None:
        self.conn_id = conn_id
        self.initialized = False
        self.client_id: str | None = None
        self._server = server
        self.api = api
        self.subscriptions: list[str] = []  # topic patterns

    async def handle_initialize(self, params: InitializeParams) -> InitializeResult:
        """Handle initialize request."""
        self.client_id = params.client_id
        self.initialized = True

        server_info = ServerInfo(name="bub-bus", version="0.2.0")
        capabilities = ServerCapabilities(
            subscribe=True,
            publish=True,
            topics=["inbound:*", "outbound:*", "agent:*"],
        )
        result = InitializeResult(
            server_id=self._server._server_id,
            server_info=server_info,
            capabilities=capabilities,
        )

        logger.info("wsbus.server.initialize_success client_id={}", self.client_id)
        return result

    async def handle_subscribe(self, params: SubscribeParams) -> SubscribeResult:
        """Handle subscribe request."""
        self._check_initialized()
        topic = params.topic
        if not topic:
            logger.warning("wsbus.server.subscribe_missing_topic client_id={}", self.client_id)
            raise RuntimeError("Topic is required")

        self.subscriptions.append(topic)

        subscription_id = f"sub_{uuid.uuid4().hex[:8]}"

        logger.info(
            "wsbus.server.subscribe client_id={} topic={} total_subs={} subscription_id={}",
            self.client_id,
            topic,
            len(self.subscriptions),
            subscription_id,
        )

        result = SubscribeResult(success=True, subscription_id=subscription_id)
        return result

    async def handle_unsubscribe(self, params: UnsubscribeParams) -> UnsubscribeResult:
        """Handle unsubscribe request."""
        self._check_initialized()
        self.subscriptions.remove(params.topic)

        logger.info(
            "wsbus.server.unsubscribe client_id={} topic={}",
            self.client_id,
            params.topic,
        )

        result = UnsubscribeResult(success=True)
        return result

    async def handle_ping(self, params: PingParams) -> PingResult:
        """Handle ping request."""
        self._check_initialized()
        result = PingResult(timestamp=datetime.now(UTC).isoformat())
        return result

    def _check_initialized(self) -> None:
        """Check if connection is initialized before handling non-initialize requests."""
        if not self.initialized:
            raise JSONRPCErrorException(-32001, "Not initialized")

    async def send_message(self, params: SendMessageParams) -> SendMessageResult:
        """Handle send message request - broadcast to all subscribers.

        Returns SendMessageResult with stop_propagation flag.
        """
        self._check_initialized()
        stop_propagation = await self._server.publish(params.topic, cast(dict, params.payload))
        return SendMessageResult(success=True, stop_propagation=stop_propagation)


class AgentBusServer:
    """JSON-RPC 2.0 WebSocket server for agent communication."""

    def __init__(self, host: str = "localhost", port: int = 7892) -> None:
        self._host = host
        self._port = port
        self._server_id = f"bus-{uuid.uuid4().hex}"
        self._connections: dict[str, AgentConnection] = {}
        self._server: websockets.Server | None = None

    @property
    def url(self) -> str:
        return f"ws://{self._host}:{self._port}"

    async def start_server(self) -> None:
        """Start WebSocket server."""
        self._server = await websockets.serve(self._handle_client, self._host, self._port)
        logger.info("wsbus.started url={}", self.url)

    async def stop_server(self) -> None:
        """Stop WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("wsbus.stopped")

    async def _handle_client(self, websocket: ServerConnection) -> None:
        """Handle incoming client connection."""
        conn_id = uuid.uuid4().hex

        # Create transport, framework, and protocol for this connection
        transport = WebSocketTransport(websocket)
        framework = JSONRPCFramework(transport)
        api = AgentBusServerApi(framework)

        # Initialize connection state
        self._connections[conn_id] = AgentConnection(conn_id=conn_id, server=self, api=api)
        conn = self._connections[conn_id]
        logger.info("wsbus.client.connected conn_id={}", conn_id)

        # Register server-side method handlers
        register_server_callbacks(framework, conn)

        # Start listening for messages
        try:
            await framework.run()
        except websockets.ConnectionClosed:
            pass
        finally:
            self._connections.pop(conn_id, None)
            logger.info("wsbus.client.disconnected conn_id={}", conn_id)

    def _topic_matches(self, topic: str, patterns: list[str]) -> bool:
        """Check if topic matches any wildcard pattern."""
        return any(fnmatch(topic, pattern) for pattern in patterns)

    async def publish(self, topic: str, payload: dict) -> bool:
        """Publish message to all subscribers.

        Returns True if propagation should stop, False otherwise.
        """
        logger.info("wsbus.server.publish topic={} payload_keys={}", topic, list(payload.keys()))
        matched_peers: list[str] = []
        for other_conn in self._connections.values():
            if other_conn.initialized and self._topic_matches(topic, other_conn.subscriptions):
                matched_peers.append(other_conn.client_id or other_conn.conn_id)
                logger.info("wsbus.server.publish sending to peer={}", other_conn.client_id or other_conn.conn_id)
                send_params = SendMessageParams(topic=topic, payload=cast(dict[str, object], payload))
                result = await other_conn.api.send_message(send_params)
                if result.stop_propagation:
                    logger.info(
                        "wsbus.publish topic={} peers={} matched={} stopped_at={}",
                        topic,
                        len(matched_peers),
                        matched_peers,
                        other_conn.client_id or other_conn.conn_id,
                    )
                    return True

        if matched_peers:
            logger.info(
                "wsbus.publish topic={} peers={} matched={}",
                topic,
                len(matched_peers),
                matched_peers,
            )
        else:
            logger.info("wsbus.publish topic={} peers=0 (no subscribers)", topic)

        return False

    async def publish_inbound(self, message: InboundMessage) -> None:
        """Publish inbound message."""
        topic = f"inbound:{message.chat_id}"
        payload = {
            "channel": message.channel,
            "chatId": message.chat_id,
            "content": message.content,
            "senderId": message.sender_id,
        }
        logger.debug(
            "wsbus.client.publish_inbound topic={} channel={} chat_id={} sender_id={} content_len={}",
            topic,
            message.channel,
            message.chat_id,
            message.sender_id,
            len(message.content),
        )
        await self.publish(topic, payload)

    async def publish_outbound(self, message: OutboundMessage) -> None:
        """Publish outbound message."""
        topic = f"outbound:{message.chat_id}"
        payload = {"chatId": message.chat_id, "content": message.content}
        logger.debug(
            "wsbus.client.publish_outbound topic={} channel={} chat_id={} content_len={}",
            topic,
            message.channel,
            message.chat_id,
            len(message.content),
        )
        await self.publish(topic, payload)


class AgentBusClient:
    """JSON-RPC 2.0 WebSocket client for agent communication with auto-reconnect."""

    def __init__(self, url: str, *, auto_reconnect: bool = True, max_reconnect_delay: float = 30.0) -> None:
        self._client_id = f"client-{uuid.uuid4().hex}"
        self._url = url
        self._ws: Any = None
        self._framework: JSONRPCFramework | None = None
        self._api: AgentBusClientApi | None = None
        self._run_task: asyncio.Task | None = None
        self._notification_handlers: dict[str, list[Callable[[str, dict[str, Any]], Any]]] = {}
        self._pending_tasks: list[asyncio.Task[Any]] = []
        self._initialized = False
        self._auto_reconnect = auto_reconnect
        self._max_reconnect_delay = max_reconnect_delay
        self._reconnect_delay = 1.0  # Initial delay
        self._reconnect_attempts = 0
        self._subscribed_topics: set[str] = set()  # Track subscriptions for reconnect
        self._stop_event = asyncio.Event()
        self._initialized_client_id: str | None = None  # Store client_id for reconnect

    @property
    def url(self) -> str:
        return self._url

    async def connect(self) -> None:
        """Connect to server with auto-reconnect support."""
        while not self._stop_event.is_set():
            try:
                await self._connect_once()
                # Reset reconnect delay on successful connection
                self._reconnect_delay = 1.0
                self._reconnect_attempts = 0
                return
            except (websockets.exceptions.WebSocketException, ConnectionRefusedError, OSError) as e:
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
                    # If stop_event is set, exit
                    return
                except TimeoutError:
                    pass
                # Exponential backoff with max limit
                self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)

    async def _connect_once(self) -> None:
        """Single connection attempt."""
        self._ws = await websockets.connect(self._url)

        # Create transport, framework, and protocol
        transport = WebSocketTransport(self._ws)
        self._framework = JSONRPCFramework(transport)
        self._api = AgentBusClientApi(self._framework)

        register_client_callbacks(self._framework, self)

        # Start listening for messages BEFORE sending requests
        self._run_task = asyncio.create_task(self._run_with_reconnect())
        await asyncio.sleep(0.01)  # Give framework time to start listening

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
                # Clear state before reconnect
                self._initialized = False
                self._api = None
                self._framework = None
                self._ws = None
                # Trigger reconnect
                asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        """Reconnect and restore subscriptions."""
        if self._stop_event.is_set():
            return

        logger.info("wsbus.client.reconnecting subscriptions={}", len(self._subscribed_topics))

        # Disconnect cleanly without setting stop_event (for internal reconnect)
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

        # Clear state before reconnect
        self._initialized = False
        self._api = None
        self._framework = None
        self._ws = None

        # Reconnect
        await self.connect()

        if self._stop_event.is_set():
            return

        # Re-initialize if we have a stored client_id
        if self._initialized_client_id:
            try:
                await self.initialize(self._initialized_client_id)
                logger.debug("wsbus.client.reinitialized client_id={}", self._initialized_client_id)
            except Exception as e:
                logger.error("wsbus.client.reinitialize_failed error={}", e)
                return

        # Restore subscriptions
        for topic in self._subscribed_topics:
            try:
                await self.subscribe(topic)
                logger.debug("wsbus.client.resubscribed topic={}", topic)
            except Exception as e:
                logger.error("wsbus.client.resubscribe_failed topic={} error={}", topic, e)

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

    async def send_message(self, params: SendMessageParams) -> SendMessageResult:
        """Handle send message request.

        Called when server sends a message to this client.
        Delegates to registered handlers.
        """
        # Dispatch to handlers via _handle_notification
        self._handle_notification({"topic": params.topic, "payload": params.payload})
        return SendMessageResult(success=True, stop_propagation=False)

    def _topic_matches(self, topic: str, pattern: str) -> bool:
        """Check if topic matches wildcard pattern."""
        return fnmatch(topic, pattern)

    async def initialize(self, client_id: str) -> InitializeResult:
        """Initialize connection with server."""
        if not self._api:
            raise RuntimeError("Not connected")
        if self._initialized:
            raise RuntimeError("Already initialized")
        result = await self._api.initialize(InitializeParams(client_id=client_id))
        self._initialized = True
        self._initialized_client_id = client_id  # Store for reconnect
        return result

    async def subscribe(self, topic: str) -> SubscribeResult:
        """Subscribe to a topic pattern."""
        if not self._api:
            raise RuntimeError("Not connected")
        result = await self._api.subscribe(SubscribeParams(topic=topic))
        # Store handler mapping for this subscription
        if topic not in self._notification_handlers:
            self._notification_handlers[topic] = []
        # Track for reconnect
        self._subscribed_topics.add(topic)
        return result

    async def unsubscribe(self, topic: str) -> UnsubscribeResult:
        """Unsubscribe from a topic pattern."""
        if not self._api:
            raise RuntimeError("Not connected")
        # Remove handlers for this topic
        self._notification_handlers.pop(topic, None)
        # Remove from tracked subscriptions
        self._subscribed_topics.discard(topic)
        return await self._api.unsubscribe(UnsubscribeParams(topic=topic))

    def on_notification(self, pattern: str, handler: Callable[[str, dict[str, Any]], Any]) -> None:
        """Register a handler for messages matching pattern."""
        if pattern not in self._notification_handlers:
            self._notification_handlers[pattern] = []
        self._notification_handlers[pattern].append(handler)

    def _handle_notification(self, params: dict[str, Any]) -> None:
        """Handle incoming notification."""
        # Note: params keys are camelCase due to ProtocolModel alias_generator
        topic = params.get("topic", "")
        payload = params.get("payload", {})

        logger.debug(
            "wsbus.client.handle_notification topic={} handlers_count={} payload_keys={}",
            topic,
            len(self._notification_handlers),
            list(payload.keys()) if isinstance(payload, dict) else [],
        )

        matched_patterns = []
        tasks: list[asyncio.Task[Any]] = []
        for pattern, handlers in self._notification_handlers.items():
            if self._topic_matches(topic, pattern):
                matched_patterns.append(pattern)
                for handler in handlers:
                    try:
                        if inspect.iscoroutinefunction(handler):
                            # Create task with exception handling
                            task = asyncio.create_task(self._run_handler_with_error_handling(handler, topic, payload))
                            tasks.append(task)
                        else:
                            handler(topic, payload)
                    except Exception:
                        logger.exception("wsbus.client.handler_error topic={}", topic)

        # Store tasks to prevent garbage collection
        if tasks:
            self._pending_tasks = tasks

        logger.debug("wsbus.client.notification_matched topic={} patterns={}", topic, matched_patterns)

    async def _run_handler_with_error_handling(
        self, handler: Callable[[str, dict[str, Any]], Any], topic: str, payload: dict[str, Any]
    ) -> None:
        """Run handler and catch any exceptions."""
        try:
            await handler(topic, payload)
        except Exception:
            logger.exception("wsbus.client.handler_execution_error topic={}", topic)

    async def publish_inbound(self, message: InboundMessage) -> None:
        """Publish inbound message using sendMessage."""
        if not self._api:
            raise RuntimeError("Not connected")
        topic = f"inbound:{message.chat_id}"
        payload: dict[str, object] = {
            "channel": message.channel,
            "senderId": message.sender_id,
            "chatId": message.chat_id,
            "content": message.content,
        }
        logger.debug(
            "wsbus.client.publish_inbound topic={} channel={} chat_id={} sender_id={} content_len={}",
            topic,
            message.channel,
            message.chat_id,
            message.sender_id,
            len(message.content),
        )
        await self._api.send_message(SendMessageParams(topic=topic, payload=payload))

    async def publish_outbound(self, message: OutboundMessage) -> None:
        """Publish outbound message using sendMessage."""
        if not self._api:
            raise RuntimeError("Not connected")
        topic = f"outbound:{message.chat_id}"
        payload: dict[str, object] = {
            "channel": message.channel,
            "chatId": message.chat_id,
            "content": message.content,
        }
        logger.debug(
            "wsbus.client.publish_outbound topic={} channel={} chat_id={} content_len={}",
            topic,
            message.channel,
            message.chat_id,
            len(message.content),
        )
        await self._api.send_message(SendMessageParams(topic=topic, payload=payload))

    async def on_inbound(self, handler: Callable[[InboundMessage], Coroutine[Any, Any, None]]) -> Callable[[], None]:
        """Register handler for inbound messages. Returns unsubscribe function."""

        async def wrapper(topic: str, payload: dict[str, Any]) -> None:
            logger.info("wsbus.client.on_inbound.wrapper received topic={}", topic)
            msg = InboundMessage(
                channel=payload.get("channel", ""),
                sender_id=payload.get("senderId", ""),
                chat_id=payload.get("chatId", ""),
                content=payload.get("content", ""),
            )
            logger.info("wsbus.client.on_inbound.wrapper calling handler with msg.chat_id={}", msg.chat_id)
            await handler(msg)
            logger.info("wsbus.client.on_inbound.wrapper handler done")

        await self.subscribe("inbound:*")
        self.on_notification("inbound:*", wrapper)

        _task_ref: list[asyncio.Task[Any]] = []

        def _unsubscribe() -> None:
            _task_ref.clear()
            _task_ref.append(asyncio.create_task(self.unsubscribe("inbound:*")))

        return _unsubscribe

    async def on_outbound(self, handler: Callable[[OutboundMessage], Coroutine[Any, Any, None]]) -> Callable[[], None]:
        """Register handler for outbound messages. Returns unsubscribe function."""

        async def wrapper(topic: str, payload: dict[str, Any]) -> None:
            msg = OutboundMessage(
                channel=payload.get("channel", ""),
                chat_id=payload.get("chatId", ""),
                content=payload.get("content", ""),
            )
            await handler(msg)

        await self.subscribe("outbound:*")
        self.on_notification("outbound:*", wrapper)

        _task_ref: list[asyncio.Task[Any]] = []

        def _unsubscribe() -> None:
            _task_ref.clear()
            _task_ref.append(asyncio.create_task(self.unsubscribe("outbound:*")))

        return _unsubscribe
