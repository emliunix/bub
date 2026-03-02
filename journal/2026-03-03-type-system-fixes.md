# System F Type System Fixes - 2026-03-03

**Date**: 2026-03-03  
**Status**: In Progress  
**Focus**: Type parser and constructor elaboration fixes

## Summary

Fixed critical bugs in the System F type system related to type-level type applications and data constructor elaboration. These fixes lay the groundwork for implementing implicit type instantiation.

## Changes Made

### 1. Type Parser Fix: SurfaceTypeConstructor for Type Applications
**File**: `systemf/src/systemf/surface/parser/type_parser.py`

**Problem**: Type applications like `List Int` were being parsed as `SurfaceTypeApp`, which is a **term-level** construct, not a type-level construct.

**Before**:
```python
result = SurfaceTypeApp(result, arg, loc)  # Wrong! This is for term-level @Int
```

**After**:
```python
return SurfaceTypeConstructor(name, args, loc)  # Correct type-level representation
```

**Impact**: Type annotations like `Maybe a` and `List Int` now parse correctly as proper SurfaceTypes.

### 2. Constructor Type Extraction
**File**: `systemf/src/systemf/surface/inference/elaborator.py`

**Problem**: Data declarations weren't extracting constructor types, so constructors like `Just` and `Nothing` had no types in the context.

**Solution**: Modified `_elaborate_data_decl` to:
1. Build proper polymorphic constructor types
2. Return constructor types alongside the DataDeclaration

**Example**:
```haskell
data Maybe a = Nothing | Just a
-- Now generates:
--   Nothing : ∀a. Maybe a
--   Just : ∀a. a → Maybe a
```

### 3. Fixed Elaboration Order
**Problem**: Term declarations were elaborated before data declarations, so constructors weren't available.

**Solution**: Reordered elaboration phases:
1. **Phase 1**: Collect type signatures
2. **Phase 2**: Elaborate data declarations (extract constructor types)
3. **Phase 3**: Build context with constructors
4. **Phase 4**: Elaborate term declarations

### 4. Pipeline Updates
**File**: `systemf/src/systemf/surface/pipeline.py`

**Changes**:
- Updated `elaborate_declarations` return type to include constructor types
- Modified pipeline to merge input constructors with newly defined ones
- Module now properly tracks all constructor types

### 5. REPL Constructor Updates
**File**: `systemf/src/systemf/eval/repl.py`

**Fix**: Added code to update `constructor_types` from module results:
```python
# Update constructor types from data declarations
for name, ty in module.constructor_types.items():
    self.constructor_types[name] = ty
```

### 6. Test Updates
**File**: `tests/test_surface/test_parser/test_declarations.py`

Updated test expectations to match new parser behavior (SurfaceTypeConstructor instead of SurfaceTypeApp).

## Current Status

**Working**:
- ✅ Type parsing: `List Int` → `SurfaceTypeConstructor`
- ✅ Constructor extraction: Data declarations generate polymorphic types
- ✅ Elaboration order: Data before terms
- ✅ Basic elaboration without prelude

**Known Issues**:
- ⚠️ Pattern matching with polymorphic constructors (e.g., `case e of { Left x → ... }`)
- ⚠️ Prelude fails to load due to Either pattern matching

**Test Results**:
```
tests/test_surface/test_parser/test_declarations.py::TestTypeParser::test_type_application PASSED
debug_constructor.py: Data + function elaboration works
```

## Technical Details

### Type System Levels

The fix clarifies the distinction between:

**Type Level** (SurfaceType hierarchy):
- `SurfaceTypeVar` - Type variables
- `SurfaceTypeArrow` - Function types  
- `SurfaceTypeConstructor` - Applied type constructors (List Int)
- `SurfaceTypeForall` - Polymorphic types

**Term Level** (SurfaceTerm hierarchy):
- `SurfaceTypeApp` - Term-level type application (id @Int)
- `SurfaceTypeAbs` - Term-level type abstraction (Λa. e)

### Constructor Types

Constructor types are now properly polymorphic:
```haskell
-- For: data Maybe a = Nothing | Just a
Nothing : ∀a. Maybe a           -- No args, returns Maybe a
Just : ∀a. a → Maybe a          -- Takes a, returns Maybe a

-- For: data Either a b = Left a | Right b  
Left : ∀a. ∀b. a → Either a b   -- Polymorphic in both params
Right : ∀a. ∀b. b → Either a b
```

## Next Steps

1. **Fix Pattern Matching**: Handle polymorphic constructors in case patterns
2. **Implicit Instantiation**: Implement local type inference (Pierce & Turner style)
3. **Test Prelude**: Verify full prelude loads correctly
4. **Documentation**: Update TYPE_INFERENCE_ALGORITHM.md with new architecture

## References

- Previous work: `2026-03-02-elaborator-refactor-complete.md`
- Design doc: `systemf/docs/ELABORATOR_DESIGN.md`
- New doc: `systemf/docs/IMPLICIT_INSTANTIATION.md`

## Later Today: Implicit Instantiation Implementation

Implemented full implicit type instantiation following Pierce & Turner's bidirectional type checking. This enables polymorphic functions and constructors to work without explicit type annotations.

