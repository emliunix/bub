# Practical Type Inference for Higher-Rank Types - Reading Notes

**Paper**: Peyton Jones, Vytiniotis, Weirich, Shields (2007)  
**Full Title**: "Practical Type Inference for Arbitrary-Rank Types"  
**Journal**: Journal of Functional Programming

---

## Overview

This paper presents a **complete, implementable type inference algorithm** for higher-rank polymorphism in Haskell. The key contribution is showing that type inference for arbitrary-rank types is practical and can be implemented efficiently.

## Key Concepts

### 1. Rank-N Polymorphism

**Rank-1 (Hindley-Milner)**: `∀a. a → a` - polymorphism only at top level  
**Rank-2**: `(∀a. a → a) → Int` - polymorphism in argument position  
**Rank-N**: Arbitrary nesting of polymorphic types

**Example from the paper**:
```haskell
-- Rank-2 type
runST :: (∀s. ST s a) → a

-- Higher-rank function
foo :: (∀a. a → a) → (Int, Bool)
foo f = (f 3, f True)
```

### 2. Bidirectional Type Checking

The system uses **two modes**:

| Mode | Symbol | Description |
|------|--------|-------------|
| **Synthesis** | ⊢⇑ | Given term, infer type |
| **Checking** | ⊢⇓ | Given term and type, verify match |

**Key insight**: Type annotations trigger checking mode; unannotated terms use synthesis.

### 3. Type System Layers

```
σ (Sigma) - Polymorphic types: ∀ā.ρ
  ↓
ρ (Rho)   - Rho types: τ | σ₁ → σ₂  
  ↓
τ (Tau)   - Monomorphic types: a | τ₁ → τ₂
```

## Files Reference

### Main Paper Documentation

**File**: [`docs/research/practical-type-inference-2007.tex`](practical-type-inference-2007.tex)

LaTeX document containing the complete formalization:
- Complete bidirectional rules (Figure 8)
- All auxiliary judgments (instantiation, subsumption, prenex conversion)
- Annotated with paper section references
- Includes elaboration to System F

### Complete Implementation

**File**: [`docs/research/putting-2007-implementation.hs`](putting-2007-implementation.hs)

Working Haskell implementation extracted from Appendix A:
```bash
# To run:
cd docs/research
cabal run --allow-newer putting-2007-implementation.hs
```

**Features**:
- Full bidirectional type checker
- Robinson unification with occurs check
- Weak prenex conversion (skolemisation)
- Deep skolemization for subsumption
- Complete with inline cabal metadata

### Implementation Manifest

**File**: [`docs/research/Putting2007-MANIFEST.md`](Putting2007-MANIFEST.md)

Complete catalog of all definitions:
- 6 type definitions (Term, Type, Tc, etc.)
- 45 functions with signatures
- 4 type class instances
- Cross-referenced to paper rules

### GHC Core Specification

**File**: [`docs/research/ghc-core-spec.mng`](ghc-core-spec.mng)

System FC specification showing the target language:
- Core syntax (expressions, types, coercions)
- Typing judgments for System FC
- Role system (nominal, representational, phantom)
- Operational semantics

**Related Files**:
- [`CoreLint.ott`](CoreLint.ott) - Formal typing rules
- [`CoreSyn.ott`](CoreSyn.ott) - Core syntax definition

### Original Paper Text

**File**: [`docs/research/putting-2007.txt`](putting-2007.txt)

Plain text extraction of the PDF for searching.

**Index**: [`docs/research/putting2007-index.md`](putting2007-index.md)

Quick reference for navigating the paper by line numbers.

---

## Deep Dive: Recursive Types in Real Compilers

### The Discovery

Through analysis of GHC Core and Idris2, we discovered that **recursive types require no special handling** in the core representation. The recursion is entirely emergent from **name resolution order**.

### The Core Insight

**Recursive types and non-recursive types look identical!**

Both use the same representation:
```haskell
-- Constructor types just reference names in scope
Ref fc (TyCon ar) name        -- Type constructor
Ref fc (DataCon tag ar) name  -- Data constructor
```

The "magic" is just **declaration order**:
1. Add type constructor name to context
2. Build constructor types (which may reference that name)

### Implementation Pattern

#### Single Recursive Type

```idris
-- Step 1: Add TyCon to environment
List : TyCon ar=1

-- Step 2: Define constructors (List is now in scope)
Nil  : forall a. List a
Cons : forall a. a -> List a -> List a
                    -- ^^^^^^^ self-reference!
```

