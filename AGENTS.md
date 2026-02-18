## Start Here (Docs)

Use these dedicated docs for details:

- Components & relationships: `docs/components.md`
- Architecture & determinism: `docs/architecture.md`
- Agent protocol (transport): `docs/agent-protocol.md`
- Agent messages (payload types): `docs/agent-messages.md`
- Interactive CLI: `docs/cli.md`
- Scripts, testing, debugging: `docs/testing.md`
- Deployment: `docs/deployment.md`

For the most up-to-date “what changed”, prefer the newest entry in `journal/`.

## Workflow Warm Up

At the start of each session:

1. Read this document.
2. Check the latest entry in `journal/` to understand recent changes and known issues.
3. Verify project structure (working directory, git status, etc.).

## Core Principles (Keep These)

### Skill-First

- Keep this file focused on principles, workflows, and conventions.
- Put detailed “how to run X” procedures in dedicated docs (or skills) so they don’t go stale.

Project skills live under `.agent/skills/` (authoritative procedures).

### Save Standard, Call by Adapting

- Store messages on tape in the standard OpenAI-compatible format.
- Convert to provider-specific formats at the boundary.

(See `docs/architecture.md` and `src/bub/llm/adapters.py`.)

### Don’t Autonomously Run Commands

Unless explicitly asked:

- Don’t run tests, scripts, linters, deployments, or “health check” commands.
- If verification is needed, propose minimal commands and wait.

## Subagent Workflow

When working on complex multi-step tasks, use subagents to split work into independent threads (e.g., protocol types + implementation + caller updates).

### Overview

1. **Plan**: Break down the task into concrete todo items.
2. **Spawn**: Create subagents for each todo item with complete context.
3. **Wait**: Wait for each subagent to complete and report results.
4. **Update**: Adjust plan based on results.
5. **Repeat**: Continue with next todo item.

### Step-by-Step Process

#### 1. Plan the Task

Create a todo list with specific, actionable items:

```python
# Example todo list for debugging
[
    {"content": "Create minimal reproducible script", "status": "in_progress", "priority": "high"},
    {"content": "Run script to identify root cause", "status": "pending", "priority": "high"},
    {"content": "Fix identified issue", "status": "pending", "priority": "high"},
    {"content": "Verify fix with end-to-end test", "status": "pending", "priority": "medium"},
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
- Test results (only if explicitly asked to run tests)
- Any issues encountered

**Prompt Template**:

```
You are a subagent working on <topic>.

Context:
- <what’s happening>

Task:
1) <step>
2) <step>

Expected result:
- <what to report back>

Constraints:
- Do NOT spawn more subagents.
- Do not run commands unless asked.
```

#### 3. Wait and Review

Wait for the subagent to complete and review the results:

- Check if task was completed successfully.
- Review findings and verify constraints were followed.
- If results reveal new unknowns, update the plan rather than patching blindly.

#### 4. Update the Plan

Based on subagent results:

- Mark completed todos as completed.
- Add new todos if issues were discovered.
- Update todo descriptions based on findings.

#### 5. Repeat

Continue with the next todo item until all tasks are complete.

### Subagent Constraints

Subagents must not:

- Spawn additional subagents.
- Create/modify the main plan/todo list.
- Make architectural decisions without reporting back.

### Best Practices

- Keep scope tight: one todo item should be completable in one subagent session.
- Provide complete context: subagents don’t have prior conversation state.
- Define success criteria: what to change, where, and how to verify.
- Prefer reporting blockers over guessing when architecture decisions are unclear.
- Write down findings: update today’s journal entry with decisions and outcomes.

## Repository Layout (Short)

- Core code: `src/bub/`
- Tests: `tests/`
- Docs: `docs/`
- Journals: `journal/`
- Debug/integration scripts: `scripts/`

For a component-wise view (bus/tape/agents/channels/CLI), see `docs/components.md`.

## Development Practices

### Build/Test Commands (Reference Only)

The repo uses `uv` + Ruff + mypy + pytest.

(See `docs/testing.md` for script/test facilities; see `docs/deployment.md` for runtime modes.)

### Multi-File Change Protocol

When a change spans multiple files (types → implementations → callers), follow this sequence.

#### Phase 1: Collect

Goal: Gather all affected locations and identify unresolved inconsistencies before making any edits.

- Find all affected files/usages.
- Identify inconsistencies (payload shapes, conflicting types, mismatched expectations).
- Map dependencies: core types → affected components → callers.
- Stop and ask if a key architectural decision is unclear.

#### Phase 2: Plan

Goal: Create a detailed, actionable edit plan that can be executed without surprises.

- Start with core types (protocol/message schemas).
- Update implementations.
- Update callers last.
- If multiple valid approaches exist, stop and ask before editing.

#### Phase 3: Execute

Goal: Implement the plan exactly as designed.

- Follow the plan.
- If the plan breaks during implementation, stop and go back to Phase 1 or Phase 2.

### Overwrite Style Editing

For files requiring substantial changes (>20% of lines or complex refactoring):

1. **Architecture design first** - Document the new structure.
2. **Read entire file** - Understand all components.
3. **Create outline** - List all classes, methods, and their purposes.
4. **Use LSP** - Let language server help identify references.
5. **Draft new outline** - According to the new architecture.
6. **Generate complete new file** - Write from scratch using the outline.
7. **Review with diff** - Compare old vs new (`diff -u old.py new.py`).
8. **Fix type/lint errors** - Before replacing.
9. **Overwrite** - Replace the old file with the new file.

Anti-pattern: Incremental small edits on complex files (creates inconsistent state).

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
- All imports must be at the top of the file (ruff E402)
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

- Strict type checking is enforced - all code must pass mypy
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
- Cover: router semantics, loop stop conditions, tape/anchor behavior, and channel dispatch

(Details and script catalog: `docs/testing.md`.)

## Security & Configuration

- Use `.env` for secrets; never commit keys.
- Validate Telegram allowlists before enabling production bots.
- Never log sensitive data.

## Settings (Env Prefixes)

| Prefix | Settings | Examples |
|--------|----------|----------|
| `BUB_TAPE_` | Tape settings | `BUB_TAPE_HOME`, `BUB_TAPE_NAME` |
| `BUB_BUS_` | Bus settings | `BUB_BUS_PORT`, `BUB_BUS_TELEGRAM_TOKEN` |
| `BUB_` | Chat settings | `BUB_MODEL`, `BUB_MAX_STEPS` |

## Journal Directory

We maintain a `./journal` directory for daily development journals. Each journal entry is a markdown file named with the date (e.g., `2026-02-18.md`).

### Purpose

- Keep a fast, accurate record of what changed, what broke, what we did, and what we learned.
- Make it easy to pick up the work later (or hand off to someone else).

### Structure

```
journal/
├── 2026-02-18.md          # Today's work
├── 2026-02-16.md          # Previous work
└── README.md              # Index of journal entries (optional)
```

### How to Read (Warm Up)

- Start with the newest entry.
- Skim for: current focus, unresolved issues, key decisions, and follow-ups.

### How to Update (During/After Work)

- Append notes to today’s file (`journal/YYYY-MM-DD.md`).
- If today’s file does not exist, create it.
- Keep entries brief and structured; include:
  - What changed and why
  - Issues found + fix status
  - Decisions made (especially protocol/schema choices)
  - Tests or verification performed (only if explicitly run)
  - Follow-ups / TODOs

