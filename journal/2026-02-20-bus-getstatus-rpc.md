# Bus Protocol Extension: getStatus RPC

Date: 2026-02-20

## Summary

Added a new RPC method `getStatus` to the bus protocol for introspecting bus routing internals. This allows operators and debugging tools to query connected clients, their subscriptions, and metadata.

## Changes

### 1. Protocol Types (`src/bub/bus/protocol.py`)

Added new Pydantic models:
- `ConnectionInfo`: Client connection details (client_id, connection_id, subscriptions, client_info)
- `GetStatusParams`: Empty params class for the RPC call
- `GetStatusResult`: Response containing server_id and connections list

Updated:
- `AgentBusServerCallbacks` protocol to include `handle_get_status` method
- `register_server_callbacks()` to register the new RPC method

### 2. Bus Server Implementation (`src/bub/bus/bus.py`)

- `AgentConnection` now stores `client_info` from initialization
- Added `handle_get_status` method to `AgentBusServer` that:
  - Iterates through all connections (with lock)
  - Only includes initialized connections
  - Converts ClientInfo to dict for serialization
  - Returns structured status data

### 3. CLI Command (`src/bub/cli/bus.py`)

Added `bub bus status` command:
```bash
uv run bub bus status              # Query default bus
uv run bub bus status -u ws://...  # Query specific bus URL
```

Output shows:
- Bus server ID
- Number of connected clients
- Per-client details: ID, connection UUID, subscriptions, client metadata

### 4. Documentation (`docs/agent-protocol.md`)

- Added section 5.6 documenting the getStatus method
- Updated Table of Contents
- Included request/response JSON examples
- Documented all response fields

## Usage

```bash
# Start the bus
uv run bub bus serve

# In another terminal, query status
uv run bub bus status
```

Example output:
```
======================================================================
Bus Server: bus-a1b2c3d4e5f6
======================================================================

Connected Clients: 3
----------------------------------------------------------------------

Client ID: agent:system
  Connection ID: conn-abc123
  Subscriptions: agent:system, system:*
  Client Info: {'name': 'bub', 'version': '0.2.0'}
...
```

## Post-Review Fixes

### 1. Type Annotation Fix (`src/bub/bus/protocol.py`)

Changed `ConnectionInfo.client_info` type from `dict[str, Any] | None` to `ClientInfo | None`:
- More precise typing - references the actual ClientInfo model
- Removed unnecessary `model_dump()` conversion in `bus.py`
- Now passes through the ClientInfo object directly

### 2. Code Review Process

Reviewed via subagent:
- All checklist items passed
- Type checking clean
- Documentation consistent
- Follows existing codebase patterns

### 3. AGENTS.md Update

Added principle: **"System Components: Use Deployment Scripts"**
- Always use deployment scripts for bus/agents
- Even during development and testing
- Ensures journalctl log aggregation and proper systemd management

## Verification

- [x] Type checking passes (mypy)
- [x] Protocol documentation updated
- [x] Implementation follows existing patterns
- [x] CLI command tested for syntax errors
- [x] Code review completed
- [x] Deployment principle documented in AGENTS.md

## Future Considerations

- This is primarily for debugging/monitoring - no other agent needs to inspect neighbors yet
- Could be extended with metrics (message counts, connection duration) if needed
- Authorization could be added if status data becomes sensitive
