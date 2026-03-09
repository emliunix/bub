# Elaboration Issue: Polymorphic Type Applications

**Status:** Pre-existing bug, not related to parser work
**Date:** 2026-03-09
**Files:** `src/systemf/surface/inference/bidi_inference.py`

## Problem

Type applications like `id @Int` fail elaboration with:
```
Type mismatch: expected 'polymorphic type (forall)', but got '_a -> _a'
In context: in type application
```

## Example

```systemf
id :: ∀a. a → a = λx → x
int_id :: Int → Int = id @Int  -- FAILS here
```

## Root Cause

When elaborating `id :: ∀a. a → a = λx → x`, the context stores the inferred type `_a → _a` instead of the generalized type `∀a. a → a`.

When `id @Int` is elaborated:
1. Look up `id` in context → gets `_a → _a`
2. Type application expects `∀a. ...` → fails

## Reference Implementation (Putting 2007)

The Haskell reference uses `inferSigma` for let-bindings:

```haskell
tcRho (Let var rhs body) exp_ty = do
    var_ty <- inferSigma rhs                 -- GEN1: infer σ
    extendVarEnv var var_ty (tcRho body exp_ty)
```

Our implementation also uses `infer_sigma` at line 424 in `bidi_inference.py`, but something goes wrong with the generalization.

## Key Difference

Putting 2007's surface language has:
- `Let Name Term Term` - no type annotations on let
- `Ann Term Sigma` - separate type annotation form

System F has:
- `id :: ∀a. a → a = λx → x` - term declarations with type signatures

These signatures should guide inference (like `Ann`), but the elaborator isn't handling them correctly in the bidirectional checking.

## Fix Needed

When elaborating a term declaration with a type signature:
1. Use the signature as the expected type (check mode)
2. After checking, generalize the result
3. Store the **generalized** type in the context

Currently, step 3 stores the inferred monomorphic type.

## Impact

- Parser: ✅ Working correctly
- All .sf files parse successfully
- Elaboration fails for polymorphic type applications
- This blocks full program execution but not parsing

## Files to Investigate

- `src/systemf/surface/inference/elab_bodies_pass.py` - how bodies are elaborated
- `src/systemf/surface/inference/bidi_inference.py` - `check()` method for declarations
- `src/systemf/surface/inference/bidi_inference.py` - `infer_sigma()` generalization logic

## Test Case

```python
from systemf.surface.parser import parse_program
from systemf.surface.pipeline import run_pipeline

source = '''
id :: ∀a. a → a = λx → x
int_id :: Int → Int = id @Int
'''

decls = parse_program(source)  # ✓ Works
result = run_pipeline(decls)   # ✗ Fails at id @Int
```

## Priority

Low for parser work (parser is complete).
High for full System F implementation.
