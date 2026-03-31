# Python Style Guide

General Python coding conventions for the Bub project.

## General

- Python 3.12+, 4-space indentation, type hints required for new/modified logic
- Line length: 120 characters (enforced by ruff)
- Format/lint with Ruff; type-check with mypy

## Naming Conventions

- `snake_case`: functions, variables, modules, methods
- `PascalCase`: classes, exceptions, type aliases
- `UPPER_CASE`: constants, enum values
- Private implementation: prefix with underscore `_internal()` or `__dunder`
- Avoid single-letter names except: `i`/`j`/`k` for loops, `x`/`y`/`z` for coordinates, `e` for exceptions

## Imports

- Use absolute imports: `from bub.core import router`
- Sort imports with ruff (isort rules): stdlib → third-party → local
- All imports must be at the top of the file (ruff E402)
- Avoid wildcard imports (`from x import *`)
- Group related imports: `from pathlib import Path, PurePath`
- No local imports inside functions (use TYPE_CHECKING for type-only imports)

## Types & Type Hints

- Use `X | None` over `Optional[X]`
- Use `dict[str, Any]` over `Dict[str, Any]`
- Avoid `Any` where possible; prefer explicit types
- Use `type` for simple type aliases: `type Foo = str | None`
- Mark untyped external calls with `# type: ignore[attr-defined]`
- Put shared type definitions in `types.py` within the module (e.g., `tape/types.py` for tape types)
- Use `@override` decorator from `typing` when overriding methods from parent classes

## Code Quality

- Strict type checking is enforced - all code must pass mypy
- No deferred type annotations - fix type errors immediately

## Functions & Classes

- Keep functions focused (< 50 lines); use composable helpers
- Use dataclasses for simple data containers, Pydantic for validated models
- Prefer early returns over deeply nested conditionals
- Use `@staticmethod` for pure utilities, `@classmethod` for alternate constructors
- See [`plain-objects.md`](plain-objects.md) for dataclass initialization and equality patterns

## Error Handling

- Use custom exceptions inheriting from `Exception` or `BubError` base class
- Catch specific exceptions, not bare `except:` clauses
- Raise with context: `raise ValueError("msg") from original_exc`
- Log errors with `loguru`: `log.error("context: {detail}", detail=val)`

## Async

- Use `async def` for I/O-bound operations; avoid blocking in async context
- Use `await` only inside async functions; use `run_in_executor` for sync libs

## Testing

- Framework: `pytest` with `pytest-asyncio`
- Name files: `tests/test_<feature>.py`
- Name tests by behavior: `test_user_shell_failure_falls_back_to_model`
- Use fixtures from `conftest.py` for shared setup
- Prefer `pytest.raises` for exception testing
- Cover: router semantics, loop stop conditions, tape/anchor behavior, and channel dispatch

See also: [`docs/testing.md`](../testing.md) for detailed testing guide.
