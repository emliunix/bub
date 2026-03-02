---
assignee: Implementor
expertise: ['Python']
skills: ['python-project', 'testing']
type: implement
priority: high
state: done
dependencies: []
refers: ['tasks/80-design-system-f-elaborator-populate-work-items.md', 'tasks/79-kanban-system-f-elaborator-refactor.md']
kanban: tasks/79-kanban-system-f-elaborator-refactor.md
created: 2026-03-02T08:42:58.097778
---

# Task: Create ScopeError exceptions

## Context
<!-- Background information and relevant context -->

## Files
- systemf/surface/scoped/errors.py

## Description
Define ScopeError exception hierarchy with location tracking for undefined variables in systemf/surface/scoped/errors.py

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-02T11:30:00] task_completed

**Details:**
- **action:** Created ScopeError exception hierarchy in systemf/surface/scoped/errors.py
- **files_created:** systemf/src/systemf/surface/scoped/errors.py
- **files_modified:** systemf/src/systemf/surface/scoped/__init__.py
- **exception_classes:**
  - ScopeError (base class inheriting from SystemFError)
  - UndefinedVariableError (undefined term variables)
  - UndefinedTypeVariableError (undefined type variables)
  - DuplicateBindingError (duplicate bindings in same scope)
  - ScopeDepthError (invalid scope depth/index)
  - GlobalVariableError (invalid global variable use)
- **features:**
  - Source location tracking via Location from systemf.utils.location
  - Term/type term tracking for error context
  - Diagnostic messages with suggestions
  - Suggestion lists for similar names
  - Integration with existing SystemFError hierarchy
