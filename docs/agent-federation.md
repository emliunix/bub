# Agent Federation Architecture

> Status: Design Document | Implementation: Not Started

This document describes the architecture for multi-agent federation - enabling agents to spawn other agents, communicate with each other, and run as isolated external processes.

## 1. Before Architecture

### Overview
The original Bub design was a **single-agent per session** system with in-memory execution.

```
┌─────────────────────────────────────────────────────────────┐
│                    Original Architecture                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Human Input                                                 │
│      │                                                       │
│      ▼                                                       │
│  ┌─────────────────┐                                        │
│  │   Channel       │ (Telegram, CLI, etc.)                  │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                        │
│  │ ChannelManager  │ ──► MessageBus                         │
│  └────────┬────────┘         │                              │
│           │                  │                              │
│           ▼                  ▼                              │
│  ┌─────────────────────────────────────────┐                │
│  │          AppRuntime                     │                │
│  │  ┌─────────────────────────────────┐   │                │
│  │  │ SessionRuntime (per session)    │   │                │
│  │  │  - AgentLoop                    │   │                │
│  │  │  - TapeService                   │   │                │
│  │  │  - ModelRunner                   │   │                │
│  │  └─────────────────────────────────┘   │                │
│  └─────────────────────────────────────────┘                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Characteristics
- **In-process execution**: All agents run in the same Python process
- **Single session = single agent**: No spawning or forking capability
- **No inter-agent communication**: Sessions are completely isolated
- **Tape fork is temporary**: Used only for speculative execution within a turn
- **No external process management**: No container or service management

---

## 2. Current Architecture

### What Was Built (2026-02-13)
We implemented the **foundational primitives** for multi-agent but haven't wired them together:

```
┌─────────────────────────────────────────────────────────────┐
│                 Current Implementation                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [NEW] tape/session.py                                       │
│    - AgentIntention: next_steps, context_summary,           │
│                      trigger_on_complete                     │
│    - SessionGraph: parent-child tracking                     │
│                                                              │
│  [NEW] tape/service.py                                       │
│    - fork_session(): creates new tape from anchor           │
│    - get_intention(): retrieves stored intention            │
│                                                              │
│  [NEW] channels/events.py                                   │
│    - AgentCompleteEvent: session_id, exit_requested,        │
│                          trigger_next                        │
│    - AgentSpawnEvent: parent/child, from_anchor            │
│                                                              │
│  [NEW] channels/bus.py                                      │
│    - publish_agent_complete(), publish_agent_spawn()        │
│    - on_agent_complete(), on_agent_spawn()                 │
│                                                              │
│  [NEW] core/router.py                                       │
│    - _parse_trigger_instruction(): [TRIGGER: session=xxx]   │
│                                                              │
│  [NEW] tools/builtin.py                                     │
│    - tape.fork_session: tool to fork new session            │
│    - session.intention: tool to view intention              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### What's Missing
1. **No actual spawning**: `fork_session` creates a new tape but doesn't spawn a process
2. **No event handling**: Events fire but nothing subscribes to them
3. **No agent registry**: Can't track all running agents
4. **No external backends**: No podman/systemd support

---

## 3. Functional Rationale

### Why This Architecture?

#### Problem 1: Agent Isolation
Currently, each session is completely isolated. If agent A needs agent B to do a subtask, there's no way to:
- Spawn B with context from A
- Have B report back to A
- Manage multiple concurrent agents

#### Problem 2: Resource Management
In-process agents compete for:
- CPU/memory (model inference)
- Context window space
- Tool execution blocking

#### Problem 3: Fault Tolerance
If the main process crashes, all agents die. There's no:
- Checkpoint persistence
- Auto-recovery
- Independent restart

#### Problem 4: Scaling
One process cannot run many agents efficiently. Need:
- Isolated containers for heavy agents
- Lightweight agents can share process
- Mix of local and remote agents

### Design Goals

1. **Abstraction**: Agent is an abstract concept - can be local thread, podman container, or systemd service
2. **Event-driven**: Agents respond to events, not just human input
3. **Registry-based**: All agents are discoverable and manageable
4. **Federated**: Agents can be local or remote, same interface

