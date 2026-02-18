# JSON-RPC Framework Architecture

This document describes the 3-tier JSON-RPC 2.0 framework architecture in the bub project.

## Executive Summary

The JSON-RPC framework is organized into three distinct layers:

1. **Message/Serialization Layer** - Pydantic models for JSON encoding/decoding
2. **JSON-RPC Framework Layer** - Direction-agnostic, transport-agnostic JSON-RPC implementation
3. **Agent Bus Protocol Layer** - Agent Bus specific protocol methods and types

### Key Design Principle: Framework is Direction-Agnostic

The JSON-RPC framework (`bub/rpc/framework.py`) is **direction-agnostic** and **transport-agnostic**. It:

- Takes a **bidirectional JSON message transport** as input
- Does not care whether it's "server" or "client" side
- Supports both sending requests/notifications AND receiving/handling them
- The same framework instance can:
  - Send requests and receive responses
  - Receive requests and send responses
  - Send and receive notifications

Server/client roles exist in TWO places only:
1. **WebSocket transport layer** (`bub/bus/bus.py`) - `AgentBusServer` and `AgentBusClient` classes
2. **Protocol usage level** - One side acts as responder (registering method handlers), the other acts as caller (making requests)

But at the **JSON-RPC framework level**, there's no server/client distinction.

## Layer 1: Message/Serialization Layer

**Location:** `src/bub/rpc/types.py`

**Purpose:** Generic JSON-RPC 2.0 data models and transport protocols for serialization/deserialization

**Components:**
- `JSONRPCRequest` - JSON-RPC request with method, params, id
- `JSONRPCNotification` - JSON-RPC notification (fire-and-forget, no id)
- `JSONRPCResponse` - JSON-RPC success response
- `JSONRPCError` - JSON-RPC error response
- `ErrorData` - Error details (code, message, data)
- `JSONRPCMessage` - Union type for all JSON-RPC message types
- `jsonrpc_message_adapter` - TypeAdapter for validating incoming messages
- `RequestId` - Type alias: `str | int`
- `Transport` - Protocol for bidirectional message transport
- `Listener` - Protocol for server-side connection acceptance

**Characteristics:**
- Pure data models with Pydantic
- Handle JSON-RPC 2.0 specification compliance
- Support `model_dump(by_alias=True)` for camelCase JSON output
- `extra="forbid"` for strict validation
- Transport protocols enable testing with mock implementations

**Example:**
```python
from bub.rpc.types import JSONRPCRequest, Transport

# Create request
request = JSONRPCRequest(
    jsonrpc="2.0",
    method="initialize",
    params={"clientId": "client-1", "clientInfo": {"name": "my-app"}},
    id="req-123",
)

# Serialize to JSON
json_str = request.model_dump_json(by_alias=True)

# Transport protocol enables mocking
class InMemoryTransport(Transport):
    async def send_message(self, message: str) -> None:
        self._outgoing.put(message)
    
    async def receive_message(self) -> str:
        return await self._incoming.get()
```

## Layer 2: JSON-RPC Framework Layer

**Location:** `src/bub/rpc/framework.py`

**Purpose:** Generic, direction-agnostic, transport-agnostic JSON-RPC 2.0 framework

### Transport Interface

The framework uses the `Transport` protocol from Layer 1:

```python
class Transport(Protocol):
    """Bidirectional JSON message transport."""

    async def send_message(self, message: str) -> None:
        """Send a JSON message."""
        ...

    async def receive_message(self) -> str:
        """Receive a JSON message. Blocks until message available."""
        ...
```

**Transport implementations:**
- `WebSocketTransport` - Wraps a WebSocket connection (in `bub/bus/bus.py`)
- `InMemoryTransport` - For testing (queue-based, in `tests/`)
- Any other bidirectional message transport implementing the `Transport` protocol

### JSONRPCFramework

The main framework class:

