# Agent Message Types (Application Level)

This document defines the message types used in the `payload` field of the Agent Communication Protocol. These are **application-level concerns** - the protocol simply delivers payloads as opaque objects.

For the protocol specification, see `agent-protocol.md`.

## Table of Contents

- [Message Structure](#message-structure)
- [Message Types](#message-types)
  - [`spawn_request`](#spawn_request)
  - [`spawn_result`](#spawn_result)
  - [`route_assigned`](#route_assigned)
  - [`configure`](#configure)
  - [`tg_message`](#tg_message)
  - [`tg_reply`](#tg_reply)
  - [`agent_event`](#agent_event)
- [Content Field Reference](#content-field-reference)
- [Addressing Notes](#addressing-notes)
- [Version](#version)

## Message Structure

Every payload must include:

- `type` (string, required): Message type discriminator.
- `content` (object, required): Type-specific body.

Optional fields commonly used:
- `from` (string): Source address (may differ from protocol-level `params.from` in some cases).
- `timestamp` (RFC3339 string): When the message was created.
- `messageId` (string): Application-level message ID for Bub's internal tracking.

## Message Types

### `spawn_request`

Request to spawn a new conversation agent.

```json
{
  "type": "spawn_request",
  "from": "tg:123456789",
  "timestamp": "2026-02-17T12:00:00Z",
  "content": {
    "chat_id": "123456789",
    "channel": "telegram"
  }
}
```

### `spawn_result`

Response indicating spawn success/failure.

```json
{
  "type": "spawn_result",
  "from": "agent:system",
  "timestamp": "2026-02-17T12:00:01Z",
  "content": {
    "success": true,
    "client_id": "agent:worker-abc123",
    "status": "running"
  }
}
```

### `route_assigned`

Notification that a route has been assigned.

```json
{
  "type": "route_assigned",
  "from": "agent:system",
  "timestamp": "2026-02-17T12:00:01Z",
  "content": {
    "chat_id": "123456789",
    "agent_id": "agent:worker-abc123"
  }
}
```

### `configure`

Configure an agent's session parameters.

```json
{
  "type": "configure",
  "from": "tg:123456789",
  "timestamp": "2026-02-17T12:00:02Z",
  "content": {
    "talkto": "tg:123456789"
  }
}
```

### `tg_message`

User message from Telegram.

```json
{
  "type": "tg_message",
  "from": "tg:123456789",
  "timestamp": "2026-02-17T12:00:03Z",
  "content": {
    "text": "Hello, how are you?",
    "senderId": "123456789",
    "channel": "telegram"
  }
}
```

**Telegram-Specific Fields:**
- `message_id` (string): Original Telegram message ID from Telegram Bot API (stored in metadata). Used for reply threading.
- `senderId` (string): Telegram user ID of the sender.
- `channel` (string): Always "telegram" for Telegram messages.
- `username` (string, optional): Telegram username.
- `full_name` (string, optional): Full name of the sender.

### `tg_reply`

Agent reply to be sent to Telegram.

```json
{
  "type": "tg_reply",
  "from": "agent:worker-abc123",
  "timestamp": "2026-02-17T12:00:04Z",
  "content": {
    "text": "I'm doing well, thank you!"
  }
}
```

### `agent_event`

Agent lifecycle or control event.

```json
{
  "type": "agent_event",
  "from": "agent:system",
  "timestamp": "2026-02-17T12:00:06Z",
  "content": {
    "event": "spawned",
    "agent_id": "agent:worker-abc123"
  }
}
```

## Content Field Reference

### Common Content Fields

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Text message content |
| `chat_id` | string | Telegram chat identifier |
| `channel` | string | Channel name (e.g., "telegram") |
| `client_id` | string | Agent identifier |
| `agent_id` | string | Agent identifier |
| `talkto` | string | Default destination for responses |
| `success` | boolean | Operation success indicator |
| `status` | string | Status string (running, stopped, spawning, etc.) |
| `event` | string | Event type identifier |
| `message_id` | string | Original Telegram message ID (for reply threading) |

## Addressing Notes

### Protocol vs Application From

- **Protocol-level** (`params.from`): Used by the bus for routing and tracking. Always present in `processMessage`.
- **Application-level** (`payload.from`): Used by agents for content-level addressing. Optional, may mirror protocol-level or provide additional context.

In most cases, these will be the same, but the distinction allows for:
- Forwarded messages (protocol-from is forwarder, payload-from is original sender)
- System-generated messages (protocol-from is bus/system, payload-from indicates logical source)

## Version

This document describes message types as of protocol v2.
