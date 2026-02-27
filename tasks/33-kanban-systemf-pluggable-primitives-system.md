---
type: kanban
title: SystemF Pluggable Primitives System
created: 2026-02-26T17:17:16.297362
phase: complete
current: null
tasks:
  - tasks/34-design-primitive-types-and-operations-architecture.md
  - tasks/35-implement-core-ast-and-type-extensions-for-primitives.md [done]
  - tasks/36-implement-surface-syntax-for-integer-literals.md [done]
  - tasks/37-implement-primitive-operations-and-type-checking.md [done]
  - tasks/38-implement-prelude-integration-for-primitives.md [done]
  - tasks/39-implement-operator-desugaring-to-primitive-operations.md [done]
---

# Kanban: SystemF Pluggable Primitives System

## Request
Implement a pluggable primitives system for System F using `$prim` prefix to bridge the gap between core language and primitive operations like Int arithmetic. The system should allow primitive types and operations to be declared in prelude while keeping the core language minimal.

## Architecture Overview (Final Design)

### Clean Separation: Types in Prelude, Only Names at Runtime

```systemf
-- Prelude declares primitive types and operations
prim_type Int
prim_op int_plus : Int -> Int -> Int

-- User can shadow regular names
plus = \x y -> x  -- Shadows 'plus'

-- But NOT $prim names
1 + 2             -- Desugars to $prim.int_plus 1 2 (always works!)
```

### Core Components

**AST Nodes:**
- `IntLit(value: int)` - Integer literal term
- `PrimOp(name: str)` - Primitive operation (args via App wrapping)
- `PrimitiveType(name: str)` - Type-level primitive
- `VInt(value: int)` - Runtime integer value

**Prelude Syntax (Single Tokens):**
- `prim_type Int` - Declare primitive type
- `prim_op int_plus : Int -> Int -> Int` - Declare primitive operation

**Name Resolution:**
```python
$prim.xxx      → PrimOp("xxx")      # Bypasses all scopes
local_var      → Var(index)         # De Bruijn index
global_name    → Global(name)       # Top-level definition
```

### Type Checking Flow

**IntLit:**
```python
case IntLit(_):
    return self.primitive_types["Int"]  # From prelude
```

**PrimOp:**
```python
case PrimOp(name):
    return self.global_types[f"$prim.{name}"]  # From prelude
```

**Key:** NO hardcoded signatures! All types from `global_types` populated by prelude.

### Evaluation Flow

**Registry Pattern:**
```python
self.primitive_impls = {
    "int_plus": lambda x, y: VInt(x.value + y.value),
    "int_minus": lambda x, y: VInt(x.value - y.value),
}
```

**Evaluation:**
```python
case IntLit(value):
    return VInt(value)
# PrimOp handled via App application
```

### Communication Between Components

- **Type Checker ↔ Evaluator:** Only operation symbol names (e.g., "int_plus")
- **Type Checker:** Knows types from prelude-declared signatures
- **Evaluator:** Knows implementations from `primitive_impls` registry

## Implementation Plan

### Phase 1: Design (Task 34) ✓ Updated
**Architect designs complete primitive system:**
- Final AST specification: IntLit, PrimOp, PrimitiveType, VInt
- Single token keywords: `PRIM_TYPE`, `PRIM_OP`
- Name resolution rules
- Type checking lookup strategy
- Evaluation registry pattern

### Phase 2: Core Infrastructure (Task 35)
**Implement core AST and type extensions:**
- Add `IntLit` to `core/ast.py`
- Add `PrimOp` to `core/ast.py`
- Add `VInt` to `eval/value.py`
- Add `PrimitiveType` to `core/types.py`
- Update exports in `core/__init__.py`

### Phase 3: Surface Syntax (Task 36)
**Update for integer literals:**
- Parser creates `IntLit` directly from NUMBER tokens
- Tests for integer literal parsing

### Phase 4: Primitive Operations (Task 37) ✓ Updated
**Implement PrimOp handling:**
- Type checker: Lookup from `global_types` (prelude-populated)
- NO hardcoded primitive signatures
- Evaluator: `primitive_impls` registry
- Elaborator: `$prim.xxx` → `PrimOp`

### Phase 5: Prelude Integration (Task 38) ✓ Updated
**Extend prelude with primitive declarations:**
- Single token keywords: `PRIM_TYPE`, `PRIM_OP`
- Parser: Parse declarations
- Elaborator: Register in `primitive_types` and `global_types`
- Update `prelude.sf` with Int type and operations

