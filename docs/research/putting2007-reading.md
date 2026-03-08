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

## Further Reading

1. **Original Paper**: Journal of Functional Programming, 2007
2. **GHC Core**: [System FC specification](https://gitlab.haskell.org/ghc/ghc/-/blob/master/docs/core-spec/)
3. **Idris2**: [Core TT module](https://github.com/idris-lang/Idris2/blob/main/src/Core/TT/Term.idr)
4. **Coercible Paper**: "Safe Coercions" (JFP'16) - for newtype handling
5. **Roles Paper**: "Generative Type Abstraction" (ICFP'11)

---

## Summary

This work shows that:

1. **Higher-rank type inference is practical** and implementable
2. **Bidirectional checking** elegantly handles annotated vs inferred types
3. **Recursive types need no special core representation** - just name resolution
4. **Real compilers** (GHC, Idris2) use this simple, uniform approach

The elegance of the solution is that **complexity emerges from simple building blocks**: unification variables, bidirectional checking, and ordered context management.
