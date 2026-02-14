# Distributed Agent Architecture

This document describes the next-generation architecture for Bub, enabling multi-agent collaboration, distributed execution, and fault tolerance.

## Motivation

The current architecture is single-process and monolithic. While functional, it has limitations:

1. **No fault tolerance**: API errors crash the session
2. **No multi-agent**: Cannot spawn sub-agents for parallel work
3. **No distribution**: Everything runs in one process
4. **No recovery**: Errors require manual intervention

The new architecture addresses these by separating concerns into standalone services.

## Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        Outside World                              │
│              (Telegram, CLI, Webhooks, Cron, etc.)               │
└──────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│               Message Bus (Standalone Process)                   │
│                                                                  │
│  - Event pub/sub (human messages, agent events, cron triggers)   │
│  - Agent registry (who's alive, status, tape_id)                │
│  - Message routing between components                            │
│                                                                  │
│  Protocol: JSON over TCP/WebSocket                               │
│  Storage: In-memory + optional persistence                       │
└──────────────────────────────────────────────────────────────────┘
                │                    │                    │
                ▼                    ▼                    ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   Standby Agent    │  │    LLM Agent A     │  │    LLM Agent B      │
│   (Static Binary)  │  │   (Spawned)        │  │   (Spawned)        │
│                    │  │                    │  │                    │
│  - Listens for    │  │  - Has own tape    │  │  - Can spawn more  │
│    incoming work  │  │  - Subscribes to   │  │  - Can subscribe   │
│  - Spawns initial │    bus                │    to other agents   │
│    agent          │  - Executes work      │  - Communicates      │
│  - Static code    │  - Publishes results  │    via bus          │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  ▼
                  ┌─────────────────────────────────┐
                  │      Tape Service               │
                  │   (Standalone Process)         │
                  │                                │
                  │   - Persist all tapes          │
                  │   - Fork/merge/rollback        │
                  │   - Query and search          │
                  │                                │
                  │   Container: Podman/Systemd   │
                  └─────────────────────────────────┘
```

## Core Concepts

### Context

Each agent operates on a **Context** that defines:

```python
@dataclass
class Context:
    tape: Tape          # Mutable conversation history
    model: str          # Model identifier (e.g., "anthropic:claude-3")
    tools: list[Tool]   # Available tools with metadata
    delivery: Delivery  # Where to send results
```

**Key difference from current**: Tape is mutable, delivery is explicit.

### Execute

The core execution loop is a simple function:

```python
async def execute(ctx: Context, input: str) -> ExecutionResult:
    """
    Single execution step:
    - Text → deliver to target
    - ToolCall → execute (possibly human-in-loop) → continue
    - Error → checkpoint + spawn debug agent
    """
```

This replaces the complex `ModelRunner` with a unified interface.

### Tape

```
Tape operations:
- read() → list[Entry]
- append(entry)  # grows tape
- fork() → tape_id  # checkpoint (manifest-based, no copy)
- truncate(to_entry_id)  # rollback
- compact() → new_tape_id  # summarize + create new tape
```

The tape is now a **service** accessed over network, not embedded in the agent.

### Message Bus

```
Events:
- human.message     # New message from user
- agent.spawn       # Agent started
- agent.done        # Agent completed
- agent.error       # Agent failed
- cron.trigger      # Scheduled task fired
- tool.result       # Tool execution complete

Actions:
- publish(event, data)
- subscribe(event_pattern, callback)
- spawn_agent(entrypoint, context) → agent_id
- subscribe_agent(agent_id) → async result
```

## Components

### 1. Standby Agent

Static binary that listens for work. Does NOT change:

```python
# Pseudo-code
async def standby_main():
    bus = await connect_message_bus()
    tape = await connect_tape_service()
    
    await bus.subscribe("human.message", on_human_message)
    
    async def on_human_message(event: HumanMessageEvent):
        # 1. Create new tape for this session
        session_id = event.session_id
        tape_id = await tape.create(session_id=session_id)
        
        # 2. Fork from last anchor or start fresh
        fork_id = await tape.fork(from_anchor="latest")
        
        # 3. Spawn LLM agent to do the work
        agent_id = await bus.spawn_agent(
            entrypoint="llm_agent",
            tape_id=tape_id,
            context={
                "initial_prompt": event.message,
                "model": event.model or default_model,
            }
        )
        
        # 4. Subscribe to completion
        await bus.subscribe(f"agent.{agent_id}.done", on_agent_done)
        
        # 5. Respond to user that work has started
        await bus.publish("agent.spawned", {"agent_id": agent_id})
```

### 2. LLM Agent

Dynamic agent spawned for each task:

```python
async def llm_agent_main(agent_id: str, tape_id: str, context: dict):
    bus = await connect_message_bus()
    tape = await connect_tape_service(tape_id)
    model = await connect_model(context["model"])
    
    # Subscribe to my events
    await bus.subscribe(f"agent.{agent_id}.human", on_human_message)
    
    # Main loop
    while True:
        # Read tape for context
        entries = tape.read()
        
        # Execute with model
        result = await execute(Context(
            tape=tape,
            model=context["model"],
            tools=default_tools,
            delivery=Delivery(bus=bus, target=agent_id)
        ), input=None)  # None = continue from tape
        
        if result.kind == "text":
            # Deliver to appropriate target
            await bus.publish("agent.done", {"agent_id": agent_id, "result": result})
            break
        elif result.kind == "tool_call":
            # Execute tool
            tool_result = await execute_tool(result.tool_call)
            tape.append(tool_result)
        elif result.kind == "error":
            # Checkpoint and spawn debug agent
            checkpoint_id = await tape.fork()
            await spawn_debug_agent(tape_id, checkpoint_id, result.error)
            break
    
    # Compaction on exit
    if should_compact(tape):
        new_tape_id = await tape.compact()
        await bus.publish("agent.compacted", {"old": tape_id, "new": new_tape_id})
```

### 3. Debug Agent

Spawned on error for diagnosis:

```python
async def debug_agent_main(tape_id: str, checkpoint_id: str, error: ErrorInfo):
    """
    Safe mode agent that:
    1. Analyzes the error context
    2. Reads relevant tape entries
    3. Suggests fix or recovery action
    4. Does NOT execute any tools by default
    """
    tape = await connect_tape_service(tape_id)
    
    # Gather diagnostic info
    entries = tape.read(from_id=checkpoint_id)
    error_context = analyze_error(error, entries)
    
    # Write diagnostic report to debug directory
    debug_path = Path(f"~/.bub/debug/{tape_id}_{checkpoint_id}")
    debug_path.write(diagnostic_report(error_context))
    
    # Publish for human review
    await bus.publish("debug.report", {"path": str(debug_path)})
```

## Communication Protocol

### Message Format

```json
{
  "id": "uuid",
  "type": "event|request|response",
  "topic": "human.message|agent.spawn|...",
  "payload": {
    "session_id": "...",
    "agent_id": "...",
    "data": {}
  },
  "reply_to": "uuid|null"
}
```

### Network

- Transport: TCP with JSON framing or WebSocket
- Service discovery: Static ports or environment variables
- Security: API keys in headers

## Tape Manifest

Instead of copying files on fork, use a manifest:

```json
// ~/.bub/tapes/manifest.json
{
  "version": 1,
  "tapes": {
    "main": {
      "file": "main.jsonl",
      "head_id": 410,
      "forks": ["main__backup_1", "main__checkpoint_2"]
    },
    "main__checkpoint_2": {
      "file": "main.jsonl",
      "head_id": 370,
      "fork_of": "main"
    }
  }
}
```

**Benefits**:
- Fork is instant (no file copy)
- Rollback is just updating `head_id`
- Full history preserved in one file

## Implementation Phases

### Phase 1: Standalone Services
1. Extract TapeService to standalone process
2. Extract MessageBus to standalone process
3. Add network communication layer

### Phase 2: Agent Framework
1. Implement Standby Agent (static binary)
2. Implement LLM Agent spawning
3. Add event subscription system

### Phase 3: Fault Tolerance
1. Implement manifest-based fork/rollback
2. Add debug agent spawning on errors
3. Add compaction on agent exit

### Phase 4: Multi-Agent
1. Add agent-to-agent communication
2. Add spawn_agent and subscribe primitives
3. Add cron/scheduled tasks

## Migration Path

The current single-process architecture can coexist with the new distributed one:

1. **Phase 1-2**: New components run alongside old
2. **Phase 3**: Error handling uses new debug agent
3. **Phase 4**: Full migration, old code becomes one agent

## Open Questions

1. **Container strategy**: Podman vs Systemd for agent isolation?
2. **Persistence**: How long to keep agent state? Auto-cleanup?
3. **Security**: API keys in agents? Sandboxing tools?
4. **Scaling**: Multiple tape services? Sharding by session?
