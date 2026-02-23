## Start Here (Docs)

Use these dedicated docs for details:

- Components & relationships: `docs/components.md`
- Architecture & determinism: `docs/architecture.md`
- Agent protocol (transport): `docs/agent-protocol.md`
- Agent messages (payload types): `docs/agent-messages.md`
- Interactive CLI: `docs/cli.md`
- Scripts, testing, debugging: `docs/testing.md`
- Deployment: `docs/deployment.md`

For the most up-to-date "what changed", prefer the newest entry in `journal/`.

## Workflow Warm Up

At the start of each session:

1. Read this document.
2. Check the latest entry in `journal/` to understand recent changes and known issues.
3. **Check relevant skills** - Read `.agent/skills/skill-management/SKILL.md` first, then domain-specific skills.
4. Verify project structure (working directory, git status, etc.).

## Core Principles (Keep These)

### Skill-First Checking (Required)

**Before starting any work**, check relevant skills and read them.

**Entry Point**: Start with `.agent/skills/skill-management/SKILL.md` - it catalogs all available skills and provides the skill-first workflow.

**Note:** Skills exist in two locations:
- **Project skills** (`.agent/skills/`): Project-specific conventions (docs, testing, deployment, etc.)
- **System skills** (`/home/liu/.claude/skills/`): Global, reusable tools (python-uv, skill-creator, etc.)

**Relevance is defined by:**
- **Domain**: The topic area (docs, testing, deployment, bus, etc.)
- **Technology**: Tools/frameworks involved (mkdocs, pytest, systemd, websockets)
- **File type**: What you're modifying (.md → docs skill, .py tests → testing skill)
- **Operation**: What you're doing (serving docs → docs skill, deploying → deployment skill)

**Mandate:**
- If a skill exists for your domain/tech/operation, **you MUST read it first**
- Skills contain authoritative conventions that prevent errors
- Skipping skill review leads to rework (e.g., wrong table formatting, invalid mermaid)

**Example:**
- Writing documentation → Read `.agent/skills/docs/SKILL.md` first
- Running tests → Read `.agent/skills/testing/SKILL.md` first  
- Using deployment scripts → Read `.agent/skills/deployment/SKILL.md` first
- Working with bus CLI → Read `.agent/skills/bus-cli/SKILL.md` first

**To list available skills:**
```bash
ls -la .agent/skills/
```

### Save Standard, Call by Adapting

- Store messages on tape in the standard OpenAI-compatible format.
- Convert to provider-specific formats at the boundary.

(See `docs/architecture.md` and `src/bub/llm/adapters.py`.)

### Don't Autonomously Run Commands

Unless explicitly asked:

- Don't run tests, scripts, linters, deployments, or "health check" commands.
- If verification is needed, propose minimal commands and wait.

### System Components: Use Deployment Scripts

**Always use deployment scripts** to manage bus and agents, even during development and testing.

**Why:**
- Ensures journalctl log aggregation (centralized debugging)
- Proper systemd process management and auto-restart
- Consistent configuration across dev/prod environments

**Correct:**
```bash
./scripts/deploy-production.sh start bus          # Start bus
./scripts/deploy-production.sh logs bus           # View logs via journalctl
./scripts/deploy-production.sh status bus         # Check status
./scripts/deploy-production.sh stop bus           # Stop cleanly
```

**Wrong:**
```bash
uv run bub bus serve          # Bypasses deployment, no journalctl logs
```

**Exception:** One-shot CLI commands (like `bub bus status`) that connect to an already-running bus are fine to run directly.

## Subagent Workflow

When working on complex multi-step tasks, use subagents to split work into dependency-ordered todos. Each subagent starts as a blank slate and receives a curated "context closure" containing everything it needs to work independently.

### What (The Pattern)

A sequential workflow where:
- Todos are structured as a dependency chain (DAG)
- Each subagent receives a complete yet bounded context closure
- Parent agent orchestrates, maintains state, and adjusts the plan as facts unfold
- Results flow forward to enrich context for subsequent tasks

### How (The Mechanics)

#### 1. Plan with Dependencies

