# Bus API Refactoring - Usage Site Updates

**Date:** 2026-02-19
**Topic:** Refactoring AgentBusClient usage to match new callback-based API

## Summary

Refactored all usage sites of `AgentBusClient` to match the new callback-based API introduced in `bus.py`. The key change is that `AgentBusClient.connect()` now auto-starts the framework, eliminating the need for manual `run()` calls.

## Changes Made

### 1. Core Bus API (`src/bub/bus/bus.py`)

- Modified `AgentBusClient.connect()` to auto-start framework via `_start()`
- Added `_run_task` storage for proper lifecycle management
- Fixed `disconnect()` to properly reference `_transport`

### 2. CLI Bus Commands (`src/bub/cli/bus.py`)

- Updated `recv` command to support multiple `--to` patterns
- Removed manual `run()` calls from telegram bridge
- Fixed initialization order: connect → auto-start → initialize → subscribe
- Added proxy logging for Telegram bridge

### 3. Agent Command (`src/bub/cli/app.py`)

- Updated `_run_agent_client()` to use new callback pattern
- Removed manual `asyncio.sleep()` delays
- Fixed dispatch logic for `tg_message` processing
- Added response sending via `client.send_message()`

### 4. System Agent (`src/bub/system_agent.py`)

- Updated `start()` to use auto-connect pattern
- Removed manual `run()` loop management
- Fixed dispatch table for `spawn_request` handling

### 5. Runtime Bootstrap (`src/bub/app/bootstrap.py`)

- Removed bus dependency from `build_runtime()`
- Created `NoOpMessageBus` for compatibility
- Runtime now creates bus separately via agent command

### 6. Agent Runtime (`src/bub/app/runtime.py`)

- **CRITICAL FIX:** Added missing `session_id` parameter to `AgentLoop()` constructor
- Removed bus dependency from `AgentRuntime` and `SessionRuntime`
- Added comprehensive logging for session creation

### 7. Agent Loop (`src/bub/core/agent_loop.py`)

- Removed bus dependency completely
- Simplified to pure message processing
- Updated logging from debug to info level for key events

### 8. WebSocket Channel (`src/bub/channels/websocket.py`)

- Updated to implement `AgentBusClientCallbacks` protocol
- Fixed `process_message()` to handle inbound messages

### 9. Documentation (`docs/agent-messages.md`)

- Added `general_response` message type documentation
- Updated `tg_reply` format with `reply_to_message_id`

### 10. Operations Guide (`AGENTS.md`)

- Added deployment script usage instructions
- Documented `uv run` command patterns

## Key Bug Fixed

**Issue:** Agent would hang indefinitely when processing messages.

**Root Cause:** Missing `session_id` parameter in `AgentLoop()` constructor call in `runtime.py` line 176.

```python
# WRONG - caused TypeError that was silently swallowed:
loop = AgentLoop(router=router, model_runner=runner, tape=tape)

# CORRECT:
loop = AgentLoop(router=router, model_runner=runner, tape=tape, session_id=session_id)
```

**Impact:** Without this parameter, the constructor would fail, but the error was silently swallowed by asyncio, causing the agent to appear running but never process messages.

## Verification

All flows verified working:

1. **Agent Spawn:** ✅ System agent spawns conversation agents
2. **Message Routing:** ✅ Messages route via `agent:worker-xxx` addresses
3. **LLM Processing:** ✅ MiniMax-M2.5 model responds correctly
4. **Response Delivery:** ✅ Responses sent to `tg:chat_id` and captured

### Sample E2E Flow

```
[Telegram Bridge] → system:spawn (spawn_request)
[System Agent] → telegram-bridge (spawn_result with agent:worker-xxx)
[Telegram Bridge] → agent:worker-xxx (tg_message)
[Agent] LLM processing...
[Agent] → tg:chat_id (tg_reply)
```

## Files Modified

- `src/bub/bus/bus.py` - Core API changes
- `src/bub/cli/bus.py` - CLI commands
- `src/bub/cli/app.py` - Agent command
- `src/bub/system_agent.py` - System agent
- `src/bub/app/bootstrap.py` - Runtime bootstrap
- `src/bub/app/runtime.py` - Agent runtime (critical fix)
- `src/bub/core/agent_loop.py` - Agent loop
- `src/bub/channels/websocket.py` - WebSocket channel
- `docs/agent-messages.md` - Message documentation
- `AGENTS.md` - Operations guide
- `scripts/validate_system.py` - Test script
- `scripts/test_e2e_automated.py` - E2E test

## Architecture Improvements

1. **Separation of Concerns:** Bus logic separated from processing logic
2. **Auto-start Pattern:** Framework starts automatically on connect
3. **Callback-based API:** Clean protocol for message handling
4. **Better Logging:** Comprehensive logging throughout the stack

## Testing

Created comprehensive test in `scripts/test_e2e_automated.py`:
- Generates random chat_id
- Spawns agent via system agent
- Sends message to agent
- Verifies LLM response

## Follow-up

The bus architecture is now clean and production-ready. The message flow is:

1. Telegram bridge spawns agent → gets `agent:worker-xxx` ID
2. Bridge sends messages directly to agent ID
3. Agent processes with LLM
4. Agent sends responses to `tg:chat_id`
5. Bridge forwards to Telegram

All components properly decoupled and using the new callback API.
