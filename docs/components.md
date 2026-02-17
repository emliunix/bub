# Bub Components

Bub is composed of several independent services that communicate via the WebSocket Message Bus. Each component has a specific responsibility and can be started/stopped independently.

## Overview

```
┌─────────────────────────────────────────────────────────┐
│                     WebSocket Bus                       │
│                    (Port 7892)                          │
└────────────┬────────────────────────────┬───────────────┘
             │                            │
    ┌────────▼────────┐         ┌────────▼────────┐
    │   Telegram      │         │     Agent       │
    │   Bridge        │         │   (Worker)      │
    └────────┬────────┘         └────────┬────────┘
             │                            │
             └────────────┬───────────────┘
                          │
                    ┌─────▼─────┐
                    │   Tape    │
                    │ (Port 7890)
                    └───────────┘
```

## Components

### 1. Message Bus (`bus`)

**Purpose**: Central message router that connects all other components

**Port**: 7892

**Responsibilities**:
- Routes messages between components using JSON-RPC 2.0 over WebSocket
- Maintains topic-based pub/sub system
- No business logic - pure message routing
- All components (agent, telegram-bridge, CLI tools) connect as clients

**When to Start**: First component to start - all others depend on it

**Logs to Check**:
- Connection/disconnection events
- Message routing errors
- Handler registration issues

---

### 2. Agent Worker (`agent`)

**Purpose**: Core AI agent that processes messages and executes tools

**Port**: None (connects to bus as client)

**Responsibilities**:
- Processes incoming messages from Telegram and other channels
- Interacts with LLM APIs (OpenAI, MiniMax, etc.)
- Executes tools (file operations, shell commands, etc.)
- Manages conversation context and tape operations
- Handles multi-turn conversations and tool calling

**When to Start**: After bus is running

**Configuration**:
- `BUB_AGENT_API_KEY` - API key for LLM provider
- `BUB_AGENT_MODEL` - Model to use (e.g., `claude-3-opus`, `gpt-4`)
- `BUB_AGENT_MAX_TOKENS` - Max tokens per response

**Logs to Check**:
- LLM API errors
- Tool execution failures
- Conversation context issues
- Tape read/write errors

---

### 3. Tape Service (`tape`)

**Purpose**: Persistent append-only storage for conversations

**Port**: 7890

**Responsibilities**:
- Stores conversation history as append-only tape entries
- Provides REST API for tape operations (read, append, fork, reset)
- Manages anchors (named points in conversation history)
- Supports forking conversations for branching workflows

**When to Start**: After bus is running (or standalone for debugging)

**Configuration**:
- `BUB_TAPE_HOME` - Directory for tape storage (default: `.bub/`)
- `BUB_TAPE_NAME` - Default tape name

**Logs to Check**:
- File I/O errors
- API request failures
- Anchor resolution issues

**API Endpoints**:
- `GET /tape/{name}` - Read tape entries
- `POST /tape/{name}` - Append entry
- `POST /tape/{name}/fork` - Fork tape
- `DELETE /tape/{name}` - Reset tape
- `GET /tape/{name}/anchors` - List anchors
- `POST /tape/{name}/anchors/{anchor}` - Create anchor

---

### 4. Telegram Bridge (`telegram-bridge`)

**Purpose**: Connects Telegram Bot API to the WebSocket bus

**Port**: None (connects to bus as client)

**Responsibilities**:
- Polls Telegram Bot API for incoming messages
- Converts Telegram messages to bus format (JSON-RPC)
- Publishes messages to `inbound:{chat_id}` topic
- Subscribes to `outbound:{chat_id}` for agent responses
- Sends responses back to Telegram

**When to Start**: After bus is running, requires `BUB_BUS_TELEGRAM_TOKEN`

**Configuration**:
- `BUB_BUS_TELEGRAM_TOKEN` - Telegram bot token (required)
- `BUB_BUS_TELEGRAM_ALLOW_FROM` - Allowed user IDs (comma-separated)

**Logs to Check**:
- Telegram API errors
- Message format conversion issues
- Bus connection problems
- Authorization failures

---

## Component Dependencies

```
Bus (7892)
├── Agent Worker
│   └── Tape Service (7890)
└── Telegram Bridge
    └── Agent Worker
```

**Startup Order**:
1. Bus (required by all)
2. Tape (can run standalone or with agent)
3. Agent (requires bus, optionally uses tape)
4. Telegram Bridge (requires bus and agent)

## Quick Reference

| Component | Command | Port | Required Env |
|-----------|---------|------|--------------|
| Bus | `./scripts/deploy-production.sh start bus` | 7892 | None |
| Agent | `./scripts/deploy-production.sh start agent` | - | `BUB_AGENT_API_KEY` |
| Tape | `./scripts/deploy-production.sh start tape` | 7890 | `BUB_TAPE_HOME` (optional) |
| Telegram | `./scripts/deploy-production.sh start telegram-bridge` | - | `BUB_BUS_TELEGRAM_TOKEN` |

## Troubleshooting

### Component Won't Start

1. Check if bus is running: `./scripts/deploy-production.sh status bus`
2. Check logs: `./scripts/deploy-production.sh logs <component>`
3. Verify environment variables are set in `.env`
4. Check for port conflicts (bus: 7892, tape: 7890)

### Messages Not Flowing

1. Verify bus is running and accepting connections
2. Check component logs for connection errors
3. Ensure components are subscribing to correct topics
4. Check Telegram bridge for token/auth issues

### Tape Not Recording

1. Verify tape service is running: `./scripts/deploy-production.sh status tape`
2. Check tape service logs for file permission errors
3. Verify `BUB_TAPE_HOME` directory exists and is writable
4. Check agent logs for tape API errors
