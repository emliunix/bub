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
created: 2026-03-09T23:07:02.560450
---

# Task: Implement ANN-SCOPE: Type Annotation Context Extension

## Context
Implement ANN-SCOPE rule which extends type context with forall-bound variables from type annotations before checking annotated term

## Files
- src/systemf/surface/inference/bidi_inference.py
- tests/test_surface/test_scoped_type_vars_integration.py

## Description
See docs/notes/visible-type-application.md for ANN-SCOPE rule documentation. Modify bidi_inference.py SurfaceAnn case to extract forall vars from annotation and extend context before checking annotated term.

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-09 23:16:16] ANN-SCOPE Implementation Complete

**Facts:**
Successfully implemented ANN-SCOPE rule in bidi_inference.py:

1. Added import for collect_forall_vars and extend_with_forall_vars from context module
2. Added _collect_surface_forall_vars() helper to extract forall-bound vars from SurfaceType
3. Modified SurfaceAnn case in infer() to extend context with forall vars before checking annotated term

Rule implemented (from docs/notes/visible-type-application.md):
Γ, ā ⊢ e ⇐ ρ where annotation is ∀ā.ρ
----------------------------------------
Γ ⊢ (e :: ∀ā.ρ) ⇒ ∀ā.ρ

Verification: All 18 scoped type vars tests pass, all 479 surface tests pass.

**Analysis:**
-

**Conclusion:**
Status: ok

---

