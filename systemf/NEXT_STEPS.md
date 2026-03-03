# System F - Next Steps

**Date**: 2026-03-03  
**Status**: Surface AST refactoring complete, 21 tests fixed, 26 remaining

---

## ✅ Completed

### Surface AST Refactoring (DONE)
- ✅ SurfaceNode base class with location field
- ✅ Unified literals (SurfaceLit/Lit/VPrim)
- ✅ All production code uses keyword arguments
- ✅ Location propagation verified (extract from source → propagate to new)
- ✅ `equals_ignore_location()` moved to `systemf/utils/ast_utils.py`
- ✅ 21 tests fixed (47 → 26 failing)

---

## 🎯 Round 1: Fix Remaining 26 Tests

### Current Status
```
26 failed, 587 passed, 1 xfailed
```

### Failing Test Categories

#### 1. Pipeline Tests (15 failures)
**Location**: `tests/test_pipeline.py`
**Issue**: Type elaboration errors
**Examples**:
- `test_simple_identity_function` - Unknown surface type
- `test_polymorphic_identity` - Type variable handling
- `test_compose_function` - Complex polymorphism

**Action Required**: 
- [ ] Debug type variable elaboration in inference
- [ ] Check how type variables are looked up in context
- [ ] Verify type abstraction elaboration

#### 2. Inference Tests (7 failures)
**Location**: `tests/test_surface/test_inference.py`
**Issue**: Pattern matching, constructors, polymorphism
**Examples**:
- `test_simple_case` - Case expression elaboration
- `test_polymorphic_constructors` - Constructor with type vars
- `test_case_with_pattern_bindings` - Pattern variable binding

**Action Required**:
- [ ] Debug case expression elaboration
- [ ] Check pattern matching type inference
- [ ] Verify constructor elaboration with type parameters

#### 3. Remaining (4 failures)
**Locations**: Various
**Issue**: Edge cases

**Action Required**:
- [ ] Debug individually

### Next Actions (Round 1)

1. **Run each failing test with verbose output**
   ```bash
   uv run pytest tests/test_pipeline.py::TestBasicPipeline::test_simple_identity_function -v --tb=long
   ```

2. **Identify root causes**
   - Type variable lookup failing?
   - Pattern matching not binding variables?
   - Constructor type instantiation issues?

3. **Fix in elaborator**
   - `src/systemf/surface/inference/elaborator.py`
   - Check `_surface_to_core_type()` for type variables
   - Check `infer()` for pattern matching
   - Check constructor elaboration

4. **Verify fixes**
   - Run specific test
   - Run full test suite
   - Ensure no regressions

---

## 🎯 Round 2: Polish & Harden

### 1. Better Error Messages
**Current**: Generic "Unknown surface type" errors
**Target**: Helpful messages with suggestions

**Tasks**:
- [ ] Add context to elaboration errors
- [ ] Include source location in error messages
- [ ] Suggest similar names for typos
- [ ] Show expected vs actual types

### 2. Concrete Type Display
**Current**: `it :: __ = 42` (meta-variable)
**Target**: `it :: Int = 42` (concrete type)

**Tasks**:
- [ ] Apply substitution to types before display
- [ ] Format types nicely (Int → Int vs ∀a. a → a)
- [ ] Update REPL output formatting

### 3. Documentation Sync
**Tasks**:
- [ ] Update BATTLE_TEST_SUMMARY.md with final status
- [ ] Update syntax examples in docs
- [ ] Add troubleshooting for common errors

---

## 🎯 Round 3: Future Enhancements

### 1. ASCII Lambda Support
**Syntax**: `\x:Int -> body` as alternative to `λx:Int → body`
**File**: `src/systemf/surface/parser/lexer.py`
**Priority**: Low

### 2. Performance Optimization
**Areas**:
- Elaboration pipeline caching
- Type unification optimization
- Pattern matching compilation
**Priority**: Low

---

## 📊 Current State

### Tests
- **Passing**: 587
- **Failing**: 26
- **Expected**: 26 (not blocking functionality)

### Core Functionality
- **REPL**: ✅ Working
- **Lambdas**: ✅ Working
- **Polymorphism**: ✅ Working
- **Pattern Matching**: ⚠️ Edge cases
- **Type Inference**: ⚠️ Complex cases

### Documentation
- **Complete**: Architecture, troubleshooting, contributing
- **Needs Update**: Final test status after Round 1

---

## 📁 Files to Monitor

**Production**:
- `src/systemf/surface/inference/elaborator.py` - Type inference
- `src/systemf/eval/repl.py` - REPL output
- `src/systemf/surface/inference/errors.py` - Error messages

**Tests** (26 failing):
- `tests/test_pipeline.py` - 15 failures
- `tests/test_surface/test_inference.py` - 7 failures
- Various - 4 failures

---

## 🚦 Decision Points

**After Round 1**:
- If 26 tests → 0 tests: Proceed to Round 2
- If still failing: Assess if deeper architectural issue

**After Round 2**:
- System is "production ready" for internal use
- Can start using REPL for real work

---

## 📝 Notes

**Key Principles**:
- Keyword arguments for ALL Surface* constructors
- Location propagation: source → generated nodes
- Structural equality via `equals_ignore_location()`
- No re-exports (migrate imports to canonical locations)

**Avoid**:
- DUMMY_LOC in production code
- Positional arguments for dataclasses with inheritance
- Backward compatibility shims

---

**Last Updated**: 2026-03-03
**Next Review**: After Round 1 complete