#### Mutual Recursion

```idris
-- PASS 1: Declare ALL type constructors
EvenList : TyCon ar=1
OddList  : TyCon ar=1

-- PASS 2: Define ALL constructors
-- EvenList constructors:
ENil  : forall a. EvenList a
ECons : forall a. a -> OddList a -> EvenList a
                          -- ^^^^^^^ cross-reference!

-- OddList constructors:  
OCons : forall a. a -> EvenList a -> OddList a
                          -- ^^^^^^^^^ cross-reference!
```

### Comparison: GHC Core vs Idris2

| Aspect | GHC Core | Idris2 |
|--------|----------|--------|
| **Type reference** | `TyConApp T args` | `Ref fc (TyCon ar) name` |
| **Constructor** | Direct application | `Ref fc (DataCon tag ar) name` |
| **Recursion mechanism** | Structural + nominal | Nominal (name resolution) |
| **Newtypes** | Coercions (`e |> g`) | Likely similar |
| **Value recursion** | `let rec` | `Bind` with recursive refs |

### What This Means

**No μ (mu) types needed!**
- No `μX.F(X)` notation
- No explicit fold/unfold operations for regular types
- No special "recursive type" handling in the compiler core

**No coercions for regular recursive types!**
- Coercions are only for:
  - Newtypes (representational equality)
  - Type families (axiom application)
  - GADTs (equality constraints)
- Regular `data` declarations use **implicit structural recursion**

**The algorithm is simple:**
```haskell
processDataDecls :: [DataDecl] -> Core ()
processDataDecls decls = do
  -- Phase 1: Add all type constructors
  for_ decls $ \decl -> 
    addTyCon decl.name decl.arity
  
  -- Phase 2: Add all data constructors
  -- (All TyCon names now visible for mutual refs)
  for_ decls $ \decl ->
    addDataCons decl.name decl.constructors
```

### Why This Matters

1. **Simplicity**: The core language stays simple without recursive-specific constructs
2. **Uniformity**: Recursive and non-recursive types handled identically
3. **Efficiency**: No runtime overhead for fold/unfold operations
4. **Composability**: Mutual recursion is just a special case of context ordering

### Examples from Real Code

**From Idris2 Core/TT/Term.idr**:
```idris
-- Name types
data NameType : Type where
     DataCon : (tag : Int) -> (arity : Nat) -> NameType
     TyCon   : (arity : Nat) -> NameType

-- Terms reference names
data Term : Scoped where
     Ref : FC -> NameType -> (name : Name) -> Term vars
```

**From GHC CoreLint**:
```haskell
-- DataAlt rule - no special recursion handling
T = dataConTyCon K
t1 = dataConRepType K
t2 = t1 {</ sj // j />}
...
G; D; T </ sj // j /> |-altern K </ ni // i /> -> e : t
```

### Edge Cases

**Newtypes ARE different**:
```haskell
-- newtype Age = MkAge Int
-- Requires coercion: Age ~Rep# Int
-- Uses cast: e |> co
```

**Type families**:
```haskell
-- type family F a where...
-- Requires axiom application for reduction
```

**But regular data types**:
```haskell
-- data List a = Nil | Cons a (List a)
-- Just constructors and pattern matching!
```

---

## Implementation Details

### Meta Type Variables

The key innovation enabling efficient inference:

```haskell
data MetaTv = Meta Uniq (IORef (Maybe Tau))
```

- Mutable cells for unification
- Start as `Nothing` (unknown)
- Solved during inference to `Just tau`
- Enables efficient in-place type inference

### Weak Prenex Conversion

Transforming types for subsumption:

```haskell
-- Input:  Int -> forall a. a -> a
-- Output: forall a. Int -> a -> a
```

This hoists quantifiers to enable algorithmic subsumption checking.

### Deep Skolemization

Checking if one type is "at least as polymorphic" as another:

```haskell
-- Check: σ₁ ≤ σ₂
-- 1. Skolemize σ₂ (replace ∀ with fresh constants)
-- 2. Instantiate σ₁ as needed
-- 3. Check structural compatibility
```

---

## Related Papers (Research Collection)

### 1. Eisenberg 2016 - Visible Type Application