Structure todos as a directed acyclic graph where each task builds on previous results:

```python
# Example: Todos with explicit dependencies
[
    {"content": "1. Design schema for user API", "status": "in_progress", "priority": "high"},
    {"content": "2. Implement API endpoints (depends on #1)", "status": "pending", "priority": "high"},
    {"content": "3. Add validation middleware (depends on #2)", "status": "pending", "priority": "high"},
    {"content": "4. Write tests for endpoints (depends on #2)", "status": "pending", "priority": "medium"},
]
```

**Key**: Dependencies are structural. Task 2 cannot succeed without Task 1's output.

#### 2. Prepare Context Closure

Before spawning each subagent, curate a context closure—relevant information that is complete yet bounded (like a mathematical closure):

**Include in the closure**:
- Project structure overview (key directories, conventions)
- Relevant documentation paths
- Accumulated decisions and findings from previous subagents
- Error patterns or constraints discovered
- Specific files/code relevant to the current task

**Context Overflow Strategy**:
When accumulated findings grow too large for a prompt (>2-3 paragraphs of dense context):
1. Save to a working document: `docs/working/<task-name>-context.md`
2. Pass to subagent: `See full context in docs/working/api-impl-context.md - includes schema decisions from #1 and error patterns discovered`
3. Include only the most critical 2-3 facts inline

#### 3. Spawn Subagent

Spawn with the context closure + specific task + constraints:

```
You are a subagent working on <topic>.

Project Context:
- Repository: Python project using FastAPI in src/api/
- Key files: src/api/models.py, src/api/routes.py
- Conventions: Follow existing patterns in routes.py

Accumulated Findings:
- Schema decision (from #1): Using Pydantic v2 with camelCase aliases
- Discovered constraint: Must support both JSON and form data
- Error pattern: Previous attempt failed due to missing validation

Current Task:
Implement POST /users endpoint following the schema from docs/working/schema-context.md

Expected Result:
- Modified src/api/routes.py with new endpoint
- Validation logic matching schema spec
- Report any deviations needed from the schema

Constraints:
- Do NOT spawn more subagents
- Do not run tests unless explicitly asked
- Report blockers immediately rather than guessing
```

#### 4. Review & Adjust

After each subagent completes:

1. **Mark todo complete** and capture key findings
2. **Adjust dependent todos** based on discoveries:
   - If Task 1 revealed the schema needs changes → update Task 2's description
   - If new constraints emerged → add them to subsequent todos
   - If unexpected issues found → insert new todos or reprioritize
3. **Enrich the context closure** with new facts for the next subagent

**Example adjustment**:
```python
# Before
{"content": "2. Implement API endpoints (depends on #1)", ...}

# After discovering auth requirement in #1
{"content": "2. Implement API endpoints with JWT auth (depends on #1)", ...}
```

#### 5. Repeat

Pass the enriched context closure to the next subagent. Continue until all todos complete.

### Why (The Rationale)

**Subagents are tabula rasa**: Each subagent starts with zero knowledge of your project structure, conventions, or previous decisions. Without adequate context, they will:
- Waste time exploring the codebase
- Make incorrect assumptions
- Produce work that doesn't integrate with existing code

**Dependencies are structural**: In multi-file changes, later tasks literally cannot begin until earlier tasks produce their outputs. Sequential execution respects these constraints.

**Plans are provisional hypotheses**: Each subagent execution reveals new facts—unexpected constraints, better approaches, hidden dependencies. Rigid plans fail; dynamic replanning succeeds.

**Context must be a closure**: Too little context → confusion and wrong turns. Too much context → noise and token waste. Curate what's relevant and sufficient for the specific task at hand.

**Overflow happens naturally**: Complex investigations generate more context than fits in a prompt. The filesystem is the right place for large context; prompts should reference it with curated highlights.

### Subagent Constraints

Subagents must not:

- Spawn additional subagents
- Create/modify the main plan/todo list
- Make architectural decisions without reporting back
- Run commands unless explicitly asked

### Best Practices

