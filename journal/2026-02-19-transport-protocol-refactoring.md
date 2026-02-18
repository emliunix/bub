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

## Next Task

Review and document all scripts in `scripts/` folder.
