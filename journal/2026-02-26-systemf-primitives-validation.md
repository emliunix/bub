# 2026-02-26: SystemF Pluggable Primitives System (Task 33)

## Summary

Validated and completed Task 33: Pluggable Primitives System for SystemF. Implemented integer literals, primitive operations, and prelude-based type registration with operator desugaring.

---

## Architecture

### Type Checking Flow

```systemf
-- Prelude declares:
prim_type Int
prim_op int_plus : Int -> Int -> Int

-- User writes:
1 + 2

-- Parser creates: SurfaceOp(left=1, op="+", right=2)

-- Desugarer generates internally: (($prim.int_plus 1) 2)

-- Elaborator creates: App(App(PrimOp("int_plus"), IntLit(1)), IntLit(2))

-- Type checker looks up from prelude-populated registries
```

### Key Insight: $prim Namespace

The `$prim` namespace is internal (not user-parseable) and bridges:
- **Surface operators** (+, -, *, /) → Desugarer
- **Prelude declarations** (prim_op int_plus) → Type signatures
- **Evaluator registry** (primitive_impls) → Implementations

---

## Components Implemented

### 1. Core AST (Task 35)

**New nodes:**
- `IntLit(value: int)` - Integer literal term
- `PrimOp(name: str)` - Primitive operation reference

**Types:**
- `PrimitiveType(name: str)` - Type-level primitive

### 2. Runtime Values (Task 35)

- `VInt(value: int)` - Integer values
- `VPrimOp(name, impl)` - Primitive closure
- `VPrimOpPartial(name, impl, arg)` - Partial application

### 3. Type Checker (Task 37)

**Registry-based (no hardcoded types):**
```python
checker = TypeChecker(
    primitive_types={"Int": PrimitiveType("Int")},
    global_types={"$prim.int_plus": Int -> Int -> Int}
)
```

- `IntLit` lookups from `primitive_types` registry
- `PrimOp` lookups from `global_types` registry (with `$prim.` prefix)
- Fails if types not registered (verified by tests)

### 4. Evaluator (Task 37)

**Implementation registry:**
```python
self.primitive_impls = {
    "int_plus": lambda x, y: VInt(x.value + y.value),
    "int_minus": ...,
    "int_multiply": ...,
    "int_divide": ...,
}
```

- Curried application via `VPrimOp`/`VPrimOpPartial`
- Returns `VInt` for integer results

### 5. Elaborator (Tasks 35, 38)

**Prelude processing:**
- `prim_type Int` → registers in `primitive_types`
- `prim_op int_plus : ...` → registers in `global_types` as `$prim.int_plus`
- `$prim.xxx` names → `PrimOp("xxx")` core terms

### 6. Prelude Syntax (Task 38)

**New keywords:**
- `prim_type TypeName` - Declare primitive type
- `prim_op name : Type` - Declare primitive operation

**Example prelude:**
```systemf
prim_type Int
prim_op int_plus : Int -> Int -> Int
prim_op int_minus : Int -> Int -> Int
prim_op int_multiply : Int -> Int -> Int
prim_op int_divide : Int -> Int -> Int
```

### 7. Operator Desugaring (Task 39)

**Mapping:**
```python
OPERATOR_TO_PRIM = {
    "+": "$prim.int_plus",
    "-": "$prim.int_minus",
    "*": "$prim.int_multiply",
    "/": "$prim.int_divide",
}
```

**Desugaring:**
- `1 + 2` → `(($prim.int_plus 1) 2)`
- Preserves operator precedence
- `$prim` names are internal only (not parseable)

---

## Bug Fixes

### 1. Type Mismatch in Elaborator

**Problem:** Type annotations used `TypeConstructor('Int')` but primitive type registry had `PrimitiveType('Int')`.

**Fix:** `elaborator.py:421-426` - Check if type constructor is a registered primitive before creating `TypeConstructor`.

### 2. Unification Missing PrimitiveType

**Problem:** `unify()` and `Substitution.apply()` didn't handle `PrimitiveType`, causing "Cannot unify Int with Int".

**Fix:** `unify.py` - Added cases for:
- `PrimitiveType` unification (compare by name)
- `PrimitiveType` in substitution application (identity)
- `PrimitiveType` in occurs check (always False)

### 3. Naming Inconsistency

**Problem:** Desugarer used `$prim.int.plus` (dotted) but prelude declared `int_plus` (underscore).

**Fix:** Changed desugarer mapping and tests to use underscore naming consistent with prelude.

### 4. Outdated Tool Call Tests

**Problem:** Tests expected `Constructor` for `42` but we now have `IntLit`.

**Fix:** Updated `test_tool_calls.py`:
- `SurfaceConstructor` → `SurfaceIntLit`
- `core.Constructor` → `CoreIntLit`
- Assertions changed from `name == "42"` to `value == 42`

---

## REPL Integration

Updated `src/systemf/eval/repl.py` to share elaborator's primitive registries with type checker:

```python
self.checker = TypeChecker(
    datatype_constructors=self.elaborator.constructor_types,
    global_types=self.global_types,
    primitive_types=dict(self.elaborator.primitive_types),
)
```

---

## Test Programs

All manual tests passing:

```python
# Test: Integer Literal
42 → 42

# Test: Addition 1 + 2
1 + 2 → 3

# Test: Subtraction 10 - 3
10 - 3 → 7

# Test: Multiplication 5 * 4
5 * 4 → 20

# Test: Division 17 / 5
17 / 5 → 3

# Test: Complex (1+2)*3
(1 + 2) * 3 → 9

# Test: Multiple ops 10-3+2
10 - 3 + 2 → 9
```

---

## Test Results

**Before fixes:** 412 passed, 2 failed

**After fixes:** 414 passed, 0 failed

All tests passing including:
- 20 primitive operation tests
- 25 operator desugaring tests
- 25 tool call tests (updated)
- All existing SystemF tests

---

## Files Modified

### Core Implementation
- `src/systemf/core/ast.py` - IntLit, PrimOp nodes
- `src/systemf/core/types.py` - PrimitiveType
- `src/systemf/core/checker.py` - Registry lookups
- `src/systemf/core/unify.py` - PrimitiveType unification

### Surface Language
- `src/systemf/surface/ast.py` - SurfaceIntLit
- `src/systemf/surface/lexer.py` - NUMBER token
- `src/systemf/surface/parser.py` - IntLit parsing
- `src/systemf/surface/elaborator.py` - PrimOp, primitive types
- `src/systemf/surface/desugar.py` - Operator mapping

### Evaluation
- `src/systemf/eval/value.py` - VInt, VPrimOp, VPrimOpPartial
- `src/systemf/eval/machine.py` - primitive_impls registry
- `src/systemf/eval/repl.py` - Share primitive registries

### Prelude
- `prelude.sf` - Int type, arithmetic operations

### Tests
- `tests/test_core/test_primitives.py` - Primitive tests
- `tests/test_surface/test_operator_desugar.py` - Operator tests
- `tests/test_surface/test_elaborator.py` - PrimOp elaboration
- `tests/test_eval/test_tool_calls.py` - Updated for IntLit

---

## Key Design Decisions

1. **No user-visible $prim syntax** - Only accessible through operators and prelude declarations
2. **Registry-based type checking** - No hardcoded primitive signatures
3. **Prelude-populated registries** - Types declared in source, not baked into compiler
4. **Consistent underscore naming** - `int_plus` not `int.plus` to match identifiers
5. **PrimitiveType distinct from TypeConstructor** - Allows proper unification

---

## Validation Complete ✅

Task 33 (SystemF Pluggable Primitives System) is fully validated and complete.