- **Keep scope tight**: One todo item should be completable in one subagent session (15-30 min of focused work)
- **Curate context like a closure**: Include what's relevant and sufficient—not everything, not nothing
- **Use overflow strategy**: When context grows large, save to `docs/working/` and pass the path
- **Define success criteria**: What to change, where, and how to verify
- **Prefer reporting blockers**: When architecture decisions are unclear, report back rather than guess
- **Write down findings**: Update today's journal entry with decisions, deviations, and outcomes
- **Pass findings forward**: Each subagent's results become part of the next subagent's context closure

## Repository Layout (Short)

- Core code: `src/bub/`
- Tests: `tests/`
- Docs: `docs/`
- Journals: `journal/`
- Debug/integration scripts: `scripts/`

For a component-wise view (bus/tape/agents/channels/CLI), see `docs/components.md`.

## Type System Architecture

When moving types between modules during refactoring:

- **Migrate imports, don't re-export**: Update all affected imports to point to the new canonical location. Don't leave re-exports in the old location as a compatibility shim.
- **Why**: Re-exports hide the true source of types, making the codebase harder to understand and maintain. They also break when the original module changes.

## Development Practices

### Build/Test Commands (Reference Only)

The repo uses `uv` + Ruff + mypy + pytest.

**Always use `uv run` to execute Python commands.** This ensures dependencies are properly managed:

```bash
# Run CLI commands
uv run python -m bub.cli.bus recv "*"

# Run scripts
uv run scripts/validate_system.py

# Run tests
uv run pytest tests/test_bus.py
```

Do not use `python -m` directly or set `PYTHONPATH` manually.

(See `docs/testing.md` for script/test facilities; see `docs/deployment.md` for runtime modes.)

### Operations Guide

**Use the deployment script for managing components:**

```bash
# Start all components
./scripts/deploy-production.sh start all

# Start individual components
./scripts/deploy-production.sh start bus
./scripts/deploy-production.sh start system-agent
./scripts/deploy-production.sh start telegram-bridge

# View logs
./scripts/deploy-production.sh logs bus              # Follow logs
./scripts/deploy-production.sh logs all              # All components
./scripts/deploy-production.sh logs system-agent -n 50  # Last 50 lines

# Check status
./scripts/deploy-production.sh status bus

# Stop components
./scripts/deploy-production.sh stop bus
./scripts/deploy-production.sh stop all              # Stop everything including dynamic agents

# List running components
./scripts/deploy-production.sh list
```

**Key Points:**
- The deployment script uses `systemd-run` to manage services with automatic restart
- Unit names are tracked in `run/*.unit_name` files
- Logs are available via `journalctl --user -u <unit-name>`
- Dynamic agents (conversation agents) are also tracked and can be stopped by name

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

We maintain a `./journal` directory for daily development journals. Journal files follow the format `YYYY-MM-DD-topic.md` (e.g., `2026-02-18-router-bug.md`).

### Purpose

- Keep a fast, accurate record of what changed, what broke, what we did, and what we learned.
- Make it easy to pick up the work later (or hand off to someone else).

### Structure

```
journal/
├── 2026-02-18-router-bug.md    # Router issue investigation
├── 2026-02-18-cli-refactor.md  # CLI refactoring work  
└── 2026-02-16-protocol.md      # Protocol changes
```

### Append-Only Style

When writing to the journal:

1. **Check the most recent journal file** for the current date
2. **If it's the same topic**: Append to that file
3. **If it's a different topic**: Create a new file with format `YYYY-MM-DD-topic.md`
4. **If no journal exists for today**: Create a new file

Example: If the latest file is `2026-02-18-router-bug.md` and you're continuing router debugging, append to it. If you're starting work on CLI changes, create `2026-02-18-cli-refactor.md`.

### How to Read (Warm Up)

- Find recent journal files relevant to your current task (check last 2-3 files)
- Skim for: current focus, unresolved issues, key decisions, and follow-ups
- Don't read everything—focus on what's relevant

### What to Write

Keep entries brief and structured; include:
- What changed and why
- Issues found + fix status
- Decisions made (especially protocol/schema choices)
- Tests or verification performed (only if explicitly run)
- Follow-ups / TODOs
