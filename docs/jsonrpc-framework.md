# JSON-RPC Framework Architecture

This document describes the 3-tier JSON-RPC 2.0 framework architecture in the bub project.

## Executive Summary

The JSON-RPC framework is organized into three distinct layers:

1. **Message/Serialization Layer** - Pydantic models for JSON encoding/decoding
2. **JSON-RPC Framework Layer** - Direction-agnostic, transport-agnostic JSON-RPC implementation
3. **Agent Protocol API Layer** - Agent Bus specific protocol methods

### Key Design Principle: Framework is Direction-Agnostic

The JSON-RPC framework (`bub/rpc/protocol.py`) is **direction-agnostic** and **transport-agnostic**. It:

- Takes a **bidirectional JSON message transport** as input
- Does not care whether it's "server" or "client" side
- Supports both sending requests/notifications AND receiving/handling them
- The same framework instance can:
  - Send requests and receive responses
  - Receive requests and send responses
  - Send and receive notifications

Server/client roles exist in TWO places only:
1. **WebSocket transport layer** (`bub/channels/wsbus.py`) - `AgentBusServer` and `AgentBusClient` classes
2. **Protocol usage level** - One side acts as responder (registering method handlers), the other acts as caller (making requests)

But at the **JSON-RPC framework level**, there's no server/client distinction.

## Layer 1: Message/Serialization Layer

**Location:** `src/bub/rpc/types.py`

**Purpose:** Generic JSON-RPC 2.0 data models for serialization/deserialization

**Components:**
- `JSONRPCRequest` - JSON-RPC request with method, params, id
- `JSONRPCNotification` - JSON-RPC notification (fire-and-forget, no id)
- `JSONRPCResponse` - JSON-RPC success response
- `JSONRPCError` - JSON-RPC error response
- `ErrorData` - Error details (code, message, data)
- `JSONRPCMessage` - Union type for all JSON-RPC message types
- `jsonrpc_message_adapter` - TypeAdapter for validating incoming messages
- `RequestId` - Type alias: `str | int`

**Characteristics:**
- Pure data models with Pydantic
- Handle JSON-RPC 2.0 specification compliance
- Support `model_dump(by_alias=True)` for camelCase JSON output
- `extra="forbid"` for strict validation
- No logic, just data structures

**Example:**
```python
from bub.rpc.types import JSONRPCRequest, JSONRPCNotification

# Create request
request = JSONRPCRequest(
    jsonrpc="2.0",
    method="initialize",
    params={"clientId": "client-1", "clientInfo": {"name": "my-app"}},
    id="req-123",
)

# Serialize to JSON
json_str = request.model_dump_json(by_alias=True)
# Output: {"jsonrpc":"2.0","method":"initialize","params":{"clientId":"client-1","clientInfo":{"name":"my-app"}},"id":"req-123"}

# Deserialize from JSON
request = JSONRPCRequest.model_validate_json(json_str)
```

## Layer 2: JSON-RPC Framework Layer

**Location:** `src/bub/rpc/protocol.py`

**Purpose:** Generic, direction-agnostic, transport-agnostic JSON-RPC 2.0 framework

### Transport Interface

The framework takes a bidirectional JSON message transport:

```python
class JSONRPCTransport(Protocol):
    """Bidirectional JSON message transport."""

    async def send_message(self, message: str) -> None:
        """Send a JSON message."""
        ...

    async def receive_message(self) -> str:
        """Receive a JSON message. Blocks until message available."""
        ...
```

**Transport implementations:**
- `WebSocketTransport` - Wraps a WebSocket connection
- `InMemoryTransport` - For testing (queue-based)
- `HTTPTransport` - For HTTP-based JSON-RPC (future)
- Any other bidirectional message transport

### JSONRPCFramework

The main framework class:

