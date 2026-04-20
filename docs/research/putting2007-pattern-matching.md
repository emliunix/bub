# Pattern Matching in Putting 2007

**Paper**: "Practical Type Inference for Arbitrary-Rank Types"
**Authors**: Peyton Jones, Vytiniotis, Weirich, Shields (2007)

A comprehensive account of everything the paper says about pattern matching, using the paper's own terms, conventions, and type-system language.

---

## 1. Source Language Syntax for Patterns

The paper extends the core term syntax (Section 7.2, line 3782) with **pattern abstractions** and a rich pattern language:

### Terms

```
t, u ::= ... | \p.t       Pattern abstraction
```

### Patterns

```
p ::= x                    Variable
    | _                    Wild card
    | (p :: σ)             Type-annotated pattern
    | (p1, p2)             Pair
    | K p1 ... pn          Constructor pattern (added in §7.3)
```

The type-annotated pattern `(p :: σ)` is the pattern-level analogue of the expression-level annotation `(t :: σ)`. It brings `σ` into scope as the type of the thing being matched.

---

## 2. The Pattern Typing Judgement

The paper introduces a new judgement form (§7.2, line 3813):

```
⊢patδ  p : σ, Γ′
```

This reads: "pattern `p` has type `σ` and binds variables described by environment `Γ′`."

Key design points:

