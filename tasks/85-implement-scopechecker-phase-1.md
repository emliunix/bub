---
assignee: Implementor
expertise: ['Type Design', 'Python', 'Pattern Matching']
skills: ['python-project', 'testing']
type: implement
priority: high
state: done
dependencies: ['tasks/81-create-scoped-ast-types.md', 'tasks/82-create-scopecontext.md', 'tasks/83-create-scopeerror-exceptions.md']
refers: ['tasks/80-design-system-f-elaborator-populate-work-items.md', 'tasks/79-kanban-system-f-elaborator-refactor.md']
kanban: tasks/79-kanban-system-f-elaborator-refactor.md
created: 2026-03-02T08:43:09.970611
---

# Task: Implement ScopeChecker Phase 1

## Context
<!-- Background information and relevant context -->

## Files
- systemf/surface/scoped/checker.py

## Description
Implement ScopeChecker in systemf/surface/scoped/checker.py for Phase 1. Transform SurfaceVar->ScopedVar, SurfaceAbs->ScopedAbs, recurse on other nodes.

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-02T13:45:00] scope_checker_implemented

**Details:**
- **action:** Implemented ScopeChecker class in systemf/surface/scoped/checker.py
- **files_created:**
  - systemf/surface/scoped/checker.py (new file)
- **files_modified:**
  - systemf/src/systemf/surface/types.py (added ScopedVar and ScopedAbs types)
- **implementation_details:**
  - Added ScopedVar dataclass with `index: int`, `debug_name: str`, and `location: Location`
  - Added ScopedAbs dataclass with `var_name: str`, `var_type`, `body`, and `location`
  - Implemented ScopeChecker.check_term() with pattern matching for all SurfaceTerm types
  - SurfaceVar -> ScopedVar conversion with de Bruijn index lookup
  - SurfaceAbs -> ScopedAbs conversion with context extension
  - Recursive handling of: SurfaceApp, SurfaceTypeAbs, SurfaceTypeApp, SurfaceLet, SurfaceAnn, SurfaceIf, SurfaceCase, SurfaceConstructor, SurfaceTuple, SurfaceOp, SurfaceToolCall
  - Literals (IntLit, StringLit) pass through unchanged
  - Implemented check_declaration() for top-level declarations
  - Error handling with UndefinedVariableError and name suggestions
- **state_transition:** todo -> done
- **note:** Phase 1 scope checking core logic complete. All surface term types handled. Ready for unit tests in Task 87.
