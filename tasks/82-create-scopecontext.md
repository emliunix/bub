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
created: 2026-03-02T08:42:55.463091
---

# Task: Create ScopeContext

## Context
<!-- Background information and relevant context -->

## Files
- systemf/surface/scoped/context.py

## Description
Create ScopeContext in systemf/surface/scoped/context.py for name-to-index mapping. Data structure tracking term_names and type_names lists with lookup/extend methods.

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-02 09:06:55] ScopeContext Implementation Complete

**Facts:**
Created ScopeContext dataclass in systemf/surface/scoped/context.py with term_names/type_names lists, lookup/extend methods for both term and type variables, globals tracking, and helper methods. Module exports ScopeContext from __init__.py. Verified working with manual test: extend_term correctly creates de Bruijn indices (0=most recent).

**Analysis:**
-

**Conclusion:**
Status: ok

---

