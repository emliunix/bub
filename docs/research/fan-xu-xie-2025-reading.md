# Practical Type Inference with Levels - Reading Notes

**Paper**: Fan, Xu, and Xie (2025)  
**Full Title**: "Practical Type Inference with Levels"  
**Venue**: PLDI 2025 (Proc. ACM Program. Lang., Vol. 9, No. PLDI, Article 235)  
**Pages**: 24 pages  
**DOI**: https://doi.org/10.1145/3729338

**Index**: [`fan-xu-xie-2025-index.md`](fan-xu-xie-2025-index.md) - Line number reference for navigating the extracted text

---

## Overview

This paper presents the **first comprehensive formalization of levels** in type inference, demonstrating that level-based techniques can efficiently and safely implement multiple type system features:

1. **Let generalization** - previously required traversing entire typing context
2. **Higher-rank polymorphism** - skolem escape prevention
3. **Type regions** - local datatype declarations without escape

The key insight is that **level numbers** (integers tracking nesting depth) provide a unified mechanism that is both efficient (O(|type|) vs O(|context|)) and formally sound. The paper proves soundness and completeness via Coq mechanization.

### Key Problem Being Solved

Standard HM type inference requires computing `ftv(τ) - ftv(Γ)` for generalization, which traverses the entire typing context. This is inefficient:

```haskell
-- Standard generalization (slow)
let f = λx → x in (f 1, f True)
-- Need to scan all of Γ to find free vars in λx.x
```

Level-based approach tracks variable levels, enabling O(|type|) generalization by collecting only variables at the current level.

---

## Key Concepts

### 1. Level Numbers and the Level Invariant

**Definition**: Each type variable is associated with an integer level `n`, where level 0 is the outermost/top level.

```
Level 0: Top-level scope
Level 1: Inside let RHS
Level 2: Nested polymorphism scope
```

**The Level Invariant** (Fundamental Rule):

```
Context Level ≥ Variable Level
```

A variable at level `n` can only be used when the typing context is at level `≥ n`.

| Variable | Level | Meaning |
|----------|-------|---------|
| `aⁿ` | n | Type variable created at level n |
| `Tⁿ` | n | Type constructor created at level n |
| `α̂ⁿ` | n | Unification variable created at level n |
| `σ ⩽ⁿ` | ≤ n | Type with level at most n |

### 2. Level-Based Generalization (ftv_{n+1})

**Traditional HM** (requires context scan):

```haskell
-- Rule HM-let (slow)
Ψ ⊢ e₁ : τ₁    Ψ, x : ∀ā.τ₁ ⊢ e₂ : τ₂    ā ∉ ftv(Ψ)
-------------------------------------------------
          Ψ ⊢ let x = e₁ in e₂ : τ₂
```

**Level-Based** (O(|type|)):

```haskell
-- Rule let (fast)
Ψ ⊢ₙ₊₁ e₁ : σ₁    Ψ, x : ∀ftvₙ₊₁(σ₁).σ₁ ⊢ₙ e₂ : σ₂
-------------------------------------------------
          Ψ ⊢ₙ let x = e₁ in e₂ : σ₂
```

**Key insight**: Variables at level `n+1` cannot appear in `Ψ` (which only has variables at level ≤ n). Therefore `ftvₙ₊₁(σ₁)` gives exactly the variables to generalize without scanning Ψ!

### 3. Polymorphic Promotion (Figure 7)

When unifying a unification variable with a type, we must "promote" the type to ensure the level invariant is maintained.

**Promotion Judgment**: `Γ ⊢ σ ⇝ᵐ± τ ⊣ Δ`

Promotes type `σ` to monotype `τ` at level `m` with polarity `±`:
- **Positive (+)**: `σ` is subtype of `τ` (for `σ <: α̂`)
- **Negative (-)**: `σ` is supertype of `τ` (for `α̂ <: σ`)

**Promotion Rules**:

