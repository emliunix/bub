---
assignee: Implementor
type: implement
title: "Implement Helper Functions for ScopedTypeVariables"
dependencies: []
skills: [python-project, testing]
expertise: ["Type System Implementation", "Python"]
state: done
---

# Task: Implement Helper Functions for ScopedTypeVariables

## Context

This is the first implementation task (Core-First) for the ScopedTypeVariables feature. It provides the helper functions needed by all other scope implementations.

## Design Specification

Implement two helper functions:

1. **`collect_forall_vars(ty: Type) -> list[str]`**
   - Extracts all forall-bound type variables from a type
   - Handles nested foralls: `forall a b. ...` → `["a", "b"]`
   - Returns vars in order (outermost first)

2. **`extend_with_forall_vars(ctx: TypeContext, ty: Type) -> TypeContext`**
   - Extends context with all forall-bound vars in type
   - Preserves order: outermost forall becomes index 0

## Location

Add to: `src/systemf/surface/inference/context.py`

## Acceptance Criteria

- [ ] Function signatures match design spec
- [ ] Handles single forall: `forall a. a -> a` → `["a"]`
- [ ] Handles multiple foralls: `forall a. forall b. a -> b` → `["a", "b"]`
- [ ] Handles non-forall types: `Int -> Int` → `[]`
- [ ] Unit tests pass

## Files

- src/systemf/surface/inference/context.py (add functions)
- tests/test_surface/test_scoped_type_vars.py (create tests)

## Work Log

### [2026-03-09 22:57:52] Implementation Complete

**Facts:**
- collect_forall_vars: extracts forall-bound type variables from types, handles nested foralls and non-forall types\n- extend_with_forall_vars: extends TypeContext with forall-bound variables, preserves outermost-first order\n- Created 16 unit tests in tests/test_surface/test_scoped_type_vars.py\n- All new tests pass (16 passed)\n- All existing tests still pass (734 passed)

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-03-09 23:00:07] Implementation Review

**Facts:**
**F:**
- Implemented 2 helper functions in systemf/src/systemf/surface/inference/context.py:
  - collect_forall_vars(ty): Extracts forall-bound type variables, handles nested foralls
  - extend_with_forall_vars(ctx, ty): Extends TypeContext with forall-bound variables
- Created 16 comprehensive unit tests in systemf/tests/test_surface/test_scoped_type_vars.py
- All 16 new tests pass
- All 734 existing systemf tests still pass (no regressions)

**A:**
- Function signatures match design specification exactly
- Code quality: Clean, well-documented with docstrings and examples
- Edge cases handled: single forall, nested foralls, non-forall types, context extension
- Test coverage: Comprehensive (single/multiple foralls, non-forall types, context preservation, immutability)
- Code style: Consistent with existing codebase (follows patterns in context.py)
- Implementation correctly handles de Bruijn indexing (outermost forall becomes index 0)

**C:** PASSED - Implementation meets all acceptance criteria and is ready for integration.

**Analysis:**
-

**Conclusion:**
Status: ok

---

