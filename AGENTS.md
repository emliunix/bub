# Repository Guidelines

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

Tests are in `tests/`. Documentation is in `docs/`. Legacy implementation is archived in `backup/src_bub_legacy/` (read-only reference).

## Build, Test, and Development Commands
- `uv sync`: install/update dependencies
- `uv pip list`: list installed packages
- `uv pip index versions <package>`: search for package versions
- `just install`: setup env + hooks

## Development Workflow

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

4. Run tests to verify:
   ```bash
   uv run pytest -q
   ```

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
- Framework: `pytest` with `pytest-asyncio`
- Name files: `tests/test_<feature>.py`
- Name tests by behavior: `test_user_shell_failure_falls_back_to_model`
- Use fixtures from `conftest.py` for shared setup
- Prefer `pytest.raises` for exception testing
- Cover: router semantics, loop stop conditions, tape/anchor behavior, channel dispatch

## Commit & Pull Request Guidelines
- Follow Conventional Commit style: `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`
- Keep commits focused; avoid mixing refactor and behavior change
- PRs should include:
  - what changed and why
  - impacted paths/modules
  - verification output (`ruff`, `mypy`, `pytest`)
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