---

## 4. Implementation Plan

### Phase 1: Agent Registry & Instance Model

Create the core abstractions:

```
src/bub/agents/
├── __init__.py
├── instance.py      # AgentInstance - represents a running agent
├── registry.py      # AgentRegistry - tracks all agents
├── state.py         # AgentState enum: STARTING, RUNNING, IDLE, STOPPED, FAILED
└── types.py         # AgentConfig, AgentMetadata
```

**AgentInstance**:
```python
@dataclass
class AgentInstance:
    agent_id: str
    session_id: str
    state: AgentState
    spawner: str  # "local", "podman", "systemd"
    process: subprocess.Popen | None
    started_at: datetime
    parent_agent_id: str | None
```

**AgentRegistry**:
```python
class AgentRegistry:
    def register(instance: AgentInstance) -> None
    def unregister(agent_id: str) -> None
    def get(agent_id: str) -> AgentInstance | None
    def list_by_session(session_id: str) -> list[AgentInstance]
    def list_by_parent(parent_id: str) -> list[AgentInstance]
    def list_all() -> list[AgentInstance]
```

### Phase 2: Spawner Interface

Define spawner backends:

```
src/bub/agents/
├── spawner.py      # AgentSpawner (abstract base)
├── local.py        # LocalSpawner - same process (current)
├── podman.py       # PodmanSpawner - isolated containers
└── systemd.py      # SystemdSpawner - systemd services
```

**AgentSpawner**:
```python
class AgentSpawner(ABC):
    @abstractmethod
    async def spawn(config: AgentConfig) -> AgentInstance: ...
    
    @abstractmethod
    async def stop(agent_id: str) -> None: ...
    
    @abstractmethod
    async def status(agent_id: str) -> AgentState: ...

    @property
    def backend_name(self) -> str: ...
```

### Phase 3: Event System Extension

Extend the message bus for agent events:

```
src/bub/agents/
└── events.py       # New event types
```

**New Event Types**:
```python
@dataclass
class AgentMessageEvent:
    """One agent sends message to another."""
    from_agent_id: str
    to_agent_id: str
    content: str
    reply_to: str | None  # message_id

@dataclass
class ToolFinishEvent:
    """Tool execution completed."""
    agent_id: str
    tool_name: str
    result: str
    duration_ms: int

@dataclass
class AgentStateChangeEvent:
    """Agent state changed."""
    agent_id: str
    old_state: AgentState
    new_state: AgentState
```

### Phase 4: Agent Controller

Wire events to actions:

```
src/bub/agents/
├── controller.py   # AgentController - event handlers
└── subscription.py # Subscription management
```

**AgentController**:
```python
class AgentController:
    def __init__(self, registry: AgentRegistry, bus: MessageBus, spawner: AgentSpawner):
        ...
    
    async def on_agent_complete(self, event: AgentCompleteEvent) -> None:
        # When agent finishes with trigger_next, spawn the next agent
        if event.trigger_next:
            await self.spawn_agent(event.trigger_next, parent=event.session_id)
    
    async def on_agent_message(self, event: AgentMessageEvent) -> None:
        # Route message to target agent's input queue
        ...
```

### Phase 5: Scheduler Integration

Add auto-backup checkpoint scheduler:

```
src/bub/agents/
└── scheduler.py    # AgentScheduler - periodic checkpointing
```

```python
class AgentScheduler:
    def __init__(self, registry: AgentRegistry, scheduler: BaseScheduler):
        ...
    
    def start_auto_checkpoint(self, interval_minutes: int = 5) -> None:
        """Create automatic checkpoints for all active agents."""
        ...
    
    async def recover_from_checkpoint(self, agent_id: str, checkpoint_name: str) -> None:
        """Resume agent from checkpoint."""
        ...
```

### Phase 6: Tool Integration

Extend built-in tools:

```python
# New tools to add
@register(name="agent.spawn")
def agent_spawn(params: AgentSpawnInput) -> str:
    """Spawn a new agent with config."""
    
@register(name="agent.list")  
def agent_list(params: AgentListInput) -> str:
    """List all agents."""
    
@register(name="agent.stop")
def agent_stop(params: AgentStopInput) -> str:
    """Stop a running agent."""
    
@register(name="agent.send")
def agent_send(params: AgentSendInput) -> str:
    """Send message to another agent."""
    
@register(name="schedule.checkpoint")
def schedule_checkpoint(params: CheckpointInput) -> str:
    """Enable automatic checkpointing."""
```

---

## 5. File Changes Summary

### New Files to Create

| File | Purpose |
|------|---------|
| `src/bub/agents/__init__.py` | Module exports |
| `src/bub/agents/types.py` | AgentConfig, AgentMetadata dataclasses |
| `src/bub/agents/state.py` | AgentState enum |
| `src/bub/agents/instance.py` | AgentInstance class |
| `src/bub/agents/registry.py` | AgentRegistry class |
| `src/bub/agents/spawner.py` | AgentSpawner abstract class |
| `src/bub/agents/local.py` | LocalSpawner implementation |
| `src/bub/agents/podman.py` | PodmanSpawner implementation |
| `src/bub/agents/events.py` | Extended event types |
| `src/bub/agents/controller.py` | AgentController |
| `src/bub/agents/scheduler.py` | Checkpoint scheduler |

### Files to Modify

| File | Changes |
|------|---------|
| `src/bub/app/runtime.py` | Add AgentRegistry, AgentController |
| `src/bub/channels/events.py` | Add more event types |
| `src/bub/channels/manager.py` | Wire up agent event handlers |
| `src/bub/tools/builtin.py` | Add agent.* tools |

---

## 6. Usage Examples

### Spawning an Agent

```bash
# From within an agent:
,tape.fork_session new_session_id=worker-1 from_anchor=phase-1 next_steps="verify results"

# Or using new tool:
,agent.spawn session_id=worker-1 from_checkpoint=phase-1 spawner=podman
```

### Agent-to-Agent Message

```python
# Agent A sends message to Agent B:
,agent.send to=worker-1 content="please verify the results"
```

### Trigger on Completion

```python
# Model outputs:
"""
[TRIGGER: session=worker-1]

Let me hand off to the verification agent.
"""

# This triggers AgentController to spawn worker-1
```

### Auto-Checkpoint

```bash
,schedule.checkpoint interval_minutes=5
```

---

## 7. Backward Compatibility

- **LocalSpawner** is the default and maintains current behavior
- Existing `tape.fork_session` continues to work (creates new tape)
- All existing tools unchanged
- No breaking changes to current single-agent flow

---

## 8. Future Architecture

> Beyond the current implementation plan - ideas for further evolution

### 8.1 Hierarchical Agent Teams

```
┌─────────────────────────────────────────────────────────────┐
│                  Hierarchical Teams                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│     ┌─────────────┐                                         │
│     │   Overseer  │ (manager agent)                         │
│     │  (agent-0)  │                                         │
│     └──────┬──────┘                                         │
│            │ spawns                                          │
│     ┌──────┴──────┬─────────────┐                           │
│     ▼             ▼             ▼                           │
│ ┌────────┐   ┌────────┐   ┌────────┐                       │
│ │Worker-1│   │Worker-2│   │Worker-3│                       │
│ └────────┘   └────────┘   └────────┘                       │
│   reports      reports      reports                         │
│     │             │             │                            │
│     └─────────────┴─────────────┘                            │
│                 ▼                                            │
│           ┌─────────┐                                        │
│           │ Overseer│ ← aggregates results                   │
│           └─────────┘                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Features**:
- Manager agents spawn and supervise worker agents
- Worker results flow back to manager
- Manager can reassign failed tasks
- Hierarchical checkpoints (each level saves state)

### 8.2 Agent Registry & Discovery

```
┌─────────────────────────────────────────────────────────────┐
│                  Agent Registry                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Global Agent Registry                    │   │
│  │                                                       │   │
│  │  agent_id    │ type      │ capabilities │ status   │   │
│  │  ────────────┼───────────┼──────────────┼───────── │   │
│  │  worker-1    │ verifier  │ code_review  │ idle     │   │
│  │  worker-2    │ runner    │ bash,fs      │ running  │   │
│  │  researcher   │ web       │ search,fetch │ ready    │   │
│  │                                                       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Capabilities:                                               │
│    - advertise: agent registers its capabilities            │
│    - discover: find agents by capability                     │
│    - invoke: call another agent directly                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Agent Types** (capability-based):
- `verifier` - reviews work, checks correctness
- `runner` - executes commands, runs code
- `researcher` - searches web, fetches pages
- `coder` - writes/edits code
- `summarizer` - condenses information