**Paper**: "Visible Type Application" (Extended version)  
**Authors**: Eisenberg, Weirich, Ahmed (University of Pennsylvania)  
**Location**: [`systemf/docs/research/`](../systemf/docs/research/)

| File | Description |
|------|-------------|
| [`eisenberg-2016-visible-type-application.txt`](../systemf/docs/research/eisenberg-2016-visible-type-application.txt) | Plain text extraction (4,161 lines) |
| [`eisenberg-2016-index.txt`](../systemf/docs/research/eisenberg-2016-index.txt) | Line number index |

**Key contribution**: Adds explicit type application syntax (`e @τ`) to HM type system. Introduces "specified" vs "generalized" type variables distinction. Systems: HM, HMV, C, V, SB, B.

**Relationship to Putting 2007**: Eisenberg builds on bidirectional checking from Putting, adds visible type application. Where Putting has implicit instantiation only, Eisenberg allows explicit `@Int` syntax.

### 2. Jones & Shields 2002 - Scoped Type Variables

**Paper**: "Lexically-scoped type variables"  
**Authors**: Simon Peyton Jones, Mark Shields (Microsoft Research)  
**Date**: April 2004 (ICFP submission)  
**Location**: [`systemf/docs/research/`](../systemf/docs/research/)

| File | Description |
|------|-------------|
| [`Jones and Shields - Lexically-scoped type variables.pdf`](../systemf/docs/research/Jones%20and%20Shields%20-%20Lexically-scoped%20type%20variables.pdf) | Original PDF |
| [`jones-shields-2002-scoped-type-variables.txt`](../systemf/docs/research/jones-shields-2002-scoped-type-variables.txt) | Plain text extraction (1,173 lines) |
| [`jones-shields-2002-index.txt`](../systemf/docs/research/jones-shields-2002-index.txt) | Line number index |

**Key contribution**: Formalizes scoped type variables (the ability to use type variables from outer scope in inner type annotations). Compares "type-lambda" (SML) vs "type-sharing" (GHC) approaches.

**Relationship to Putting 2007**: Foundation for scoped type variables used in higher-rank systems. The pattern signature `(x :: a)` brings `a` into scope for inner annotations.

---

## Paper Relationships

```
Jones & Shields 2002 (Scoped Type Variables)
        ↓
Putting 2007 (Higher-Rank Type Inference)  ←  You are here
        ↓
Eisenberg 2016 (Visible Type Application)
```

**Reading order for implementation:**
1. **Jones & Shields** - Understand scoped type variables (HMV_Annot, SB_Annot rules)
2. **Putting 2007** - Understand bidirectional checking and higher-rank inference
3. **Eisenberg 2016** - Add visible type application on top of the above

---

## Further Reading