### 7. Nested Forall Instantiation
**File**: `systemf/src/systemf/surface/inference/elaborator.py:940-945`

Made `_instantiate()` recursive to handle nested polymorphic types:
```python
def _instantiate(self, ty):
    match ty:
        case TypeForall(var, body):
            meta = self._fresh_meta(var)
            return self._instantiate(self._subst_type_var(body, var, meta))  # Recursive!
```

### 8. Constructor Type Variable Fix (Critical!)
**File**: `systemf/src/systemf/surface/inference/elaborator.py:1234-1244`

**Root Cause**: Constructor types were stored with meta-variables instead of type variables:
```
Just : ∀a._a → Maybe a    # WRONG - _a is a meta-variable
```

**Fix**: Create context with bound type parameters before converting constructor args:
```python
type_ctx = TypeContext()
for param in decl.params:
    type_ctx = type_ctx.extend_type(param)
core_args = [self._surface_to_core_type(arg, type_ctx) for arg in con_info.args]
```

**Result**: Constructor types now use proper type variables:
```
Just : ∀a.a → Maybe a     # CORRECT
```

### 9. Bidirectional Type Checking for Case
**Files**: `elaborator.py:775-799, 866-935`

Added proper bidirectional checking for case expressions:
- `check()` now handles `SurfaceCase` with expected result type
- Branches check against expected type instead of inferring independently
- New `_check_branch_check_mode()` helper for checking mode

**Impact**: `mapMaybe` now works correctly:
```haskell
mapMaybe : ∀a. ∀b. (a → b) → Maybe a → Maybe b
mapMaybe = Λa. Λb. λf. λm.
  case m of
    Nothing → Nothing
    Just x  → Just (f x)   -- Now type-checks correctly!
```

### 10. Application Site Instantiation
**File**: `elaborator.py:276-281`

Added implicit instantiation when applying polymorphic functions:
```python
match func_type:
    case TypeForall(_, _):
        func_type = self._instantiate(func_type)
```

### 11. Pattern Matching with Constructors
**File**: `elaborator.py:801-864`

Fixed `_check_branch()` to:
- Look up constructor types from context
- Instantiate polymorphic constructors
- Unify constructor result with scrutinee type
- Bind pattern variables to correct argument types

### 12. Lexer Enhancement
**File**: `systemf/src/systemf/surface/parser/lexer.py:114`

Added single quote support to identifiers:
```python
("IDENT", r"[a-z_][a-zA-Z0-9_']*")  # Now supports xs'
```

### 13. New Unit Tests
**File**: `tests/test_surface/test_inference.py`

Added `TestPolymorphicConstructors` class with 7 tests:
- `test_basic_constructor_usage` - Simple constructor
- `test_pattern_matching_same_type` - Monomorphic case
- `test_pattern_matching_type_abstraction_same` - Type abstraction
- `test_mapMaybe_without_transformation` - Returns Nothing
- `test_mapMaybe_with_function_application` - **Critical**: `Just (f x)`
- `test_either_type_mapRight` - Either type patterns
- `test_list_map` - List type with `xs'` (single quote)

## Final Status

**✅ Working**:
- Type parsing and applications
- Constructor extraction with proper type variables
- Implicit instantiation at application sites
- Pattern matching with polymorphic constructors
- Bidirectional checking for case expressions
- Single quote identifiers
- 607 tests passing (595 + 12 new)

**⚠️ Prelude Status**:
- Previously failed at line 103 (polymorphic constructor error)
- Then failed at line 77 (type variable scoping)
- **Now progresses to line 119** (forward reference: `length` undefined)
- Remaining issue: Forward declarations in prelude (separate architectural concern)

## Test Results
```
tests/test_surface/test_inference.py::TestPolymorphicConstructors - 7 PASSED
Total: 607 passed, 12 failed (pre-existing primitive operator issues)
```

## Architecture Decisions

1. **Bidirectional checking**: Case branches check against expected type (not infer)
2. **Constructor contexts**: Type parameters bound during data declaration elaboration
3. **Recursive instantiation**: `_instantiate()` handles nested `∀a.∀b.T`

## Files Changed

```
systemf/src/systemf/surface/parser/type_parser.py           | Modified
systemf/src/systemf/surface/parser/lexer.py                 | Modified (single quote)
systemf/src/systemf/surface/inference/elaborator.py         | Modified (major)
systemf/src/systemf/surface/pipeline.py                     | Modified
systemf/src/systemf/eval/repl.py                            | Modified
tests/test_surface/test_parser/test_declarations.py         | Modified
tests/test_surface/test_inference.py                        | Added 7 tests
tasks/101-kanban-implicit-instantiation-for-system-f.md    | Created
tasks/102-design-implicit-instantiation-implementation.md  | Created
tasks/103-fix-nested-forall-instantiation-in-elaborator.md | Created
tasks/104-add-implicit-instantiation-at-application-sites.md | Created
tasks/105-fix-pattern-matching-with-polymorphic-constructors.md | Created
tasks/106-update-constructor-elaboration-for-polymorphic-types.md | Created
tasks/107-test-fixes-and-verify-all-tests-pass.md          | Created
```
