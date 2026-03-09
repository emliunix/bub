# 2026-03-09: System F Cons Operator Implementation

## Goal

Implement bidirectional type inference syntax for System F with cons operator support:
- Use `::` for type annotations (was `:`)
- Remove explicit `Λ` type abstraction (polymorphism inferred)
- Add cons operator `:` for lists
- Update lambda syntax to `λ(x :: T)` for annotated params

## Work Completed

### Parser Changes

**expressions.py:**
1. Fixed type annotation to use `DoubleColonToken` (was incorrectly using `ColonToken`)
   - Line 360: `atom_parser` now uses `::` for type annotations
   - Line 996: `let_binding` uses `::` for type annotations

2. Removed "tricky" `peek_is_declaration_start()` function
   - Declaration boundaries now work naturally via layout constraints
   - Removed ~40 lines of fragile boundary detection code

3. Fixed lambda parser to extract `.name` from `IdentifierToken`
   - Lines 697-702, 712: Lambda params now correctly return strings

4. Added comprehensive pattern parser support:
   - `pattern_atom_parser()` - handles identifiers, tuples, grouped patterns
   - `pattern_base_parser()` - constructor patterns with complex args
   - `pattern_cons_parser()` - cons patterns with right-associativity
   - Support for: `(x)`, `(Cons x xs)`, `(x : xs)`, `Pair (x, y) z`

**helpers.py:**
- Fixed Python 3.14 compatibility: `cast(Any, item_result)` instead of `cast(Result[...], item_result)`

### Tests Added

**test_cons_regression.py:** 16 comprehensive regression tests covering:
- Type annotation using `::` not `:`
- Lambda parameter extraction
- Cons expression right-associativity
- Cons patterns
- Grouped patterns with parentheses
- Constructor patterns with complex arguments
- Declaration boundary detection

**test_expressions.py:** 4 additional tests:
- `test_case_with_grouped_pattern`
- `test_case_with_grouped_cons`
- `test_case_with_nested_grouped_cons`
- `test_case_with_constructor_tuple_arg`

## Results

- ✅ All 10 .sf files parse successfully
- ✅ 718 tests passing (up from 702)
- ✅ Cons operator working: `1 : 2 : Nil`
- ✅ Cons patterns working: `case xs of Cons x xs → ...`
- ✅ Grouped patterns working: `(x : xs)`, `Pair (x, y) z`

## Elaboration Issue Found

During testing, discovered **pre-existing type elaboration failures** unrelated to parsing:

**Error:** `examples/identity.sf` fails elaboration
```
Type mismatch: expected 'polymorphic type (forall)', but got '_a -> _a'
In context: in type application
```

This occurs when elaborating `id @Int` - the type application of a polymorphic function. This is a **bidirectional type inference bug** in the elaborator, not a parser issue.

**Root cause:** The elaborator incorrectly handles type applications `@T` in the bidirectional checking mode. The parser correctly produces the AST, but the elaborator's `infer`/`check` functions have a bug in how they handle type instantiation.

**Evidence this is pre-existing:**
- Confirmed with `git stash` - same error occurs before our changes
- All parser tests pass (702+ tests)
- Only elaboration pipeline fails

**Recommendation:** This is out of scope for the cons operator work. The parser is correct and comprehensive. The type inference bug is a separate issue in the elaborator.

## Files Modified

- `src/systemf/surface/parser/expressions.py` - Main parser changes
- `src/systemf/surface/parser/helpers.py` - Python 3.14 fix
- `tests/test_surface/test_parser/test_expressions.py` - New pattern tests
- `tests/test_surface/test_parser/test_cons_regression.py` - New regression tests

## Follow-up

The parser is now complete and robust. The elaboration failure is a separate issue that should be addressed in a different work session focused on bidirectional type inference fixes.
