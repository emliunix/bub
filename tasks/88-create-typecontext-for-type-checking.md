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
created: 2026-03-02T08:43:21.032022
---

# Task: Create TypeContext for type checking

## Context
<!-- Background information and relevant context -->

## Files
- systemf/surface/inference/context.py

## Description
Create TypeContext in systemf/surface/inference/context.py for type checking state. Track type bindings, metas, and constraints during elaboration.

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-02T15:30:00] Task Completed - TypeContext Implementation

**Files Created:**
- `systemf/src/systemf/surface/inference/context.py` - TypeContext class with full type checking support
- `systemf/src/systemf/surface/inference/__init__.py` - Module exports

**Implementation Summary:**
- Created `TypeContext` dataclass with frozen=True for immutability
- Tracks term variable types indexed by de Bruijn index (index 0 = most recent)
- Tracks type variables with optional kinds
- Supports type constructor signatures (e.g., `Just : forall a. a -> Maybe a`)
- Supports global type signatures for mutual recursion
- Tracks meta type variables for unification

**Key Methods:**
- `lookup_term_type(index)` - Get type of term variable by de Bruijn index
- `lookup_type_var(name)` - Get kind of type variable
- `lookup_type_var_index(name)` - Get de Bruijn index for type variable
- `lookup_constructor(name)` - Get type scheme for data constructor
- `lookup_global(name)` - Get type signature for global
- `extend_term(ty)` - Add term variable binding (returns new context)
- `extend_type(name, kind)` - Add type variable binding (returns new context)
- `add_constructor(name, ty)` - Add type constructor
- `add_global(name, ty)` - Add global binding
- `add_meta(meta)` - Add meta type variable for unification

**Design Decisions:**
- Followed same immutable pattern as ScopeContext (frozen dataclass)
- Type variables stored as list of tuples (name, kind) for proper de Bruijn indexing
- Used None for kind to represent kind * (star) as default
- All extend/add methods return new TypeContext (functional update)

**Verification:**
All manual tests passed:
- Term variable lookup by de Bruijn index ✓
- Type variable lookup by name ✓
- Constructor signature lookup ✓
- Global signature lookup ✓
- Immutability preservation ✓
