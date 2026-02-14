# Implementation Plan: Distributed Architecture

This document outlines the phased implementation approach.

## Phase 0: Foundation (Prerequisite)

Before distributed architecture, fix the immediate bug:

### 0.1 Error Recovery (Immediate Fix)
- Add `truncate(to_entry_id)` to TapeService
- Add error detection in context selection
- Filter out error entries during replay

```python
# src/bub/tape/service.py
def truncate(self, to_entry_id: int) -> None:
    """Truncate tape after entry_id (for rollback)."""
    # Implement in store.py
    
# src/bub/tape/context.py
def _select_messages(entries, context):
    # Skip entries after error
```

### 0.2 Manifest-Based Fork
- Add `manifest.json` for tape tracking
- Fork becomes instant (no file copy)

---

## Phase 1: Standalone Services

Goal: Extract tape and message bus to separate processes.

### 1.1 Tape Service (Standalone)

```
Host: localhost:7890
Protocol: HTTP/JSON
```

**API**:
```
POST /tapes/create         → {"tape_id": "..."}
GET  /tapes/{id}/read     → {"entries": [...]}
POST /tapes/{id}/append   → {"entry": {...}}
POST /tapes/{id}/fork     → {"fork_id": "..."}
POST /tapes/{id}/truncate → {"head_id": 123}
POST /tapes/{id}/compact  → {"new_tape_id": "..."}
```

**Implementation**:
1. Create `src/bub/tape/server.py` - HTTP server wrapper
2. Create `src/bub/tape/client.py` - Network client
3. Add manifest handling
4. Containerize with Podman

### 1.2 Message Bus (Standalone)

```
Host: localhost:7891
Protocol: WebSocket (for subscriptions)
```

**API**:
```
POST /events/publish      → {"topic": "...", "payload": {...}}
WS   /events/subscribe   → stream of events
POST /agents/spawn       → {"agent_id": "..."}
GET  /agents/list        → [{"id": "...", "status": "..."}]
```

**Implementation**:
1. Create `src/bub/bus/server.py` - WebSocket server
2. Create `src/bub/bus/client.py` - Async client with subscription
3. Add agent registry in-memory
4. Containerize

### 1.3 Communication Layer

```python
# src/bub/net/__init__.py
class TapeClient:
    def __init__(self, host="localhost", port=7890):
        ...
    async def read(self, tape_id: str) -> list[TapeEntry]:
        ...
    async def append(self, tape_id: str, entry: TapeEntry):
        ...
```

---

## Phase 2: Agent Framework

Goal: Implement Standby Agent and agent spawning.

### 2.1 Standby Agent (Static Binary)

**Responsibilities**:
- Listen to message bus for incoming work
- Create/fork tapes for new sessions
- Spawn LLM agents
- Return job ID to user

**Entry Point**: `bub-standby` CLI command

```python
# src/bub/agents/standby.py
async def main():
    bus = await MessageBusClient.connect()
    tape = await TapeClient.connect()
    
    await bus.subscribe("human.message", handle_message)
    
    async def handle_message(event):
        tape_id = await tape.create(session_id=event.session_id)
        agent_id = await bus.spawn_agent(
            entrypoint="llm_agent",
            tape_id=tape_id,
            context={"prompt": event.message}
        )
        return {"status": "spawned", "agent_id": agent_id}
```

### 2.2 LLM Agent (Spawned)

**Responsibilities**:
- Read from assigned tape
- Execute with model
- Handle tool calls
- Publish results on completion

**Entry Point**: `bub-agent llm` CLI command

### 2.3 Execute Function

Replace `ModelRunner` with unified `execute()`:

```python
# src/bub/agents/execute.py
async def execute(ctx: Context, input: str | None) -> Result:
    """
    Single execution step:
    - input is None: continue from tape
    - input is str: add as user message
    """
    messages = ctx.tape.get_messages()
    
    response = await ctx.model.chat(
        messages=messages,
        tools=ctx.tools
    )
    
    if response.kind == "text":
        return TextResult(response.text)
    
    if response.kind == "tools":
        for tool_call in response.tool_calls:
            result = await ctx.tools.execute(tool_call)
            ctx.tape.append_tool_result(result)
        return ToolCallResult(tool_call)
    
    if response.kind == "error":
        return ErrorResult(response.error)
```

---

## Phase 3: Fault Tolerance

Goal: Automatic error recovery with debug agents.

### 3.1 Checkpoint on Error

