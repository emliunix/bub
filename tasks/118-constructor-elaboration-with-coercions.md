---
assignee: Implementor
expertise: ['Python', 'Type Theory', 'Elaboration']
skills: []
type: implement
priority: high
state: done
dependencies: ['tasks/117-extend-elaborator-context-with-coercion-environment.md']
refers: ['tasks/116-generate-coercion-axioms-for-adts.md', 'tasks/108-kanban-system-fc-elaborator.md']
kanban: tasks/108-kanban-system-fc-elaborator.md
created: 2026-03-07T13:33:00.923724
---

# Task: Constructor elaboration with coercions

## Context
<!-- Background information and relevant context -->

## Files
- src/systemf/surface/inference/elaborator.py

## Description
Modify constructor application case in elaborator to automatically insert coercions based on ADT axiom mappings

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-07 13:34:58] Implementation Complete

**Facts:**
Modified systemf/src/systemf/surface/inference/elaborator.py to insert coercions in constructor applications: Added _maybe_add_coercion() helper method that checks if result type has a coercion axiom (ax_{TypeName}) in context and wraps constructor in Cast(term, axiom) when found. Modified SurfaceConstructor case in infer() to call _maybe_add_coercion() after elaborating constructor, automatically converting from representation type to abstract type using ADT coercion axioms. Verified working - constructor with axiom gets wrapped in Cast, constructor without axiom passes through unchanged.

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-03-07 13:36:31] Implementation Review

**Facts:**
<!-- No facts recorded -->

**Analysis:**
<!-- No analysis recorded -->

**Conclusion:**
<!-- No conclusion recorded -->

---

