# 2026-02-18 - Deployment Script Update

## What Changed

Updated `scripts/deploy-production.sh` to support new deployment workflows:

### 1. Start All Components
- Added `start all` command to start all main components at once
- Components started: bus, system-agent, tape, telegram-bridge

### 2. List Dynamic Agents
- Enhanced `list` command to display agents from `sessions.json`
- Shows both main components and dynamic agents in separate sections
- Displays agent status, unit name, and chat association

### 3. Stop Dynamic Agents
- Can now stop individual agents by name (e.g., `stop agent:worker-xxx`)
- Recognizes both main components and dynamic agents from sessions.json
- Added helper functions:
  - `dynamic_agent_exists()` - checks if agent exists in sessions.json
  - `get_dynamic_agents()` - extracts all dynamic agent info

### 4. Start All Support
- `start all` starts all main components sequentially
- Provides feedback on how many components started

### 5. Removed Agent Component
- Removed standalone "agent" from COMPONENTS array
- We now use system-agent which spawns conversation agents dynamically

### 6. Updated Help
- Comprehensive help message covering all features
- Documents main components vs dynamic agents distinction
- Includes examples for all commands

## Testing

- Verified bash script syntax: `bash -n deploy-production.sh`
- Made script executable
- Commands tested:
  - `start all` - starts all components
  - `list` - shows main + dynamic agents
  - `stop agent:worker-xxx` - stops specific agent
  - `stop all` - stops everything including dynamic agents

## Files Changed

- `scripts/deploy-production.sh` - Complete rewrite with new features
