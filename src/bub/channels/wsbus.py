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
    PublishInboundParams,
    PublishInboundResult,
    PublishOutboundParams,
    PublishOutboundResult,
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

    async def handle_publish_inbound(self, params: PublishInboundParams) -> PublishInboundResult:
        """Handle publish inbound request - broadcast to all subscribers."""
        self._check_initialized()
        topic = f"inbound:{params.chat_id}"
        payload = {
            "channel": params.channel,
            "senderId": params.sender_id,
            "chatId": params.chat_id,
            "content": params.content,
        }
        await self._server.publish(topic, payload)
        return PublishInboundResult(success=True)

    async def handle_publish_outbound(self, params: PublishOutboundParams) -> PublishOutboundResult:
        """Handle publish outbound request - broadcast to all subscribers."""
        self._check_initialized()
        topic = f"outbound:{params.chat_id}"
        payload = {
            "channel": params.channel,
            "chatId": params.chat_id,
            "content": params.content,
        }
        await self._server.publish(topic, payload)
        return PublishOutboundResult(success=True)


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
        for other_conn in self._connections.values():
            if other_conn.initialized and self._topic_matches(topic, other_conn.subscriptions):
                send_params = SendMessageParams(topic=topic, payload=cast(dict[str, object], payload))
                result = await other_conn.api.send_message(send_params)
                if result.stop_propagation:
                    return True
        return False

    async def publish_inbound(self, message: InboundMessage) -> None:
        """Publish inbound message."""
        topic = f"inbound:{message.chat_id}"
        payload = {"chatId": message.chat_id, "content": message.content, "senderId": message.sender_id}
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

    async def start_with_telegram(
        self,
        token: str,
        allow_from: set[str] | None = None,
        allow_chats: set[str] | None = None,
        proxy: str | None = None,
    ) -> None:
        """Start bus server with embedded telegram upstream channel."""
        from bub.channels.telegram import TelegramChannel, TelegramConfig

        telegram_config = TelegramConfig(
            token=token,
            allow_from=allow_from or set(),
            allow_chats=allow_chats or set(),
            proxy=proxy,
        )
        telegram = TelegramChannel(self, telegram_config)

        await telegram.start()
        self._telegram_channel = telegram
        logger.info("wsbus.telegram.started")

    async def stop_with_telegram(self) -> None:
        """Stop embedded telegram channel."""
        if hasattr(self, "_telegram_channel"):
            await self._telegram_channel.stop()


class AgentBusClient:
    """JSON-RPC 2.0 WebSocket client for agent communication."""

    def __init__(self, url: str) -> None:
        self._client_id = f"client-{uuid.uuid4().hex}"
        self._url = url
        self._ws: Any = None
        self._framework: JSONRPCFramework | None = None
        self._api: AgentBusClientApi | None = None
        self._run_task: asyncio.Task | None = None
        self._notification_handlers: dict[str, list[Callable[[str, dict[str, Any]], Any]]] = {}
        self._pending_tasks: list[asyncio.Task[Any]] = []
        self._initialized = False

    @property
    def url(self) -> str:
        return self._url

    async def connect(self) -> None:
        """Connect to server."""
        self._ws = await websockets.connect(self._url)

        # Create transport, framework, and protocol
        transport = WebSocketTransport(self._ws)
        self._framework = JSONRPCFramework(transport)
        self._api = AgentBusClientApi(self._framework)

        register_client_callbacks(self._framework, self)

        # Start listening for messages BEFORE sending requests
        self._run_task = asyncio.create_task(self._framework.run())
        await asyncio.sleep(0.01)  # Give framework time to start listening

        logger.info("wsbus.client.connected url={}", self._url)

    async def disconnect(self) -> None:
        """Disconnect from server."""
        if self._framework:
            await self._framework.stop()
        if self._ws:
            await self._ws.close()
        if self._run_task:
            self._run_task.cancel()
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
        return result

    async def subscribe(self, topic: str) -> SubscribeResult:
        """Subscribe to a topic pattern."""
        if not self._api:
            raise RuntimeError("Not connected")
        result = await self._api.subscribe(SubscribeParams(topic=topic))
        # Store handler mapping for this subscription
        if topic not in self._notification_handlers:
            self._notification_handlers[topic] = []
        return result

    async def unsubscribe(self, topic: str) -> UnsubscribeResult:
        """Unsubscribe from a topic pattern."""
        if not self._api:
            raise RuntimeError("Not connected")
        # Remove handlers for this topic
        self._notification_handlers.pop(topic, None)
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
                            task = asyncio.create_task(handler(topic, payload))
                            tasks.append(task)
                        else:
                            handler(topic, payload)
                    except Exception:
                        logger.exception("wsbus.client.handler_error topic={}", topic)

        # Store tasks to prevent garbage collection
        if tasks:
            self._pending_tasks = tasks

        logger.debug("wsbus.client.notification_matched topic={} patterns={}", topic, matched_patterns)

    async def publish_inbound(self, message: InboundMessage) -> None:
        """Publish inbound message."""
        if not self._api:
            raise RuntimeError("Not connected")
        params = PublishInboundParams(
            channel=message.channel,
            sender_id=message.sender_id,
            chat_id=message.chat_id,
            content=message.content,
        )
        logger.debug(
            "wsbus.client.publish_inbound channel={} chat_id={} sender_id={} content_len={}",
            message.channel,
            message.chat_id,
            message.sender_id,
            len(message.content),
        )
        await self._api.publish_inbound(params)

    async def publish_outbound(self, message: OutboundMessage) -> None:
        """Publish outbound message."""
        if not self._api:
            raise RuntimeError("Not connected")
        params = PublishOutboundParams(
            channel=message.channel,
            chat_id=message.chat_id,
            content=message.content,
        )
        logger.debug(
            "wsbus.client.publish_outbound channel={} chat_id={} content_len={}",
            message.channel,
            message.chat_id,
            len(message.content),
        )
        await self._api.publish_outbound(params)

    async def on_inbound(self, handler: Callable[[InboundMessage], Coroutine[Any, Any, None]]) -> Callable[[], None]:
        """Register handler for inbound messages. Returns unsubscribe function."""

        async def wrapper(topic: str, payload: dict[str, Any]) -> None:
            msg = InboundMessage(
                channel=payload.get("channel", ""),
                sender_id=payload.get("senderId", ""),
                chat_id=payload.get("chatId", ""),
                content=payload.get("content", ""),
            )
            await handler(msg)

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
