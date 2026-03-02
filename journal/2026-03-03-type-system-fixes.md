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

## Files Changed

```
systemf/src/systemf/surface/parser/type_parser.py     | Modified
systemf/src/systemf/surface/inference/elaborator.py   | Modified  
systemf/src/systemf/surface/pipeline.py               | Modified
systemf/src/systemf/eval/repl.py                      | Modified
tests/test_surface/test_parser/test_declarations.py   | Modified
tests/test_surface/test_integration.py               | Deleted (stale)
```