```python
class JSONRPCFramework:
    """Direction-agnostic JSON-RPC 2.0 framework."""

    def __init__(self, transport: JSONRPCTransport) -> None:
        self._transport = transport
        self._pending_requests: dict[RequestId, asyncio.Future[dict[str, Any]]] = {}
        self._method_handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any] | None]] = {}
        self._notification_handlers: list[Callable[[str, dict[str, Any]], None]] = []
        self._running = False

    # ========== Sending (Caller side) ==========

    async def send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send JSON-RPC request and await response.

        Creates a request with unique ID, sends it, waits for response.
        """

    async def send_notification(self, method: str, params: dict[str, Any]) -> None:
        """Send JSON-RPC notification (fire-and-forget).

        Creates a notification (no ID), sends it. No response expected.
        """

    async def _send_message(self, message: JSONRPCMessage) -> None:
        """Send a JSON-RPC message via transport.

        Uses Layer 1 types, serializes to JSON.
        """

    # ========== Receiving (Responder side) ==========

    async def listen(self) -> None:
        """Start listening for incoming messages.

        Loops calling transport.receive_message(), dispatches to handlers.
        """

    async def _process_message(self, raw_message: str) -> None:
        """Process incoming JSON message.

        1. Deserialize using jsonrpc_message_adapter
        2. If request: call method handler, send response
        3. If notification: call notification handlers
        4. If response: match to pending request, complete future
        5. If error: match to pending request, complete future with exception
        """

    # ========== Method Registration (Responder side) ==========

    def register_method(self, name: str, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        """Register handler for incoming JSON-RPC requests.

        Handler takes params dict, returns result dict.
        """

    # ========== Notification Handling (Both sides) ==========

    def on_notification(self, method: str, handler: Callable[[dict[str, Any]], None]) -> None:
        """Register handler for incoming JSON-RPC notifications.

        Can register multiple handlers per method.
        """
```

### Direction-Agnostic Design

The same `JSONRPCFramework` instance can:

**Act as caller:**
```python
framework = JSONRPCFramework(transport)

# Send request and await response
result = await framework.send_request("initialize", {"clientId": "client-1"})

# Send notification (fire-and-forget)
await framework.send_notification("notify", {"topic": "test", "payload": {}})
```

**Act as responder:**
```python
framework = JSONRPCFramework(transport)

# Register method handler (responds to incoming requests)
async def handle_initialize(params: dict[str, Any]) -> dict[str, Any]:
    return {"serverId": "bus-123", "serverInfo": {"name": "bub-bus"}}

framework.register_method("initialize", handle_initialize)

# Register notification handler
def on_notify(params: dict[str, Any]) -> None:
    print(f"Received notify: {params}")

framework.on_notification("notify", on_notify)

# Start listening for incoming messages
await framework.listen()
```

**Act as both simultaneously:**
```python
framework = JSONRPCFramework(transport)

# Register method handlers (respond to incoming requests)
framework.register_method("ping", lambda params: {"timestamp": datetime.now().isoformat()})

# Listen for incoming messages
listen_task = asyncio.create_task(framework.listen())

# Send requests to other side
result = await framework.send_request("initialize", {"clientId": "client-1"})
```

### Request/Response Correlation

The framework handles matching responses to requests:

1. When `send_request()` is called:
   - Generates unique request ID
   - Creates `asyncio.Future` for the response
   - Stores `request_id -> future` in `_pending_requests`
   - Sends request via transport

2. When response is received in `_process_message()`:
   - Looks up `request_id` in `_pending_requests`
   - If found and response has `result`: completes future with result
   - If found and response has `error`: completes future with exception
   - Removes from `_pending_requests`

### Notification Handling

Notifications are fire-and-forget (no ID, no response):

1. When `send_notification()` is called:
   - Creates notification without ID
   - Sends via transport
   - Returns immediately (no waiting)

2. When notification is received in `_process_message()`:
   - Calls all registered handlers for that method
   - No response sent

## Layer 3: Agent Protocol API Layer

**Location:** `src/bub/rpc/agent_protocol.py`

**Purpose:** Agent Bus specific protocol types and API methods

### Protocol Types (Pydantic Models)

All extend `ProtocolModel` with automatic snake_case → camelCase conversion:

```python
class ProtocolModel(BaseModel):
    """Base model for Agent Bus protocol types.

    Uses alias_generator to convert snake_case to camelCase.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda s: "".join(word.capitalize() for word in s.split("_")),
        extra="forbid",
    )
```

**Protocol Types:**
- `ClientInfo` - Client metadata
- `ServerInfo` - Server metadata
- `ServerCapabilities` - Server capabilities
- `InitializeParams` - Initialize request parameters
- `InitializeResult` - Initialize response
- `SubscribeParams` - Subscribe request parameters
- `SubscribeResult` - Subscribe response
- `UnsubscribeParams` - Unsubscribe request parameters
- `UnsubscribeResult` - Unsubscribe response
- `NotifyParams` - Notify request parameters
- `PingParams` - Ping request (empty)
- `PingResult` - Ping response with timestamp

