# Visible Type Application Implementation

**Status:** Fixed ✓
**Date:** 2026-03-09
**Files:** `src/systemf/surface/inference/bidi_inference.py`

## References

1. **Eisenberg et al., "Visible Type Application", ESOP 2016**
   - Paper: https://www.seas.upenn.edu/~sweirich/papers/esop2016-type-app.pdf
   - Extended version: https://richarde.dev/papers/2016/type-app/visible-type-app-extended.pdf
   - GHC Documentation: https://downloads.haskell.org/ghc/9.6.5/docs/users_guide/exts/type_applications.html

2. **Peyton Jones et al., "Practical type inference for arbitrary-rank types", JFP 2007**
   - Foundation: Bidirectional type checking for higher-rank polymorphism
   - Our base implementation follows this paper

## Overview

System F implements **visible type application**, an extension to the Hindley-Milner type system that allows explicit type instantiation via the `@` operator (e.g., `id @Int`). This feature was introduced by Eisenberg et al. (2016) as an extension to GHC.

**Key insight from Eisenberg 2016:**
> "Visible type application lets the caller write the type argument directly (e.g., `read @Int "5"`), making code clearer and eliminating the need for auxiliary proxy values."

## Syntax

```systemf
-- Polymorphic identity
id :: ∀a. a → a = λx → x

-- Explicit instantiation
int_id :: Int → Int = id @Int
bool_id :: Bool → Bool = id @Bool
```

## Implementation

### Bidirectional Typing Rule (B_TApp)

Following Eisenberg's System B (Figure 10 in the paper):

```
Γ ⊢ e ⇒ ∀a. σ
------------------- (B_TApp)
Γ ⊢ e @τ ⇒ σ[τ/a]
```

Where:
- `e` synthesizes a polymorphic type `∀a. σ`
- The visible type application `@τ` instantiates `a` with `τ`
- The result type is `σ` with `τ` substituted for `a`

### Key Implementation Detail

**Problem:** When looking up a polymorphic global variable (like `id`), the elaborator was **instantiating** the type immediately (replacing `∀a. a → a` with a fresh meta `_a → _a`). This broke type applications because the forall was lost.

**Solution:** In `SurfaceTypeApp` handling, special-case `GlobalVar` to **not instantiate** the type. Keep the forall so the type application can substitute the type argument.

```python
case SurfaceTypeApp(location=location, func=func, type_arg=type_arg):
    # Special case: if func is a GlobalVar, don't instantiate
    match func:
        case GlobalVar(name=name):
            if name in ctx.globals:
                func_type = ctx.globals[name]  # Keep the forall!
                func_type = self._apply_subst(func_type)
                core_func = core.Global(location, name)
        case _:
            # Normal case: instantiate as usual
            core_func, func_type = self.infer(func, ctx)
            func_type = self._apply_subst(func_type)
    
    # Now func_type should be a forall
    match func_type:
        case TypeForall(var, body_type):
            # Substitute type argument
            core_type_arg = self._surface_to_core_type(type_arg, ctx)
            result_type = self._subst_type_var(body_type, var, core_type_arg)
            return (core.TApp(location, core_func, core_type_arg), result_type)
```

### Difference from Putting 2007

**Putting 2007 (base algorithm):**
- No explicit type application syntax
- Type instantiation is always **implicit** via unification
- When using a polymorphic function, the type system automatically picks the right instantiation

**Eisenberg 2016 (our extension):**
- Adds explicit `e @τ` syntax
- Programmer can specify type arguments explicitly
- Falls back to implicit instantiation when not specified
- Distinguishes **specified** variables (user-written forall) from **inferred** variables

## Status

✅ **FIXED** - Type applications now work correctly

```python
source = '''
id :: ∀a. a → a = λx → x
int_id :: Int → Int = id @Int
'''

decls = parse_program(source)
result = run_pipeline(decls)  # ✓ Success!
```

## Limitations

1. **Specified vs. Inferred:** Our current implementation doesn't distinguish between:
   - **Specified variables:** `∀a.` (user-written, can be instantiated via `@`)
   - **Inferred variables:** From generalization (cannot be instantiated via `@`)
   
   Full Eisenberg implementation tracks this distinction.

2. **Single variable:** Current implementation handles `∀a. ...` but not `∀a b. ...` (multiple variables).

## Test Cases

```systemf
-- Basic polymorphic function
id :: ∀a. a → a = λx → x

-- Type application at use site
int_id :: Int → Int = id @Int

-- Multiple instantiations
use_id :: Int = id @Int 42
use_id_bool :: Bool = id @Bool True
```

All parse and elaborate correctly.

## See Also

- `src/systemf/surface/inference/bidi_inference.py` - Main implementation
- Eisenberg, R. A., Weirich, S., & Ahmed, A. (2016). Visible Type Application. In *Programming Languages and Systems* (pp. 229-254). Springer.
- Peyton Jones, S., Vytiniotis, D., Weirich, S., & Shields, M. (2007). Practical type inference for arbitrary-rank types. *Journal of Functional Programming*, 17(1), 1-82.
