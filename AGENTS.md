# Repository Guidelines

> **IMPORTANT**: This document is for human developers only. DO NOT execute any commands or workflows described in this file unless explicitly requested by the user. This is documentation, not instructions for automated execution.

## Project Structure & Module Organization
Core code lives under `src/bub/`:
- `app/`: runtime bootstrap and session wiring
- `core/`: input router, command detection, model runner, agent loop
- `tape/`: append-only tape store, anchor/handoff services
- `tools/`: unified tool registry and progressive tool-view rendering
- `skills/`: skill discovery and loading (`SKILL.md`-based)
- `cli/`: interactive CLI (`bub chat`)
- `channels/`: channel bus/manager and Telegram adapter
- `integrations/`: Republic client setup

Tests are in `tests/`. Documentation is in `docs/`. See [docs/README.md](docs/README.md) for the full docs site structure. Legacy implementation is archived in `backup/src_bub_legacy/` (read-only reference). The `upstream/` directory contains external repositories cloned for reference and study purposes (e.g., comparing implementations or examining how other projects solve similar problems).

## Build, Test, and Development Commands

> **Note**: The following commands are documentation for developers. The agent should NOT execute these commands unless explicitly requested by the user.

- `uv sync`: install/update dependencies
- `uv pip list`: list installed packages
- `uv pip index versions <package>`: search for package versions
- `just install`: setup env + hooks

## Development Workflow

> **DEVELOPER ONLY**: These commands are for human developers to run before committing changes. DO NOT execute these commands automatically as part of normal agent operations.

Run these checks before committing (or let pre-commit hooks handle it):

```bash
# Check only changed files (recommended)
uv run ruff check .
uv run mypy src

# Run tests
uv run pytest -q

# Or all at once
just check
```

**Note**: The agent should NOT run tests, linting, or type-checking automatically unless explicitly asked by the user.

Pre-commit hooks (installed via `just install`) will automatically run these checks on staged files before each commit.

## Dependency Management
When adding new dependencies:

1. Search for the latest version:
   ```bash
   uv run --with pip pip index versions <package>
   ```

2. Add to project (auto-updates pyproject.toml):
   ```bash
   uv add <package>>=X.Y.Z
   ```

3. Sync dependencies:
   ```bash
   uv sync
   ```

4. Run tests to verify (developer only):
   ```bash
   uv run pytest -q
   ```
   **Note**: The agent should NOT run tests automatically.

## Code Style Guidelines

### General
- Python 3.12+, 4-space indentation, type hints required for new/modified logic
- Line length: 120 characters (enforced by ruff)
- Format/lint with Ruff; type-check with mypy

### Naming Conventions
- `snake_case`: functions, variables, modules, methods
- `PascalCase`: classes, exceptions, type aliases
- `UPPER_CASE`: constants, enum values
- Private implementation: prefix with underscore `_internal()` or `__dunder`
- Avoid single-letter names except: `i`/`j`/`k` for loops, `x`/`y`/`z` for coordinates, `e` for exceptions

### Imports
- Use absolute imports: `from bub.core import router`
- Sort imports with ruff (isort rules): stdlib → third-party → local
- **All imports must be at the top of the file** (enforced by ruff E402)
- Avoid wildcard imports (`from x import *`)
- Group related imports: `from pathlib import Path, PurePath`
- No local imports inside functions (use TYPE_CHECKING for type-only imports)

### Types & Type Hints
- Use `X | None` over `Optional[X]`
- Use `dict[str, Any]` over `Dict[str, Any]`
- Avoid `Any` where possible; prefer explicit types
- Use `type` for simple type aliases: `type Foo = str | None`
- Mark untyped external calls with `# type: ignore[attr-defined]`
- Put shared type definitions in `types.py` within the module (e.g., `tape/types.py` for tape types)

### Code Quality
- **Strict type checking is enforced** - all code must pass mypy
- Run `just check` (lint + typecheck) before committing
- No deferred type annotations - fix type errors immediately