**Example:**
```python
# Create params
params = InitializeParams(
    client_id="client-1",
    client_info=ClientInfo(name="my-app", version="1.0.0")
)

# Serialize to JSON (automatic camelCase)
json_dict = params.model_dump(by_alias=True)
# Output: {"clientId": "client-1", "clientInfo": {"name": "my-app", "version": "1.0.0"}}

# Deserialize from JSON
params = InitializeParams.model_validate(json_dict)
```

### AgentProtocol API

Convenient methods that use Layer 2 framework and Layer 3 types:

```python
class AgentProtocol:
    """Agent Bus protocol API.

    Provides typed methods for Agent Bus operations.
    """

    def __init__(self, framework: JSONRPCFramework) -> None:
        self._framework = framework

    # ========== Server-side handlers ==========

    async def initialize(self, params: InitializeParams) -> InitializeResult:
        """Handle initialize request.

        Server-side: called when client initializes.
        Returns server info and capabilities.
        """

    async def subscribe(self, params: SubscribeParams) -> SubscribeResult:
        """Handle subscribe request.

        Server-side: called when client subscribes to topic.
        Returns subscription ID.
        """

    async def unsubscribe(self, params: UnsubscribeParams) -> UnsubscribeResult:
        """Handle unsubscribe request.

        Server-side: called when client unsubscribes.
        """

    async def notify(self, params: NotifyParams) -> None:
        """Handle notify request.

        Server-side: called when client publishes a message.
        Broadcasts to all subscribers.
        """

    async def ping(self, params: PingParams) -> PingResult:
        """Handle ping request.

        Server-side: returns timestamp.
        """

    # ========== Client-side API ==========

    async def client_initialize(self, client_id: str, client_info: ClientInfo) -> InitializeResult:
        """Initialize connection (client-side).

        Sends initialize request to server.
        """

    async def client_subscribe(self, topic: str) -> SubscribeResult:
        """Subscribe to topic (client-side).

        Sends subscribe request to server.
        """

    async def client_unsubscribe(self, subscription_id: str) -> UnsubscribeResult:
        """Unsubscribe from topic (client-side).

        Sends unsubscribe request to server.
        """

    async def client_notify(self, topic: str, payload: dict[str, Any]) -> None:
        """Send notification (client-side).

        Sends notify notification to server.
        """

    async def client_ping(self) -> PingResult:
        """Ping server (client-side).

        Sends ping request to server.
        """
```

## Integration with WebSocket

**Location:** `src/bub/channels/wsbus.py`

**Purpose:** WebSocket implementation using JSON-RPC framework

### Components

```python
# WebSocket transport for JSON-RPC framework
class WebSocketTransport:
    def __init__(self, ws: websockets.WebSocketClientProtocol | websockets.ServerConnection):
        self._ws = ws

    async def send_message(self, message: str) -> None:
        await self._ws.send(message)

    async def receive_message(self) -> str:
        return await self._ws.recv()

# Server-side (AgentBusServer)
class AgentBusServer:
    def __init__(self, host: str, port: int):
        self._connections: dict[str, dict] = {}  # conn_id -> conn_data
        self._server: WebSocketServer | None = None

        # Each connection gets its own framework + protocol
        self._frameworks: dict[str, JSONRPCFramework] = {}
        self._agent_protocols: dict[str, AgentProtocol] = {}

    async def _handle_connection(self, ws, path):
        """Handle new WebSocket connection."""
        transport = WebSocketTransport(ws)
        framework = JSONRPCFramework(transport)
        agent_protocol = AgentProtocol(framework)

        # Register server-side method handlers
        agent_protocol.initialize = lambda p: self._on_initialize(conn, p)
        agent_protocol.subscribe = lambda p: self._on_subscribe(conn, p)
        # ...

        # Start listening
        await framework.listen()

# Client-side (AgentBusClient)
class AgentBusClient:
    def __init__(self, url: str):
        self._url = url
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._framework: JSONRPCFramework | None = None
        self._agent_protocol: AgentProtocol | None = None

    async def connect(self):
        """Connect to server."""
        self._ws = await websockets.connect(self._url)
        transport = WebSocketTransport(self._ws)
        self._framework = JSONRPCFramework(transport)
        self._agent_protocol = AgentProtocol(self._framework)

        # Start listening
        asyncio.create_task(self._framework.listen())

    async def initialize(self, client_id: str, client_info: ClientInfo) -> InitializeResult:
        """Initialize connection."""
        return await self._agent_protocol.client_initialize(client_id, client_info)
```