1. **Original Paper**: Journal of Functional Programming, 2007
2. **GHC Core**: [System FC specification](https://gitlab.haskell.org/ghc/ghc/-/blob/master/docs/core-spec/)
3. **Idris2**: [Core TT module](https://github.com/idris-lang/Idris2/blob/main/src/Core/TT/Term.idr)
4. **Coercible Paper**: "Safe Coercions" (JFP'16) - for newtype handling
5. **Roles Paper**: "Generative Type Abstraction" (ICFP'11)

---

## Reference Implementation Details

From [`putting-2007-implementation.hs`](putting-2007-implementation.hs) - the working Haskell code from Appendix A.

### Meta Type Variable Structure

```haskell
data MetaTv = Meta Uniq (IORef (Maybe Tau))
```

- `IORef` allows **in-place mutation** for unification
- `Nothing` = unbound/unknown meta variable
- `Just tau` = solved (tau may itself be another MetaTv)
- Creates a **chain** for union-find style unification

### Key Functions

```haskell
-- Instantiate: replace ∀ with fresh metas
instantiate :: Sigma -> Tc Rho
instantiate (ForAll tvs ty) = do
    tvs' <- mapM (\_ -> newMetaTyVar) tvs
    return (substTy tvs (map MetaTv tvs') ty)

-- Skolemise: replace ∀ with rigid skolem constants
skolemise :: Sigma -> Tc ([TyVar], Rho)
skolemise (ForAll tvs ty) = do
    sks <- mapM newSkolemTyVar tvs
    (sks2, ty') <- skolemise (substTy tvs (map TyVar sks) ty)
    return (sks1 ++ sks2, ty')

-- Quantify: bind free metas to forall
quantify :: [MetaTv] -> Rho -> Tc Sigma
quantify tvs ty = do
    mapM_ bind (tvs `zip` new_bndrs)  -- Bind each meta to a bound var
    ty' <- zonkType ty                  -- Follow chains, substitute
    return (ForAll new_bndrs ty')
```

### Unification Chain Resolution

```haskell
zonkType :: Type -> Tc Type
zonkType (MetaTv tv) = do
    mb_ty <- readTv tv
    case mb_ty of
        Nothing -> return (MetaTv tv)  -- Unbound, return as-is
        Just ty -> do
            ty' <- zonkType ty          -- Follow chain recursively
            writeTv tv ty'              -- Path compression!
            return ty'
```

**Pattern**: When a MetaTv points to `Just ty`, recursively resolve `ty` (which may be another MetaTv). Write back the final result for path compression.

### Unification with Occurs Check

```haskell
unifyVar :: MetaTv -> Tau -> Tc ()
unifyVar tv1 ty2 = do
    mb_ty1 <- readTv tv1
    case mb_ty1 of
        Just ty1 -> unify ty1 ty2     -- Already bound, unify that
        Nothing -> unifyUnboundVar tv1 ty2

unifyUnboundVar :: MetaTv -> Tau -> Tc ()
unifyUnboundVar tv1 ty2@(MetaTv tv2) = do
    mb_ty2 <- readTv tv2
    case mb_ty2 of
        Just ty2' -> unify (MetaTv tv1) ty2'  -- tv2 is alias, follow it
        Nothing -> writeTv tv1 ty2            -- Both unbound, create link

unifyUnboundVar tv1 ty2 = do
    tvs2 <- getMetaTyVars [ty2]           -- Get all metas in ty2
    if tv1 `elem` tvs2 then
        occursCheckErr tv1 ty2            -- OCCURS CHECK!
    else
        writeTv tv1 ty2                   -- Safe to bind
```

**Key insights**:
1. **Chain following**: If meta A points to meta B, unify with B's value
2. **Alias chains**: If both unbound, create link A → B
3. **Occurs check**: Before binding, ensure meta doesn't appear in target type
4. **Path compression**: `zonkType` flattens chains after unification

### The Create → Unify → Generalize Pattern

```haskell
-- In inferSigma (GEN1)
exp_ty <- inferRho e                    -- Create metas, unify as needed
env_tvs <- getMetaTyVars env_tys        -- What's locked in Γ?
res_tvs <- getMetaTyVars [exp_ty]       -- What's in result?
let forall_tvs = res_tvs \\ env_tvs    -- Subtract to find candidates
quantify forall_tvs exp_ty              -- Bind survivors to ∀
```

**Flow**:
1. **Create**: Fresh metas during inference
2. **Unify**: Constrain metas through type checking
3. **Survivors**: Metas not locked by Γ become ∀

---

## Critical Insight: ftv(ρ) - ftv(Γ)

**What it means:** "Type variables in the result that aren't locked down by the environment"

The GEN1 rule generalizes over variables that appear free in the result type but NOT in the environment:

```haskell
ā = ftv(ρ) - ftv(Γ)   -- Variables free to be polymorphic
```

### Why This Blocks Generalization

```haskell
\x -> let y = x in y
-- ρ = _a (y's type is same as x's)
-- Γ = {x : _a}  (x claims _a)
-- ftv(ρ) - ftv(Γ) = {_a} - {_a} = {}
-- Result: y : _a (MONOMORPHIC - _a is locked to x!)
```

### Why This Allows Generalization

```haskell
let id = \x -> x in ...
-- ρ = _a -> _a
-- Γ = {} (empty at top level)
-- ftv(ρ) - ftv(Γ) = {_a} - {} = {_a}
-- Result: id : ∀a. a -> a (POLYMORPHIC!)
```

### The Pattern

- `extendEnv x _a` → locks `_a` to `x` → blocks generalization
- Empty Γ at `let` → no locks → can generalize all free vars
- This is the **Damas-Milner restriction**: polymorphism only at `let`, never at `λ`

---

## Summary

This work shows that:

1. **Higher-rank type inference is practical** and implementable
2. **Bidirectional checking** elegantly handles annotated vs inferred types
3. **Recursive types need no special core representation** - just name resolution
4. **Real compilers** (GHC, Idris2) use this simple, uniform approach

The elegance of the solution is that **complexity emerges from simple building blocks**: unification variables, bidirectional checking, and ordered context management.