- **`Γ′` is an output**, written on the right of the judgement as a hint (it has no mathematical significance to the judgement's meaning).
- **`δ` is the direction** (`⇑` inference or `⇓` checking), consistent with the bidirectional framework.
- **`σ` is a Sigma-type** (polymorphic type), not just a Rho-type or Tau-type. This is because the argument position of a function can be a `σ`-type in a higher-rank system.

The pattern judgement is used in the `abs` rule for pattern-matching lambda:

```
        ⊢patδ  p : σ, Γ′    Γ, Γ′ ⊢δ t : ρ
abs:    ───────────────────────────────────────
        Γ ⊢δ (\p.t) : (σ → ρ)
```

This **single rule** replaces the four previous rules (`abs1`, `abs2`, `aabs1`, `aabs2`) from the simpler variable-only system. The same `⊢pat` judgement can be reused by all constructs that use pattern-matching: `case` expressions, list comprehensions, `do` notation, and so on.

---

## 3. The Core Function: `tcPat`

The central implementation function (§7.2, line 3847):

```haskell
tcPat :: Pat -> Expected Sigma -> Tc [(Name, Sigma)]
```

- **Input**: a pattern and an `Expected Sigma` type (the same `Expected` datatype used by `tcRho` — either `Infer (IORef Rho)` or `Check Sigma`).
- **Output**: a list of `(Name, Sigma)` bindings — the variables bound by the pattern, each with its possibly-polymorphic type.

### 3.1 Wild-card Pattern

```haskell
tcPat PWild exp_ty = return []
```

Trivial: succeed immediately, returning the empty environment. No variables are bound.

### 3.2 Variable Pattern

```haskell
tcPat (PVar v) (Infer ref) = do { ty <- newTyVar
                                 ; writeTcRef ref ty
                                 ; return [(v, ty)] }
tcPat (PVar v) (Check ty)  = return [(v, ty)]
```

Splits into two cases, mirroring the bidirectional structure:

- **Inference mode**: create a fresh monomorphic meta type variable, write it into the inference ref, and bind `v` to it. This corresponds to the `abs1` rule where `x` gets type `τ`.
- **Checking mode**: the expected type is already known, so simply bind `v` to it. This corresponds to the `abs2` rule where `x` gets type `σa`.

### 3.3 Type-Annotated Pattern

```haskell
tcPat (PAnn p pat_ty) exp_ty = do { checkPat p pat_ty
                                   ; instPatSigma pat_ty exp_ty }
```

Analogous to the expression-level annotation rule `annot`. The pattern `p` is checked against `pat_ty` (the annotation), and then `instPatSigma` reconciles `pat_ty` with the expected type `exp_ty`.

### 3.4 The `instPatSigma` Function

```haskell
instPatSigma :: Sigma -> Expected Sigma -> Tc ()
instPatSigma pat_ty (Infer ref) = writeTcRef ref pat_ty
instPatSigma pat_ty (Check exp_ty) = subsCheck exp_ty pat_ty
```

This checks that the expected type `exp_ty` is **at least as polymorphic** as the pattern type `pat_ty`:

- **Inference mode**: simply write the pattern type into the ref.
- **Checking mode**: use `subsCheck` to verify subsumption `exp_ty ≥ pat_ty`. This is the key: the *context* must supply a type at least as polymorphic as what the pattern expects.

---

## 4. Pattern-Matching Lambda (`PLam`)

The `tcRho` function handles pattern-matching lambda with the now-familiar bidirectional split (§7.2, line 3875):

```haskell
tcRho (PLam pat body) (Infer ref)
  = do { (binds, pat_ty) <- inferPat pat
       ; body_ty <- extendVarEnvList binds (inferRho body)
       ; writeTcRef ref (pat_ty --> body_ty) }

tcRho (PLam pat body) (Check ty)
  = do { (arg_ty, res_ty) <- unifyFun ty
       ; binds <- checkPat pat arg_ty
       ; extendVarEnvList binds (checkRho body res_ty) }
```

Where `inferPat` and `checkPat` are simple wrappers for `tcPat`, just as `inferRho` and `checkRho` wrap `tcRho`. The function `extendVarEnvList` extends the environment with a list of bindings from the pattern.

**Checking mode** decomposes the expected function type via `unifyFun`, pushes the argument type into the pattern, and pushes the result type into the body.

**Inference mode** infers the pattern type, infers the body type under the pattern bindings, and constructs the function type.

---

## 5. Constructor Patterns and Higher-Ranked Data Constructors

### 5.1 The Problem

Section 7.3 (line 3888) introduces constructor patterns with higher-ranked types. Consider:

```haskell
data T = MkT (forall a. a -> a)
```

The constructor `MkT` has type:

```
MkT :: (∀a. a → a) → T
```

When **constructing** values, `MkT` is treated as an ordinary function with a higher-rank type (no new machinery needed).

When **pattern-matching**, we need something new:

```haskell
case x of
  MkT v -> (v 3, v True)
```

We want `v` to be attributed type `∀a. a → a` **without** requiring an explicit annotation. The data type declaration should be sufficient.

### 5.2 Extended Pattern Syntax

```haskell
data Pat = ... | PCon Name [Pat]
```

Where `Name` is the name of a data constructor bound in the type environment.

### 5.3 The `tcPat` Case for Constructor Patterns

```haskell
tcPat (PCon con ps) exp_ty
  = do { (arg_tys, res_ty) <- instDataCon con
       ; envs <- mapM check_arg (ps `zip` arg_tys)
       ; instPatSigma res_ty exp_ty
       ; return (concat envs) }
  where
    check_arg (p, ty) = checkPat p ty
```

The algorithm:

1. **`instDataCon con`**: Look up the data constructor in the environment, instantiate its type using `instantiate` (replacing `∀`-bound variables with fresh meta type variables), and split out the argument types and result type.
   ```haskell
   instDataCon :: Name -> Tc ([Sigma], Tau)
   ```

2. **`mapM check_arg`**: Push each argument type into the corresponding sub-pattern in **checking mode**. This is exactly analogous to how function application pushes argument types: the constructor's argument types become the expected types for the sub-patterns.

3. **`instPatSigma res_ty exp_ty`**: Reconcile the constructor's result type with the expected type from the context using subsumption.

4. **`return (concat envs)`**: Collect all variable bindings from all sub-patterns.

### 5.4 Predicativity of Data Constructors

Section 7.4 (line 3933) discusses whether type constructors can be parameterized by `σ`-types (polymorphic) or only `τ`-types (monomorphic). Example:

```haskell
data Tree a = Leaf a | Branch (Tree a) (Tree a)
```

The constructor `Leaf` has type `∀a. a → Tree a`. Due to **predicativity** (Section 3.4), `Leaf` can only be instantiated at a `τ`-type. So `Tree (∀a. a → Int)` is **not** allowed.

The paper notes three issues with impredicative data constructors:

1. **Variance complications**: For `data Contra a = Contra (a → Int)`, the subsumption direction reverses. Multiple type arguments with different variances make this worse.

2. **Phantom types**: Type arguments that don't appear on the right-hand side have no natural variance.

3. **Runtime cost**: If type-directed translation is used (Section 4.8), impredicative instantiation would require traversing entire data structures at runtime to insert coercions — "a rather expensive operation to happen behind the scenes."

---

## 6. Polymorphic Tuples and Pattern Matching

Section 7.4 (line 3966) proposes special treatment for tuples, which are co-variant and ubiquitous. The extended rho-type syntax:

```
σ ::= ∀a. ρ
ρ ::= σ₁ → σ₂ | (σ₁, ..., σₙ) | τ        ← tuple added to rho-types
τ ::= τ₁ → τ₂ | (τ₁, ..., τₙ) | K τ | a
```

This allows types like `(∀a. a → a, Int)` — tuples with polymorphic components.

### Synthesis (inference) rule for tuples:

```
tup1:    Γ ⊢⇑ tᵢ : ρᵢ   (1 ≤ i ≤ n)
         ──────────────────────────────
         Γ ⊢⇑ (t₁, ..., tₙ) : (ρ₁, ..., ρₙ)
```

### Checking rule for tuples:

```
tup2:    Γ ⊢⇓ tᵢ : σᵢ   (1 ≤ i ≤ n)
         ──────────────────────────────
         Γ ⊢⇓ (t₁, ..., tₙ) : (σ₁, ..., σₙ)
```

### Subsumption for tuples:

```
tuple:   ⊢dsk  σᵢ ≤ σᵢ′   (1 ≤ i ≤ n)
         ──────────────────────────────────
         ⊢dsk  (σ₁, ..., σₙ) ≤ (σ₁′, ..., σₙ′)
```

The paper notes: "There would be similar extra typing judgements for patterns" (line 3996). These rules "lead directly to new cases in the implementation."

**Limitation**: Functions like `fst :: ∀ab. (a, b) → a` remain predicative. The application `fst (id :: ∀a. a → a, Int)` would be rejected because `fst` is an ordinary polymorphic function.

---

## 7. Type-Directed Translation of Patterns

Section 8 (line 4025) extends the system to elaborate source terms into **System F**. The key change is that `tcPat` (like `tcRho`) now returns **translated patterns**:

```haskell
tcRho :: Term -> Expected Rho -> Tc Term     -- returns translated term
-- similarly tcPat returns translated patterns
```

### 7.1 Lambda with Patterns (with translation)

```haskell
tcRho (Lam pat body) (Check exp_ty)
  = do { (pat_ty, body_ty) <- unifyFun exp_ty
       ; (pat', binds) <- checkPat pat pat_ty
       ; body' <- extendVarEnvList binds (checkRho body body_ty)
       ; return (Lam pat' body') }

tcRho (Lam pat body) (Infer ref)
  = do { (pat', pat_ty, binds) <- inferPat pat
       ; (body', body_ty) <- extendVarEnvList binds (inferRho body)
       ; writeTcRef ref (pat_ty --> body_ty)
       ; return (Lam pat' body') }
```

The pattern `pat` is translated to `pat'`, which may contain type annotations, type applications, or coercions needed for the System F target.

### 7.2 Pattern Coercions

Section 8.2 (line 4102) identifies a key complication: **patterns may require non-trivial coercions**. Example:

```haskell
f = (\(t::Int->Int). \x. t (t x)) :: (∀a. a → a) → Int → Int
```

This is well-typed: the outer signature requires a polymorphic argument, but the inner pattern annotation `(t::Int->Int)` is more generous — any `Int → Int` function will do. When type-checking the pattern `(t::Int->Int)`, the call to `subsCheck` inside `checkPat` generates a **coercion** that must be recorded in the translated pattern.

GHC does exactly this: it records coercions in patterns and uses them during **desugaring of nested pattern-matching**, subsequent to type inference.

---

## 8. Multi-Branch Constructs and Pattern Matching

Section 7.1 (line 3652) discusses `if`/`case` expressions, which are the "multi-branch" constructs that pattern matching feeds into. The paper presents three design choices for unifying branch types:

### Choice 1: Monotype branches only

```
if1a:    Γ ⊢⇓ e₁ : Bool   Γ ⊢⇑ e₂ : τ   Γ ⊢⇑ e₃ : τ
         ────────────────────────────────────────────────
         Γ ⊢⇑ if e₁ then e₂ else e₃ : τ
```

Note the **monotype** `τ`. This kills higher-rank polymorphism in branches.

### Choice 2: Unification under mixed prefix

```
if:      Γ ⊢⇓ e₁ : Bool   Γ ⊢δ e₂ : ρ   Γ ⊢δ e₃ : ρ
         ──────────────────────────────────────────────────
         Γ ⊢δ if e₁ then e₂ else e₃ : ρ
```

Extend the unifier to handle polytypes by skolemising both with the same skolem constants and recursively unifying. Requires maintaining a bijection between skolem variables.

### Choice 3: Two-way subsumption (recommended)

```
if:      Γ ⊢⇓ e₁ : Bool
         Γ ⊢⇑ e₂ : ρ₁   Γ ⊢⇑ e₃ : ρ₂
         ⊢dsk  ρ₁ ≤ ρ₂   ⊢dsk  ρ₂ ≤ ρ₁
         ─────────────────────────────────
         Γ ⊢⇑ if e₁ then e₂ else e₃ : ρ₁
```

Implementation:

```haskell
tcRho (If e1 e2 e3) (Infer ref)
  = do { checkRho e1 boolType
       ; rho1 <- inferRho e2
       ; rho2 <- inferRho e3
       ; subsCheck rho1 rho2
       ; subsCheck rho2 rho1
       ; writeTcRef ref rho1 }
```

Choice (3) is "much simpler to implement, because the subsumption check already implements all the tricky points." It ensures that a conditional (or case expression, or pattern-matching in a function definition) **does not accidentally kill higher-rank polymorphism**.

**Minor infelicity**: The rule arbitrarily picks `ρ₁` as the result type. Though `ρ₁` and `ρ₂` are equivalent (each subsumes the other), they may have different syntactic forms (e.g., `Int → ∀a. Int → a → a` vs `Int → Int → ∀a. a → a`).

---

## 9. How Pattern Typing Fits the Bidirectional Framework

The entire pattern matching apparatus is a direct application of the paper's bidirectional type checking methodology. The key insight is that patterns are **dual to expressions**:

| Aspect | Expressions | Patterns |
|--------|-------------|----------|
| Judgement | `Γ ⊢δ t : ρ` | `⊢patδ p : σ, Γ′` |
| Inference (`⇑`) | Pull type *out* of term | Push bindings *out* of pattern |
| Checking (`⇓`) | Push type *into* term | Push type *into* pattern |
| Expected type | `Expected Rho` | `Expected Sigma` |
| Annotations | `(t :: σ)` triggers checking | `(p :: σ)` triggers checking |
| Subsumption | `instSigma` / `subsCheck` | `instPatSigma` / `subsCheck` |
| Variable binding | `extendVarEnv` | `extendVarEnvList` |

The `Expected` type unifies both modes:

```haskell
data Expected a = Infer (IORef a)   -- inference: fill this ref
                | Check a           -- checking: check against this
```

When `tcPat` receives `Infer ref`, it creates a fresh type variable and writes it. When it receives `Check ty`, it uses `ty` directly and may invoke `subsCheck`.

---

## 10. Summary of Paper Locations

| Topic | Section | Lines |
|-------|---------|-------|
| Rich pattern syntax | §7.2 | 3782–3812 |
| Pattern typing judgement `⊢pat` | §7.2 | 3813–3841 |
| `tcPat` implementation | §7.2 | 3844–3865 |
| `instPatSigma` | §7.2 | 3860–3865 |
| Pattern-matching lambda (`PLam`) | §7.2 | 3868–3886 |
| Constructor patterns (`PCon`) | §7.3 | 3888–3931 |
| `instDataCon` | §7.3 | 3927–3929 |
| Predicativity of data constructors | §7.4 | 3933–3965 |
| Polymorphic tuples + patterns | §7.4 | 3966–4023 |
| Type-directed translation of patterns | §8 | 4046–4053 |
| Pattern coercions | §8.2 | 4102–4113 |
| Multi-branch constructs (if/case) | §7.1 | 3652–3780 |
| Bidirectional Figure 8 (formal rules) | §4.7 | 1497–1683 |
| Figure 10 (translation rules) | §4.8 | 1918–2042 |
