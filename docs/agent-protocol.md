# Agent Communication Protocol

This document defines the JSON-RPC 2.0 protocol for agent-to-agent and agent-to-bus communication over WebSocket.

## Transport

- Protocol: JSON-RPC 2.0 over WebSocket
- Encoding: UTF-8 JSON
- WebSocket URL: `ws://host:port` or `wss://host:port` for TLS

## Design Philosophy

This protocol uses **request/response for message delivery** (instead of notifications) to support interceptor patterns. Subscribers can halt propagation, enabling middleware-like behaviors such as authentication, transformation, and logging.

### Message Flow

1. Publisher calls `sendMessage(topic, payload)` → Server
2. Server matches topic against all subscriber patterns
3. Server calls `sendMessage(topic, payload)` → each Subscriber (in order)
4. If any subscriber returns `stopPropagation: true`, remaining subscribers are skipped
5. Result is aggregated back to original publisher

### Built-in Topics

| Topic | Purpose | Direction |
|-------|---------|-----------|
| `inbound:{chat_id}` | External messages entering system | External → Bus |
| `outbound:{chat_id}` | Messages to be sent externally | Bus → External |
| `agent:*` | Agent lifecycle (spawn, complete, error) | Bidirectional |

### When to Use stopPropagation

Use `stopPropagation: true` when:

- **Authentication**: Message is unauthorized and should not reach other handlers
- **Transformation**: Message has been modified/deduplicated, original should not be processed
- **Rate Limiting**: Message quota exceeded for this subscriber
- **Completion**: This subscriber has fully handled the message, no further action needed

## Message Format

All messages follow JSON-RPC 2.0 specification:

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "method_name",
  "params": {...},
  "id": 1
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {...},
  "id": 1
}
```

**Error:**
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32600,
    "message": "Invalid Request",
    "data": "optional details"
  },
  "id": 1
}
```

**Notification (no id):**
```json
{
  "jsonrpc": "2.0",
  "method": "method_name",
  "params": {...}
}
```

## Connection Lifecycle

### 1. Initialize Handshake

Client connects to server and must send `initialize` as the first request.

**Client → Server:**
```json
{
  "jsonrpc": "2.0",
  "method": "initialize",
  "params": {
    "clientId": "agent-1",
    "clientInfo": {
      "name": "bub",
      "version": "0.2.0"
    }
  },
  "id": 1
}
```

**Server → Client:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "serverId": "bus-1",
    "serverInfo": {
      "name": "bub-bus",
      "version": "0.2.0"
    },
    "capabilities": {
      "subscribe": true,
      "publish": true,
      "topics": ["inbound:*", "outbound:*", "agent:*"]
    }
  },
  "id": 1
}
```

Error codes:
- `-32001`: Already initialized
- `-32002`: Invalid client info

## Core Methods

### subscribe

Subscribe to messages on a topic pattern.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "subscribe",
  "params": {
    "topic": "inbound:chat-*"
  },
  "id": 2
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true
  },
  "id": 2
}
```

Topic patterns:
- Exact match: `"inbound:chat-1"`
- Wildcard: `"inbound:*"` matches all `inbound:xxx`
- Prefix: `"inbound:chat-"` matches `inbound:chat-1`, `inbound:chat-2`

Error codes:
- `-32600`: Invalid params (missing topic)
- `-32003`: Already subscribed to this topic

### unsubscribe

Unsubscribe from a topic pattern. Pass the exact same topic string used in subscribe.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "unsubscribe",
  "params": {
    "topic": "inbound:chat-*"
  },
  "id": 3
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true
  },
  "id": 3
}
```

### sendMessage

Send a message to subscribers. Returns response with stopPropagation flag.

**Client → Server:**
```json
{
  "jsonrpc": "2.0",
  "method": "sendMessage",
  "params": {
    "topic": "inbound:chat-1",
    "payload": {
      "chat_id": "chat-1",
      "text": "hello",
      "from": "user-1"
    }
  },
  "id": 4
}
```

**Server → Client (broadcast to subscribers):**
```json
{
  "jsonrpc": "2.0",
  "method": "sendMessage",
  "params": {
    "topic": "inbound:chat-1",
    "payload": {
      "chat_id": "chat-1",
      "text": "hello",
      "from": "user-1"
    }
  },
  "id": 5
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "stopPropagation": false
  },
  "id": 5
}
```

The server broadcasts to all clients subscribed to matching topics. If any subscriber returns `stopPropagation: true`, propagation stops.

### ping

Keep-alive ping.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "ping",
  "params": {},
  "id": 100
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "timestamp": "2025-02-14T12:00:00Z"
  },
  "id": 100
}
```

## Built-in Topics

| Topic | Direction | Description |
|-------|-----------|-------------|
| `inbound:*` | Client→Server | Incoming messages (e.g., from Telegram) |
| `outbound:*` | Client→Server | Outgoing messages to be sent to external channels |
| `agent:*` | Bidirectional | Agent lifecycle events |

## Error Codes

| Code | Meaning |
|------|---------|
| `-32600` | Invalid Request |
| `-32601` | Method not found |
| `-32602` | Invalid params |
| `-32603` | Internal error |
| `-32001` | Already initialized |
| `-32002` | Invalid client info |
| `-32003` | Already subscribed |
| `-32004` | Subscription not found |

## Implementation Notes

1. `initialize` must be the first request after WebSocket connection
2. Server rejects non-initialize requests until handshake completes
3. Subscriptions are per-connection (not persistent)
4. `sendMessage` uses request/response pattern with `stopPropagation` flag for flow control
5. Topic matching uses prefix + wildcard semantics (fnmatch-style)
6. Unsubscribe uses the same topic string passed to subscribe (not a subscription ID)