```python
# In execute(), on error:
async def handle_error(ctx, error):
    # 1. Create checkpoint (fork with manifest)
    checkpoint_id = await ctx.tape.fork()
    
    # 2. Save diagnostic info
    debug_info = {
        "tape_id": ctx.tape.id,
        "checkpoint_id": checkpoint_id,
        "error": error,
        "recent_entries": ctx.tape.read_last(50)
    }
    save_debug_report(debug_info)
    
    # 3. Spawn debug agent
    debug_id = await bus.spawn_agent(
        entrypoint="debug_agent",
        tape_id=ctx.tape.id,
        context={"checkpoint_id": checkpoint_id, "error": error}
    )
```

### 3.2 Debug Agent

**Behavior**:
- Read error + checkpoint
- Analyze what went wrong
- Write report to `~/.bub/debug/`
- Publish report for human review

**Tools** (restricted):
- `tape.read` - yes
- `bash` - NO (safe mode)

### 3.3 Manual Recovery

Human reviews debug report, chooses:
1. `tape.rollback(checkpoint_id)` - restore to checkpoint
2. `tape.truncate(to_entry_id)` - manual cut
3. `agent.resume(agent_id)` - continue from here

---

## Phase 4: Multi-Agent

Goal: Agents can spawn and communicate.

### 4.1 Agent Primitives

```python
# Tools available to agents
@register(name="spawn_agent")
async def spawn_agent(params: SpawnParams) -> str:
    """Spawn a sub-agent to do parallel work."""
    agent_id = await bus.spawn_agent(
        entrypoint=params.entrypoint,
        tape_id=params.tape_id,  # can fork from current
        context=params.context
    )
    return agent_id

@register(name="subscribe_agent")
async def subscribe_agent(params: SubscribeParams) -> str:
    """Wait for another agent to complete."""
    result = await bus.subscribe(f"agent.{params.agent_id}.done")
    return result.payload

@register(name="cron")
async def schedule_wake(params: CronParams) -> str:
    """Schedule self to wake at time."""
    await bus.schedule(
        at=params.at,
        message=params.message,
        target=current_agent_id
    )
```

### 4.2 Compaction

```python
@register(name="compact")
async def compact_tape() -> str:
    """Create new tape with summarized context."""
    entries = tape.read()
    summary = await model.summarize(entries)
    new_tape_id = await tape.create(summary=summary)
    await bus.publish("agent.compacted", {"old": tape_id, "new": new_tape_id})
    return new_tape_id
```

---

## File Structure (Target)

```
src/bub/
├── net/                    # NEW: Network layer
│   ├── __init__.py
│   ├── client.py          # TapeClient, BusClient
│   ├── server.py          # HTTP/WS servers
│   └── protocol.py        # Message definitions
│
├── bus/                    # NEW: Message bus (standalone)
│   ├── __init__.py
│   ├── server.py
│   ├── client.py
│   └── registry.py        # Agent registry
│
├── tape/                   # MODIFIED: Service extraction
│   ├── __init__.py
│   ├── service.py
│   ├── store.py
│   ├── client.py          # NEW: Network client
│   ├── server.py          # NEW: Standalone server
│   └── manifest.py        # NEW: Fork manifest
│
├── agents/                # NEW: Agent framework
│   ├── __init__.py
│   ├── execute.py        # Unified execute()
│   ├── context.py        # Context dataclass
│   ├── standby.py        # Static standby agent
│   ├── llm.py            # LLM agent
│   ├── debug.py          # Debug agent
│   └── tools.py          # Agent-specific tools
│
├── cli/
│   ├── __init__.py
│   ├── app.py
│   ├── interactive.py
│   └── standby.py        # NEW: bub-standby command
│
└── ... (keep existing)
```

---

## Backward Compatibility

**Current single-process mode** should still work:

```python
# Old: Embed tape in same process
tape = TapeService(llm, name, store=FileTapeStore(...))

# New: Connect to standalone service
tape = TapeClient(host="localhost", port=7890)
```

Config option `BUB_TAPE_MODE=embedded|remote`:

- `embedded`: Current behavior
- `remote`: Connect to tape service

---

## Testing Strategy

### Unit Tests
- `test_execute_*`: Execute function behavior
- `test_tape_manifest`: Fork/rollback logic
- `test_bus_events`: Event pub/sub

### Integration Tests
- `test_tape_service`: Start service, make API calls
- `test_agent_spawn`: Standby → spawn → complete

### E2E Tests
- `test_human_message_flow`: Telegram → Bus → Agent → Result

---

## Open Questions for Discussion

1. **Container runtime**: Podman or systemd for agent isolation?
2. **Service discovery**: Static ports, env vars, or service mesh?
3. **Persistence**: How long to keep debug info? Auto-cleanup policy?
4. **Tool sandboxing**: Which tools can debug agent use?
5. **API compatibility**: Keep old CLI working during migration?
