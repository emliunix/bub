# Failing Tests - Categorized

**Total: 47 failing tests**

---

## Category 1: Type Parser Constructor Issues (4 tests)
**Files:** `tests/test_surface/test_parser/test_declarations.py`

**Tests:**
- TestTypeParser::test_simple_type
- TestTypeParser::test_type_application
- TestTypeParser::test_unit_type
- TestTypeParser::test_tuple_type

**Error:** 
```
AssertionError: assert [] == 'Int'
where [] = SurfaceTypeConstructor(location='Int', name=[], args=Location(...)).name
```

**Root Cause:** 
Parser creating SurfaceTypeConstructor with wrong field order:
- OLD (broken): `SurfaceTypeConstructor(name, args, loc)` → binds name to location field
- NEW (correct): `SurfaceTypeConstructor(name=name, args=args, location=loc)`

**Fix:** Update type_parser.py to use keyword arguments

---

## Category 2: Operator Desugaring Not Happening (13 tests)
**Files:** `tests/test_surface/test_operator_desugar.py`

**Tests:**
- All TestOperatorDesugaring tests (10 tests)
- All TestDesugarInContext tests (3 tests)

**Error:**
```
AssertionError: assert False
where False = isinstance(SurfaceOp(...), SurfaceApp)
```

**Root Cause:**
SurfaceOp is not being desugared to SurfaceApp with primitive calls. The test expects:
```python
# After desugaring:
SurfaceApp(SurfaceApp(SurfaceVar("int_plus"), left), right)
# But getting:
SurfaceOp(left, "+", right)
```

**Fix:** 
Desugaring logic needs to be checked. Either:
1. Desugarer._desugar_operators not being called, OR
2. Test is checking before desugaring happens

---

## Category 3: Tests Reference Deleted IntLit/StringLit (15+ tests)
**Files:** `tests/test_surface/test_inference.py`, `tests/test_pipeline.py`

**Tests:**
- TestTypeAnnotations::test_annotation_inference
- TestTypeAnnotations::test_annotation_check
- TestElaborateTerm::test_elaborate_term_without_context
- TestConstructorsAndCases::test_simple_case
- TestConstructorsAndCases::test_case_with_pattern_bindings
- TestComplexExpressions::test_case_in_lambda
- TestPolymorphicConstructors (7 tests)
- All TestBasicPipeline tests (2 tests)
- All TestPolymorphism tests (2 tests)
- All TestLetBindings tests (2 tests)
- And more...

**Error:**
```
AttributeError: module 'systemf.core.ast' has no attribute 'IntLit'
# or
AttributeError: module 'systemf.core.ast' has no attribute 'StringLit'
```

**Root Cause:**
Tests still import and use:
```python
from systemf.core.ast import IntLit, StringLit
# Should be:
from systemf.core.ast import Lit
# And use: Lit(prim_type="Int", value=42)
```

**Fix:** 
Update all test imports and usages:
- `IntLit(loc, 42)` → `Lit(prim_type="Int", value=42, source_loc=loc)`
- `StringLit(loc, "hi")` → `Lit(prim_type="String", value="hi", source_loc=loc)`

---

## Category 4: SurfaceTypeVar Parsing Issues (13 tests)
**Files:** `tests/test_pipeline.py`

**Tests:**
- Most pipeline tests

**Error:**
```
ElaborationError(message='Unknown surface type: test.py:1:1', ...)
```

**Root Cause:**
SurfaceTypeVar not being recognized/parsed correctly. The test creates:
```python
SurfaceTypeVar("_", DUMMY_LOC)  # For wildcard type
# or
SurfaceTypeVar("a", DUMMY_LOC)  # For type variable
```

But elaborator doesn't handle these correctly.

**Fix:**
Check how SurfaceTypeVar is processed in elaborator and parser.

---

## Category 5: Type Constructor Keyword Args (2 tests)
**Files:** Tests using SurfaceTypeConstructor

**Error:**
Fields binding to wrong attributes due to inherited location field.

**Fix:** 
Same as Category 1 - use keyword arguments.

---

## Summary

**By Category:**
1. Type parser issues: 4 tests
2. Operator desugaring: 13 tests
3. IntLit/StringLit references: ~20 tests
4. SurfaceTypeVar handling: ~10 tests

**By Root Cause:**
- Missing keyword args: ~20 tests
- Deleted class references: ~20 tests  
- Desugaring logic: 13 tests
- Type handling: ~10 tests

**Priority Order:**
1. **HIGH:** Fix IntLit/StringLit references (blocks many tests)
2. **HIGH:** Fix type parser keyword args (4 tests)
3. **MEDIUM:** Fix operator desugaring (13 tests)
4. **MEDIUM:** Fix SurfaceTypeVar handling (10 tests)