```python
class JSONRPCFramework:
    """Direction-agnostic JSON-RPC 2.0 framework."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport
        self._pending_requests: dict[RequestId, asyncio.Future[dict[str, Any]]] = {}
        self._method_handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any] | None]] = {}
        self._notification_handlers: list[Callable[[str, dict[str, Any]], None]] = []
        self._running = False

    async def send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send JSON-RPC request and await response."""

    async def send_notification(self, method: str, params: dict[str, Any]) -> None:
        """Send JSON-RPC notification (fire-and-forget)."""

    async def listen(self) -> None:
        """Start listening for incoming messages."""

    def register_method(self, name: str, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        """Register handler for incoming JSON-RPC requests."""

    def on_notification(self, method: str, handler: Callable[[dict[str, Any]], None]) -> None:
        """Register handler for incoming JSON-RPC notifications."""
```

### Direction-Agnostic Design

The same `JSONRPCFramework` instance can act as caller, responder, or both simultaneously.

## Layer 3: Agent Bus Protocol Layer

**Location:** `src/bub/bus/protocol.py`

**Purpose:** Agent Bus specific protocol types and typed API

### Protocol Types (Pydantic Models)

All extend `ProtocolModel` with automatic snake_case → camelCase conversion:

```python
class ProtocolModel(BaseModel):
    """Base model for Agent Bus protocol types."""
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
    )
```

**Core Protocol Types:**
- `ClientInfo` / `ServerInfo` - Metadata
- `InitializeParams` / `InitializeResult` - Connection initialization
- `SubscribeParams` / `SubscribeResult` - Topic subscription
- `UnsubscribeParams` / `UnsubscribeResult` - Topic unsubscription
- `SendMessageParams` / `SendMessageResult` - Message sending with delivery acks
- `ProcessMessageParams` / `ProcessMessageResult` - Message processing with retry support
- `PingParams` / `PingResult` - Health checks

### Callback Protocols

The protocol layer defines callback interfaces:

```python
class AgentBusServerCallbacks(Protocol):
    """Callbacks for server request handlers."""
    async def handle_initialize(self, params: InitializeParams) -> InitializeResult: ...
    async def handle_subscribe(self, params: SubscribeParams) -> SubscribeResult: ...
    async def send_message(self, params: SendMessageParams) -> SendMessageResult: ...

class AgentBusClientCallbacks(Protocol):
    """Callbacks for client to handle server requests."""
    async def process_message(self, params: ProcessMessageParams) -> ProcessMessageResult: ...
```

### Typed API Classes

Convenient typed APIs that wrap the framework:

```python
class AgentBusServerApi:
    """Server API for bus->peer requests."""
    
    async def process_message(self, params: ProcessMessageParams) -> ProcessMessageResult:
        """Send processMessage request from bus to a peer."""

class AgentBusClientApi:
    """Client API for peer->bus requests."""
    
    def __init__(self, framework: JSONRPCFramework, client_id: str | None = None) -> None:
        # Auto-generates message IDs with atomic counter
        
    async def send_message2(self, from_: str, to: str, payload: dict) -> SendMessageResult:
        """Send message with auto-generated message ID."""
        
    async def initialize(self, params: InitializeParams) -> InitializeResult: ...
    async def subscribe(self, params: SubscribeParams) -> SubscribeResult: ...
    async def send_message(self, params: SendMessageParams) -> SendMessageResult: ...
```

## Integration with WebSocket

**Location:** `src/bub/bus/bus.py`

**Purpose:** WebSocket implementation using JSON-RPC framework

### Transport Implementation

```python
class WebSocketTransport:
    """WebSocket transport adapter for JSON-RPC framework."""
    
    def __init__(self, ws: ServerConnection | ClientConnection) -> None:
        self._ws = ws

    async def send_message(self, message: str) -> None:
        await self._ws.send(message)

    async def receive_message(self) -> str:
        data = await self._ws.recv()
        # Handle bytes/memoryview conversion
        return data
```

### Listener Implementation

