# Workflow Helper Scripts

This directory contains helper scripts for managing the simplified workflow system.

## Overview

The workflow system uses a simplified structure with all files in `./tasks/`:
- **Task files**: `N-slug.md` (e.g., `0-design-api.md`, `1-implement-models.md`)
- **Kanban files**: `N-kanban-slug.md` (e.g., `2-kanban-api-refactor.md`)
- **Global sequenced numbering**: All files share the same numbering sequence

## Scripts

### 1. create-task.py

Creates a new task file with a validated YAML header.

**Usage:**
```bash
# Basic usage (kanban and creator-role are required)
uv run scripts/create-task.py \
    --role Architect \
    --expertise "System Design,Python" \
    --title "Design API Layer" \
    --kanban "tasks/0-kanban-project.md" \
    --creator-role manager

# Full usage with all options
uv run scripts/create-task.py \
    --role Implementor \
    --expertise "Software Engineering,Type Theory" \
    --skills "python-project,testing" \
    --title "Implement Authentication" \
    --kanban "tasks/0-kanban-project.md" \
    --creator-role user \
    --type implement \
    --priority high \
    --dependencies "tasks/0-design-api.md" \
    --refers "tasks/0-design-api.md" \
    --context "Background info here" \
    --files "src/auth.py,tests/test_auth.py" \
    --description "Implement JWT authentication"
```

**Options:**
- `--role, -r` (required): Agent role (Supervisor, Manager, Architect, Implementor)
- `--expertise, -e` (required): Comma-separated expertise areas
- `--title, -t` (required): Task title (used for filename slug)
- `--kanban, -k` (required): Path to kanban file for global context
- `--creator-role, -cr` (required): Role of the creator - must be `manager` or `user`. Only Manager and users are allowed to create tasks; agents (Architect, Implementor) should NEVER create task files directly.
- `--skills, -s`: Comma-separated skills to load
- `--type`: Task type (exploration, design, review, implement, redesign; auto-inferred if not specified)
- `--priority`: Priority level (critical, high, medium, low; default: medium)
- `--dependencies, -d`: Comma-separated task file dependencies
- `--refers`: Comma-separated related task files to reference
- `--context`: Task context/background
- `--files, -f`: Comma-separated list of relevant files
- `--description`: Detailed task description
- `--tasks-dir`: Directory for task files (default: ./tasks)

**Output:**
- Returns the filepath of the created task (e.g., `tasks/0-design-api-layer.md`)

### 2. create-kanban.py

Creates a new kanban file with a validated YAML header and optionally an initial exploration task.

**Usage:**
```bash
# Create kanban with exploration task
uv run scripts/create-kanban.py \
    --title "API Refactor" \
    --request "Refactor the API layer for better performance"

# Create kanban without exploration task
uv run scripts/create-kanban.py \
    --title "Bug Fix" \
    --request "Fix critical authentication bug" \
    --no-exploration
```

**Options:**
- `--title, -t` (required): Kanban title (used for filename)
- `--request, -r` (required): Original user request/description
- `--no-exploration`: Skip creating initial exploration task
- `--tasks-dir`: Directory for task files (default: ./tasks)

**Output:**
- Returns the filepath of the created kanban (e.g., `tasks/2-kanban-api-refactor.md`)

**What it does:**
1. Creates an exploration task first (if not --no-exploration)
2. Creates the kanban file with proper ID sequencing
3. Updates the exploration task to reference the kanban
4. Updates the kanban to point to the current task

### 3. log-task.py

Logs work to a task file using a two-phase commit system.

**Phase 1 - Generate temp file:**
```bash
TEMP_FILE=$(uv run scripts/log-task.py \
    --task ./tasks/0-explore.md \
    --title "Initial Analysis" \
    --phase generate)
echo "Temp file: $TEMP_FILE"
# Agent writes work log to $TEMP_FILE...
```

**Phase 2 - Commit log:**
```bash
uv run scripts/log-task.py \
    --task ./tasks/0-explore.md \
    --title "Initial Analysis" \
    --phase commit \
    --temp-file "$TEMP_FILE"
```

**Single-phase (direct content):**
```bash
uv run scripts/log-task.py \
    --task ./tasks/0-explore.md \
    --title "Quick Update" \
    --content "Fixed the bug in auth module"
```

**Options:**
- `--task, -t` (required): Path to the task file
- `--title` (required): Title for this work log entry
- `--phase`: Phase of logging (generate, commit; default: generate)
- `--temp-file`: Path to temp file (required for commit phase)
- `--content, -c`: Direct content to log (skips temp file)
- `--temp-dir`: Directory for temporary files

**Why two-phase?**
- Agents can write freely without worrying about YAML frontmatter
- Proper formatting and timestamping is handled by the script
- Logs are consistently formatted with Facts/Analysis/Conclusion structure

## File Naming Convention

All files in `./tasks/` use global sequenced numbering:

```
tasks/
├── 0-design-api.md              # Task: Design API (ID 0)
├── 1-implement-models.md        # Task: Implement Models (ID 1)
├── 2-kanban-api-refactor.md     # Kanban: API Refactor (ID 2)
├── 3-review-models.md           # Task: Review Models (ID 3)
└── 4-fix-bugs.md                # Task: Fix Bugs (ID 4)
```

## Task File Structure

```yaml
---
role: Architect
expertise: ['System Design', 'Python']
skills: ['code-reading']
type: design
priority: high
dependencies: []
refers: []
kanban: tasks/0-kanban-project.md
created: 2026-02-25T11:38:30.998352
---

# Task: Design API Layer

## Context
Background information...

## Files
- src/api.py
- tests/test_api.py

## Description
What needs to be done...

## Work Log

### [2026-02-25 11:38:47] Initial Design Session

**Facts:**
- Analyzed requirements
- Reviewed existing code

**Analysis:**
- Identified key issues
- Proposed solutions

**Conclusion:**
- Design complete
- Ready for implementation

---
```

## Kanban File Structure

```yaml
---
type: kanban
title: API Refactor
request: Refactor the API layer for better performance
created: 2026-02-25T11:38:34.470783
phase: exploration
current: 1-explore-request.md
tasks: ['tasks/1-explore-request.md']
---

# Kanban: Workflow Tracking

## Plan Adjustment Log

### [2026-02-25 11:45:00] KANBAN_CREATED

**Details:**
- **reason:** New request received
- **action:** Created exploration task
- **next_step:** Architect will explore codebase

### [2026-02-25 12:30:00] TASKS_CREATED

**Details:**
- **from_work_item:** Design API authentication
- **tasks_created:**
  - tasks/2-design-auth.md
  - tasks/3-implement-auth.md
```
