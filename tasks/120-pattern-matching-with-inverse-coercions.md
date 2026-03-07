---
assignee: Implementor
expertise: ['Python', 'Type Theory', 'Pattern Matching']
skills: []
type: implement
priority: high
state: done
dependencies: ['tasks/119-review-adt-processing-implementation.md']
refers: ['tasks/118-constructor-elaboration-with-coercions.md', 'tasks/108-kanban-system-fc-elaborator.md']
kanban: tasks/108-kanban-system-fc-elaborator.md
created: 2026-03-07T13:38:31.573113
---

# Task: Pattern matching with inverse coercions

## Context
<!-- Background information and relevant context -->

## Files
- src/systemf/surface/inference/elaborator.py

## Description
Modify Case expression elaboration to insert inverse coercions (sym coercion) when destructuring ADT values

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-07 13:40:52] Implementation Complete

**Facts:**
Modified systemf/src/systemf/surface/inference/elaborator.py to insert inverse coercions in Case expressions: Added _maybe_add_inverse_coercion() helper method that checks if scrutinee type has a coercion axiom and wraps scrutinee in Cast(term, Sym(axiom)) to convert from abstract type to representation type for pattern matching. Modified SurfaceCase case in infer() to call _maybe_add_inverse_coercion() after inferring scrutinee, automatically converting from abstract ADT type (T) to representation type (Repr(T)) using inverse coercion. Verified working - scrutinee with axiom gets wrapped in Cast with Sym coercion, converting type from Nat to Repr(Nat); scrutinee without axiom passes through unchanged.

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-03-07 13:42:39] Implementation Review

**Facts:**
<!-- No facts recorded -->

**Analysis:**
<!-- No analysis recorded -->

**Conclusion:**
<!-- No conclusion recorded -->

---

