---
assignee: Implementor
expertise: ['Type Design', 'Python']
skills: ['python-project', 'testing']
type: implement
priority: medium
state: done
dependencies: ['tasks/84-add-source-locations-to-core-ast.md']
refers: ['tasks/80-design-system-f-elaborator-populate-work-items.md', 'tasks/79-kanban-system-f-elaborator-refactor.md']
kanban: tasks/79-kanban-system-f-elaborator-refactor.md
created: 2026-03-02T08:43:13.780252
---

# Task: Scope checking for top-level declarations

## Context
<!-- Background information and relevant context -->

## Files
- systemf/surface/scoped/checker.py

## Description
Implement scope checking for top-level declarations in systemf/surface/scoped/checker.py. Handle SurfaceTermDeclaration with type annotation and body scope checking.

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### 2026-03-02T14:00:00 - Task Completed

**Implementation Summary:**

Implemented scope checking for top-level declarations with mutual recursion support in `systemf/surface/scoped/checker.py`.

**Key Changes:**

1. **Added `check_declarations()` method** - New method that handles multiple declarations with mutual recursion:
   - Collects all global names from `SurfaceTermDeclaration`s first
   - Creates a `ScopeContext` with all globals
   - Scope-checks each declaration body with the full context
   - This enables mutually recursive functions like `even`/`odd`

2. **Updated `check_declaration()` docstring** - Clarified that single declarations should use this method, while multiple declarations with mutual recursion support should use `check_declarations()`

**Design Pattern:**

Following the top-level collection strategy from `ELABORATOR_DESIGN.md`:
```
Step 1: Collect all global names from declarations
Step 2: Create context with all globals
Step 3: Scope-check each body with full context
```

**Files Modified:**
- `systemf/src/systemf/surface/scoped/checker.py` - Added `check_declarations()` method and updated documentation

**State:** done
