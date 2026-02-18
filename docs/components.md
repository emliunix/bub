# Components

This page describes Bub’s **core components** and how they relate.

The goal is to be *component-wise and conceptual*: what each part does, and how they connect.
Detailed protocol specs, message schemas, and APIs are documented in dedicated pages.

## Overview

```text
External Channels (Telegram/Discord/WebSocket)
             │
             ▼
         Channels / Bridges
             │  (translate external events ↔ bus payloads)
             ▼
     WebSocket Message Bus (JSON-RPC)
             │
             ▼
            Agents
    (system agent + worker agents)
             │
             ▼
         Tape (storage)
```

## Core Components

### Bus

**What it is**: WebSocket message bus that routes JSON-RPC messages.

**Core responsibilities**:
- Connection management
- Message routing (topic / addressing)
- Ack/response fan-out (transport-level)

**Detailed docs**:
- Protocol: `docs/agent-protocol.md`

### Tape

**What it is**: Persistent append-only conversation storage.

**Core responsibilities**:
- Store conversation entries
- Provide read/append/fork/reset primitives
- Support anchors/handoffs (phase boundaries)

**Detailed docs**:
- Tape REST API: `docs/tape-service-rest-api.md`
- Tape test plan: `docs/tape-service-test-plan.md`

### Agents

Agents are the compute layer that interpret messages and produce replies.

**Subcomponents**:

- **System agent**: orchestration / routing layer (assigns routes, spawns or coordinates worker agents).
- **Worker (plain) agent**: the LLM-driven worker that runs tools, manages context, and writes to tape.

**Core responsibilities**:
- Decode inbound payloads and maintain per-conversation state
- Call LLM providers and execute tool calls
- Publish outbound payloads
- Persist key events to tape

**Detailed docs**:
- Application payload types: `docs/agent-messages.md`
- Architecture (design rationale): `docs/architecture.md`

### Channels / Bridges

Channels connect external systems to Bub.

**Core responsibilities**:
- Translate external events into application payloads
- Translate application payloads into external replies

**Examples**:
- Telegram
- Discord
- WebSocket

**Detailed docs**:
- Telegram: `docs/telegram.md`
- Discord: `docs/discord.md`

### CLI

The interactive CLI is the primary developer/operator interface.

**Core responsibilities**:
- Provide interactive chat loop
- Expose commands and session/tape utilities

**Detailed docs**:
- Interactive CLI: `docs/cli.md`

## Relationship Notes

- The **bus** transports messages; it should avoid channel- or application-specific logic.
- The **agent protocol** defines transport-level envelopes; the **agent messages** define application payload shapes.
- The **tape** is the durable memory/audit trail. Agent behavior should remain replayable against tape.

## Related Docs

- Testing and scripts: `docs/testing.md`
- Deployment: `docs/deployment.md`
