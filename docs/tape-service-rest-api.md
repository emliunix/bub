# Tape Service REST API Design

## Overview

Convert `TapeService` to a standalone HTTP service with JSON REST endpoints.

**Protocol**: HTTP/1.1 + JSON
**Port**: 7890 (configurable via `BUB_TAPE_PORT`)

---

## Data Models

### Entry (in tape file)

```json
{
  "id": 1,
  "kind": "message | tool_call | tool_result | system | event | error",
  "payload": {...},
  "meta": {"run_id": "..."}
}
```

### Manifest (`manifest.json`)

Single source of truth for tape metadata and anchors:

```json
{
  "version": 1,
  "tapes": {
    "main": {
      "id": "main",
      "file": "main.jsonl",
      "parent_id": null,
      "head_id": 410,
      "created_at": "2026-01-01T00:00:00Z"
    },
    "main__fork_1": {
      "id": "main__fork_1",
      "file": "main.jsonl",
      "parent_id": "main",
      "head_id": 100,
      "created_at": "2026-02-13T20:00:00Z"
    }
  },
  "anchors": {
    "main": [
      {
        "name": "session/start",
        "tape_id": "main",
        "entry_id": 1,
        "state": {"owner": "human"},
        "created_at": "2026-01-01T00:00:00Z"
      },
      {
        "name": "phase1",
        "tape_id": "main",
        "entry_id": 50,
        "state": {"summary": "Setup done"},
        "created_at": "2026-02-10T10:00:00Z"
      }
    ]
  }
}
```

### Manifest (`manifest.json`)

Single source of truth for tape metadata and anchors:

```json
{
  "version": 1,
  "tapes": {
    "main": {
      "id": "main",
      "file": "main.jsonl",
      "parent_id": null,
      "head_id": 410,
      "created_at": "2026-01-01T00:00:00Z"
    },
    "main__fork_1": {
      "id": "main__fork_1",
      "file": "main.jsonl",
      "parent_id": "main",
      "head_id": 100,
      "created_at": "2026-02-13T20:00:00Z"
    }
  },
  "anchors": {
    "session/start": {
      "name": "session/start",
      "tape_id": "main",
      "entry_id": 1,
      "state": {"owner": "human"},
      "created_at": "2026-01-01T00:00:00Z"
    },
    "phase1": {
      "name": "phase1",
      "tape_id": "main",
      "entry_id": 50,
      "state": {"summary": "Setup done"},
      "created_at": "2026-02-10T10:00:00Z"
    }
  }
}
```

**Key design:**
- Anchors are independent objects (global, not per-tape)
- Tape files can be shared (same `file` path for forks)
- `head_id` is the "pointer" - like git's HEAD
- Fork is instant (just add manifest entry, no file copy)

---

## REST Endpoints

### Tapes

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/tapes` | List all tapes |
| `POST` | `/tapes` | Create new tape (adds manifest entry) |
| `GET` | `/tapes/{id}` | Get tape info (from manifest) |
| `PATCH`| `/tapes/{id}` | Update tape (e.g., set head_id) |
| `DELETE` | `/tapes/{id}` | Delete tape (removes manifest entry) |

### Entries

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/tapes/{id}/entries` | Read all entries |
| `GET` | `/tapes/{id}/entries?from=10&to=50` | Read entries in range |
| `POST` | `/tapes/{id}/entries` | Append entries |
| `GET` | `/tapes/{id}/entries/latest?n=10` | Read last N entries |

### Anchors (Independent Objects)

Anchors are independent pointers, not tied to a specific tape:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/anchors` | List all anchors |
| `POST` | `/anchors` | Create anchor |
| `GET` | `/anchors/{name}` | Get anchor |
| `PUT` | `/anchors/{name}` | Update anchor (entry_id, state, etc.) |
| `DELETE` | `/anchors/{name}` | Delete anchor |

**Anchor model:**
```json
{
  "name": "phase1",
  "tape_id": "main",
  "entry_id": 50,
  "state": {"summary": "Setup done"},
  "created_at": "2026-02-10T10:00:00Z"
}
```

### Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/tapes/{id}/search?q=error` | Search entries |

---

## Request/Response Examples

### Create Tape

```bash
curl -X POST http://localhost:7890/tapes \
  -H "Content-Type: application/json" \
  -d '{"name": "session_123"}'
```

```json
{
  "id": "session_123",
  "name": "session_123",
  "entries": 0,
  "anchors": [],
  "head_id": 0
}
```

### Fork Tape

```bash
curl -X POST http://localhost:7890/tapes/main/fork \
  -H "Content-Type: application/json" \
  -d '{"from_anchor": "phase1", "name": "session_fork_1"}'
```

