"""Agent Communication Protocol over WebSocket.

This module implements the JSON-RPC 2.0 protocol defined in docs/agent-protocol.md.
Uses JSONRPCFramework and AgentProtocol for typed API.

Follows typed API pattern from MCP Python SDK.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import sqlite3
import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path
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

background_tasks: set[asyncio.Task[Any]] = set()  # Store background tasks to prevent garbage collection


class ActivityLogWriter:
    """Async append-only SQLite activity logger."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._init_db)
        self._worker = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._worker is None:
            return
        await self._queue.put({})
        await self._worker
        self._worker = None

    async def log(
        self,
        *,
        event: str,
        message_id: str,
        rpc_id: str | None = None,
        actor: str | None = None,
        topic: str | None = None,
        status: str | None = None,
        payload: dict[str, object] | None = None,
        error: str | None = None,
    ) -> None:
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "event": event,
            "message_id": message_id,
            "rpc_id": rpc_id or "",
            "actor": actor or "",
            "topic": topic or "",
            "status": status or "",
            "payload_json": json.dumps(payload or {}, ensure_ascii=False),
            "error": error or "",
        }
        await self._queue.put(entry)

    async def _run(self) -> None:
        while True:
            entry = await self._queue.get()
            if not entry:
                return
            await asyncio.to_thread(self._insert, entry)

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS activity_log (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ts TEXT NOT NULL,
                  event TEXT NOT NULL,
                  message_id TEXT NOT NULL,
                  rpc_id TEXT,
                  actor TEXT,
                  topic TEXT,
                  status TEXT,
                  payload_json TEXT,
                  error TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_message_id ON activity_log(message_id)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity_log(ts)")

    def _insert(self, entry: dict[str, str]) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO activity_log (ts, event, message_id, rpc_id, actor, topic, status, payload_json, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry["ts"],
                    entry["event"],
                    entry["message_id"],
                    entry["rpc_id"],
                    entry["actor"],
                    entry["topic"],
                    entry["status"],
                    entry["payload_json"],
                    entry["error"],
                ),
            )


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
        self.subscriptions: set[str] = set()  # topic patterns

    async def handle_initialize(self, params: InitializeParams) -> InitializeResult:
        """Handle initialize request."""
        if self.initialized:
            raise JSONRPCErrorException(-32001, "Already initialized")
        self.client_id = params.client_id
        self.initialized = True

        server_info = ServerInfo(name="bub-bus", version="0.2.0")
        capabilities = ServerCapabilities(
            subscribe=True,
            publish=True,
            process_message=True,
            topics=["tg:*", "agent:*", "system:*"],
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

        self.subscriptions.add(topic)

        logger.info(
            "wsbus.server.subscribe client_id={} topic={} total_subs={}",
            self.client_id,
            topic,
            len(self.subscriptions),
        )

        result = SubscribeResult(success=True)
        return result

    async def handle_unsubscribe(self, params: UnsubscribeParams) -> UnsubscribeResult:
        """Handle unsubscribe request."""
        self._check_initialized()
        if params.topic not in self.subscriptions:
            raise JSONRPCErrorException(-32003, "Subscription not found")
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
        """Handle send message request - broadcast to all subscribers."""
        self._check_initialized()
        payload = cast(dict[str, object], params.payload)
        self._server.validate_send_message(
            sender=self.client_id or self.conn_id,
            topic=params.topic,
            payload=payload,
        )
        message_id = str(payload.get("messageId", f"msg_{uuid.uuid4().hex}"))
        delivered_to = await self._server.publish(
            params.topic,
            payload,
            message_id=message_id,
            sender=self.client_id or self.conn_id,
        )
        return SendMessageResult(accepted=True, message_id=message_id, delivered_to=delivered_to)


class AgentBusServer:
    """JSON-RPC 2.0 WebSocket server for agent communication."""

    def __init__(self, host: str = "localhost", port: int = 7892, activity_log_path: Path | None = None) -> None:
        self._host = host
        self._port = port
        self._server_id = f"bus-{uuid.uuid4().hex}"
        self._connections: dict[str, AgentConnection] = {}
        self._server: websockets.Server | None = None
        self._activity_log = ActivityLogWriter(activity_log_path or Path("run/wsbus_activity.sqlite3"))

    @property
    def url(self) -> str:
        return f"ws://{self._host}:{self._port}"

    async def start_server(self) -> None:
        """Start WebSocket server."""
        await self._activity_log.start()
        self._server = await websockets.serve(self._handle_client, self._host, self._port)
        logger.info("wsbus.started url={}", self.url)

    async def stop_server(self) -> None:
        """Stop WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        await self._activity_log.stop()
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

    def _topic_matches(self, topic: str, patterns: set[str]) -> bool:
        """Check if topic matches any wildcard pattern."""
        return any(fnmatch(topic, pattern) for pattern in patterns)

    def validate_send_message(self, *, sender: str, topic: str, payload: dict[str, object]) -> None:
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
                f"Sender '{sender}' is not allowed to send type '{msg_type}' to topic '{topic}'",
            )

    def _allowed_types_for_sender(self, sender: str) -> set[str]:
        if sender.startswith("tg:"):
            return {"spawn_request", "configure", "tg_message", "delivery_status"}
        if sender == "agent:system":
            return {"spawn_result", "route_assigned", "agent_event"}
        if sender.startswith("agent:"):
            return {"tg_reply", "agent_event", "delivery_status"}
        return set()

    async def publish(
        self,
        topic: str,
        payload: dict[str, object],
        *,
        message_id: str,
        sender: str,
        rpc_id: str | None = None,
    ) -> int:
        """Publish message to all subscribers and return delivered count."""
        logger.info("wsbus.server.publish topic={} payload_keys={}", topic, list(payload.keys()))
        await self._activity_log.log(
            event="send_start",
            message_id=message_id,
            rpc_id=rpc_id,
            actor=sender,
            topic=topic,
            status="start",
            payload=payload,
        )
        matched_peers: list[str] = []
        for other_conn in self._connections.values():
            if other_conn.initialized and self._topic_matches(topic, other_conn.subscriptions):
                peer_id = other_conn.client_id or other_conn.conn_id
                matched_peers.append(peer_id)
                logger.info("wsbus.server.publish sending to peer={}", peer_id)
                await self._activity_log.log(
                    event="process_start",
                    message_id=message_id,
                    rpc_id=rpc_id,
                    actor=peer_id,
                    topic=topic,
                    status="start",
                    payload=payload,
                )
                try:
                    process_params = ProcessMessageParams(topic=topic, payload=payload)
                    result = await other_conn.api.process_message(process_params)
                    await self._activity_log.log(
                        event="process_finish",
                        message_id=message_id,
                        rpc_id=rpc_id,
                        actor=peer_id,
                        topic=topic,
                        status=result.status,
                        payload=payload,
                    )
                except Exception as exc:
                    await self._activity_log.log(
                        event="process_finish",
                        message_id=message_id,
                        rpc_id=rpc_id,
                        actor=peer_id,
                        topic=topic,
                        status="error",
                        payload=payload,
                        error=str(exc),
                    )
                    logger.exception("wsbus.publish.process_error peer={} topic={}", peer_id, topic)

        if matched_peers:
            logger.info(
                "wsbus.publish topic={} peers={} matched={}",
                topic,
                len(matched_peers),
                matched_peers,
            )
        else:
            logger.info("wsbus.publish topic={} peers=0 (no subscribers)", topic)

        await self._activity_log.log(
            event="send_finish",
            message_id=message_id,
            rpc_id=rpc_id,
            actor=sender,
            topic=topic,
            status="ok",
            payload=payload,
        )
        return len(matched_peers)

    async def publish_inbound(self, message: InboundMessage) -> None:
        """Publish inbound message."""
        topic = f"tg:{message.chat_id}"
        payload: dict[str, object] = {
            "messageId": f"msg_{uuid.uuid4().hex}",
            "type": "tg_message",
            "from": topic,
            "timestamp": message.timestamp.isoformat(),
            "content": {
                "text": message.content,
                "senderId": message.sender_id,
                "channel": message.channel,
            },
        }
        logger.debug(
            "wsbus.client.publish_inbound topic={} channel={} chat_id={} sender_id={} content_len={}",
            topic,
            message.channel,
            message.chat_id,
            message.sender_id,
            len(message.content),
        )
        await self.publish(topic, payload, message_id=str(payload["messageId"]), sender="bus")

    async def publish_outbound(self, message: OutboundMessage) -> None:
        """Publish outbound message."""
        topic = f"tg:{message.chat_id}"
        payload: dict[str, object] = {
            "messageId": f"msg_{uuid.uuid4().hex}",
            "type": "tg_reply",
            "from": "agent:unknown",
            "timestamp": datetime.now(UTC).isoformat(),
            "content": {"text": message.content, "channel": message.channel},
        }
        logger.debug(
            "wsbus.client.publish_outbound topic={} channel={} chat_id={} content_len={}",
            topic,
            message.channel,
            message.chat_id,
            len(message.content),
        )
        await self.publish(topic, payload, message_id=str(payload["messageId"]), sender="bus")


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
        self._subscription_refcounts: dict[str, int] = {}
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
                await self._api.subscribe(SubscribeParams(topic=topic))
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

    async def process_message(self, params: ProcessMessageParams) -> ProcessMessageResult:
        """Handle processMessage request from bus."""
        matched = await self._dispatch_message(params.topic, cast(dict[str, Any], params.payload))
        if matched == 0:
            return ProcessMessageResult(processed=False, status="ignored", message="No matching handlers")
        return ProcessMessageResult(processed=True, status="ok", message="Processed")

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
        count = self._subscription_refcounts.get(topic, 0)
        if count == 0:
            result = await self._api.subscribe(SubscribeParams(topic=topic))
            self._subscribed_topics.add(topic)
        else:
            result = SubscribeResult(success=True)
        # Store handler mapping for this subscription
        if topic not in self._notification_handlers:
            self._notification_handlers[topic] = []
        self._subscription_refcounts[topic] = count + 1
        return result

    async def unsubscribe(self, topic: str) -> UnsubscribeResult:
        """Unsubscribe from a topic pattern."""
        if not self._api:
            raise RuntimeError("Not connected")
        count = self._subscription_refcounts.get(topic, 0)
        if count <= 1:
            self._notification_handlers.pop(topic, None)
            self._subscribed_topics.discard(topic)
            self._subscription_refcounts.pop(topic, None)
            return await self._api.unsubscribe(UnsubscribeParams(topic=topic))

        self._subscription_refcounts[topic] = count - 1
        return UnsubscribeResult(success=True)

    def on_notification(self, pattern: str, handler: Callable[[str, dict[str, Any]], Any]) -> None:
        """Register a handler for messages matching pattern."""
        if pattern not in self._notification_handlers:
            self._notification_handlers[pattern] = []
        self._notification_handlers[pattern].append(handler)

    async def _dispatch_message(self, topic: str, payload: dict[str, Any]) -> int:
        """Dispatch one routed message to matching handlers."""
        logger.debug(
            "wsbus.client.handle_notification topic={} handlers_count={} payload_keys={}",
            topic,
            len(self._notification_handlers),
            list(payload.keys()) if isinstance(payload, dict) else [],
        )

        matched_patterns = []
        matched_count = 0
        for pattern, handlers in self._notification_handlers.items():
            if self._topic_matches(topic, pattern):
                matched_patterns.append(pattern)
                for handler in handlers:
                    matched_count += 1
                    try:
                        if inspect.iscoroutinefunction(handler):
                            await self._run_handler_with_error_handling(handler, topic, payload)
                        else:
                            handler(topic, payload)
                    except Exception:
                        logger.exception("wsbus.client.handler_error topic={}", topic)

        logger.debug("wsbus.client.notification_matched topic={} patterns={}", topic, matched_patterns)
        return matched_count

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
        topic = f"tg:{message.chat_id}"
        payload: dict[str, object] = {
            "messageId": f"msg_{uuid.uuid4().hex}",
            "type": "tg_message",
            "from": topic,
            "timestamp": message.timestamp.isoformat(),
            "content": {
                "text": message.content,
                "senderId": message.sender_id,
                "channel": message.channel,
            },
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
        topic = f"tg:{message.chat_id}"
        payload: dict[str, object] = {
            "messageId": f"msg_{uuid.uuid4().hex}",
            "type": "tg_reply",
            "from": "agent:unknown",
            "timestamp": datetime.now(UTC).isoformat(),
            "content": {
                "text": message.content,
                "channel": message.channel,
            },
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
            content_obj = payload.get("content", {})
            text = content_obj.get("text", "") if isinstance(content_obj, dict) else ""
            sender_id = content_obj.get("senderId", "") if isinstance(content_obj, dict) else ""
            channel = content_obj.get("channel", "telegram") if isinstance(content_obj, dict) else "telegram"
            chat_id = topic.split(":", 1)[1] if ":" in topic else ""
            msg = InboundMessage(
                channel=str(channel),
                sender_id=str(sender_id),
                chat_id=chat_id,
                content=str(text),
            )
            logger.info("wsbus.client.on_inbound.wrapper calling handler with msg.chat_id={}", msg.chat_id)
            await handler(msg)
            logger.info("wsbus.client.on_inbound.wrapper handler done")

        await self.subscribe("tg:*")

        async def typed_wrapper(topic: str, payload: dict[str, Any]) -> None:
            msg_type = str(payload.get("type", ""))
            if msg_type != "tg_message":
                return
            await wrapper(topic, payload)

        self.on_notification("tg:*", typed_wrapper)

        _task_ref: list[asyncio.Task[Any]] = []

        def _unsubscribe() -> None:
            _task_ref.clear()
            _task_ref.append(asyncio.create_task(self.unsubscribe("tg:*")))

        return _unsubscribe

    async def on_outbound(self, handler: Callable[[OutboundMessage], Coroutine[Any, Any, None]]) -> Callable[[], None]:
        """Register handler for outbound messages. Returns unsubscribe function."""

        async def wrapper(topic: str, payload: dict[str, Any]) -> None:
            content_obj = payload.get("content", {})
            text = content_obj.get("text", "") if isinstance(content_obj, dict) else ""
            channel = content_obj.get("channel", "telegram") if isinstance(content_obj, dict) else "telegram"
            chat_id = topic.split(":", 1)[1] if ":" in topic else ""
            msg = OutboundMessage(
                channel=str(channel),
                chat_id=chat_id,
                content=str(text),
            )
            await handler(msg)

        await self.subscribe("tg:*")

        async def typed_wrapper(topic: str, payload: dict[str, Any]) -> None:
            msg_type = str(payload.get("type", ""))
            if msg_type != "tg_reply":
                return
            await wrapper(topic, payload)

        self.on_notification("tg:*", typed_wrapper)

        _task_ref: list[asyncio.Task[Any]] = []

        def _unsubscribe() -> None:
            _task_ref.clear()
            _task_ref.append(asyncio.create_task(self.unsubscribe("tg:*")))

        return _unsubscribe