| Rule | Premise | Effect |
|------|---------|--------|
| `pr-sk` | `aᵐ¹ ∈ Γ` and `m₁ ≤ m₂` | Promote type variable if level ≤ target |
| `pr-tyctor` | `Tᵐ¹ ∈ Γ` and `m₁ ≤ m₂` | Promote type constructor if level ≤ target |
| `pr-uvar` | `α̂ᵐ¹ ∈ Γ` and `m₁ ≤ m₂` | Keep unification variable if level ≤ target |
| `pr-uvarPr` | `α̂ᵐ¹ ∈ Γ` and `m₁ > m₂` | **Lower level**: Create new `α̂₂ᵐ²`, set `α̂₁ = α̂₂` |
| `pr-forallPos` | (+) polarity | Instantiate ∀ with fresh unification variable |
| `pr-forallNeg` | (-) polarity | Instantiate ∀ with fresh type variable at m+1 |

**Example**:

```
-- Unifying: α̂⁰ <: ∀b. b → b
-- Promotion under (+):
Γ ⊢ ∀b. b → b ⇝⁺⁰ β̂ → β̂  (instantiate b with β̂⁰)

-- Unifying: α̂⁰ <: ∀b. b → b  (doesn't work under -)
Γ ⊢ ∀b. b → b ⇝⁻⁰ ?  (fails - can't promote polymorphic type to monotype)
```

### 4. Algorithmic Type System with Levels (Figure 4-5)

**Syntax** (extends monotypes with unification variables):

```
σ ::= ∀a.σ | σ₁ → σ₂ | τ           (Polymorphic types)
τ ::= Int | a | T | τ₁ → τ₂ | α̂    (Monomorphic types + unification vars)
```

**Algorithmic Context** `Γ`:
- `Tⁿ` - Type constructor at level n
- `aⁿ` - Type variable at level n  
- `α̂ⁿ` - Unsolved unification variable at level n
- `α̂ⁿ = τ` - Solved unification variable

**Key Algorithmic Rules**:

**at-lam** (Lambda abstraction):
```
Γ, α̂ⁿ ⊢ Σ, x:α̂ ⊢ₙ e ⇒ σ ⊣ Δ
---------------------------
Γ ⊢ₙ λx.e ⇒ α̂ → σ ⊣ Δ
```
Creates fresh unification variable at current level.

**at-let** (Let generalization):
```
Γ ⊢ₙ₊₁ e₁ ⇒ σ₁ ⊣ Θ    fuvₙ₊₁ᴼ([Θ]σ₁) = α̂̄
Θ ⊢ Σ, x:∀ā.(([Θ]σ₁)[α̂̄:=ā]) ⊢ₙ e₂ ⇒ σ₂ ⊣ Δ
--------------------------------------------
       Γ ⊢ₙ let x=e₁ in e₂ ⇒ σ₂ ⊣ Δ
```

**at-forall** (Polymorphic checking):
```
Γ, aⁿ⁺¹ ⊢ₙ₊₁ e ⇐ σ ⊣ Δ
----------------------
Γ ⊢ₙ e ⇐ ∀a.σ ⊣ Δ
```

### 5. Higher-Rank Polymorphism and Skolem Escape

**The Problem**:

```haskell
-- Should be rejected:
(λ(f :: ∀c. c → ∀d. d → d) → f 1) g
-- where g :: ∀a b. a → b → b
```

The subtyping `∀a b. a → b → b <: ∀c. c → ∀d. d → d` fails because `d` would need to be instantiated with `b`, but `d` is introduced after `b` goes out of scope.

**Level-Based Solution**:

1. When checking subtyping, increment level
2. Skolemize type variables at the new level
3. Unification variables from outer scope have lower levels
4. **Level invariant prevents unification**: `α̂¹` cannot unify with `skolem²`

**Subtyping Rules** (Figure 6):

```
as-forallR:  Γ, aⁿ⁺¹ ⊢ₙ₊₁ σ₁ <: σ₂ ⊣ Δ
         -----------------------------
          Γ ⊢ₙ σ₁ <: ∀a.σ₂ ⊣ Δ

as-forallL:  Γ, α̂ⁿ ⊢ₙ σ₁[a:=α̂] <: σ₂ ⊣ Δ
         --------------------------------
          Γ ⊢ₙ ∀a.σ₁ <: σ₂ ⊣ Δ

as-solveL:  α̂ ∉ fuv(σ)    Γ ⊢ σ ⇝⁻ᵐ τ ⊣ Δ
         ----------------------------------
          Γ ⊢ₙ α̂ <: σ ⊣ Δ[α̂ᵐ=τ]
```

