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
- `just install`: setup env + hooks
- `uv run bub chat`: run interactive CLI
- `uv run bub telegram`: run Telegram adapter
- `uv run pytest -q` or `just test`: run all tests
- `uv run pytest tests/test_foo.py`: run specific test file
- `uv run pytest tests/test_foo.py::test_bar`: run specific test function
- `uv run pytest -k "test_name_pattern"`: run tests matching pattern
- `uv run ruff check .`: lint checks
- `uv run ruff check src/bub/file.py`: lint specific file
- `uv run ruff check --fix .`: auto-fix lint issues
- `uv run mypy src`: type-check all source
- `uv run mypy src/bub/file.py`: type-check specific file
- `just check`: lock validation + lint + typing
- `just docs` / `just docs-test`: serve/build docs

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
- Avoid wildcard imports (`from x import *`)
- Group related imports: `from pathlib import Path, PurePath`

### Types & Type Hints
- Use `X | None` over `Optional[X]`
- Use `dict[str, Any]` over `Dict[str, Any]`
- Avoid `Any` where possible; prefer explicit types
- Use `type` for simple type aliases: `type Foo = str | None`
- Mark untyped external calls with `# type: ignore[attr-defined]`
- Put shared type definitions in `types.py` within the module (e.g., `tape/types.py` for tape types)

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
- Use `.env` for secrets (`OPENROUTER_API_KEY`, `BUB_TELEGRAM_TOKEN`); never commit keys
- Validate Telegram allowlist (`BUB_TELEGRAM_ALLOW_FROM`) before enabling production bots
- Never log sensitive data (API keys, tokens, passwords)

## Pre-commit Hooks
The project uses prek for pre-commit hooks (installed via `just install`):
- Runs ruff, isort, trailing-whitespace checks before commits
- Skip hooks with `--no-verify` only when absolutely necessary

## Settings

Settings are split into focused components:

```python
from bub.config import TapeSettings, BusSettings, ChatSettings, Settings

# Individual settings
tape = TapeSettings()          # BUB_TAPE_* env vars
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

### Observed Patterns

#### 1. Null Check Patterns
- **Location-based null checks**: Prefer initializing contextual objects in `__init__` rather than checking for None throughout the code. Example: `meta.title if meta else None` is acceptable but consider requiring meta to exist upfront.
- **Update methods**: Checking `if key not in dict` before update is appropriate for enforcing invariants.

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
