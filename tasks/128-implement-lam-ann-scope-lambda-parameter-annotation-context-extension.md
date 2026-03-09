---
assignee: Implementor
expertise: ['Type System Implementation', 'Bidirectional Type Checking']
skills: ['python-project', 'testing']
type: implement
priority: high
state: review
dependencies: ['tasks/1-implement-helper-functions.md']
refers: ['tasks/0-kanban-scoped-type-vars.md']
kanban: tasks/0-kanban-scoped-type-vars.md
created: 2026-03-09T23:07:12.687968
---

# Task: Implement LAM-ANN-SCOPE: Lambda Parameter Annotation Context Extension

## Context
Implement LAM-ANN-SCOPE rule which extends type context with forall-bound variables from lambda parameter type annotations before checking lambda body

## Files
- src/systemf/surface/inference/bidi_inference.py
- tests/test_surface/test_scoped_type_vars_integration.py

## Description
See docs/notes/visible-type-application.md for LAM-ANN-SCOPE rule documentation. Modify bidi_inference.py ScopedAbs case to extend context when param annotation contains forall.

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-09 23:23:08] Implementation Complete

**Facts:**
Implemented LAM-ANN-SCOPE rule for bidirectional type checking. Modified bidi_inference.py:

1. check() ScopedAbs case: Extract forall-bound type variables from param annotation using _collect_surface_forall_vars(), extend context with these type variables before checking lambda body.

2. infer() SurfaceTypeApp case: Added ScopedVar handling similar to GlobalVar - look up type without instantiating to preserve forall structure for type application.

Verified with manual tests: \(f :: forall a. a -> a) -> f @Int 42 type-checks correctly to λ(f:∀a.a -> a).((f[Int]) 42).

All 736 existing tests pass.

**Analysis:**
-

**Conclusion:**
Status: ok

---

