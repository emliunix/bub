"""WebSocket-based message bus for distributed communication."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import websockets
from loguru import logger

from bub.channels.events import (
    InboundMessage,
    OutboundMessage,
)


@dataclass
class BusMessage:
    """Message envelope for WebSocket bus."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    topic: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class WebSocketMessageBus:
    """WebSocket-based message bus.

    Can run as server (receives connections) or client (connects to server).
    """

    def __init__(self, host: str = "localhost", port: int = 7892) -> None:
        self._host = host
        self._port = port
        self._server: websockets.Server | None = None
        self._clients: set[websockets.WebSocketServerProtocol] = set()
        self._handlers: dict[str, list[Callable]] = {}
        self._subscription_id = 0
        self._subscriptions: dict[str, dict[str, Callable]] = {}
        self._running = False

    @property
    def url(self) -> str:
        return f"ws://{self._host}:{self._port}"

    async def start_server(self) -> None:
        """Start WebSocket server."""
        self._server = await websockets.serve(self._handle_client, self._host, self._port)
        self._running = True
        logger.info("wsbus.started url={}", self.url)

    async def stop_server(self) -> None:
        """Stop WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        self._running = False
        logger.info("wsbus.stopped")

    async def connect_client(self) -> websockets.WebSocketClientProtocol:
        """Connect as client to another bus."""
        ws = await websockets.connect(self.url)
        self._clients.add(ws)
        asyncio.create_task(self._receive_loop(ws))
        return ws

    async def _handle_client(self, websocket: websockets.WebSocketServerProtocol) -> None:
        """Handle incoming client connection."""
        self._clients.add(websocket)
        logger.info("wsbus.client_connected")
        try:
            async for message in websocket:
                await self._handle_message(message, websocket)
        except websockets.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            logger.info("wsbus.client_disconnected")

    async def _handle_message(self, raw: str, sender: websockets.WebSocketProtocol) -> None:
        """Handle incoming message."""
        try:
            data = json.loads(raw)
            msg = BusMessage(
                id=data.get("id", ""),
                topic=data.get("topic", ""),
                payload=data.get("payload", {}),
            )
        except json.JSONDecodeError:
            return

        # Call handlers
        for handler in self._handlers.get(msg.topic, []):
            try:
                await handler(msg.payload)
            except Exception:
                logger.exception("wsbus.handler_error topic={}", msg.topic)

        # Broadcast to other clients
        if self._clients:
            await asyncio.gather(
                *[c.send(raw) for c in self._clients if c != sender],
                return_exceptions=True,
            )

    async def _receive_loop(self, ws: websockets.WebSocketClientProtocol) -> None:
        """Receive loop for client connections."""
        try:
            async for message in ws:
                await self._handle_message(message, ws)
        except websockets.ConnectionClosed:
            self._clients.discard(ws)

    # -------------------------------------------------------------------------
    # Pub/Sub interface (same as in-process MessageBus)
    # -------------------------------------------------------------------------

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Publish message to bus."""
        msg = BusMessage(topic=topic, payload=payload)
        raw = json.dumps({"id": msg.id, "topic": msg.topic, "payload": msg.payload})

        # Call local handlers
        for handler in self._handlers.get(topic, []):
            try:
                await handler(payload)
            except Exception:
                logger.exception("wsbus.handler_error topic={}", topic)

        # Broadcast to connected clients
        if self._running and self._clients:
            await asyncio.gather(
                *[c.send(raw) for c in self._clients],
                return_exceptions=True,
            )

    async def subscribe(self, topic: str, handler: Callable) -> str:
        """Subscribe to topic. Returns subscription ID."""
        self._subscription_id += 1
        sub_id = f"sub_{self._subscription_id}"
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)
        self._subscriptions[sub_id] = {topic: handler}
        return sub_id

    async def unsubscribe(self, sub_id: str) -> None:
        """Unsubscribe by ID."""
        if sub_id in self._subscriptions:
            for topic, handler in self._subscriptions[sub_id].items():
                if topic in self._handlers:
                    self._handlers[topic].remove(handler)
            del self._subscriptions[sub_id]

    # Convenience methods matching MessageBus interface
    async def publish_inbound(self, message: InboundMessage) -> None:
        await self.publish(
            "inbound",
            {
                "channel": message.channel,
                "sender_id": message.sender_id,
                "chat_id": message.chat_id,
                "content": message.content,
                "metadata": message.metadata,
            },
        )

    async def publish_outbound(self, message: OutboundMessage) -> None:
        await self.publish(
            "outbound",
            {
                "channel": message.channel,
                "chat_id": message.chat_id,
                "content": message.content,
                "metadata": message.metadata,
                "reply_to_message_id": message.reply_to_message_id,
            },
        )

    def on_inbound(self, handler: Callable) -> Callable:
        """Subscribe to inbound messages."""
        sub_id = asyncio.get_event_loop().run_until_complete(self.subscribe("inbound", handler))
        return lambda: asyncio.get_event_loop().run_until_complete(self.unsubscribe(sub_id))

    def on_outbound(self, handler: Callable) -> Callable:
        """Subscribe to outbound messages."""
        sub_id = asyncio.get_event_loop().run_until_complete(self.subscribe("outbound", handler))
        return lambda: asyncio.get_event_loop().run_until_complete(self.unsubscribe(sub_id))


