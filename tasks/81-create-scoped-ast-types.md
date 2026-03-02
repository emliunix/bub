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
created: 2026-03-02T08:42:52.197277
---

# Task: Create Scoped AST types

## Context
<!-- Background information and relevant context -->

## Files
- systemf/surface/types.py

## Description
Extend `surface/types.py` with ScopedVar and ScopedAbs types per design spec in `systemf/docs/scoped-extended-ast-design.md`. Add ScopedVar (with de Bruijn index and debug_name), ScopedAbs (with var_name), and ScopedTypeVar (for type variables) alongside existing SurfaceVar/SurfaceAbs. Do NOT create a separate scoped/types.py - extend Surface AST in place. Add type aliases for clarity (ScopedTerm, ScopedType).

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-02 10:14:00] Architect Design Review Approved

**Facts:**
- Reviewed corrected task 81 against scoped-extended-ast-design.md specification
- Original design violation: Proposed creating surface/scoped/types.py (parallel hierarchy)
- Correction applied by Manager: Now extends surface/types.py in place
- Verified task specifies: ScopedVar (index + debug_name), ScopedAbs (var_name), ScopedTypeVar
- Verified explicit note: "Do NOT create a separate scoped/types.py - extend Surface AST in place"
- Verified type aliases: ScopedTerm, ScopedType for clarity

**Analysis:**
- Aligns perfectly with extend-in-place architecture decision in design doc
- Follows Core-First principle by extending existing surface/types.py rather than creating new module
- Proper scope: Only adds scoped variants for binding constructs (Var, Abs, TypeVar)
- Reuses existing SurfaceApp, constructors, etc. as intended
- Type aliases provide clear API: UnscopedTerm/ScopedTerm distinction

**Conclusion:**
Status: ok

Design review approved. Task correctly follows scoped-extended-ast-design.md. Ready for Implementor to proceed with extending surface/types.py in place.
