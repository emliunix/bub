# Scoped Type Variables Implementation Analysis

**Date:** 2026-03-09  
**Participants:** User, Claude  
**Topic:** Implementing ScopedTypeVariables with Eisenberg 2016 visible type application

## Summary

Analyzed the theoretical and practical requirements for implementing **ScopedTypeVariables** in System F, building on the existing Eisenberg 2016 visible type application implementation.

## Key Findings

### Current Status
- ✅ **Visible Type Application (B_TApp)**: Works for global variables
- ❌ **ScopedTypeVariables**: Not implemented - causes errors when type variables from forall are used in nested annotations

### The Core Problem

When type-checking declarations like:
```systemf
id :: forall a. a -> a = \x -> (x :: a)
```

The type variable `a` from the declaration's `forall` is **not available** when checking the annotation `(x :: a)`. This causes `a` to be treated as an unbound variable (creating a fresh meta instead of a rigid type variable).

### Required Typing Rules

We need to implement four rules from Eisenberg 2016:

1. **B_TApp** (already done): Type application on polymorphic expressions
2. **DECL-SCOPE**: Declaration signatures bind type variables for the body
3. **ANN-SCOPE**: Type annotations bind their forall variables for the annotated term
4. **LAM-ANN-SCOPE**: Lambda parameter annotations bind type variables for the body

Plus pattern matching support from Eisenberg 2018:
5. **PAT-POLY**: Pattern variables retain polymorphic types from constructors

### Implementation Strategy

**Safe approach - don't modify core VAR rule:**
- Keep eager instantiation in variable lookup
- Instead, **extend context before type conversion** at scope boundaries

**Three locations need changes:**
1. `elab_bodies_pass.py`: Extend context per declaration with forall vars
2. `bidi_inference.py::check()`: Handle SurfaceAnn with context extension
3. `bidi_inference.py::check()`: Handle ScopedAbs with param annotation context extension

### Pattern Matching Connection

Pattern matching on ADT with polymorphic fields has the same issue:
```systemf
data PolyBox = PolyBox (forall a. a -> a)
unbox (PolyBox f) = f 42  -- f should be polymorphic
```

The pattern variable `f` is eagerly instantiated, losing polymorphism.

## References Added to Documentation

- **Eisenberg 2016**: Visible Type Application (ESOP)
- **Eisenberg 2018**: Type Variables in Patterns (ICFP) - NEW
- **Putting 2007**: Base bidirectional algorithm (JFP)

## Documentation Updated

**File:** `systemf/docs/notes/visible-type-application.md`

- Added LaTeX notation for all typing rules
- Documented current implementation gaps
- Added implementation pseudocode
- Clarified relationship between visible type application and scoped type variables
- Noted System SB vs System V distinction (we're at SB, V adds specified/inferred distinction)

## Next Steps

1. Implement helper functions: `collect_forall_vars()`, `extend_with_forall_vars()`
2. Modify `elab_bodies_pass.py` for DECL-SCOPE
3. Modify `bidi_inference.py` for ANN-SCOPE and LAM-ANN-SCOPE
4. Test with examples:
   - `id :: forall a. a -> a = \x -> (x :: a)`
   - `usePoly = \(f :: forall a. a -> a) -> f @a 42`
   - Pattern matching with polymorphic fields

## Design Decisions

**Staying at System SB level (not System V):**
- Don't track specified vs inferred distinction
- More permissive, simpler implementation
- Matches our philosophy: explicit forall is already mandatory

**No explicit Λ in surface language:**
- Confirmed: Surface language has no explicit type abstraction syntax
- All type variables introduced via forall in annotations

**Pattern type signatures:**
- Not currently in syntax
- Can be future extension per 2018 paper

## Testing Strategy

Created test matrix:
1. Basic scoped type variable: `id :: forall a. a -> a = \x -> (x :: a)`
2. Type application with scoped var: `f :: forall a. a -> a = \x -> id @a x`
3. Lambda param annotation: `usePoly = \(f :: forall a. a -> a) -> f 42`
4. Pattern matching: `data PolyBox = PolyBox (forall a. a -> a)` with `(PolyBox f)` pattern

## Related Issues

- Pattern matching with polymorphic binders (noted in `systemf-putting2007-validation-results.md`)
- Connection: Both issues stem from eager instantiation of polymorphic types

---

**Status:** Analysis complete, documentation updated, ready for implementation
