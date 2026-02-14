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
from typing import Any, cast

import websockets
import websockets.asyncio.client
import websockets.asyncio.server
from loguru import logger

from bub.channels.events import InboundMessage, OutboundMessage
from bub.rpc.agent_protocol import (
    AgentProtocol,
    ClientInfo,
    InitializeParams,
    InitializeResult,
    NotifyParams,
    PingParams,
    ServerCapabilities,
    ServerInfo,
    SubscribeParams,
    SubscribeResult,
    UnsubscribeParams,
    UnsubscribeResult,
)
from bub.rpc.protocol import JSONRPCErrorException, JSONRPCFramework


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
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return data


class AgentBusServer:
    """JSON-RPC 2.0 WebSocket server for agent communication."""

    def __init__(self, host: str = "localhost", port: int = 7892) -> None:
        self._host = host
        self._port = port
        self._server_id = f"bus-{uuid.uuid4().hex[:8]}"
        self._connections: dict[str, dict[str, Any]] = {}
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

    async def _handle_client(self, websocket: Any) -> None:
        """Handle incoming client connection."""
        conn_id = str(id(websocket))

        # Create transport, framework, and protocol for this connection
        transport = WebSocketTransport(websocket)
        framework = JSONRPCFramework(transport)
        agent_protocol = AgentProtocol(framework)

        # Initialize connection state
        self._connections[conn_id] = {
            "ws": websocket,
            "transport": transport,
            "framework": framework,
            "protocol": agent_protocol,
            "initialized": False,
            "client_id": None,
            "subscriptions": {},
        }

        conn = self._connections[conn_id]
        logger.info("wsbus.client.connected conn_id={}", conn_id)

        # Register server-side method handlers with initialization check wrapper
        framework.register_method("initialize", lambda params: self._handle_initialize(conn, params))
        framework.register_method("subscribe", lambda params: self._handle_subscribe_check_init(conn, params))
        framework.register_method("unsubscribe", lambda params: self._handle_unsubscribe_check_init(conn, params))
        framework.register_method("ping", lambda params: self._handle_ping_check_init(conn, params))

        # Register notification handler for "notify" with initialization check
        framework.on_notification("notify", lambda params: self._handle_notify_check_init(conn, params))

        # Start listening for messages
        try:
            await framework.listen()
        except websockets.ConnectionClosed:
            pass
        finally:
            self._connections.pop(conn_id, None)
            logger.info("wsbus.client.disconnected conn_id={}", conn_id)

    def _check_initialized(self, conn: dict[str, Any], method: str) -> None:
        """Check if connection is initialized before handling non-initialize requests."""
        if not conn["initialized"] and method != "initialize":
            raise JSONRPCErrorException(-32001, "Not initialized")

    def _handle_subscribe_check_init(self, conn: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        """Handle subscribe request with initialization check."""
        self._check_initialized(conn, "subscribe")
        return self._handle_subscribe(conn, params)

    def _handle_unsubscribe_check_init(self, conn: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        """Handle unsubscribe request with initialization check."""
        self._check_initialized(conn, "unsubscribe")
        return self._handle_unsubscribe(conn, params)

    def _handle_ping_check_init(self, conn: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        """Handle ping request with initialization check."""
        self._check_initialized(conn, "ping")
        return self._handle_ping(params)

    def _handle_notify_check_init(self, conn: dict[str, Any], params: dict[str, Any]) -> None:
        """Handle notify notification with initialization check."""
        try:
            self._check_initialized(conn, "notify")
        except JSONRPCErrorException:
            return
        return self._handle_notify(conn, params)

    def _handle_initialize(self, conn: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        """Handle initialize request."""
        if conn["initialized"]:
            raise RuntimeError("Already initialized")

        try:
            # Use model_validate to handle aliased field names from JSON
            init_params = InitializeParams.model_validate(params)
        except Exception as e:
            logger.exception("wsbus.server.invalid_initialize_params")
            raise RuntimeError(f"Invalid params: {e}") from e

        client_id = init_params.client_id
        conn["client_id"] = client_id
        conn["initialized"] = True

        server_info = ServerInfo(name="bub-bus", version="0.2.0")
        capabilities = ServerCapabilities(
            subscribe=True,
            publish=True,
            topics=["inbound:*", "outbound:*", "agent:*"],
        )
        result = InitializeResult(
            server_id=self._server_id,
            server_info=server_info,
            capabilities=capabilities,
        )

        logger.info("wsbus.server.initialize_success client_id={}", client_id)
        return result.model_dump(by_alias=True)

    def _handle_subscribe(self, conn: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        """Handle subscribe request."""
        try:
            # Use model_validate to handle aliased field names from JSON
            sub_params = SubscribeParams.model_validate(params)
            topic = sub_params.topic
        except Exception as e:
            logger.exception("wsbus.server.invalid_subscribe_params")
            raise RuntimeError(f"Invalid params: {e}") from e

        if not topic:
            logger.warning("wsbus.server.subscribe_missing_topic client_id={}", conn.get("client_id"))
            raise RuntimeError("Topic is required")

        sub_id = f"sub_{uuid.uuid4().hex[:8]}"
        conn["subscriptions"][topic] = sub_id

        logger.info(
            "wsbus.server.subscribe client_id={} topic={} sub_id={} total_subs={}",
            conn["client_id"],
            topic,
            sub_id,
            len(conn["subscriptions"]),
        )

        result = SubscribeResult(subscription_id=sub_id)
        return result.model_dump(by_alias=True)

    def _handle_unsubscribe(self, conn: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        """Handle unsubscribe request."""
        try:
            # Use model_validate to handle aliased field names from JSON
            unsub_params = UnsubscribeParams.model_validate(params)
            subscription_id = unsub_params.subscription_id
        except Exception as e:
            logger.exception("wsbus.server.invalid_unsubscribe_params")
            raise RuntimeError(f"Invalid params: {e}") from e

        topic_to_remove = None
        for topic, sub_id in list(conn["subscriptions"].items()):
            if sub_id == subscription_id:
                topic_to_remove = topic
                break

        if topic_to_remove:
            conn["subscriptions"].pop(topic_to_remove)
            logger.info(
                "wsbus.server.unsubscribe client_id={} sub_id={} topic={}",
                conn["client_id"],
                subscription_id,
                topic_to_remove,
            )
            result = UnsubscribeResult(success=True)
        else:
            logger.warning(
                "wsbus.server.unsubscribe_not_found client_id={} sub_id={}", conn["client_id"], subscription_id
            )
            raise RuntimeError("Subscription not found")

        return result.model_dump(by_alias=True)

    def _handle_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ping request."""
        from bub.rpc.agent_protocol import PingResult

        result = PingResult(timestamp=datetime.now(UTC).isoformat())
        return result.model_dump(by_alias=True)

    def _handle_notify(self, conn: dict[str, Any], params: dict[str, Any]) -> None:
        """Handle notify notification - broadcast to all subscribers."""
        try:
            # Use model_validate to handle aliased field names from JSON
            notify_params = NotifyParams.model_validate(params)
            topic = notify_params.topic
            payload = notify_params.payload or {}
        except Exception:
            return

        if not topic:
            return

        logger.debug(
            "wsbus.server.broadcast_notify from_client={} topic={} total_conns={}",
            conn.get("client_id"),
            topic,
            len(self._connections),
        )

        # Broadcast to all matching subscribers using their frameworks
        tasks: list[asyncio.Task[Any]] = []
        for other_conn in self._connections.values():
            if other_conn["initialized"]:
                for sub_topic in list(other_conn["subscriptions"].keys()):
                    if self._topic_matches(topic, sub_topic):
                        other_framework = other_conn["framework"]
                        notify_params_dict = NotifyParams(topic=topic, payload=cast(dict[str, object], payload))
                        task = asyncio.create_task(
                            other_framework.send_notification(
                                "notify",
                                notify_params_dict.model_dump(by_alias=True),
                            )
                        )
                        tasks.append(task)
                        break
        # Store tasks to prevent garbage collection
        if tasks:
            conn["_notify_tasks"] = tasks

    def _topic_matches(self, topic: str, pattern: str) -> bool:
        """Check if topic matches pattern (supports wildcard *)."""
        if "*" in pattern:
            prefix = pattern.replace("*", "")
            return topic.startswith(prefix)
        return topic == pattern

    async def publish(self, topic: str, payload: dict) -> None:
        """Publish message to all subscribers."""
        for conn in self._connections.values():
            if conn["initialized"]:
                for sub_topic in list(conn["subscriptions"].keys()):
                    if self._topic_matches(topic, sub_topic):
                        framework = conn["framework"]
                        notify_params = NotifyParams(topic=topic, payload=cast(dict[str, object], payload))
                        await framework.send_notification(
                            "notify",
                            notify_params.model_dump(by_alias=True),
                        )
                        break

    async def publish_inbound(self, message: InboundMessage) -> None:
        """Publish inbound message."""
        topic = f"inbound:{message.chat_id}"
        payload = {"chat_id": message.chat_id, "content": message.content, "sender_id": message.sender_id}
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
        self._url = url
        self._ws: Any = None
        self._framework: JSONRPCFramework | None = None
        self._agent_protocol: AgentProtocol | None = None
        self._listen_task: asyncio.Task | None = None
        self._notification_handlers: dict[str, list[Callable[[str, dict[str, Any]], Any]]] = {}
        self._pending_tasks: list[asyncio.Task[Any]] = []

    @property
    def url(self) -> str:
        return self._url

    async def connect(self) -> None:
        """Connect to server."""
        self._ws = await websockets.connect(self._url)

        # Create transport, framework, and protocol
        transport = WebSocketTransport(self._ws)
        self._framework = JSONRPCFramework(transport)
        self._agent_protocol = AgentProtocol(self._framework)

        # Register notification handler for "notify"
        self._framework.on_notification("notify", self._handle_notification)

        # Start listening for messages
        self._listen_task = asyncio.create_task(self._framework.listen())

        logger.info("wsbus.client.connected url={}", self._url)

    async def disconnect(self) -> None:
        """Disconnect from server."""
        if self._framework:
            await self._framework.stop()
        if self._ws:
            await self._ws.close()
        if self._listen_task:
            self._listen_task.cancel()
        logger.info("wsbus.client.disconnected")

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

    def _topic_matches(self, topic: str, pattern: str) -> bool:
        """Check if topic matches pattern."""
        if "*" in pattern:
            prefix = pattern.replace("*", "")
            return topic.startswith(prefix)
        return topic == pattern

    async def initialize(self, client_id: str, client_info: dict[str, Any] | None = None) -> InitializeResult:
        """Send initialize handshake."""
        if not self._agent_protocol:
            raise RuntimeError("Not connected")

        info = ClientInfo(**client_info) if client_info else ClientInfo(name="unknown", version="0.0.0")
        result = await self._agent_protocol.initialize(InitializeParams(client_id=client_id, client_info=info))

        logger.info("wsbus.client.initialized server_id={}", result.server_id)
        return result

    async def subscribe(self, topic: str) -> SubscribeResult:
        """Subscribe to a topic."""
        if not self._agent_protocol:
            raise RuntimeError("Not connected")

        result = await self._agent_protocol.subscribe(SubscribeParams(topic=topic))

        if topic not in self._notification_handlers:
            self._notification_handlers[topic] = []

        logger.debug("wsbus.client.subscribe topic={} sub_id={}", topic, result.subscription_id)
        return result

    async def unsubscribe(self, subscription_id: str) -> UnsubscribeResult:
        """Unsubscribe from a topic."""
        if not self._agent_protocol:
            raise RuntimeError("Not connected")

        result = await self._agent_protocol.unsubscribe(UnsubscribeParams(subscription_id=subscription_id))

        logger.debug("wsbus.client.unsubscribe sub_id={} success={}", subscription_id, result.success)
        return result

    async def notify(self, topic: str, payload: dict[str, Any]) -> None:
        """Send notification (fire and forget)."""
        if not self._agent_protocol:
            raise RuntimeError("Not connected")

        await self._agent_protocol.notify(NotifyParams(topic=topic, payload=cast(dict[str, object], payload)))

        logger.debug(
            "wsbus.client.notify_send topic={} payload_keys={}",
            topic,
            list(payload.keys()) if isinstance(payload, dict) else [],
        )

    async def ping(self) -> None:
        """Send ping request."""
        if not self._agent_protocol:
            raise RuntimeError("Not connected")

        result = await self._agent_protocol.ping(PingParams())
        logger.debug("wsbus.client.ping timestamp={}", result.timestamp)

    def on_notification(self, topic_pattern: str, handler: Callable[[str, dict[str, Any]], Any]) -> None:
        """Register handler for notifications matching topic pattern."""
        if topic_pattern not in self._notification_handlers:
            self._notification_handlers[topic_pattern] = []
        self._notification_handlers[topic_pattern].append(handler)

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
        await self.notify(topic, payload)

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
        await self.notify(topic, payload)

    async def on_inbound(self, handler: Callable[[InboundMessage], Coroutine[Any, Any, None]]) -> Callable[[], None]:
        """Register handler for inbound messages. Returns unsubscribe function."""
        sub_id = ""

        async def wrapper(topic: str, payload: dict[str, Any]) -> None:
            msg = InboundMessage(
                channel=payload.get("channel", ""),
                sender_id=payload.get("senderId", ""),
                chat_id=payload.get("chatId", ""),
                content=payload.get("content", ""),
            )
            await handler(msg)

        sub_result = await self.subscribe("inbound:*")
        sub_id = sub_result.subscription_id

        _task_ref: list[asyncio.Task[Any]] = []

        def _unsubscribe() -> None:
            if sub_id:
                _task_ref.clear()
                _task_ref.append(asyncio.create_task(self.unsubscribe(sub_id)))

        return _unsubscribe

    async def on_outbound(self, handler: Callable[[OutboundMessage], Coroutine[Any, Any, None]]) -> Callable[[], None]:
        """Register handler for outbound messages. Returns unsubscribe function."""
        sub_id = ""

        async def wrapper(topic: str, payload: dict[str, Any]) -> None:
            msg = OutboundMessage(
                channel=payload.get("channel", ""),
                chat_id=payload.get("chatId", ""),
                content=payload.get("content", ""),
            )
            await handler(msg)

        sub_result = await self.subscribe("outbound:*")
        sub_id = sub_result.subscription_id

        _task_ref: list[asyncio.Task[Any]] = []

        def _unsubscribe() -> None:
            if sub_id:
                _task_ref.clear()
                _task_ref.append(asyncio.create_task(self.unsubscribe(sub_id)))

        return _unsubscribe