### Where Server/Client Roles Exist

**1. WebSocket transport layer:**
- `AgentBusServer` - Accepts WebSocket connections
- `AgentBusClient` - Connects to WebSocket server

**2. Protocol usage level:**
- Server side: Registers method handlers (initialize, subscribe, etc.)
- Client side: Makes requests (client_initialize, client_subscribe, etc.)

**3. Framework level:**
- NO server/client distinction
- Same `JSONRPCFramework` class used on both sides
- Same `AgentProtocol` class used on both sides
- Direction determined by usage (registering handlers vs making requests)

## Message Flow Examples

### Initialize Handshake

```
Client (Caller)                          Server (Responder)
     |                                        |
     | send_request("initialize", ...)          |
     |--------------------------------------->|
     |                                        | _process_message()
     |                                        | dispatch to "initialize" handler
     |                                        | handler returns result
     |                                        | send_response(result)
     |<---------------------------------------|
await send_request() returns                 |
     |                                        |
```

### Subscribe

```
Client (Caller)                          Server (Responder)
     |                                        |
     | send_request("subscribe", ...)           |
     |--------------------------------------->|
     |                                        | _process_message()
     |                                        | dispatch to "subscribe" handler
     |                                        | handler stores subscription
     |                                        | send_response(result)
     |<---------------------------------------|
await send_request() returns                 |
     |                                        |
```

### Notify (Fire-and-Forget)

```
Client (Caller)                          Server (Responder)
     |                                        |
     | send_notification("notify", ...)         |
     |--------------------------------------->|
     |                                        | _process_message()
     |                                        | dispatch to "notify" handler
     |                                        | handler broadcasts to subscribers
     | returns immediately                     |
     |                                        |
```

### Server Broadcasting to Subscribers

```
Publisher (Client)                        Server                          Subscriber (Client)
     |                                          |                                    |
     | send_notification("notify", ...)             |                                    |
     |---------------------------------------->|                                    |
     |                                          | _process_message()                    |
     |                                          | dispatch to "notify" handler         |
     |                                          | handler finds matching subscribers     |
     |                                          |                                    |
     |                                          | send_notification("notify", ...)     |
     |                                          |------------------------------------>|
     |                                          |                                    | _process_message()
     |                                          |                                    | dispatch to notification handlers
     |                                          |                                    | handler processes message
     |                                          |                                    |
```

## Design Principles

1. **Separation of Concerns** - Each layer has a single, clear responsibility
2. **Reusability** - Lower layers can be used independently
3. **Type Safety** - Pydantic models ensure type safety throughout
4. **Protocol Compliance** - Strict adherence to JSON-RPC 2.0 specification
5. **Direction-Agnostic** - Framework doesn't care if it's server or client
6. **Transport-Agnostic** - Framework works with any bidirectional JSON transport
7. **Extensibility** - Easy to add new protocols without changing framework

## File Structure

```
src/bub/
├── rpc/                           # JSON-RPC Framework (Layers 1, 2, 3)
│   ├── __init__.py                # Public API exports
│   ├── types.py                   # Layer 1: Generic JSON-RPC types
│   ├── protocol.py                # Layer 2: Generic JSON-RPC framework
│   └── agent_protocol.py         # Layer 3: Agent Bus specific protocol
├── channels/                      # WebSocket Implementation
│   ├── wsbus.py                  # WebSocket server/client using JSON-RPC
│   ├── events.py                  # Agent Bus message types
│   └── ...
└── docs/
    ├── jsonrpc-framework.md        # This document
    └── agent-protocol.md          # Agent Bus protocol specification
```

## References

- JSON-RPC 2.0 Specification: https://www.jsonrpc.org/specification
- MCP SDK (Python): https://github.com/modelcontextprotocol/python-sdk