class WebSocketMessageBusClient:
    """Client that connects to a WebSocketMessageBus server."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._handlers: dict[str, list[Callable]] = {}
        self._running = False

    async def connect(self) -> None:
        """Connect to server."""
        self._ws = await websockets.connect(self._url)
        self._running = True
        asyncio.create_task(self._receive_loop())
        logger.info("wsbus.client.connected url={}", self._url)

    async def disconnect(self) -> None:
        """Disconnect from server."""
        self._running = False
        if self._ws:
            await self._ws.close()
        logger.info("wsbus.client.disconnected")

    async def _receive_loop(self) -> None:
        """Receive messages from server."""
        ws = self._ws
        if ws is None:
            return
        try:
            async for raw in ws:
                try:
                    data = json.loads(raw)
                    topic = data.get("topic", "")
                    payload = data.get("payload", {})
                except json.JSONDecodeError:
                    continue

                for handler in self._handlers.get(topic, []):
                    try:
                        await handler(payload)
                    except Exception:
                        logger.exception("wsbus.client.handler_error topic={}", topic)
        except websockets.ConnectionClosed:
            logger.info("wsbus.client.connection_closed")

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Publish to server."""
        if self._ws and self._running:
            await self._ws.send(json.dumps({"topic": topic, "payload": payload}))

    async def subscribe(self, topic: str, handler: Callable) -> None:
        """Subscribe to topic."""
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)

    async def unsubscribe(self, topic: str, handler: Callable) -> None:
        """Unsubscribe from topic."""
        if topic in self._handlers:
            self._handlers[topic].remove(handler)

    # Convenience methods
    async def publish_inbound(self, message: InboundMessage) -> None:
        await self.publish(
            "inbound",
            {
                "channel": message.channel,
                "sender_id": message.sender_id,
                "chat_id": message.chat_id,
                "content": message.content,
                "metadata": message.metadata,
            },
        )

    async def publish_outbound(self, message: OutboundMessage) -> None:
        await self.publish(
            "outbound",
            {
                "channel": message.channel,
                "chat_id": message.chat_id,
                "content": message.content,
                "metadata": message.metadata,
                "reply_to_message_id": message.reply_to_message_id,
            },
        )

    def on_inbound(self, handler: Callable) -> Callable:
        """Subscribe to inbound messages."""
        asyncio.get_event_loop().run_until_complete(self.subscribe("inbound", handler))
        return lambda: asyncio.get_event_loop().run_until_complete(self.unsubscribe("inbound", handler))

    def on_outbound(self, handler: Callable) -> Callable:
        """Subscribe to outbound messages."""
        asyncio.get_event_loop().run_until_complete(self.subscribe("outbound", handler))
        return lambda: asyncio.get_event_loop().run_until_complete(self.unsubscribe("outbound", handler))
