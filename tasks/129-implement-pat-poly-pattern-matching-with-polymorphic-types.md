---
assignee: Implementor
expertise: ['Type System Implementation', 'Pattern Matching']
skills: ['python-project', 'testing']
type: implement
priority: medium
state: review
dependencies: ['tasks/1-implement-helper-functions.md']
refers: ['tasks/0-kanban-scoped-type-vars.md']
kanban: tasks/0-kanban-scoped-type-vars.md
created: 2026-03-09T23:07:19.483128
---

# Task: Implement PAT-POLY: Pattern Matching with Polymorphic Types

## Context
Implement PAT-POLY rule which preserves polymorphic types for pattern variables bound to polymorphic constructor arguments

## Files
- src/systemf/surface/inference/bidi_inference.py
- tests/test_surface/test_scoped_type_vars_integration.py

## Description
See docs/notes/visible-type-application.md for PAT-POLY rule documentation. Modify _check_branch() to not eagerly instantiate polymorphic constructor argument types. Pattern variables should retain forall types.

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-09 23:28:42] PAT-POLY implementation complete

**Facts:**
Modified _check_branch() in bidi_inference.py to not eagerly instantiate polymorphic constructor argument types; pattern variables now retain forall types per PAT-POLY rule

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-03-09 23:45:00] Additional fix to _check_branch_check_mode()

**Facts:**
Updated _check_branch_check_mode() to also preserve polymorphic arg types using the same pattern as _check_branch():
- Save original constructor type (preserves foralls in arg types)
- Create instantiated version for unification with scrutinee type  
- Extract arg types from ORIGINAL type, result type from INSTANTIATED type

This ensures both inference mode and checking mode pattern matching preserve polymorphic types for pattern variables.

**Analysis:**
Both _check_branch() and _check_branch_check_mode() now correctly implement PAT-POLY rule.

**Conclusion:**
Status: ok

---

