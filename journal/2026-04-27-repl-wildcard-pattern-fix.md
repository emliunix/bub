# REPL Pattern Matching Fix - Wildcard `_` in Constructor Patterns

**Date:** 2026-04-27  
**Topic:** elab3 REPL pattern matching bug  
**Status:** Fixed

---

## Problem

REPL-defined case expressions with multi-argument constructor patterns containing wildcards (`_`) were failing with:

```
duplicate param names: _ at <repl 0>:3:3
```

Example that failed:
```haskell
test1 :: List Int -> Bool = \xs -> case xs of
  Nil -> True
  Cons _ _ -> False
```

## Root Cause

In `rename_expr.py`, the pattern renamer treated `_` as a regular variable pattern and created a bound variable for it. When a constructor pattern had multiple `_` arguments (e.g., `Cons _ _`):

1. Each `_` yielded a bound variable with surface name `_`
2. `check_dups()` then rejected the duplicate `_` names

Module-level case expressions worked because they either:
- Used named variables instead of `_`
- Had single-argument constructors

## Fix

In `rename_expr.py:191`, added special handling for `_`:

```python
case SurfacePattern(patterns=[SurfaceVarPattern(name=var, location=loc)]):
    if var == "_":
        return WildcardPat()
    match self.lookup_maybe(UnqualName(var)):
        ...
```

`_` now returns `WildcardPat()` which doesn't bind any variable, matching standard functional language behavior.

## Verification

- All 165 elab3 tests pass
- REPL case expressions with `Cons _ _` now compile correctly:
  ```
  test1 Nil = (VData(tag=0, vals=[]), Bool)        -- True
  test1 (Cons 1 Nil) = (VData(tag=1, vals=[]), Bool)  -- False
  ```
- Core output shows both alternatives present:
  ```
  case _scrut_1178 of
     { Nil -> True
     | Cons _mc_con_1180 _mc_con_1181 -> False
     }
  ```

## Files Changed

- `systemf/src/systemf/elab3/rename_expr.py`
  - Import `WildcardPat`
  - Return `WildcardPat()` for `_` patterns instead of creating bound variables
