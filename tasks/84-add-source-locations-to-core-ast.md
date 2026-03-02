---
assignee: Implementor
expertise: ['Type Design', 'Python']
skills: ['python-project', 'testing']
type: implement
priority: high
state: done
dependencies: []
refers: ['tasks/80-design-system-f-elaborator-populate-work-items.md', 'tasks/79-kanban-system-f-elaborator-refactor.md']
kanban: tasks/79-kanban-system-f-elaborator-refactor.md
created: 2026-03-02T08:43:01.023494
---

# Task: Add source locations to Core AST

## Context
<!-- Background information and relevant context -->

## Files
- systemf/core/ast.py

## Description
Add source location support to Core AST in systemf/core/ast.py. Every Core term must carry source_loc for error reporting; add debug_name to Var/Abs.

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### 2026-03-02 - Task Verification Complete

**Status**: Already implemented (no changes needed)

**Verification**:
- Base `Term` class has `source_loc: Optional[Location] = None` (line 16)
- All 12 term types inherit from `Term`: Var, Abs, App, TAbs, TApp, Constructor, Case, Let, IntLit, StringLit, PrimOp, ToolCall, Global
- `Var.debug_name` preserves original variable names (line 30)
- `Abs.var_name` preserves parameter names (line 62)

**Confirmed in journal**: 2026-03-02-elaborator-design.md documents this as completed work.

**All elaborator tests passing**: 32/32 tests pass with current implementation.
