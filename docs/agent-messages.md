# Agent Message Types (Application Level)

This document defines the message types used in the `payload` field of the Agent Communication Protocol. These are **application-level concerns** - the protocol simply delivers payloads as opaque objects.

For the protocol specification, see `agent-protocol.md`.

## Table of Contents

- [Message Structure](#message-structure)
- [Active Message Types](#active-message-types)
  - [`spawn_request`](#spawn_request)
  - [`spawn_result`](#spawn_result)
  - [`tg_message`](#tg_message)
  - [`tg_reply`](#tg_reply)
- [Planned Message Types](#planned-message-types)
  - [`configure`](#configure)
  - [`route_assigned`](#route_assigned)
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

## Active Message Types

These message types are currently implemented and used in production code.

### `spawn_request`

**Direction**: telegram-bridge → system_agent  
**Purpose**: Request to spawn a new conversation agent.

```json
{
  "type": "spawn_request",
  "from": "telegram-bridge",
  "timestamp": "2026-02-17T12:00:00Z",
  "content": {
    "chat_id": "123456789",
    "channel": "telegram",
    "channel_type": "telegram"
  }
}
```

**Fields:**
- `chat_id` (string): Telegram chat identifier
- `channel` (string): Channel identifier for routing
- `channel_type` (string): Type of channel for replies (e.g., "telegram", "discord")

### `spawn_result`

**Direction**: system_agent → requester  
**Purpose**: Response indicating spawn success/failure.

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

### `tg_message`

**Direction**: telegram-bridge → agent  
**Purpose**: User message from Telegram (or Discord) to be processed by an agent.

```json
{
  "type": "tg_message",
  "from": "tg:123456789",
  "timestamp": "2026-02-17T12:00:03Z",
  "content": {
    "text": "Hello, how are you?",
    "senderId": "123456789",
    "channel": "telegram",
    "username": "johndoe",
    "full_name": "John Doe"
  }
}
```

**Fields:**
- `text` (string): Message content
- `senderId` (string): Telegram user ID of the sender
- `channel` (string): Channel name ("telegram" or "discord")
- `username` (string, optional): Telegram username
- `full_name` (string, optional): Full name of the sender

### `tg_reply`

**Direction**: agent → telegram-bridge  
**Purpose**: Agent reply to be sent back to Telegram.

```json
{
  "type": "tg_reply",
  "from": "agent:worker-abc123",
  "reply_to_message_id": "msg_abc123",
  "timestamp": "2026-02-17T12:00:04Z",
  "chat_id": "123456789",
  "content": {
    "text": "I'm doing well, thank you!",
    "channel": "telegram"
  }
}
```

**Fields:**
- `reply_to_message_id` (string): ID of the message being replied to (enables thread support in group chats)
- `chat_id` (string): Target chat ID
- `content.text` (string): Response text
- `content.channel` (string): Channel identifier for routing

### `general_response`

**Direction**: any → any  
**Purpose**: Generic response for protocol-level acknowledgments. Used when the actual response is sent separately or not needed.

```json
{
  "type": "general_response",
  "from": "agent:worker-abc123",
  "timestamp": "2026-02-17T12:00:04Z",
  "content": {
    "status": "ok",
    "message": "Processed successfully",
    "request_id": "msg_abc123"
  }
}
```

**Fields:**
- `status` (string): "ok" or "error"
- `message` (string, optional): Human-readable description
- `request_id` (string, optional): ID of the request being responded to
- `error_code` (string, optional): Machine-readable error code (only for error status)

**Note**: This is a lightweight acknowledgment type. For business logic responses (e.g., agent replies), use channel-specific types like `tg_reply`.

## Planned Message Types

These message types are defined in documentation but **not yet implemented**. They require further design before being added to the codebase.

### `configure`

> **Status**: Planned - needs design

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

### `route_assigned`

> **Status**: Planned - needs design

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

### `agent_event`

> **Status**: Planned - needs design

Agent lifecycle or control event.

```json
{
  "type": "agent_event",
  "from": "agent:system",
  "timestamp": "2026-02-17T12:00:06Z",
  "content": {
    "event": "spawned",
    "data": {
      "agent_id": "agent:worker-abc123"
    }
  }
}
```

## Content Field Reference

### Active Fields

| Field | Type | Used In | Description |
|-------|------|---------|-------------|
| `text` | string | tg_message, tg_reply | Message content |
| `chat_id` | string | spawn_request | Telegram chat identifier |
| `channel` | string | tg_message, tg_reply, spawn_request | Channel name for routing |
| `channel_type` | string | spawn_request | Reply channel type (telegram, discord, etc.) |
| `senderId` | string | tg_message | Telegram user ID |
| `username` | string | tg_message | Telegram username |
| `full_name` | string | tg_message | Full name of sender |
| `success` | boolean | spawn_result | Operation success indicator |
| `client_id` | string | spawn_result | Assigned agent identifier |
| `status` | string | spawn_result | Status (running, spawning, etc.) |

### Planned Fields

| Field | Type | Planned For | Description |
|-------|------|-------------|-------------|
| `talkto` | string | configure | Default destination for responses |
| `agent_id` | string | route_assigned, agent_event | Agent identifier |
| `event` | string | agent_event | Event type identifier |
| `data` | object | agent_event | Event-specific data |

## Addressing Notes

### Protocol vs Application From

- **Protocol-level** (`params.from`): Used by the bus for routing and tracking. Always present in `processMessage`.
- **Application-level** (`payload.from`): Used by agents for content-level addressing. Optional, may mirror protocol-level or provide additional context.

In most cases, these will be the same, but the distinction allows for:
- Forwarded messages (protocol-from is forwarder, payload-from is original sender)
- System-generated messages (protocol-from is bus/system, payload-from indicates logical source)

## Version

This document describes message types as of protocol v2.

**Active Types**: 4 (spawn_request, spawn_result, tg_message, tg_reply)  
**Planned Types**: 3 (configure, route_assigned, agent_event)**Direction**: agent → telegram-bridge  
**Purpose**: Agent reply to be sent back to Telegram.

```json
{
  "type": "tg_reply",
  "from": "agent:worker-abc123",
  "timestamp": "2026-02-17T12:00:04Z",
  "content": {
    "text": "I'm doing well, thank you!",
    "channel": "telegram"
  }
}
```

## Planned Message Types

These message types are defined in documentation but **not yet implemented**. They require further design before being added to the codebase.

### `configure`

> **Status**: Planned - needs design

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

### `route_assigned`

> **Status**: Planned - needs design

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

### `agent_event`

> **Status**: Planned - needs design

Agent lifecycle or control event.

```json
{
  "type": "agent_event",
  "from": "agent:system",
  "timestamp": "2026-02-17T12:00:06Z",
  "content": {
    "event": "spawned",
    "data": {
      "agent_id": "agent:worker-abc123"
    }
  }
}
```

## Content Field Reference

### Active Fields

| Field | Type | Used In | Description |
|-------|------|---------|-------------|
| `text` | string | tg_message, tg_reply | Message content |
| `chat_id` | string | spawn_request | Telegram chat identifier |
| `channel` | string | tg_message, tg_reply, spawn_request | Channel name for routing |
| `channel_type` | string | spawn_request | Reply channel type (telegram, discord, etc.) |
| `senderId` | string | tg_message | Telegram user ID |
| `username` | string | tg_message | Telegram username |
| `full_name` | string | tg_message | Full name of sender |
| `success` | boolean | spawn_result | Operation success indicator |
| `client_id` | string | spawn_result | Assigned agent identifier |
| `status` | string | spawn_result | Status (running, spawning, etc.) |

### Planned Fields

| Field | Type | Planned For | Description |
|-------|------|-------------|-------------|
| `talkto` | string | configure | Default destination for responses |
| `agent_id` | string | route_assigned, agent_event | Agent identifier |
| `event` | string | agent_event | Event type identifier |
| `data` | object | agent_event | Event-specific data |

## Addressing Notes

### Protocol vs Application From

- **Protocol-level** (`params.from`): Used by the bus for routing and tracking. Always present in `processMessage`.
- **Application-level** (`payload.from`): Used by agents for content-level addressing. Optional, may mirror protocol-level or provide additional context.

In most cases, these will be the same, but the distinction allows for:
- Forwarded messages (protocol-from is forwarder, payload-from is original sender)
- System-generated messages (protocol-from is bus/system, payload-from indicates logical source)

## Version

This document describes message types as of protocol v2.

**Active Types**: 4 (spawn_request, spawn_result, tg_message, tg_reply)  
**Planned Types**: 3 (configure, route_assigned, agent_event)