### Phase 6: Operator Desugaring (Task 39)
**Implement infix operators:**
- Lexer: Operator tokens (+, -, *, etc.)
- Parser: Infix expressions
- Desugarer: `+` → `$prim.int_plus`

## Key Design Decisions

1. **Single Token Keywords:** `prim_type` and `prim_op` instead of `PRIM` + `TYPE`/`OP`
2. **IntLit by Parser:** Parser directly creates IntLit from NUMBER tokens
3. **No Hardcoded Types:** Type checker looks up from prelude-populated registries
4. **PrimOp with App:** Arguments handled via App wrapping (consistent with functions)
5. **$prim Bypasses Scopes:** `$prim.xxx` names never check local/global scopes
6. **Registry Pattern:** Evaluator has `primitive_impls` dict mapping names to implementations

## Example Flow

```systemf
-- prelude.sf
prim_type Int
prim_op int_plus : Int -> Int -> Int

-- user.sf  
1 + 2
```

**Step-by-step:**
1. Parse prelude → declarations
2. Elaborate → `primitive_types["Int"]`, `global_types["$prim.int_plus"]`
3. Parse `1 + 2` → `App(App(Var("+"), IntLit(1)), IntLit(2))`
4. Desugar `+` → `App(App(PrimOp("int_plus"), IntLit(1)), IntLit(2))`
5. Type check → lookup `$prim.int_plus` in `global_types`
6. Evaluate → `primitive_impls["int_plus"](VInt(1), VInt(2))` → `VInt(3)`

## Files to Modify

**Core Language:**
- `systemf/src/systemf/core/ast.py` - IntLit, PrimOp
- `systemf/src/systemf/core/types.py` - PrimitiveType
- `systemf/src/systemf/core/checker.py` - Lookup from prelude registries
- `systemf/src/systemf/core/__init__.py` - Export new types

**Surface Language:**
- `systemf/src/systemf/surface/ast.py` - SurfacePrimTypeDecl, SurfacePrimOpDecl
- `systemf/src/systemf/surface/lexer.py` - PRIM_TYPE, PRIM_OP tokens
- `systemf/src/systemf/surface/parser.py` - Parse declarations
- `systemf/src/systemf/surface/elaborator.py` - Elaborate IntLit, PrimOp, declarations
- `systemf/src/systemf/surface/desugar.py` - Operator desugaring

**Evaluator:**
- `systemf/src/systemf/eval/value.py` - VInt
- `systemf/src/systemf/eval/machine.py` - primitive_impls registry

**Prelude:**
- `systemf/prelude.sf` - Add primitive declarations

**Tests:**
- `systemf/tests/test_core/` - Type checking tests
- `systemf/tests/test_surface/` - Parsing/elaboration tests  
- `systemf/tests/test_eval/` - Evaluation tests

## Success Criteria

- [ ] Integer literals parse and elaborate: `42` → `IntLit(42)`
- [ ] Primitive type declared in prelude: `prim_type Int`
- [ ] Primitive operation declared: `prim_op int_plus : Int -> Int -> Int`
- [ ] Type checker looks up from prelude (no hardcoded signatures)
- [ ] Primitive operations work: `$prim.int_plus 1 2` → `3`
- [ ] Evaluator uses `primitive_impls` registry
- [ ] Operators desugar correctly: `1 + 2` → `$prim.int_plus 1 2`
- [ ] User can shadow non-$prim names
- [ ] All existing tests pass
- [ ] New tests added

## Work Log

### [2026-02-26] Task 39 Complete - Workflow Finished

**Facts:**
- Task 39 (Implement - Operator Desugaring to Primitive Operations) completed by Implementor
- All 6 tasks in the SystemF Pluggable Primitives System are now complete
- Workflow phase transitioned from "implementation" to "complete"
- All tasks marked as done

**Analysis:**
- The entire pluggable primitives system has been successfully implemented:
  1. Architecture designed (Task 34)
  2. Core AST and type extensions (Task 35)
  3. Surface syntax for literals (Task 36)
  4. Primitive operations and type checking (Task 37)
  5. Prelude integration (Task 38)
  6. Operator desugaring (Task 39)