### Functions & Classes
- Keep functions focused (< 50 lines); use composable helpers
- Use dataclasses for simple data containers, Pydantic for validated models
- Prefer early returns over deeply nested conditionals
- Use `@staticmethod` for pure utilities, `@classmethod` for alternate constructors

### Error Handling
- Use custom exceptions inheriting from `Exception` or `BubError` base class
- Catch specific exceptions, not bare `except:` clauses
- Raise with context: `raise ValueError("msg") from original_exc`
- Log errors with `loguru`: `log.error("context: {detail}", detail=val)`

### Async
- Use `async def` for I/O-bound operations; avoid blocking in async context
- Use `await` only inside async functions; use `run_in_executor` for sync libs

### Testing

> **DEVELOPER ONLY**: Testing is for development verification only. The agent should NOT run tests unless the user explicitly asks for it.

- Framework: `pytest` with `pytest-asyncio`
- Name files: `tests/test_<feature>.py`
- Name tests by behavior: `test_user_shell_failure_falls_back_to_model`
- Use fixtures from `conftest.py` for shared setup
- Prefer `pytest.raises` for exception testing
- Cover: router semantics, loop stop conditions, tape/anchor behavior, channel dispatch

## Commit & Pull Request Guidelines

> **DEVELOPER ONLY**: These guidelines are for human developers creating pull requests.

- Follow Conventional Commit style: `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`
- Keep commits focused; avoid mixing refactor and behavior change
- PRs should include:
  - what changed and why
  - impacted paths/modules
  - verification output from developer-run checks (`ruff`, `mypy`, `pytest`)
  - docs updates when CLI behavior, commands, or architecture changes

## Security & Configuration
- Use `.env` for secrets (`OPENROUTER_API_KEY`, `BUB_BUS_TELEGRAM_TOKEN`); never commit keys
- Validate Telegram allowlist (`BUB_BUS_TELEGRAM_ALLOW_FROM`) before enabling production bots
- Never log sensitive data (API keys, tokens, passwords)

## Pre-commit Hooks
The project uses prek for pre-commit hooks (installed via `just install`):
- Runs ruff, isort, trailing-whitespace checks before commits
- Skip hooks with `--no-verify` only when absolutely necessary

## Settings

Settings are split into focused components:

```python
from bub.config import TapeSettings, BusSettings, AgentSettings, Settings

# Individual settings
tape = TapeSettings()          # BUB_TAPE_* env vars
bus = BusSettings()           # BUB_BUS_* env vars
agent = AgentSettings()       # BUB_AGENT_* env vars
bus = BusSettings()           # BUB_BUS_* env vars
chat = ChatSettings()          # BUB_* env vars

# Unified (backwards compatible)
settings = Settings()
```

### Environment Variables

| Prefix | Settings | Examples |
|--------|----------|----------|
| `BUB_TAPE_` | TapeSettings | `BUB_TAPE_HOME`, `BUB_TAPE_NAME` |
| `BUB_BUS_` | BusSettings | `BUB_BUS_PORT`, `BUB_BUS_TELEGRAM_TOKEN` |
| `BUB_` | ChatSettings | `BUB_MODEL`, `BUB_MAX_STEPS` |

## Key APIs

### FileTapeStore (`src/bub/tape/store.py`)
```python
from bub.tape.store import FileTapeStore
from pathlib import Path

store = FileTapeStore(home=Path(".bub"), workspace_path=Path.cwd())

# Tape operations
store.create_tape("main", title="My Session")
store.get_title("main")
store.set_title("main", "New Title")
store.list_tapes()
store.read("main", from_entry_id=10, to_entry_id=50)
store.append("main", entry)
store.fork("main")                                    # fork from start
store.fork("main", "fork1")                          # fork with name
store.fork("main", from_entry=("main", 50))         # fork from entry 50
store.fork("main", from_anchor="phase1")             # fork from anchor
store.archive("main")
store.reset("main")

# Anchor operations
store.create_anchor("phase1", "main", 50, {"summary": "done"})
store.get_anchor("phase1")
store.list_anchors()
store.resolve_anchor("phase1")
```