### 6. Type Regions (Local Datatypes)

**Example**:

```haskell
data Tree = Leaf Int | Node Tree Tree in
let f x = case x of Leaf i → i; Node y z → f y + f z
in f (Node (Leaf 2) (Leaf 3))  -- OK: Tree doesn't escape

-- Error case:
data Tree = Leaf Int | Node Tree Tree in
Leaf 5  -- Error: Tree escapes its scope
```

**Level-Based Enforcement**:

```
lt-data:  Γ ⊢ₙ σⱼⱼ   Γ, Tⁿ⁺¹, Dᵢ:σⱼⱼ→T ⊢ₙ₊₁ e ⇒ σ ⩽ⁿ
--------------------------------------------------
        Γ ⊢ₙ data T=Dᵢ σⱼⱼ in e ⇒ σ
```

Since `σ` must have level ≤ n, it cannot contain `T` which is at level n+1.

---

## Files Reference

### Main Paper Documentation

**File**: [`docs/research/fan-xu-xie-2025-practical-type-inference-with-levels.txt`](fan-xu-xie-2025-practical-type-inference-with-levels.txt)

Plain text extraction of the paper for searching and reference.

**Index**: [`docs/research/fan-xu-xie-2025-index.md`](fan-xu-xie-2025-index.md)

Line number index for navigating the extracted text. Use this to find specific sections, figures, and rules quickly.

### Key Figures and Rules

| Figure | Content | Location (lines) |
|--------|---------|------------------|
| Figure 1 | Syntax (expressions, types, contexts) | 357-383 |
| Figure 2 | Declarative type system (selected rules) | 385-498 |
| Figure 3 | Level-based declarative type system | 575-730 |
| Figure 4 | Algorithmic system syntax, context application, well-formedness | 1005-1087 |
| Figure 5 | Algorithmic typing rules | 1128-1279 |
| Figure 6 | Algorithmic subtyping | 1294-1360 |
| Figure 7 | Polymorphic promotion judgment | 1362-1449 |
| Figure 8 | Example derivation | 1545-1583 |
| Figure 9 | Well-formedness of contexts | 1667-1757 |
| Figure 10 | Context extension | 1759-1807 |

### Coq Mechanization

**Location**: Paper artifact / supplementary material

Complete Coq proofs including:
- Level-based declarative system (Section 4)
- Soundness: level-based ⇒ non-level-based (Theorem 5.2)
- Completeness: non-level-based ⇒ level-based (Theorem 5.7)
- Algorithmic system soundness (Theorem 6.3)
- Algorithmic system completeness (Theorem 6.6)
- Locally nameless representation for binding structure

### Koka Implementation

**Reference**: Section 7 of the paper

Implementation details:
- Level tracking integrated with Koka's type-and-effect system
- Performance evaluation: 2.9-3.7x faster generalization
- 308 test cases validated

---

## Deep Dive: Polymorphic Promotion in Detail

### The Core Problem

When unifying `α̂ᵐ` with type `σ`, we need to ensure the solution doesn't violate the level invariant. Since `α̂` is at level `m`, its solution must only reference variables at level ≤ m.

### Promotion Process

**Example 1**: Successful promotion (positive polarity)

```
-- Unifying: α̂⁰ <: ∀b. b → b

1. as-solveR applies (since α̂ on right)
2. Need to promote ∀b. b → b under (+) to level 0

   Γ, β̂⁰ ⊢ b → b [b:=β̂] ⇝⁺⁰ β̂ → β̂   (pr-forallPos)
   -----------------------------------
   Γ ⊢ ∀b. b → b ⇝⁺⁰ β̂ → β̂

3. Set α̂⁰ = β̂ → β̂
```

**Example 2**: Variable level lowering

```
-- Context: Γ = α̂⁰, β̂¹
-- Unifying: α̂⁰ <: β̂¹ → β̂¹

1. as-solveL applies
2. Promote β̂¹ → β̂¹ under (-) to level 0:

   β̂¹ must be lowered to level 0!
   
   -- pr-uvarPr (since 1 > 0):
   Create β̂₁⁰, set β̂¹ = β̂₁⁰
   
   Γ, β̂₁⁰, β̂¹=β̂₁⁰ ⊢ β̂₁ ⇝⁻⁰ β̂₁   (pr-uvar, since 0 ≤ 0)
   --------------------------------------------------
   Γ ⊢ β̂ → β̂ ⇝⁻⁰ β̂₁ → β̂₁

3. Set α̂⁰ = β̂₁ → β̂₁
```

