"""Bus package.

WebSocket-based message bus implementation for agent communication.
"""

from bub.bus.bus import (
    AgentBusClient,
    AgentBusServer,
    AgentConnection,
    WebSocketTransport,
)
from bub.bus.log import ActivityLogWriter
from bub.bus.protocol import (
    AgentBusClientApi,
    AgentBusClientCallbacks,
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
from bub.bus.types import (
    Address,
    ClientId,
    Closable,
    ConnectionId,
    Listener,
    MessageHandler,
    MessagePayload,
    TestMessage,
)

__all__ = [
    # Bus classes
    "ActivityLogWriter",
    "AgentBusClient",
    "AgentBusServer",
    "AgentConnection",
    "WebSocketTransport",
    # Protocol API
    "AgentBusClientApi",
    "AgentBusClientCallbacks",
    "AgentBusServerApi",
    "InitializeParams",
    "InitializeResult",
    "PingParams",
    "PingResult",
    "ProcessMessageParams",
    "ProcessMessageResult",
    "SendMessageParams",
    "SendMessageResult",
    "ServerCapabilities",
    "ServerInfo",
    "SubscribeParams",
    "SubscribeResult",
    "UnsubscribeParams",
    "UnsubscribeResult",
    "register_client_callbacks",
    "register_server_callbacks",
    # Types and protocols
    "Address",
    "ClientId",
    "Closable",
    "ConnectionId",
    "Listener",
    "MessageHandler",
    "MessagePayload",
    "TestMessage",
]