```json
{
  "id": "session_fork_1",
  "name": "session_fork_1",
  "parent_id": "main",
  "from_entry_id": 50,
  "entries": 50,
  "head_id": 50
}
```

### Read Entries

```bash
curl http://localhost:7890/tapes/main/entries?from=1&to=10
```

```json
{
  "tape_id": "main",
  "entries": [
    {"id": 1, "kind": "anchor", "payload": {"name": "session/start"}, "meta": {}},
    {"id": 2, "kind": "message", "payload": {"role": "user", "content": "hello"}, "meta": {}},
    ...
  ],
  "total": 410,
  "from": 1,
  "to": 10
}
```

### Append Entry

```bash
curl -X POST http://localhost:7890/tapes/main/entries \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "message",
    "payload": {"role": "user", "content": "test"},
    "meta": {}
  }'
```

```json
{
  "id": 411,
  "kind": "message",
  "status": "appended"
}
```

---

## Implementation

### File Structure

```
src/bub/tape/
├── __init__.py
├── service.py       # Existing (refactor to use client)
├── store.py         # Existing (file operations)
├── manifest.py      # NEW: Anchor + manifest storage
├── client.py        # NEW: HTTP client
└── server.py        # NEW: REST server
```

### Server Implementation

```python
# src/bub/tape/server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class TapeStore:
    def __init__(self):
        self.manifest = Manifest()  # Anchors + tape metadata
        self.tapes: dict[str, list[TapeEntry]] = {}

# Endpoints
@app.get("/tapes")
async def list_tapes():
    ...

@app.post("/tapes")
async def create_tape(req: CreateTapeRequest):
    ...

@app.post("/tapes/{tape_id}/fork")
async def fork_tape(tape_id: str, req: ForkRequest):
    from_entry_id = req.from_entry_id or resolve_anchor(req.from_anchor)
    new_tape_id = do_fork(tape_id, from_entry_id)
    return {"id": new_tape_id, "from_entry_id": from_entry_id}
```

---

## Client Library

```python
# src/bub/tape/client.py
class TapeClient:
    def __init__(self, base_url: str = "http://localhost:7890"):
        self.base_url = base_url
    
    async def create(self, name: str) -> TapeInfo:
        ...
    
    async def read(self, tape_id: str, from_: int = None, to: int = None):
        ...
    
    async def append(self, tape_id: str, entry: TapeEntry):
        ...
    
    async def fork(self, tape_id: str, from_entry_id: int = None, 
                   from_anchor: str = None, name: str = None):
        ...
    
    async def anchors(self, tape_id: str) -> list[Anchor]:
        ...
    
    async def create_anchor(self, tape_id: str, name: str, 
                            entry_id: int = None, state: dict = None):
        ...
```

---

## Configuration

```bash
# Environment
BUB_TAPE_PORT=7890
BUB_TAPE_HOST=localhost
BUB_TAPE_MODE=embedded|remote
```

```python
# Usage
from bub.tape import TapeService

# Embedded (current)
tape = TapeService(llm, name, store=FileTapeStore(...))

# Remote (new)
tape = TapeClient.connect()  # or
tape = TapeService(llm, name, store=RemoteTapeStore())
```

---

## Future: Message Bus (JSON-RPC over WebSocket)

> **Note**: When implementing the message bus, use JSON-RPC 2.0 over WebSocket instead of REST.

### Why JSON-RPC?
- Bidirectional communication (subscriptions)
- Request/response with IDs
- Notifications (fire-and-forget)
- Batch requests

### Protocol

```json
// WebSocket message format
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "subscribe",
  "params": {"topic": "human.message"}
}
```

```json
// Response
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {"subscription_id": "sub_123"}
}
```

```json
// Notification (push)
{
  "jsonrpc": "2.0",
  "method": "event",
  "params": {
    "topic": "human.message",
    "data": {"message": "hello", "session_id": "abc"}
  }
}
```

### Methods

| Method | Description |
|--------|-------------|
| `publish` | Publish event |
| `subscribe` | Subscribe to topic |
| `unsubscribe` | Unsubscribe |
| `spawn_agent` | Spawn new agent |
| `list_agents` | List running agents |
| `send` | Send message to agent |

---

## Implementation Order

1. **Manifest + Anchor objects** - Refactor anchor from entry to separate object
2. **REST server** - `src/bub/tape/server.py` with endpoints
3. **Client library** - `src/bub/tape/client.py`
4. **Config integration** - `BUB_TAPE_MODE=remote`
5. **Deprecation** - Keep embedded mode for backward compatibility