**Example 3**: Failed promotion (skolem escape)

```
-- Context: Γ = α̂⁰, b¹
-- Unifying: α̂⁰ <: b¹ → b¹

1. as-solveL applies
2. Try to promote b¹ → b¹ under (-) to level 0:

   For b¹: need b¹.level ≤ 0, but 1 > 0
   -- pr-sk fails!

3. Promotion fails → unification fails
```

This is correct! We prevented `b` from escaping its scope through unification.

### Why Polarity Matters

**Positive (+)**: Type is a **subtype** of the unification variable
- ∀ can be instantiated (we're making the type more specific)
- Example: `∀a. a → a` is subtype of `Int → Int`

**Negative (-)**: Type is a **supertype** of the unification variable  
- ∀ must be skolemized (we're making the type more general)
- Example: No monotype is a supertype of `∀a. a → a`

---

## Deep Dive: Levels Unify Three Mechanisms

| Mechanism | Traditional Approach | Level-Based Approach |
|-----------|---------------------|---------------------|
| **Let Generalization** | `ftv(τ) - ftv(Γ)` (context scan) | `ftvₙ₊₁(τ)` (O(\|type\|)) |
| **Skolem Escape** | Post-hoc check after unification | Level invariant prevents escape |
| **GADT Untouchable** | Implication constraint machinery | `meta.level < current.level` |

**All reduce to**: Comparing two integers (level numbers)!

### Comparison: Level-Based vs Constraint-Based (OutsideIn(X))

| Aspect | OutsideIn(X) | Fan et al. Levels |
|--------|-------------|-----------------|
| Core abstraction | Constraints + implications | Levels on variables |
| Generalization | Solve constraints at let | Collect level-n+1 vars |
| Skolem escape | Separate post-check | Level invariant |
| GADT handling | Untouchables via implication | Level comparison |
| Complexity | Higher (constraint solver) | Lower (level tracking) |
| Power | Accepts more programs | Rejects some edge cases |

**Trade-off**: Levels are simpler and more efficient but may reject some programs that OutsideIn(X) accepts. Both guarantee principal types when they succeed.

---

## Implementation Details

### Level Representation

```haskell
-- TcLevel is just an Int
newtype TcLevel = TcLevel Int

topTcLevel :: TcLevel
topTcLevel = TcLevel 0

pushTcLevel :: TcLevel -> TcLevel
pushTcLevel (TcLevel n) = TcLevel (n + 1)
```

### Type Variables with Levels

```haskell
data TcTyVar =
  | MetaTv {
      mtv_ref   :: IORef MetaDetails,
      mtv_tclvl :: TcLevel    -- Creation level
    }
  | SkolemTv {
      sk_lvl    :: TcLevel,   -- Binding level
      sk_info   :: SkolemInfo
    }
  | BoundTv {
      bndr_name :: Name,
      bndr_lvl  :: TcLevel
    }
```

### The Level Invariant Check

```haskell
checkLevelInvariant :: TcLevel -> TcLevel -> Bool
checkLevelInvariant (TcLevel ctxt_lvl) (TcLevel var_lvl) = 
    ctxt_lvl >= var_lvl

-- Usage in unification:
unifyVar :: MetaTv -> Type -> TcM ()
unifyVar meta ty = do
    let meta_lvl = mtv_tclvl meta
    ty_lvl <- getTypeLevel ty
    unless (checkLevelInvariant meta_lvl ty_lvl) $
        fail "Level invariant violated: variable would escape"
    -- ... proceed with unification
```

### Touchability Check

```haskell
isTouchable :: TcLevel -> MetaTv -> Bool
isTouchable ctxt_lvl meta = 
    mtv_tclvl meta == ctxt_lvl

-- Untouchable: meta.level < ctxt_lvl
-- (meta from outer scope under local assumption)
-- This prevents GADT variables from being solved prematurely
```

### Generalization Algorithm

```haskell
generalize :: TcLevel -> Type -> TcM Scheme
generalize lvl ty = do
    -- Collect all unification variables at level (lvl + 1)
    let vars_at_next_level = filter (\v -> mtv_tclvl v == lvl + 1) (freeMetaVars ty)
    
    -- Convert them to bound variables
    bound_vars <- mapM (const newBoundVar) vars_at_next_level
    
    -- Substitute in the type
    let ty' = substTypes vars_at_next_level bound_vars ty
    
    return $ Scheme bound_vars ty'
```

**Complexity**: O(|type|) - only traverse the type, not the context!

### Skolemization with Anticipatory Levels

```haskell
skolemize :: TcLevel -> Type -> TcM ([SkolemTv], Type)
skolemize lvl (ForAll vars body) = do
    -- Create skolems at level (lvl + 1)
    skolems <- mapM (\v -> newSkolemTv (lvl + 1)) vars
    
    -- Substitute and continue at incremented level
    let body' = substTypes vars skolems body
    (more_skolems, rho) <- skolemize (pushTcLevel lvl) body'
    
    return (skolems ++ more_skolems, rho)
skolemize lvl ty = return ([], ty)
```

**Key insight**: Create skolems at level n+1, then work at level n+1. The level invariant naturally prevents escape.

---

## Related Papers (Research Collection)

### 1. Rémy 1992 - Original Level-Based Generalization

**Paper**: "Extension of ML type system with a sorted equation theory on types"  
**Author**: Didier Rémy  
**Type**: Ph.D. Dissertation, INRIA

**Key contribution**: First introduction of levels (called "ranks") for efficient let-generalization in ML. Showed that generalization can be O(|type|) instead of O(|context|).

**Relationship to Fan et al. 2025**: Fan et al. extend Rémy's work beyond let-generalization to higher-rank polymorphism, type regions, and provide complete formalization with Coq proofs.

### 2. Putting 2007 - Bidirectional Type Checking Foundation

**Paper**: "Practical Type Inference for Arbitrary-Rank Types"  
**Authors**: Peyton Jones, Vytiniotis, Weirich, Shields  
**Journal**: Journal of Functional Programming, 2007

**Key contribution**: Complete bidirectional type inference algorithm for higher-rank polymorphism. Uses meta type variables and deep skolemization.

**Relationship to Fan et al. 2025**: Fan et al. build on Putting's bidirectional system but replace the skolem escape checking mechanism with level-based prevention. Both use two-mode checking (⊢⇑ inference, ⊢⇓ checking).

### 3. OutsideIn(X) 2011 - Constraint-Based Approach

**Paper**: "OutsideIn(X): Modular type inference with local assumptions"  
**Authors**: Vytiniotis, Peyton Jones, Schrijvers, Sulzmann  
**Journal**: Journal of Functional Programming, 2011

**Key contribution**: Constraint-based type inference with implication constraints for GADTs. Uses "untouchable" variables under local assumptions.

**Relationship to Fan et al. 2025**: 
- OutsideIn(X): Uses implication constraints `Q ⊃ Q'` and checks for untouchables after solving
- Fan et al.: Uses levels directly - a variable is untouchable if `var.level < current.level`
- Levels are simpler but may be less powerful for some GADT patterns

### 4. Dunfield & Krishnaswami 2013 - Ordered Contexts

**Paper**: "Complete and easy bidirectional typechecking for higher-rank polymorphism"  
**Authors**: Jana Dunfield, Neelakantan R. Krishnaswami  
**Venue**: ICFP 2013

**Key contribution**: Elegant formalization using ordered contexts where variables must be solved left-to-right. Prevents skolem escape via context ordering.

**Relationship to Fan et al. 2025**: 
- Ordered contexts: Maintain strict order; unification variable can only reference preceding variables
- Levels: More flexible ordering; any variable can reference any variable at lower or equal level
- Levels are more efficient in practice (less context manipulation)

### 5. Kuan & MacQueen 2007 - Efficient Type Inference

**Paper**: "Efficient type inference using ranked type variables"  
**Authors**: George Kuan, David MacQueen  
**Venue**: ML Workshop 2007

**Key contribution**: Practical implementation of level-based generalization showing efficiency improvements.

**Relationship to Fan et al. 2025**: Provided empirical evidence for level efficiency. Fan et al. provide the first complete formal proofs and extend to higher-rank polymorphism.

---

## Paper Relationships

### Type System Evolution

```
Damas & Milner 1982 (HM type inference)
         ↓
Rémy 1992 (Levels for let-generalization)
         ↓
Odersky & Läufer 1996 (Higher-rank polymorphism)
         ↓
Putting 2007 (Complete higher-rank inference)
         ↓
OutsideIn(X) 2011 (Constraints for GADTs)
         ↓
Fan et al. 2025 (Levels unify everything)
```

### Level-Based Lineage

```
Rémy 1992 (Original level-based generalization)
         ↓
Kuan & MacQueen 2007 (Efficient implementation)
         ↓
GHC Implementation (TcLevel for untouchables, ~2010s)
         ↓
Kiselyov 2022 (OCaml levels explained)
         ↓
Fan et al. 2025 (Complete formalization)
```

### Reading Order for Implementation

1. **Damas & Milner 1982** - Understand HM basics and standard generalization
2. **Putting 2007** - Understand bidirectional checking and higher-rank inference  
3. **Fan et al. 2025** - Understand level-based approach (this paper)
4. **OutsideIn(X) 2011** - Understand the constraint-based alternative

**Trade-offs**:
- Use **levels** when you want simplicity and efficiency
- Use **constraints** when you need maximum expressiveness for GADTs

---

## Summary

This paper establishes that **level numbers are the right abstraction** for managing type variable scope in practical type inference:

### Key Achievements

1. **First comprehensive formalization** of levels beyond let-generalization
   - Let generalization: O(|type|) vs O(|context|)
   - Higher-rank polymorphism: Level-based skolem escape prevention
   - Type regions: Level-based scope checking

2. **Novel polymorphic promotion** judgment
   - Handles unification with level constraints
   - Uses polarity to determine instantiation vs skolemization
   - Enables lowering of unification variable levels

3. **Mechanized proofs** in Coq
   - Soundness: level-based ⇒ non-level-based
   - Completeness: non-level-based ⇒ level-based  
   - Algorithmic soundness and completeness

4. **Validated in practice**
   - Implemented in Koka compiler
   - 2.9-3.7x faster generalization
   - 308 test cases passing

### The Elegance of Levels

| Feature | Before Levels | With Levels |
|---------|---------------|-------------|
| Generalization | `ftv(τ) - ftv(Γ)` | `ftvₙ₊₁(τ)` |
| Complexity | O(\|context\|) | O(\|type\|) |
| Skolem escape | Post-hoc check | Level invariant |
| GADT untouchable | Implication machinery | `meta.level < ctxt.level` |
| **All unified by** | **Different mechanisms** | **Level comparison** |

### Core Insights

1. **Level invariant** (`context.level >= var.level`) is sufficient to ensure soundness
2. **Generalization at level n+1** requires only type traversal, not context traversal
3. **Skolem escape prevention** happens automatically via level comparison during unification
4. **Untouchability** is simply: variable level < current typing level

### Practical Impact

This work provides the theoretical foundation for level-based type inference used in:
- **GHC**: TcLevel system for untouchables and generalization
- **OCaml**: Level-based type inference with in-place level updates
- **Koka**: Validated implementation with measurable performance gains

**The bottom line**: Levels provide a simple, efficient, and formally verified foundation for advanced type inference.

---

## Further Reading

### Original Sources

1. **Fan et al. 2025**: "Practical Type Inference with Levels", PLDI 2025, Article 235
2. **Rémy 1992**: "Extension of ML type system with a sorted equation theory on types", Ph.D. Thesis
3. **Putting 2007**: "Practical Type Inference for Arbitrary-Rank Types", JFP 2007

### Implementation References

4. **GHC Documentation**: 
   - `Note [TcLevel and untouchable type variables]`
   - `Note [TcLevel assignment]`
   - `Note [Skolemising type variables]`
   
5. **Koka**: https://koka-lang.github.io/

6. **OCaml Levels**: Kiselyov's blog post "How OCaml type checker works"

### Related Papers

7. **OutsideIn(X) 2011**: Vytiniotis et al., JFP 2011
8. **Dunfield & Krishnaswami 2013**: ICFP 2013  
9. **Kuan & MacQueen 2007**: ML Workshop 2007
10. **Carnier et al. 2024**: "Type Inference Logics", OOPSLA 2024 (verified constraint-based inference)
