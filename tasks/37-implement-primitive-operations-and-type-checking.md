---
assignee: Implementor
expertise: ['Python', 'Type Checking', 'Evaluation']
skills: ['python-project', 'testing']
type: implement
priority: high
state: review
dependencies: ['tasks/35-implement-core-ast-and-type-extensions-for-primitives.md']
refers: []
kanban: tasks/33-kanban-systemf-pluggable-primitives-system.md
created: 2026-02-26T17:18:01.829603
---

# Task: Implement - Primitive Operations and Type Checking

## Context
Implement primitive operations (PrimOp) and update type checker and evaluator to handle them. Primitive operations use `$prim` prefix namespace which cannot be shadowed. Type signatures come from prelude declarations, NOT hardcoded.

## Key Implementation Details

### Type Checker Changes

**For IntLit:**
```python
case IntLit(_):
    # Lookup from prelude-populated registry
    return self.primitive_types["Int"]
```

**For PrimOp:**
```python
case PrimOp(name):
    full_name = f"$prim.{name}"
    if full_name not in self.global_types:
        raise TypeError(f"Unknown primitive: {name}")
    return self.global_types[full_name]
```

**Important:** Type checker has NO hardcoded primitive type signatures. All come from `global_types` populated by elaborating prelude's `prim_op` declarations.

### Evaluator Changes

**Registry Pattern:**
```python
class Evaluator:
    def __init__(self):
        self.primitive_impls = {
            "int_plus": self._int_plus,
            "int_minus": self._int_minus,
            # Add implementations here
        }
    
    def _int_plus(self, x: Value, y: Value) -> Value:
        if not isinstance(x, VInt) or not isinstance(y, VInt):
            raise RuntimeError("int_plus expects Int arguments")
        return VInt(x.value + y.value)
```

**Evaluation Cases:**
```python
case IntLit(value):
    return VInt(value)

# Note: PrimOp evaluation handled via App application
# App(PrimOp("int_plus"), arg1) applies the primitive
```

### Elaborator Changes

**$prim Name Resolution:**
```python
def _lookup_term(self, name: str, location: Location) -> core.Term:
    if name.startswith("$prim."):
        op_name = name[6:]  # Strip "$prim."
        return core.PrimOp(op_name)
    # ... existing resolution ...
```

## Files
- systemf/src/systemf/core/ast.py - Add PrimOp (already has IntLit from task 35)
- systemf/src/systemf/core/checker.py - Type checking for IntLit and PrimOp
- systemf/src/systemf/eval/machine.py - primitive_impls registry
- systemf/src/systemf/surface/elaborator.py - $prim name resolution

## Success Criteria
- [x] `IntLit(42)` type checks as `primitive_types["Int"]`
- [x] `PrimOp("int_plus")` type checks by looking up `global_types["$prim.int_plus"]`
- [x] No hardcoded primitive signatures in type checker
- [x] `primitive_impls` registry in evaluator
- [x] Tests for primitive operation type checking and evaluation

## Work Log

### 2026-02-26
**Implemented:** Primitive operations and type checking

**Changes Made:**
1. **systemf/src/systemf/core/checker.py**
   - Added `primitive_types` parameter to TypeChecker
   - Added inference case for `IntLit` that looks up from `primitive_types["Int"]`
   - Added inference case for `PrimOp` that looks up `global_types["$prim.{name}"]`
   - No hardcoded primitive signatures - all come from registries

2. **systemf/src/systemf/eval/machine.py**
   - Added `primitive_impls` registry with implementations for: int_plus, int_minus, int_mult, int_div
   - Added evaluation case for `IntLit` returning `VInt(value)`
   - Added evaluation case for `PrimOp` creating a `VPrimOp` closure
   - Added `apply` support for `VPrimOp` and `VPrimOpPartial` (currying)
   - Added helper method `_make_primop_closure`

3. **systemf/src/systemf/eval/value.py**
   - Added `VPrimOp` class to represent primitive operation closures
   - Added `VPrimOpPartial` class for partial application
   - Updated `Value` union type

4. **systemf/src/systemf/surface/elaborator.py**
   - Updated `_lookup_term` to handle `$prim.xxx` names
   - Names starting with `$prim.` are converted to `core.PrimOp`

5. **Tests Created:**
   - **systemf/tests/test_core/test_primitives.py** (20 tests)
     - Type checking tests for IntLit and PrimOp
     - No hardcoded signature verification
     - Evaluation tests for all primitive operations
     - Registry verification tests
     - Integration tests
   - **systemf/tests/test_surface/test_elaborator.py** (4 tests)
     - $prim name resolution tests

**Test Results:** 370 passed, 2 failed (pre-existing failures unrelated to this task)
**Status:** Complete

### [2026-02-26 18:17:12] Implementation Complete

**Facts:**
Implemented primitive operations and type checking. TypeChecker now handles IntLit and PrimOp. Evaluator has primitive_impls registry with int_plus, int_minus, int_mult, int_div. Elaborator handles .xxx names. Created 20 primitive tests and 4 elaborator tests. All success criteria met. 370 tests passing.

**Analysis:**
-

**Conclusion:**
Status: ok

---

