# 2026-02-19 - Transport/Protocol Refactoring

## Work Completed

### 1. Added `send_message2` to `AgentBusClientApi`

**File:** `src/bub/bus/protocol.py:251-264`

Added convenience method that auto-generates message IDs:
```python
async def send_message2(
    self,
    from_: str,
    to: str,
    payload: dict[str, JsonValue],
) -> SendMessageResult:
```

- Generates message IDs atomically at API instance level
- Format: `msg_{client_id}_{counter:010d}`
- Constructor now accepts optional `client_id` parameter

### 2. Moved Transport Protocols to RPC Layer

**Files:** 
- `src/bub/rpc/types.py` - Added `Transport` and `Listener` protocols
- `src/bub/bus/types.py` - Removed re-exports
- `src/bub/bus/__init__.py` - Removed `Transport` from exports

**Rationale:** Transport protocols are fundamental to RPC layer, enabling mock implementations for testing without WebSocket dependencies.

### 3. Updated `AgentBusServer` Constructor

**File:** `src/bub/bus/bus.py:250-275`

Changed from:
```python
AgentBusServer(host="localhost", port=7892)
```

To:
```python
AgentBusServer(server=("localhost", 7892))  # tuple
# or
AgentBusServer(server=mock_listener)        # Listener protocol
```

This allows passing mock `Listener` implementations for testing.

### 4. Updated AGENTS.md with Type System Architecture

**File:** `AGENTS.md`

Added section documenting the refactoring principle:
- **Migrate imports, don't re-export**
- Update all affected imports to point to new canonical location
- Don't leave re-exports as compatibility shims

## Files Changed

| File | Change |
|------|--------|
| `src/bub/bus/protocol.py` | Added `send_message2`, updated constructor |
| `src/bub/bus/bus.py` | Updated `AgentBusServer` to use `Listener` protocol |
| `src/bub/rpc/types.py` | Added `Transport` and `Listener` protocols |
| `src/bub/bus/types.py` | Removed re-exports |
| `src/bub/bus/__init__.py` | Removed `Transport` from exports |
| `src/bub/cli/bus.py` | Updated server instantiation to use tuple |
| `tests/bub/bus/test_transport.py` | Updated import |
| `AGENTS.md` | Added Type System Architecture section |

## Status

✅ All changes applied
✅ Imports migrated to canonical locations
✅ No re-exports remain
✅ Testing module imports updated

## Scripts Documentation

Created comprehensive scripts documentation skill at `.agent/skills/scripts-docs/SKILL.md`:

- **24 scripts documented** with last_modified_date tracking
- **Git log commands** included to check if docs are outdated:
  - Single script: `git log -1 --format="%ai %s" -- scripts/NAME`
  - All scripts: `git log --name-only --pretty=format: scripts/ | grep -E '\.py$|\.sh$' | sort | uniq`
- **Categories covered**:
  - Bus/RPC testing (4 scripts)
  - End-to-End testing (3 scripts)  
  - MiniMax/LLM testing (4 scripts)
  - Bub Stack testing (5 scripts)
  - Issue reproduction (1 script)
  - Validation (2 scripts)
  - Shell scripts (4 scripts)
- **Maintenance checklist** included for keeping documentation current

## Commits

1. `0524dab` - refactor: move Transport/Listener protocols to rpc.types
2. `c60c4ea` - docs: add scripts-docs skill for maintaining script documentation
3. `0655b5e` - docs: update testing.md with accurate last_modified dates for all scripts
4. `2127b09` - test: update tests to use new AgentBusServer signature
5. `d013f8b` - test: merge test_protocol_validation.py into test_bus.py
6. `034450a` - test: fix hanging tests by using PairedTransport with proper mock responses
7. `00fd9a3` - refactor: remove unused InMemoryTransport and dead test code

## Scripts Documentation Maintenance Complete

✅ All 24 scripts documented in `docs/testing.md` with accurate last_modified dates
✅ Fixed 8 scripts with incorrect dates (2026-02-18 → 2026-02-17)
✅ Added 7 previously undocumented scripts
✅ Created skill at `.agent/skills/scripts-docs/SKILL.md` with maintenance procedure

## Test Updates Complete

✅ Updated `AgentBusServer` constructor calls in tests (10 occurrences)
✅ Merged `test_protocol_validation.py` into `test_bus.py`
✅ Fixed all 9 tests to use `PairedTransport` with proper mock responses
✅ Removed unused `InMemoryTransport` class (58 lines)
✅ Removed empty placeholder test
✅ Fixed bug in `bus.py` `_handle_transport` method

## Documentation Updated

✅ Updated `docs/jsonrpc-framework.md` to reflect:
  - Correct file locations (`bub/rpc/framework.py`, `bub/bus/protocol.py`)
  - New `Transport` and `Listener` protocols
  - Updated `AgentBusServer` constructor signature
  - Removed references to non-existent `AgentProtocol` class
  - Added testing example with `MockListener`

## Current Status

- **9/9 bus tests passing**
- **No dead code remaining**
- **All imports updated to canonical locations**
- **Documentation synchronized with code**