- System now supports: integer literals, primitive types, primitive operations, operator desugaring
- Clean separation achieved: types defined in prelude, only names at runtime

**Conclusion:**
- **WORKFLOW COMPLETE** - All tasks successfully finished
- Current task set to null to indicate no further work required
- Phase set to "complete"
- Pluggable primitives system is fully operational

### [2026-02-26] Task 34 Complete - Moving to Implementation

**Facts:**
- Task 34 (Design - Primitive Types and Operations Architecture) completed by Architect
- Design specification finalized with AST nodes: IntLit, PrimOp, PrimitiveType, VInt
- Single token keywords: prim_type, prim_op
- Type checker lookup strategy: from prelude-populated registries (no hardcoded signatures)
- Evaluation registry pattern established

**Analysis:**
- Design phase complete, ready for implementation
- Task 35 is the first implementation task (core AST extensions)

**Conclusion:**
- Updated kanban phase: design → implementation
- Next task: Task 35 (Implement core AST and type extensions for primitives)

### [2026-02-26] Task 35 Complete - Core AST Extensions Implemented

**Facts:**
- Task 35 (Implement - Core AST and Type Extensions for Primitives) completed by Implementor
- IntLit, PrimOp added to core/ast.py
- VInt added to eval/value.py
- PrimitiveType added to core/types.py
- Exports updated in core/__init__.py

**Analysis:**
- Core infrastructure for primitives is now in place
- Ready to implement surface syntax for integer literals

**Conclusion:**
- Updated kanban: Task 35 marked as done
- Next task: Task 36 (Implement surface syntax for integer literals)

### [2026-02-26] Task 36 Complete - Surface Syntax for Integer Literals Implemented

**Facts:**
- Task 36 (Implement - Surface Syntax for Integer Literals) completed by Implementor
- Parser updated to create IntLit directly from NUMBER tokens
- Tests added for integer literal parsing

**Analysis:**
- Surface syntax infrastructure for literals is now complete
- Ready to implement primitive operations and type checking

**Conclusion:**
- Updated kanban: Task 36 marked as done
- Next task: Task 37 (Implement primitive operations and type checking)

### [2026-02-26] Task 37 Complete - Primitive Operations and Type Checking Implemented

**Facts:**
- Task 37 (Implement - Primitive Operations and Type Checking) completed by Implementor
- TypeChecker now handles IntLit and PrimOp
- Evaluator has primitive_impls registry with int_plus, int_minus, int_mult, int_div
- Elaborator handles $prim.xxx names
- Created 20 primitive tests and 4 elaborator tests
- 370 tests passing (2 pre-existing failures unrelated to this task)

**Analysis:**
- Primitive operations infrastructure is complete
- Type checker successfully looks up from prelude-populated registries
- No hardcoded primitive signatures in type checker
- Registry pattern working correctly in evaluator

**Conclusion:**
- Updated kanban: Task 37 marked as done
- Next task: Task 38 (Implement prelude integration for primitives)

### [2026-02-26] Task 38 Complete - Prelude Integration for Primitives Implemented

**Facts:**
- Task 38 (Implement - Prelude Integration for Primitives) completed by Implementor
- Single token keywords PRIM_TYPE and PRIM_OP added to lexer
- Parser updated to parse prim_type and prim_op declarations
- Elaborator registers primitive types in primitive_types registry
- Elaborator registers primitive operations in global_types with $prim prefix
- prelude.sf updated with Int type and arithmetic operations

**Analysis:**
- Prelude integration infrastructure is complete
- All primitive declarations now go through prelude
- Type checker and evaluator can look up primitives from prelude-populated registries
- Ready for operator desugaring to complete the pluggable primitives system

**Conclusion:**
- Updated kanban: Task 38 marked as done
- Next task: Task 39 (Implement operator desugaring to primitive operations)

## Plan Adjustment Log

### 2026-02-26: Design Finalization
**Changes:**
1. Single token keywords (`prim_type`, `prim_op`) instead of two-token approach
2. Type checker has NO hardcoded primitive signatures - all from prelude
3. Simplified: Parser creates IntLit directly, no dispatch tables
4. Updated Task 34 with complete design specification
5. Updated Task 37 with lookup-from-prelude strategy
6. Updated Task 38 with single token syntax

**Rationale:** Cleaner separation between parser (makes terms), prelude (provides types), type checker (looks up), and evaluator (implements).