### WebSocketMessageBus (`src/bub/channels/wsbus.py`)
```python
from bub.channels.wsbus import WebSocketMessageBus, WebSocketMessageBusClient

# Server mode
bus = WebSocketMessageBus(host="localhost", port=7892)
await bus.start_server()
await bus.publish("topic", {"data": "value"})
sub_id = await bus.subscribe("topic", handler)
await bus.publish_inbound(message)
await bus.publish_outbound(message)

# Client mode
client = WebSocketMessageBusClient("ws://localhost:7892")
await client.connect()
await client.publish("topic", {"data": "value"})
```

See [Utility Scripts](#bus-cli-commands) for the `bub bus` CLI commands.

### TapeMeta (`src/bub/tape/types.py`)
```python
from bub.tape.types import Anchor, Manifest, TapeMeta

# Manifest is in-memory data structure; file I/O is in FileTapeStore
```

## Code Review Findings

### Type Design Principles

Types are classified into two categories:

#### 1. Data Types
Data types are concrete types where the class itself is both the definition and the type. Use dataclasses, Pydantic models, or simple classes.

```python
# Good - dataclass is both definition and type
from dataclasses import dataclass

@dataclass
class Anchor:
    name: str
    tape_id: str
    entry_id: int
    state: dict[str, Any] | None = None

def find_anchor(anchors: list[Anchor], name: str) -> Anchor | None:
    ...
```

#### 2. Behavior Protocols (Interfaces)
Protocols define behavior contracts. They are defined in `types.py` and implemented in `runtime.py` (or similar) within the same module.

```
src/bub/app/
├── types.py      # Protocol definitions only
└── runtime.py   # Concrete implementations
```

**Protocol Definition (types.py):**
```python
# In app/types.py - no circular imports
class TapeStore(Protocol):
    """Protocol for tape store implementations."""

    def create_tape(self, tape: str, title: str | None = None) -> str: ...
    def read(self, tape: str) -> list[TapeEntry] | None: ...
    def append(self, tape: str, entry: TapeEntry) -> None: ...
```

**Protocol Implementation (runtime.py):**
```python
# In app/runtime.py
from app.types import TapeStore
from bub.tape.store import FileTapeStore

class FileTapeStoreAdapter(TapeStore):
    """Adapter for FileTapeStore."""

    def __init__(self, store: FileTapeStore) -> None:
        self._store = store

    def create_tape(self, tape: str, title: str | None = None) -> str:
        return self._store.create_tape(tape, title)

    def read(self, tape: str) -> list[TapeEntry] | None:
        return self._store.read(tape)

    def append(self, tape: str, entry: TapeEntry) -> None:
        self._store.append(tape, entry)
```

#### 3. Avoid `TYPE_CHECKING`, `Any`, and `object` Types
- **Never use `TYPE_CHECKING`** for type imports - it's a code smell indicating a circular import problem
- **Never use `Any`** - it defeats the purpose of static typing
- **Never use `object`** as a type hint - it's too vague and equivalent to `Any`

**Exceptions**:
- `TYPE_CHECKING` may be used to break circular imports between deeply nested modules (e.g., core ↔ channels), but this should be rare and documented.
- `Any` is acceptable for pydantic BaseSettings `__init__` kwargs, because pydantic handles runtime validation from unstructured input (env vars, .env files) to typed objects.

#### 4. Root Cause: Circular Imports
Using `TYPE_CHECKING`, `Any`, or `object` typically indicates a circular import problem. Instead of workarounds, fix the root cause by extracting protocols to a dedicated types module.

When defining protocols, use concrete types for all attributes:
```python
# Good - concrete types
class AgentSettings(Protocol):
    model: str
    max_tokens: int

# Bad - too vague
class BadSettings(Protocol):
    settings: object  # Never do this
```

#### 5. Test Without Full Bundles
- Extract pure functions from classes for testing
- Test individual behaviors, not full integration
- Example: `reset_session_context()` and `cancel_active_inputs()` are tested as standalone functions

```python
# Good - test the function directly
from app.runtime import reset_session_context

def test_reset_session_context():
    sessions = {"id": DummySession()}
    reset_session_context(sessions, "id")
    assert sessions["id"].calls == 1

# Bad - requires building full AgentRuntime with all dependencies
def test_agent_runtime():
    runtime = build_runtime(workspace)  # Too heavy for unit tests
```

### Observed Patterns

#### 1. Null Check Patterns
- **Location-based null checks**: Prefer initializing contextual objects in `__init__` rather than checking for None throughout the code. Example: `meta.title if meta else None` is acceptable but consider requiring meta to exist upfront.
- **Update methods**: Checking `if key not in dict` before update is appropriate for enforcing invariants.
- **Component None checks**: When a None check targets a component (not runtime messages or data being processed), it should only happen at `__init__`. If the component is required for valid operation, crash immediately with a clear error. If optional with a sensible default, set the default in `__init__`:
  ```python
  # Good - crash immediately if required
  def __init__(self, bus: MessageBus):
      if bus is None:
          raise ValueError("bus is required for AgentLoop")
      self._bus = bus

  # Good - sensible default at __init__
  def __init__(self, *, timeout: int | None = None):
      self._timeout = timeout if timeout is not None else 30
  ```
- **Anti-pattern**: Checking `if bus is not None` outside of `__init__` on a component is an anti-pattern. The component should be required at construction time, not checked at runtime.

#### 2. Delegate Pattern (FileTapeStore → Manifest)
- FileTapeStore delegates many methods to Manifest (create_anchor, get_anchor, etc.)
- This is acceptable for encapsulation; consider using `__getattr__` if delegation grows significantly

#### 3. CLI Initialization Pattern (Duplication)
- Each CLI command repeats: workspace resolution, settings loading, store creation, Console instantiation
- Consider extracting a shared callback or helper function:
  ```python
  def _get_store(workspace: Path | None) -> FileTapeStore:
      resolved = (workspace or Path.cwd()).resolve()
      return build_tape_store(load_settings(resolved), resolved)
  ```

#### 4. WebSocket Server/Client Duplication
- publish_inbound/publish_outbound and on_inbound/on_outbound are identical in both classes
- Consider extracting a mixin or base class for shared pub/sub logic

#### 5. Datetime Parsing (Manifest.load)
- Duplicate datetime parsing: `datetime.fromisoformat(...) if ... else datetime.now(UTC)`
- Extract to helper: `_parse_datetime(data: dict, key: str) -> datetime`

## Utility Scripts

### Bus CLI Commands

The `bub bus` subcommand provides utilities for interacting with the WebSocket message bus:

```bash
# Start the bus server (pure message router)
uv run bub bus serve

# Send a message to a topic and wait for responses
uv run bub bus send "hello world" --channel telegram --chat-id 123456

# Subscribe to a topic pattern and print messages (planned)
uv run bub bus recv --topic "telegram:*"
```

**Architecture**: All components (agent, telegram-bridge, CLI tools) connect to the bus as JSON-RPC clients. The bus server is a pure message router with no embedded channel logic.

**Telegram Integration**: Telegram is being extracted from the bus server into a standalone bridge process (`bub telegram-bridge` or similar) that connects to wsbus as a proper JSON-RPC client. The bridge handles:
- Telegram Bot API communication
- Message format conversion (Telegram JSON ↔ Bus JSON-RPC)
- Inbound message publishing to the bus
- Outbound message handling from the bus

### Production Deployment (`scripts/deploy-production.sh`)
Systemd-based production deployment script for managing Bub components as user services.

**Components:**
- `bus` - WebSocket message bus server (port 7892)
- `agent` - Agent worker process
- `tape` - Tape store REST API service (port 7890)
- `telegram-bridge` - Telegram Bot API bridge (connects to bus as JSON-RPC client) [planned]

**Commands:**
```bash
# Start components
./scripts/deploy-production.sh start bus      # Start message bus
./scripts/deploy-production.sh start agent    # Start agent worker
./scripts/deploy-production.sh start tape     # Start tape service
./scripts/deploy-production.sh start telegram-bridge  # Start Telegram bridge [planned]

# Monitor and manage
./scripts/deploy-production.sh logs agent     # Follow agent logs
./scripts/deploy-production.sh status tape    # Check tape service status
./scripts/deploy-production.sh list           # List all running components
./scripts/deploy-production.sh stop bus       # Stop message bus
./scripts/deploy-production.sh stop telegram-bridge  # Stop Telegram bridge [planned]
```

**Features:**
- Uses `systemd-run` for process management with automatic cleanup
- **Auto-restart on failure** (`Restart=always`) with 5-second delay
- **Rate limiting**: Max 3 restarts per minute to prevent restart loops
- Persists unit names in `run/` directory for lifecycle management
- Integrates with `journalctl` for centralized logging
- Sets proper working directory and environment variables

**Restart Behavior:**
- Services automatically restart if they crash or exit with error
- 5-second delay between restart attempts
- After 3 failed restarts within 1 minute, systemd stops trying
- Check restart count: `systemctl --user show <unit> | grep NRestarts`

### Documentation Server (`scripts/docs-server.sh`)
MkDocs documentation server with live reload via systemd.

```bash
./scripts/docs-server.sh start [port]   # Start on port (default: 8000)
./scripts/docs-server.sh stop           # Stop server
./scripts/docs-server.sh status         # Check status
./scripts/docs-server.sh logs           # View logs
```

### Test/Debug Scripts

Located in `scripts/` directory for testing specific integrations:

#### MiniMax API Testing
- **`test_minimax_tools.py`** - Direct OpenAI SDK tests for MiniMax tool calling
  - Tests: basic chat, tool calls, tool results with OpenAI format
  - Usage: `uv run python scripts/test_minimax_tools.py`

- **`test_minimax_format.py`** - Check MiniMax response format details
  - Dumps complete API response structure
  - Usage: `uv run python scripts/test_minimax_format.py [API_KEY]`

- **`test_republic_minimax.py`** - Test MiniMax through Republic client
  - Validates tool_calls() and raw response parsing
  - Usage: `uv run python scripts/test_republic_minimax.py`

#### Bub Integration Testing
- **`test_bub_minimax_flow.py`** - Test Bub's LLM configuration flow
  - Tests settings loading, tape store, LLM client setup
  - Validates end-to-end tool calling with Bub's stack
  - Usage: `uv run python scripts/test_bub_minimax_flow.py`

- **`test_tape_tool_calls.py`** - Debug tape recording of tool calls
  - Checks what's actually stored on tape after tool calls
  - Tests both tool_calls() and run_tools() methods
  - Usage: `uv run python scripts/test_tape_tool_calls.py`

#### Bus Testing
- **`test_bus_client.py`** - WebSocket bus test client
  - Simulates Telegram messages via WebSocket
  - Tests JSON-RPC initialization, subscription, message sending
  - Usage: `uv run python scripts/test_bus_client.py [message]`

**Environment Setup:**
All test scripts automatically load `.env` file and configure paths. Ensure required API keys are set in `.env`:
- `BUB_AGENT_API_KEY` or `MINIMAX_API_KEY` for MiniMax tests
- `BUB_BUS_TELEGRAM_TOKEN` for Telegram-related tests

---

## Journal Directory

We maintain a `./journal` directory for daily development journals. Each journal entry is a markdown file named with the date (e.g., `2026-02-16.md`).

**Purpose**: Focus on what was accomplished each day, issues encountered, decisions made, and lessons learned.

**Structure**:
```
journal/
├── 2026-02-16.md          # Today's work
├── 2026-02-15.md          # Previous day's work
└── README.md              # Index of journal entries (optional)
```

**Content Guidelines**:
- Date-based filename: `YYYY-MM-DD.md`
- Overview of the day's work
- Issues discovered and how they were fixed
- Architecture decisions made
- Testing approach and results
- Files modified
- Lessons learned
- Follow-up actions (completed and TODO)

**Example**: See `journal/2026-02-16.md` for a comprehensive example covering MiniMax API integration debugging.

---

## Subagent Workflow

When working on complex multi-step tasks, use the following workflow to coordinate with subagents:

### Overview
1. **Plan**: Break down the task into concrete todo items
2. **Spawn**: Create subagents for each todo item with complete context
3. **Wait**: Wait for subagent to complete and report results
4. **Update**: Adjust plan based on results
5. **Repeat**: Continue with next todo item

### Step-by-Step Process

#### 1. Plan the Task
Create a todo list with specific, actionable items:
```python
# Example todo list for debugging
[
    {"content": "Create minimal reproducible script", "status": "in_progress", "priority": "high"},
    {"content": "Run script to identify root cause", "status": "pending", "priority": "high"},
    {"content": "Fix identified issue", "status": "pending", "priority": "high"},
    {"content": "Verify fix with end-to-end test", "status": "pending", "priority": "medium"}
]
```

#### 2. Spawn a Subagent
For each todo item, spawn a subagent with:

**Required Context**:
- Complete background information
- What has been done so far
- What the current issue is
- Relevant file paths
- Any error messages or logs

**Clear Goal**:
- Specific task to accomplish
- Expected outcome

**Expected Result Format**:
- What should be reported back
- File paths of created/modified files
- Test results
- Any issues encountered

**Example Prompt**:
```
You are a subagent working on debugging MiniMax API integration.

**Context**:
- We're debugging tool calling issues with MiniMax API
- Republic client works fine in isolation
- The issue may be in Bub's integration layer
- Test scripts are in scripts/ directory

**Your Task**:
Create a minimal test script at scripts/test_debug.py that:
1. Sets up minimal Bub environment
2. Tests tool call round trip
3. Prints debug info at each step

**Expected Result**:
- Confirm script was created
- Show test output
- Identify where breakdown occurs (if any)
- Report specific file paths and line numbers

**Important**: Do NOT spawn additional subagents. If the task is too complex, report it as an issue with suggestions for subdivision.
```

#### 3. Wait and Review
Wait for the subagent to complete and review the results:
- Check if task was completed successfully
- Review any findings or issues reported
- Verify files were created/modified correctly

#### 4. Update the Plan
Based on subagent results:
- Mark completed todos as "completed"
- Add new todos if issues were discovered
- Update todo descriptions based on findings
- Adjust priorities if needed

#### 5. Repeat
Continue with the next todo item until all tasks are complete.

### Subagent Constraints

**Subagents MUST NOT**:
- Spawn additional subagents
- Create new todos
- Modify the main todo list
- Make architectural decisions without reporting back

**If Task is Too Complex**:
If a single todo item proves too complex, the subagent should:
1. Report the issue clearly
2. Describe what was attempted
3. Suggest how to subdivide the task
4. Provide optional breakdown suggestions

**Example Report**:
```
**Issue**: Task too complex - require deeper investigation

**Attempted**: Created test script but discovered 3 separate issues:
1. Bus handler notification bug
2. Message format conversion issue  
3. Tape recording bug

**Suggestion**: Split into 3 separate todo items:
- Fix bus handler notification in wsbus.py
- Debug message format in republic_client.py
- Investigate tape recording in server.py

**Current Status**: Test script created at scripts/test_issue.py with baseline tests.
```

### Best Practices

1. **Clear Scope**: Each todo should be completable in a single subagent session
2. **Complete Context**: Always provide full context - subagents don't see previous conversations
3. **Specific Goals**: Define exactly what success looks like
4. **Verification**: Always include how to verify the work (tests, checks, etc.)
5. **Iterate**: Don't try to plan everything upfront - adjust based on findings
6. **Document**: Update the journal with findings from each subagent

### Example Workflow

```python
# Initial todo list
todos = [
    {"content": "Debug MiniMax role error", "status": "in_progress", "priority": "high"},
    {"content": "Fix tape server bug", "status": "pending", "priority": "high"}
]

# Spawn subagent for first task
task("Debug MiniMax role error", context=...)

# Review results, update todos
todos[0]["status"] = "completed"
todos[1]["status"] = "in_progress"

# Spawn subagent for second task
task("Fix tape server bug", context=...)

# Continue until complete
```
