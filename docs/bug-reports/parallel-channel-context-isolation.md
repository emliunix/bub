# Bug Report: Parallel Channel Message Processing Lacks Shared Context

| Field | Details |
|---|---|
| **Status** | Open |
| **Severity** | High |
| **Component** | Channel Message Processing / Agent Loop |
| **Date** | 2026-05-09 |

## Summary

When multiple channel messages arrive concurrently (e.g., from Telegram, Discord, or other integrations), each message is processed in its own agent loop invocation. These parallel runs do not share tape/context state, meaning one agent run cannot see what another is doing or has done. This leads to duplicate work, conflicting actions, and inconsistent responses.

## Description

### Current Behavior

1. Multiple messages arrive on a channel in quick succession.
2. Each message triggers an independent `agent.run()` call with its own tape fork.
3. Each fork operates on a snapshot of the tape taken at fork time.
4. Changes made by one run (tool calls, tape events, state mutations) are **not visible** to other concurrent runs.
5. When runs complete and merge back, later merges may overwrite earlier state, or worse — both runs may take the same action (e.g., sending duplicate replies).

### Steps to Reproduce

1. Send two messages to a Telegram bot in quick succession (within ~1 second).
2. Observe that both agent loops start independently.
3. Both loops see the same tape history (pre-fork snapshot) and do not see each other's intermediate results.
4. Each loop may independently decide to perform overlapping or conflicting actions.

### Example Scenario

```
User sends: "Research X.com API pricing"
User sends: "Also check GitHub issues"

→ Agent Run A starts on tape (sees N entries)
→ Agent Run B starts on tape (sees N entries, same snapshot)

→ Run A calls web_fetch, writes to tape
→ Run B calls web_fetch, writes to tape
   (B cannot see A's fetch results or tape writes)

→ Both runs try to send replies via Telegram
→ Possible duplicate or contradictory responses
```

## Impact

- **Duplicate responses**: Multiple agent runs may send overlapping replies to the channel.
- **State corruption**: Tape merge-back may lose or overwrite events from concurrent runs.
- **Resource waste**: Identical or similar work performed in parallel (API calls, tool invocations).
- **Confusing UX**: Users see inconsistent or contradictory behavior from the bot.

## Root Cause

The agent's `run()` method forks the tape at entry and operates independently:

```python
# In agent.py
async with self.tapes.fork_tape(tape.name, merge_back=merge_back):
    return await self._agent_loop(tape=tape, prompt=prompt, ...)
```

Each fork is isolated. There is no coordination mechanism (lock, queue, or shared state) between concurrent forks of the same tape.

## Proposed Fix

### Short-term: Serialize Message Processing

Enforce sequential processing of messages per tape/channel using an async lock or queue:

```python
# In agent.py or channel handler
import asyncio

class Agent:
    def __init__(self, framework: BubFramework) -> None:
        self.settings = load_settings()
        self.framework = framework
        self._tape_locks: dict[str, asyncio.Lock] = {}

    def _get_tape_lock(self, tape_name: str) -> asyncio.Lock:
        if tape_name not in self._tape_locks:
            self._tape_locks[tape_name] = asyncio.Lock()
        return self._tape_locks[tape_name]

    async def run(self, *, tape_name: str, prompt, state, ...) -> str:
        tape_lock = self._get_tape_lock(tape_name)
        async with tape_lock:
            # existing run logic
            ...
```

**Pros:**
- Simple to implement
- Guarantees each message sees the latest tape state
- No race conditions or merge conflicts

**Cons:**
- Reduces throughput — messages wait in queue
- Long-running tasks block subsequent messages

### Long-term: Concurrent-Aware Context Sharing

- Implement a shared context bus that broadcasts intermediate results between concurrent runs.
- Add optimistic concurrency control for tape merge-back (detect conflicts, resolve or retry).
- Allow parallel processing but with awareness of sibling runs (e.g., via a "sibling context" that tracks in-flight operations).

## Related Files

- `src/bub/builtin/agent.py` — Main agent loop and tape forking logic
- `src/bub/builtin/store.py` — `ForkTapeStore` and merge-back behavior
- `src/bub/channels/manager.py` — Channel message dispatch

## Acceptance Criteria

- [ ] Sequential message processing is enforced per tape
- [ ] No duplicate replies when multiple messages arrive concurrently
- [ ] Tape state is consistent after processing a burst of messages
- [ ] Performance impact is documented (expected latency increase under load)
