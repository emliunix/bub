"""Bus package.

WebSocket-based message bus implementation for agent communication.
"""

from bub.bus.bus import AgentBusClient, AgentBusServer, AgentConnection
from bub.bus.log import ActivityLogWriter
from bub.bus.protocol import (
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

__all__ = [
    "ActivityLogWriter",
    "AgentBusClient",
    "AgentBusServer",
    "AgentConnection",
    "AgentBusClientApi",
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
]
