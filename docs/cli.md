# CLI Commands

Bub provides a comprehensive CLI for running agents, managing the message bus, and inspecting tape history.

## Command Overview

| Command | Purpose |
|---------|---------|
| `bub chat` | Interactive coding agent |
| `bub run` | One-shot command execution |
| `bub agent` | Connect agent to message bus |
| `bub system-agent` | Run system agent (spawns conversation agents) |
| `bub bus` | Bus server and operations |
| `bub tape` | Tape operations |
| `bub telegram` | Telegram integration (legacy) |
| `bub idle` | Scheduler-only mode |

---

## Interactive Agent

### `bub chat`

Run the interactive CLI for pair programming.

```bash
uv run bub chat
```

**Options:**
- `-w, --workspace PATH` - Set working directory
- `--model TEXT` - Model to use (e.g., `openrouter:qwen/qwen3-coder-next`)
- `--max-tokens INTEGER` - Maximum tokens per response
- `--session-id TEXT` - Session identifier (default: `cli`)
- `--disable-scheduler` - Disable scheduled tasks

**Example:**
```bash
uv run bub chat \
  --workspace /path/to/repo \
  --model openrouter:qwen/qwen3-coder-next \
  --max-tokens 1400 \
  --session-id cli-main
```

### `bub run`

Execute a single message and exit.

```bash
uv run bub run "summarize the current repo"
```

**Options:**
- `-w, --workspace PATH` - Set working directory
- `--model TEXT` - Model to use
- `--max-tokens INTEGER` - Maximum tokens
- `--session-id TEXT` - Session identifier
- `--tools TEXT` - Allowed tool names (comma-separated)
- `--skills TEXT` - Allowed skill names (comma-separated)
- `--disable-scheduler` - Disable scheduled tasks

**Examples:**
```bash
uv run bub run ",help"
uv run bub run --tools fs.read,fs.glob --skills friendly-python "inspect Python layout"
uv run bub run --disable-scheduler "quick reasoning task"
```

---

## Message Bus Agents

### `bub agent`

Connect an agent to the WebSocket message bus.

```bash
uv run bub agent --client-id agent:worker-abc123 --talkto tg:123456789
```

**Options:**
- `-w, --workspace PATH` - Set working directory
- `--model TEXT` - Model to use
- `--max-tokens INTEGER` - Maximum tokens
- `--client-id TEXT` - Client identifier (default: `agent:default`)
- `--talkto TEXT` - Target address for responses
- `--bus-url TEXT` - Bus WebSocket URL (env: `BUB_BUS_URL`)
- `--reply-type TEXT` - Reply channel type: `telegram`, `discord` (default: `telegram`)

**Usage:**
```bash
# Terminal 1: Start bus server
./scripts/deploy-production.sh start bus

# Terminal 2: Start agent
BUB_BUS_URL=ws://localhost:7892 uv run bub agent \
  --client-id agent:my-agent \
  --talkto tg:123456789
```

### `bub system-agent`

Run the system agent that spawns conversation agents on demand.

```bash
uv run bub system-agent
```

**Options:**
- `-u, --bus-url TEXT` - Bus URL (default: `ws://localhost:7892`)

---

## Bus Operations

### `bub bus serve`

Start the WebSocket message bus server.

```bash
./scripts/deploy-production.sh start bus
```

> **Note:** Always use the deployment script to ensure proper systemd management and journalctl logging.

### `bub bus send`

Send a message to the bus and print responses.

```bash
uv run bub bus send "Hello world"
```

**Options:**
- `-c, --chat-id TEXT` - Chat ID (default: `cli`)
- `--channel TEXT` - Channel name (default: `cli`)
- `-a, --address TEXT` - Response address (default: `tg:cli`)
- `-t, --timeout INTEGER` - Receive timeout in seconds (default: `30`)
- `-u, --bus-url TEXT` - Bus URL (env: `BUB_BUS_URL`)

### `bub bus status`

Query bus status - show connected clients and subscriptions.

```bash
uv run bub bus status              # Query default bus
uv run bub bus status -u ws://host:port  # Query specific bus
```

**Output:**
- Server ID
- Number of connected clients
- Per-client details: ID, connection UUID, subscriptions, client metadata

### `bub bus telegram`

Run Telegram bridge - receives Telegram messages and forwards to bus.

```bash
uv run bub bus telegram --token YOUR_BOT_TOKEN
```

**Options:**
- `-t, --token TEXT` - Telegram bot token (env: `BUB_BUS_TELEGRAM_TOKEN`)
- `-u, --bus-url TEXT` - Bus URL (env: `BUB_BUS_URL`)
- `--allow-from TEXT` - Allow users by ID/username
- `--allow-chats TEXT` - Allow chats by ID
- `--proxy TEXT` - Proxy URL (env: `BUB_BUS_TELEGRAM_PROXY`)

---

## Tape Operations

### `bub tape list`

List all tapes.

```bash
uv run bub tape list
```

**Options:**
- `-w, --workspace PATH` - Set working directory

### `bub tape history NAME`

Show tape history.

```bash
uv run bub tape history my-tape
```

**Options:**
- `-w, --workspace PATH` - Set working directory

### `bub tape anchors NAME`

List anchors in a tape.

```bash
uv run bub tape anchors my-tape
```

**Options:**
- `-w, --workspace PATH` - Set working directory

### `bub tape serve`

Start the tape server.

```bash
uv run bub tape serve
```

**Options:**
- `-w, --workspace PATH` - Set working directory

---

## Other Commands

### `bub telegram`

Run Telegram channel with the same agent loop runtime (legacy).

```bash
uv run bub telegram
```

**Options:**
- `-w, --workspace PATH` - Set working directory
- `--model TEXT` - Model to use
- `--max-tokens INTEGER` - Maximum tokens

### `bub idle`

Start the scheduler only - useful for running a completely autonomous agent.

```bash
uv run bub idle
```

**Options:**
- `-w, --workspace PATH` - Set working directory
- `--model TEXT` - Model to use
- `--max-tokens INTEGER` - Maximum tokens

---

## Session Context Commands

When in interactive mode (`bub chat`), these internal commands are available:

```text
,tape.info                    # Show tape info
,tape.search query=error      # Search tape
,anchors                      # Show phase boundaries
,tape.reset archive=true      # Archive and clear tape
```

---

## Input Interpretation

### Command Detection

- **Lines starting with `,`** are interpreted as commands
- **Registered names** like `,help` are internal commands
- **Other comma-prefixed lines** run through shell: `,git status`
- **Non-comma input** is always treated as natural language

### Shell Mode

Press `Ctrl-X` to toggle between modes:

- **`agent` mode**: Send input as typed
- **`shell` mode**: Auto-normalizes input to `, <command>` if no comma prefix

Use shell mode when running multiple shell commands quickly.

---

## Typical Workflow

1. **Check repo status:** `,git status`
2. **Read files:** `,fs.read path=README.md`
3. **Edit files:** `,fs.edit path=foo.py old=... new=...`
4. **Validate:** `uv run pytest -q`
5. **Mark phase:** `,handoff name=phase-x summary="tests pass"`

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `command not found` | Verify it's an internal command (`,help` for list) |
| `bub message` exits immediately | No message channel enabled in `.env` |
| Context too heavy | Add a handoff anchor, then reset tape |
| Cannot connect to bus | Ensure bus is running: `./scripts/deploy-production.sh status bus` |

---

## Related Docs

- Components and relationships: `docs/components.md`
- Testing and debug scripts: `docs/testing.md`
- Agent protocol: `docs/agent-protocol.md`
- Agent message payload types: `docs/agent-messages.md`