### 8.3 Persistent Agent Identity

```
┌─────────────────────────────────────────────────────────────┐
│               Persistent Agent Identity                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Agent Identity = stable across sessions                      │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ AgentIdentity                                         │     │
│  │   - unique_name: "reviewer-alice"                   │     │
│  │   - long_term_memory: MemoryStore                   │     │
│  │   - preferences: AgentPreferences                    │     │
│  │   - skills: list[SkillMetadata]                     │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  Memory System:                                              │
│    - semantic: embeddings + vector search                     │
│    - episodic: past conversation summaries                   │
│    - procedural: learned tool sequences                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 8.4 Distributed Agent Network

```
┌─────────────────────────────────────────────────────────────┐
│               Distributed Agent Network                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────┐     ┌─────────┐     ┌─────────┐              │
│   │ Node A  │◄───►│ Node B  │◄───►│ Node C  │              │
│   │ (local) │     │(remote) │     │(remote) │              │
│   └────┬────┘     └────┬────┘     └────┬────┘              │
│        │               │               │                     │
│    ┌───┴───┐       ┌───┴───┐       ┌───┴───┐              │
│    │agents │       │agents │       │agents │              │
│    └───────┘       └───────┘       └───────┘              │
│                                                              │
│   Communication:                                             │
│     - gRPC for low-latency agent-to-agent                   │
│     - Message bus spans process boundaries                  │
│     - Agents can migrate between nodes                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 8.5 Agent Marketplace

```
┌─────────────────────────────────────────────────────────────┐
│                 Agent Marketplace                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Marketplace Registry                    │    │
│  │                                                      │    │
│  │  name           │ author   │ rating │ price         │    │
│  │  ───────────────┼──────────┼────────┼────────────── │    │
│  │  code-reviewer  │ alice    │ 4.8    │ free          │    │
│  │  security-scan  │ bob      │ 4.5    │ $0.01/call   │    │
│  │  doc-writer     │ charlie  │ 4.9    │ free          │    │
│  │                                                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  Features:                                                   │
│    - publish: share agent definition                         │
│    - rate: review agents                                    │
│    - invoke: call marketplace agents                        │
│    - compose: chain multiple agents                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 8.6 Learning Agent System

```
┌─────────────────────────────────────────────────────────────┐
│               Learning from Interactions                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐      ┌─────────────────┐              │
│  │  Agent Executor │─────►│  Experience     │              │
│  │                 │      │  Store          │              │
│  └─────────────────┘      └────────┬────────┘              │
│                                     │                        │
│                                     ▼                        │
│  ┌─────────────────┐      ┌─────────────────┐              │
│  │  Strategy       │◄─────│  Learning       │              │
│  │  Selector      │      │  Engine         │              │
│  └─────────────────┘      └─────────────────┘              │
│                                                              │
│  Patterns learned:                                           │
│    - successful tool sequences                              │
│    - retry strategies                                        │
│    - when to spawn sub-agents                               │
│    - optimal checkpoint frequency                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 8.7 Long-term Vision

| Phase | Description |
|-------|-------------|
| **v1** | Multi-agent with local spawning (current plan) |
| **v2** | Container-based isolation, agent registry |
| **v3** | Distributed agents across machines |
| **v4** | Persistent agent identities with memory |
| **v5** | Agent marketplace and composability |
| **v6** | Self-improving agents via learning |

---

## 9. Open Questions

1. **Consensus**: How do agents agree on shared state?
2. **Security**: How to isolate untrusted agent code?
3. **Cost**: How to track/compute agent usage?
4. **Debugging**: How to trace agent-to-agent conversations?
5. **Testing**: How to test multi-agent systems?

---

*Document Status: Draft - Subject to revision as implementation progresses*

