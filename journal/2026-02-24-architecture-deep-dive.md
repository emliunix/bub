# 2026-02-24: Architecture Deep Dive - Runtime, Tools, and Session Forking

## Summary

Comprehensive analysis of Bub's architecture covering component relationships, command execution paths, tape lifecycle, tool handling, and the current state of session forking.

---

## 1. Component Hierarchy

```
AgentRuntime (manages multiple sessions)
  └── SessionRuntime (per session state)
        ├── AgentLoop (turn orchestration)
        │     └── ModelRunner (bounded model loop)
        ├── TapeService (persistence)
        └── ProgressiveToolView (tools)
```

**Key Files:**
- `AgentRuntime`: `src/bub/app/runtime.py:66`
- `SessionRuntime`: `src/bub/app/runtime.py:37`
- `AgentLoop`: `src/bub/core/agent_loop.py:26`
- `ModelRunner`: `src/bub/core/model_runner.py:48`

---

## 2. Command Execution: Two Distinct Paths

### 2.1 LLM Tool Calls (Model-initiated)

**Flow:**
```
ModelRunner.run()
  → tape.tape.run_tools_async(prompt, tools, system_prompt)
    → republic library:
      - Calls LLM with tools schema
      - LLM decides which tool(s) to call
      - republic executes tool handler(s)
      - Returns ToolAutoResult
```

**Characteristics:**
- Uses `republic` library's `run_tools_async()`
- LLM decides tool selection based on context
- Automatic tool loop (LLM → tool → LLM → ...)
- Returns `ToolAutoResult` with text, tool_calls, tool_results, or error

### 2.2 User Commands (Human-initiated)

**Flow:**
```
InputRouter.route_user(",command")
  → _execute_command()
    → _execute_shell() OR _execute_internal()
      → ToolRegistry.execute(name, kwargs)
        → Runs tool handler directly
```

**Characteristics:**
- Parses comma-prefixed commands (`<command ...>` blocks)
- No LLM involvement
- Direct execution via `ToolRegistry.execute()`
- Synchronous immediate response

### 2.3 Shared Infrastructure

| Aspect | Shared? | Notes |
|--------|---------|-------|
| Tool Registry | Yes | Both use `ToolRegistry` for registration |
| Tool Handlers | Yes | Same underlying functions (bash, read, write, etc.) |
| Tool Schema | Yes | `Tool` objects from `model_tools()` |
| Execution Layer | Partial | Commands use `ToolRegistry.execute()`; LLM uses republic auto-execution |
| Logging | Yes | Both logged via `_log_tool_call()` |

**Key Difference:** LLM tool calls go through the **republic** library which orchestrates the model interaction, while user commands are executed **directly** without model involvement.

---

## 3. System Prompt Construction

All instructions passed as **system role** via `system_prompt` parameter:

```python
# ModelRunner._render_system_prompt() order:
1. base_system_prompt (from AgentSettings)
2. workspace_system_prompt (AGENTS.md content)
3. _runtime_contract() (hardcoded rules)
4. render_tool_prompt_block() (tool descriptions)
5. render_compact_skills() (available skills)
```

**Skills Loading:**
- **Compact form**: Always included (names + descriptions)
- **Full body**: Loaded on `$skillname` hint into `_expanded_skills` dict
- **Bug**: Full skill bodies stored but **never appended to prompt** (incomplete implementation)

---

## 4. Tool Execution: Native API vs Prompt Text

Bub uses **both approaches together:**

1. **Native API tools** (primary): Passed via `tools=` parameter to `run_tools_async()`
2. **Prompt text descriptions** (secondary): XML-style descriptions in system prompt for model context

**Tool Call Extraction:**
- Extracted from `response.choices[0].message.tool_calls` (native API)
- **NOT parsed from assistant text** - XML in prompt is descriptive only
- Assistant messages are NOT probed for XML-formatted tool calls

---

## 5. Tape Lifecycle: Multiple Appends Per Turn

A single turn generates **5-12 tape entries** across multiple layers:

### AgentLoop (1 entry)
- `loop.result` - after ModelRunner completes

### ModelRunner (2-5 entries per step)
- `loop.step.start` - beginning of each step
- `loop.step.error` - if LLM call fails
- `loop.step.finish` - after routing assistant output
- `loop.step.empty` - if assistant returns empty
- `loop.max_steps` - if limit reached

### Republic Library (2-6 entries per tool call)
- `system` - system prompt
- `user` - user message
- `assistant` - assistant response
- `tool_call` - if tools called
- `tool_result` - tool execution results

---

## 6. Session Forking: Current State

### What Works

**`tape.fork_session` tool** (`src/bub/tools/builtin.py:503`):
- ✅ Creates new tape file with copied history
- ✅ Stores `AgentIntention` (next_steps, context_summary, trigger_on_complete)
- ✅ Publishes `AgentSpawnEvent` (fire-and-forget)
- ✅ Returns success message

### What's Missing (Critical)

**The forked session is NOT runnable:**

| Component | Status |
|-----------|--------|
| Tape file | ✅ Created |
| Entries | ✅ Copied |
| Intention | ✅ Stored |
| **SessionRuntime** | ❌ NOT created |
| **AgentLoop** | ❌ NOT created |
| **ModelRunner** | ❌ NOT created |
| **Registry entry** | ❌ NOT in `AgentRuntime._sessions` |

**Result:** Fork creates data on disk but has **NO RUNNING AGENT**. The returned `TapeService` is discarded.

### trigger_on_complete

- **Status**: Design field only, **NOT IMPLEMENTED**
- `AgentIntention.trigger_on_complete` stored but never read
- `publish_agent_complete()` exists but **NEVER CALLED**
- No `AgentController` to handle completion events

---

## 7. Comparison: Current vs Upstream

### Current Bub (./bub)
- Added `fork_session` tool for multi-agent federation
- `AgentSpawnEvent` published but no subscribers
- Half-implemented: creates tape but not execution context

### Upstream Bub (./upstream/bub)
- Has `fork_tape()` as **context manager**
- Used internally by `AgentLoop.handle_input()` for every turn
- Auto-merges back when done
- **Purpose:** Speculative execution, NOT subagent spawning
- **No user-visible session forking**

---

## 8. Open Questions

1. **Session forking completion**: Need `AgentController` to subscribe to `AgentSpawnEvent` and spawn child agents
2. **Skill expansion**: `_expanded_skills` populated but never used in prompt
3. **Trigger on complete**: Full implementation pending
4. **Merge semantics**: How should child results be merged back to parent?

---

## Files Modified

- `docs/architecture.md` - Added component hierarchy and command execution sections

## References

- Agent Federation Design: `docs/agent-federation.md`
- Session Forking Pattern: `docs/architecture/10-session-forking-pattern.md`