```python
class WebSocketListener:
    """WebSocket-based implementation of the Listener protocol."""
    
    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port

    @property
    def url(self) -> str:
        return f"ws://{self._host}:{self._port}"

    async def start(self, handler: Callable[[Transport], Awaitable[None]]) -> None:
        """Start WebSocket server and forward connections to handler."""
        # Creates WebSocketTransport for each connection
        
    async def stop(self) -> None:
        """Stop the WebSocket server."""
```

### Server

```python
class AgentBusServer:
    """WebSocket server that manages multiple agent connections."""
    
    def __init__(
        self,
        server: tuple[str, int] | Listener,  # Can accept tuple or mock Listener
        activity_log_path: Path | None = None,
    ) -> None:
        # If tuple provided, creates WebSocketListener internally
        # If Listener provided, uses it directly (enables testing)
```

### Client

```python
class AgentBusClient:
    """WebSocket client for peers to connect to the bus."""
    
    def __init__(self, url: str, *, auto_reconnect: bool = True) -> None:
        self._url = url
        # Creates WebSocketTransport internally
```

## Testing with Mock Listener

The `Listener` protocol enables testing without actual WebSocket:

```python
from bub.rpc.types import Listener, Transport

class MockListener:
    """Mock listener for testing."""
    
    async def start(self, handler: Callable[[Transport], Awaitable[None]]) -> None:
        # Create mock transport and call handler
        transport = MockTransport()
        await handler(transport)
        
    async def stop(self) -> None:
        pass
        
    @property
    def url(self) -> str:
        return "mock://test"

# Use in tests
server = AgentBusServer(server=MockListener())
```

## Message Flow

### SendMessage / ProcessMessage Flow

```
Client (tg:123)              Bus Server                 Agent (agent:abc)
      |                          |                              |
      | sendMessage              |                              |
      |------------------------->|                              |
      |                          | _dispatch_process_message()  |
      |                          | processMessage               |
      |                          |----------------------------->|
      |                          |                              | handle message
      |                          | result                       |
      |                          |<-----------------------------|
      | acks                     |                              |
      |<-------------------------|                              |
```

### Key Differences from Generic JSON-RPC

1. **Dual method names**: `sendMessage` (client→bus) vs `processMessage` (bus→client)
2. **Message IDs**: Auto-generated by `AgentBusClientApi` with atomic counter
3. **Delivery acks**: `SendMessageResult` includes acks from all recipients
4. **Retry support**: `ProcessMessageResult` includes `should_retry` and `retry_seconds`

## Design Principles

1. **Separation of Concerns** - Each layer has a single, clear responsibility
2. **Reusability** - Lower layers can be used independently
3. **Type Safety** - Pydantic models ensure type safety throughout
4. **Protocol Compliance** - Strict adherence to JSON-RPC 2.0 specification
5. **Direction-Agnostic** - Framework doesn't care if it's server or client
6. **Transport-Agnostic** - Framework works with any bidirectional JSON transport
7. **Testability** - `Listener` and `Transport` protocols enable mocking

## File Structure

```
src/bub/
├── rpc/                           # JSON-RPC Framework (Layers 1, 2)
│   ├── __init__.py                # Public API exports
│   ├── types.py                   # Layer 1: Generic JSON-RPC types + Transport/Listener protocols
│   └── framework.py               # Layer 2: Generic JSON-RPC framework
├── bus/                           # Agent Bus (Layer 3 + WebSocket)
│   ├── protocol.py                # Layer 3: Agent Bus specific protocol
│   ├── bus.py                     # WebSocket server/client implementation
│   ├── types.py                   # Bus-specific types (Address, MessageHandler, etc.)
│   └── log.py                     # Activity logging
└── docs/
    ├── jsonrpc-framework.md       # This document
    └── agent-protocol.md          # Agent Bus protocol specification
```

## References

- JSON-RPC 2.0 Specification: https://www.jsonrpc.org/specification
