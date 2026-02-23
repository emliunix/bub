# Architecture

This page is for developers and advanced users who need to understand why Bub behavior is deterministic and how to extend it safely.

## Core Principles

1. One session, one append-only tape.
2. Same routing rules for user input and assistant output.
3. Command execution and model reasoning are explicit layers.
4. Phase transitions are represented by `anchor/handoff`, not hidden state jumps.

## Runtime Topology

```text
input -> InputRouter -> AgentLoop -> ModelRunner -> InputRouter(assistant output) -> ...
                \-> direct command response
```

Key modules:

- `src/bub/app/runtime.py`: `AgentRuntime` (session factory), `SessionRuntime` (per-session state)
- `src/bub/core/router.py`: command detection, execution, and failure context wrapping.
- `src/bub/core/agent_loop.py`: turn orchestration and stop conditions.
- `src/bub/core/model_runner.py`: bounded model loop and user-driven skill-hint activation.
- `src/bub/tape/service.py`: tape read/write, anchor/handoff, reset, and search.
- `src/bub/tools/*`: unified registry and progressive tool view.

## Single Turn Flow

1. `InputRouter.route_user` checks whether input starts with `,`.
2. If command succeeds, return output directly.
3. If command fails, generate a `<command ...>` block for model context.
4. `ModelRunner` gets assistant output.
5. `route_assistant` applies the same command parsing/execution rules.
6. Loop ends on plain final text, explicit quit, or `max_steps`.

## Tape, Anchor, Handoff

- Tape is workspace-level JSONL for replay and audit.
- `handoff` writes an anchor with optional `summary` and `next_steps`.
- `anchors` lists phase boundaries.
- `tape.reset` clears active context (optionally archiving first).

## Component Hierarchy

The runtime consists of nested layers:

```text
AgentRuntime (manages multiple sessions)
  └── SessionRuntime (per session state)
        ├── AgentLoop (turn orchestration)
        │     └── ModelRunner (bounded model loop)
        ├── TapeService (persistence)
        └── ProgressiveToolView (tools)
```

| Component | File | Responsibility |
|-----------|------|----------------|
| `AgentRuntime` | `src/bub/app/runtime.py` | Top-level manager; factory for sessions; owns workspace, settings, LLM |
| `SessionRuntime` | `src/bub/app/runtime.py` | Per-session state wrapper; delegates to AgentLoop |
| `AgentLoop` | `src/bub/core/agent_loop.py` | Turn orchestration; decides routing and stop conditions |
| `ModelRunner` | `src/bub/core/model_runner.py` | Bounded model loop; makes LLM calls; processes responses |

## Command Execution

Two distinct execution paths exist:

### 1. LLM Tool Calls (Model-initiated)

**Flow:**

```text
ModelRunner.run()
  → tape.tape.run_tools_async(prompt, tools, system_prompt)
    → republic library:
      - Calls LLM with tools schema
      - LLM decides which tool(s) to call
      - republic executes tool handler(s)
      - Returns ToolAutoResult
```

**Location:** `src/bub/core/model_runner.py`

**Characteristics:**

- Uses `republic` library's `run_tools_async()`
- LLM decides tool selection based on context
- Automatic tool loop (LLM → tool → LLM → ...)
- Returns `ToolAutoResult` with text, tool_calls, tool_results, or error

### 2. User Commands (Human-initiated)

**Flow:**

```text
InputRouter.route_user(",command")
  → _execute_command()
    → _execute_shell() OR _execute_internal()
      → ToolRegistry.execute(name, kwargs)
        → Runs tool handler directly
```

**Location:** `src/bub/core/router.py`

**Characteristics:**

- Parses comma-prefixed commands (`<command ...>` blocks)
- No LLM involvement
- Direct execution via `ToolRegistry.execute()`
- Synchronous immediate response

### Shared Infrastructure

| Aspect | Shared? | Notes |
|--------|---------|-------|
| Tool Registry | Yes | Both use `ToolRegistry` for registration |
| Tool Handlers | Yes | Same underlying functions (bash, read, write, etc.) |
| Tool Schema | Yes | `Tool` objects from `model_tools()` |
| Execution Layer | Partial | Commands use `ToolRegistry.execute()`; LLM uses republic auto-execution |
| Logging | Yes | Both logged via `_log_tool_call()` |

## Tools and Skills

- Built-in tools and skills live in one registry.
- System prompt starts with compact tool descriptions.
- Full tool schema is expanded on demand (`tool.describe` or explicit selection).
- `$name` hints progressively expand tool/skill details from either user input or model output.
