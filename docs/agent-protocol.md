# Agent Communication Protocol (Extended v2)

This document defines the authoritative JSON-RPC protocol for Bub peers communicating over WebSocket.

This is the only supported protocol. Backward compatibility with earlier protocol variants is out of scope.

## 1. Scope and Principles

- Transport is JSON-RPC 2.0 over WebSocket.
- All participants are peers connected to the same bus.
- Bus-to-peer delivery uses `processMessage` only.
- Peer-to-bus publish uses `sendMessage` only.
- No protocol version negotiation.
- No compatibility fallback.
- Delivery is in-memory at runtime.
- Bus writes persistent append-only activity logs to SQLite for audit/debug.

## 2. Roles

- `bus`: Message router and delivery coordinator.
- `tg:{chat_id}` peer: Telegram bridge peer per chat identity, tracks chat state, agent assignment, and retry queue.
- `agent:system`: System agent that spawns/assigns conversation agents.
- `agent:{id}` peer: Conversation agent assigned to one or more topics.

## 3. Transport

- WebSocket URL: `ws://host:port` or `wss://host:port`.
- Encoding: UTF-8 JSON.
- JSON-RPC envelope must be valid per spec.

## 4. Connection Lifecycle

### 4.1 Initialize Required

First request after connect must be `initialize`.

Client request:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "clientId": "agent:system",
    "clientInfo": {
      "name": "bub",
      "version": "0.2.0"
    }
  }
}
```

Server response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "serverId": "bus-abc",
    "serverInfo": {
      "name": "bub-bus",
      "version": "0.2.0"
    },
    "capabilities": {
      "subscribe": true,
      "publish": true,
      "processMessage": true,
      "topics": ["tg:*", "agent:*", "system:*"]
    }
  }
}
```

## 5. Methods

## 5.1 subscribe

Subscribe connection to a topic pattern.

Request:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "subscribe",
  "params": {
    "topic": "tg:*"
  }
}
```

Response:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "success": true
  }
}
```

Rules:
- Subscriptions are a set of exact pattern strings.
- Subscriptions are connection-scoped.
- No subscription ID.

## 5.2 unsubscribe

Unsubscribe by exact topic pattern string.

Request:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "unsubscribe",
  "params": {
    "topic": "tg:*"
  }
}
```

Response:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "success": true
  }
}
```

Rules:
- Removes the exact topic pattern from the connection subscription set.

## 5.3 sendMessage (peer -> bus)

Peer publishes a message to a topic.

Request:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "sendMessage",
  "params": {
    "topic": "tg:123456789",
    "payload": {
      "messageId": "msg_01J...",
      "type": "tg_message",
      "from": "tg:123456789",
      "timestamp": "2026-02-17T12:00:00Z",
      "content": {
        "text": "hello"
      }
    }
  }
}
```

Response:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "accepted": true,
    "messageId": "msg_01J...",
    "deliveredTo": 1
  }
}
```

Notes:
- `sendMessage` confirms bus acceptance and current delivery count.
- `stopPropagation` is not part of v2.
- Delivery policy object may be added later.

## 5.4 processMessage (bus -> peer)

Bus delivers message to subscribed peer.

Request:

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "processMessage",
  "params": {
    "topic": "agent:worker-42",
    "payload": {
      "messageId": "msg_01J...",
      "type": "configure",
      "from": "tg:123456789",
      "timestamp": "2026-02-17T12:00:02Z",
      "content": {
        "talkto": "tg:123456789"
      }
    }
  }
}
```

Response:

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "processed": true,
    "status": "ok",
    "message": "configured"
  }
}
```

Rules:
- Bus waits for each target peer `processMessage` response.
- If peer is offline/unavailable, bus marks failure in activity log.
- Retry policy is peer-managed for now (for example tg peer retry queue).

## 5.5 ping

Liveness check.

## 6. Topic Conventions

- `tg:{chat_id}`: Telegram chat topic.
- `agent:{agent_id}`: Direct agent topic.
- `system:spawn`: Spawn requests for system agent.
- `system:route`: Routing/assignment control events.

## 7. Message Envelope

Every `payload` must contain:

- `messageId` (string, required): globally unique message ID.
- `type` (string, required): message type discriminator.
- `from` (string, required): sender identity topic/client.
- `timestamp` (RFC3339 string, required).
- `content` (object, required): type-specific body.

Routing rule:
- `params.topic` is the only decisive destination field.
- `payload` does not carry authoritative routing fields.

## 8. Canonical Message Types

- `spawn_request`: ask system agent to spawn conversation agent.
- `spawn_result`: system agent confirms spawned/failed.
- `route_assigned`: binds `tg:{chat_id}` to `agent:{id}`.
- `configure`: configure agent session, especially `talkto` topic.
- `tg_message`: user message forwarded from Telegram peer.
- `tg_reply`: agent reply to Telegram peer.
- `delivery_status`: accepted/delivered/failed status updates.
- `agent_event`: lifecycle/control events.

## 9. Role/Type Authorization Matrix

| Sender Role | Allowed Types Sent | Expected Receives |
|---|---|---|
| `tg:{chat_id}` peer | `spawn_request`, `configure`, `tg_message`, `delivery_status` | `spawn_result`, `route_assigned`, `tg_reply`, `delivery_status` |
| `agent:system` | `spawn_result`, `route_assigned`, `agent_event` | `spawn_request`, `agent_event` |
| `agent:{id}` | `tg_reply`, `agent_event`, `delivery_status` | `configure`, `tg_message`, `agent_event` |

Bus should reject invalid sender/type combinations with `-32602` (invalid params).

## 10. TG Empty-Channel Bootstrap Flow

When `tg:{chat_id}` has no assigned agent:

1. TG peer sends `spawn_request` to `system:spawn`.
2. Bus routes to `agent:system` via `processMessage`.
3. `agent:system` uses system tool (`systemd`) to spawn `agent:{id}`.
4. `agent:system` sends `route_assigned` to `tg:{chat_id}` with assigned `agent:{id}`.
5. TG peer sends `configure` to `agent:{id}` with `content.talkto = "tg:{chat_id}"`.
6. TG peer forwards user text as `tg_message` to assigned `agent:{id}`.
7. Agent responds with `tg_reply` to `tg:{chat_id}`.

This makes TG peer stateful and self-healing across temporary peer outages/restarts.

## 11. Delivery and Retry Ownership

- Bus: in-memory delivery only.
- TG peer: durable mapping `chat_id -> assigned agent`, message history, retry queue.
- Agent peer: may keep local resend/outbox for critical responses.

If target peer is offline, sender-side peer retries after reconnect based on its queue policy.

## 12. Activity Logging (SQLite, Append-Only)

Bus writes protocol activity records asynchronously to SQLite.

Required events per message:
- `send_start`
- `process_start`
- `process_finish`
- `send_finish`

Recommended schema:

```sql
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
);

CREATE INDEX IF NOT EXISTS idx_activity_message_id ON activity_log(message_id);
CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity_log(ts);
```

Notes:
- Append-only; no updates/deletes in normal operation.
- Logging path is async queue -> single writer task.
- Log is for observability/audit, not durable replay source.

## 13. Error Codes

- `-32001`: Not initialized.
- `-32003`: Subscription not found for unsubscribe pattern.
- `-32600`: Invalid request.
- `-32601`: Method not found.
- `-32602`: Invalid params or unauthorized type for sender role.
- `-32603`: Internal error.

## 14. Non-Goals

- Backward compatibility with pre-v2 bus behavior.
- Negotiated protocol capabilities.
- Persistent delivery queue inside bus process.
- stopPropagation semantics in v2 baseline.
