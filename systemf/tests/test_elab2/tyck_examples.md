# Bidirectional Type Checker Test Specification

Based on "Practical Type Inference for Arbitrary-Rank Types" (Peyton Jones et al., 2007)

## Notation

- **Source types**: `τ` (monomorphic), `σ` (polymorphic), `ρ` (weak prenex)
- **Core terms**: `e` (System F terms)
- **Wrappers**: `f` (coercions as wrapper structures)
- **Skolems**: `sk_a`, `sk_b` (rigid type constants)
- **Metas**: `?1`, `?2` (unification variables)

---

## Meta Variables vs Skolem Variables

This is a **critical distinction** in higher-rank type inference.

### Meta Variables (`?1`, `?2`, ...)

| Property | Description |
|----------|-------------|
| **Nature** | Unification variables (unknown types to be determined) |
| **Behavior** | Can be **unified** with any type via substitution |
| **Use Case** | Type inference for unknown types |
| **Example** | Inferring `λx.x` creates `?1 → ?1`, then `?1` is generalized to `∀a.a→a` |

**Key operation**: `unify(?1, Int)` succeeds by substituting `?1 ↦ Int`.

### Skolem Variables (`sk_a`, `sk_b`, ...)

| Property | Description |
|----------|-------------|
| **Nature** | Rigid type constants (represent "some specific but unknown type") |
| **Behavior** | **Cannot be unified** — they are rigid! |
| **Use Case** | Checking polymorphic types (subsumption, skolemization) |
| **Example** | Checking against `∀a.a→a` creates `sk_a → sk_a` where `sk_a` is rigid |

**Key operation**: `unify(sk_a, Int)` **FAILS** — `sk_a` is rigid and cannot be substituted.

### Why the Distinction Matters

**Meta variables** are for **inference** (discovering types):
- `λx.x` infers as `?1 → ?1`
- Later we learn `?1 = Int` from context
- We substitute and get `Int → Int`

**Skolem variables** are for **checking** (verifying subsumption):
- Checking `Int → Int ≤ ∀a.a → a`
- Skolemize: check `Int → Int ≤ sk_a → sk_a`
- `sk_a` is rigid — we **cannot** set `sk_a = Int`
- Instead, we check that `Int` and `sk_a` are **compatible as types**
- The wrapper records this relationship

### Common Mistake

```python
# WRONG: Thinking skolem can be unified
sk_a = make_skolem("a")
unify(sk_a, Int)  # ERROR: sk_a is rigid!

# CORRECT: Rigid equality check
check_equal(sk_a, Int)  # Verifies they're the same type (post-zonking)
```

### Anti-Test: `test_skolem_cannot_unify`

This test verifies that unification **fails** with skolem variables:

```python
sk_a = make_skolem("a")
unify(sk_a, Int)  # Raises TypeError: rigid type variable
```

**Expected behavior**: The type checker must throw an error when attempting to unify a skolem. This ensures the rigidity invariant is maintained.

**Why this matters**: If skolems could be unified, the distinction between `?1` (inference) and `sk_a` (checking) would collapse, breaking higher-rank type inference.

### In DEEP-SKOL

When checking `σ₁ ≤ σ₂`:
1. Skolemize `σ₂` to get `ρ₂` with skolems `ā`
2. Check `σ₁ ≤ ρ₂` with **rigid equality** (not unification)
3. The skolems represent the "forall-bound" positions
4. Wrapper converts the witness from `ρ₂` back to `σ₂`

---

## Figure 9: Subsumption and Skolemization (PR Rules)

### PRMONO — Monomorphic Type

| Aspect | Value |
|--------|-------|
| **Rule** | `pr(τ) = τ ↦ λx.x` |
| **Input** | `Int` |
| **Skolems** | `[]` |
| **Output Type** | `Int` |
| **Wrapper** | `WP_HOLE` |
| **Test** | `test_skolemise_mono` |

---

### PRPOLY — Polymorphic Type

#### Simple Case: `∀a. a → a`

| Aspect | Value |
|--------|-------|
| **Rule** | `pr(∀a.ρ) = ∀a.pr(ρ)` with wrapper composition |
| **Input** | `∀a. a → a` |
| **Skolems** | `[sk_a]` |
| **Output Type** | `sk_a → sk_a` |
| **Inner (PRFUN)** | `WpFun(sk_a, WP_HOLE, WP_HOLE)` |
| **Outer (PRPOLY)** | `WpCompose(WpTyLam(sk_a), WpFun(...))` |
| **Test** | `test_skolemise_prpoly` |

#### Nested: `∀a. ∀b. a → b → a`

| Aspect | Value |
|--------|-------|
| **Input** | `∀a. ∀b. a → b → a` |
| **Skolems** | `[sk_a, sk_b]` |
| **Output Type** | `sk_a → sk_b → sk_a` |
| **Innermost** | `WpFun(sk_b, WP_HOLE, WP_HOLE)` (PRFUN on `sk_b → sk_a`) |
| **Middle** | `WpFun(sk_a, WP_HOLE, inner)` (PRFUN on `sk_a → (sk_b → sk_a)`) |
| **Wrapper** | `WpCompose(WpTyLam(sk_a), WpCompose(WpTyLam(sk_b), middle))` |
| **Test** | `test_skolemise_nested` |

---

### PRFUN — Function Type with Prenex Result

#### Case: `Int → ∀a. a`

| Aspect | Value |
|--------|-------|
| **Rule** | `pr(σ₂) = ∀ā.ρ₂ ↦ f  /  pr(σ₁→σ₂) = ∀ā.(σ₁→ρ₂) ↦ λx.λy.f(x[ā]y)` |
| **Input** | `Int → ∀a. a` |
| **Skolems** | `[sk_a]` |
| **Output Type** | `Int → sk_a` |
| **Inner (PRPOLY)** | `WpTyLam(sk_a)` (simplified from `WpCompose(WpTyLam(sk_a), WP_HOLE)`) |
| **Wrapper** | `WpFun(Int, WP_HOLE, WpTyLam(sk_a))` |
| **Test** | `test_skolemise_prfun` |

#### Case: `(∀a. a→a) → Int` (Polymorphic Argument)

| Aspect | Value |
|--------|-------|
| **Input** | `(∀a. a→a) → Int` |
| **Skolems** | `[]` (forall in contravariant position, not prenex) |
| **Output Type** | `(∀a. a→a) → Int` (unchanged) |
| **Wrapper** | `WpFun(∀a.a→a, WP_HOLE, WP_HOLE)` (identity) |
| **Test** | `test_skolemise_prfun_poly_arg` |

---

### Complex Case: `∀a. a → ∀b. b → a`

| Aspect | Value |
|--------|-------|
| **Input** | `∀a. a → ∀b. b → a` |
| **Structure** | `∀a. (a → ∀b. (b → a))` |
| **Skolems** | `[sk_a, sk_b]` |
| **Output Type** | `sk_a → sk_b → sk_a` |
| **Innermost** | `WpFun(sk_b, WP_HOLE, WP_HOLE)` (PRFUN on `sk_b → sk_a`) |
| **Inner PRPOLY** | `WpCompose(WpTyLam(sk_b), innermost)` |
| **Middle PRFUN** | `WpFun(sk_a, WP_HOLE, inner_prpoly)` |
| **Outer PRPOLY** | `WpCompose(WpTyLam(sk_a), middle_prfun)` |
| **Test** | `test_skolemise_complex` |

---

## Wrapper Structure Summary

### Construction Rules

```
PRMONO(τ):     WP_HOLE

PRPOLY(∀a.ρ):  WpCompose(WpTyLam(sk_a), inner_wrap)
               where inner_wrap = pr(ρ)[sk_a/a]

PRFUN(σ₁→σ₂):  WpFun(σ₁, WP_HOLE, inner_wrap)
               where inner_wrap = pr(σ₂) if σ₂ has prenex foralls
```

### Simplification Rule

After construction, `WpCompose` is simplified:
- `WpCompose(w, WP_HOLE)` → `w`
- `WpCompose(WP_HOLE, w)` → `w`

This ensures minimal wrapper representation while preserving correctness.

### Examples with Simplification

| Type | Before Simplification | After Simplification |
|------|----------------------|----------------------|
| `∀a. a` | `WpCompose(WpTyLam(sk_a), WP_HOLE)` | `WpTyLam(sk_a)` |
| `Int → ∀a. a` | `WpFun(Int, WP_HOLE, WpCompose(WpTyLam(sk_a), WP_HOLE))` | `WpFun(Int, WP_HOLE, WpTyLam(sk_a))` |
| `∀a. a → a` | `WpCompose(WpTyLam(sk_a), WpFun(sk_a, WP_HOLE, WP_HOLE))` | *unchanged* (no WP_HOLE)

---

## INST — Instantiation Judgment

The `inst` method implements bidirectional instantiation (INST1/INST2 rules).

### INST1 — Infer Mode

| Input Type | Mode | Instantiated Type | Wrapper |
|------------|------|-------------------|---------|
| `∀a. a` | Infer | `?1` | `WpTyApp(?1)` |
| `Int` | Infer | `Int` | `WP_HOLE` |

### INST2 — Check Mode

| Input Type | Check Against | Wrapper |
|------------|---------------|---------|
| `∀a. a → a` | `Int → Int` | `WpTyApp(Int)` |

**Note**: Contravariant argument position triggers unification (`?1 := Int`).

---

## Figure 8: Bidirectional Type Checking Rules (To Be Implemented)

### INT — Integer Literal
| Source | Expected | Core Term | Wrapper |
|--------|----------|-----------|---------|
| `42` | `Int` | `42` | `WP_HOLE` |

### VAR — Variable
| Context | Source | Expected | Core Term |
|---------|--------|----------|-----------|
| `x:∀a.a→a ∈ Γ` | `x` | `?1→?1` | `x[?1]` |

### ABS1/ABS2 — Lambda
| Mode | Source | Check Against | Core Term |
|------|--------|---------------|-----------|
| Infer | `λx.x` | — | `λx:?1.x` |
| Check | `λx.x` | `Int→Int` | `λx:Int.x` |

### AABS1/AABS2 — Annotated Lambda
| Mode | Source | Annotation | Result |
|------|--------|------------|--------|
| Infer | `λx:Int.x` | `Int` | `Int→Int` |
| Check | `λx:(Int→Int).x` | `Int→Int` | coercion via subsumption |

### APP — Application
| Source | Fun Type | Arg | Result |
|--------|----------|-----|--------|
| `id 42` | `?1→?1` | `42:Int` | `Int`, core: `id[Int] 42` |

### ANNOT — Type Annotation
| Source | Annotation | Check | Core Term |
|--------|------------|-------|-----------|
| `λx.x :: ∀a.a→a` | `∀a.a→a` | `sk_a→sk_a` | `Λsk_a.λx:sk_a.x` |

### LET — Let Binding
| Source | Binding | Body | Result |
|--------|---------|------|--------|
| `let id=λx.x in id 42` | `id:∀a.a→a` | `id 42` | `Int` |

### GEN1/GEN2 — Generalization
| Mode | Source | Context | Result |
|------|--------|---------|--------|
| GEN1 | `λx.x` | `ftv(Γ)=∅` | `∀a.a→a` with `Λa.λx:a.x` |
| GEN2 | `λx.x` | Check `∀a.a→a` | `Λsk_a.λx:sk_a.x` via skolemise |

---

## Subsumption Rules

**Notation**: `σ₁ ≤ σ₂` means σ₁ is at least as polymorphic as σ₂ (σ₁ can be used where σ₂ is expected).

### MONO — Monomorphic Base Case

Direct unification when both types are monomorphic.

| Test | Coverage | Wrapper |
|------|----------|---------|
| `Int ≤ Int` | Identity | `WP_HOLE` |

---

### SPEC — Instantiate Left (LHS is ∀, RHS is ρ)

When LHS has outer foralls, instantiate with fresh metas.

| Test | Coverage | Wrapper |
|------|----------|---------|
| `∀a.a ≤ Int` | Simple instantiation | `WpTyApp(Int)` |
| `∀a.a → a ≤ Int → Int` | Instantiate in function | `WpTyApp(Int)` |
| `∀a.∀b.a → b ≤ Int → String` | Nested foralls | `WpCompose(WpTyApp(Int), WpTyApp(String))` |
| `Bool → (∀a.a → a) ≤ Bool → Int → Int` | Paper §4.6.2: instantiate nested ∀ in result | `WpTyApp(Int → Int)` |

---

### FUN — Function Subsumption (Contravariant Arg, Covariant Res)

For `σ₁ → σ₂ ≤ σ₃ → ρ₄`:
- **Arg**: `σ₃ ≤ σ₁` (flipped! contravariant)
- **Res**: `σ₂ ≤ ρ₄` (same direction, covariant)

| Test | Arg Check | Res Check | Wrapper |
|------|-----------|-----------|---------|
| `Int → String ≤ Int → String` | `Int ≤ Int` | `String ≤ String` | `WpFun(Int, WP_HOLE, WP_HOLE)` |
| `(Int→Int) → String ≤ (∀a.a→a) → String` | `∀a.a→a ≤ Int→Int` ✓ | `String ≤ String` | `WpFun(∀a.a→a, WpTyApp(Int), WP_HOLE)` |
| `(Int → Int) → Bool ≤ (∀a.a → a) → Bool` | Paper §4.6.2: contravariant arg | `Bool ≤ Bool` | `WpFun(∀a.a→a, WpTyApp(Int), WP_HOLE)` |

**Key insight**: A function accepting *polymorphic* arguments can be used where a function accepting *monomorphic* arguments is expected. The caller provides monomorphic, the function accepts polymorphic.

---

### DEEP-SKOL — Skolemize Right (RHS is ∀)

When RHS has foralls, skolemize to rigid constants and check subsumption. Uses **weak prenex conversion** `pr(σ)` to float ∀s from result position.

| Test | LHS | RHS (skolemized) | Result |
|------|-----|------------------|--------|
| `∀a.a → a ≤ ∀b.b → b` | `?1 → ?1` | `sk_b → sk_b` | unifies `?1 := sk_b` ✓ |
| `∀a.∀b.a → b ≤ ∀a.a → a` | `?1 → ?2` | `sk_a → sk_a` | fails: `?2 ≠ sk_a` (rigid) |
| `∀a.∀b.a → b ≤ ∀a.a → Int` | `?1 → ?2` | `sk_a → sk_a` | fails: `sk_a ≠ Int` (rigid) |

**Weak Prenex Equivalences** (Paper §4.6.2): These type pairs are equivalent under deep skolemization because `pr(∀a.a → (∀b.b → b)) = ∀ab.a → b → b`.

| Test | Direction | pr(RHS) | Result |
|------|-----------|---------|--------|
| `∀ab.a → b → b ≤ ∀a.a → (∀b.b → b)` | Forward | `∀ab.a → b → b` (already prenex) | ✓ |
| `∀a.a → (∀b.b → b) ≤ ∀ab.a → b → b` | Reverse | `∀ab.a → b → b` (floats ∀b) | ✓ |

---

### Anti-Tests (Must Fail)

| Test | Why It Fails |
|------|--------------|
| `Int → String ≤ Int → Bool` | Different result types |
| `(∀a.a→a) → Int ≤ (Int→Int) → Int` | Arg check: `Int→Int ≤ ∀a.a→a` fails (not more polymorphic) |
| `Int → Int ≤ ∀a.a → a` | RHS skolemizes to `sk_a → sk_a`; `sk_a ≠ Int` (rigid) |
| `String ≤ Int` | Different types |

---

## Documentation Style Guide

### Separation of Concerns

This test suite uses a **two-tier documentation approach**:

| Location | Purpose | Content |
|----------|---------|---------|
| `tyck_examples.md` (this file) | **Full specification** | Detailed rule explanations, derivation steps, wrapper constructions, rationale |
| `test_*.py` | **Concise reference** | Rule identifier + pointer to spec |

### Docstring Convention

Test docstrings should be **minimal but informative**:

```python
def test_skolemise_prpoly():
    """PRPOLY: pr(∀a. a → a) = sk_a → sk_a ↦ Λsk_a

    Polymorphic type skolemizes to rigid variables with type lambda wrapper.
    """
```

**Pattern**: `<RULE>: <brief description>` followed by one-line insight.

### Why This Style?

1. **Single source of truth**: Detailed documentation lives in one place
2. **DRY principle**: Avoid duplicating specs across test files
3. **Maintainability**: Update spec in one place, tests stay clean
4. **Readability**: Tests are readable without scrolling through paragraphs
5. **Reference integrity**: Tests link to specific sections for traceability

### Adding New Tests

When adding a new test:

1. **Document in tyck_examples.md first**:
   - Add a new section under the appropriate rule category
   - Include the full derivation, wrapper structure, and rationale

2. **Write minimal test docstring**:
   - Identify the rule (e.g., PRPOLY, DEEP-SKOL)
   - Brief description of what the test checks
   - One-line insight or expected behavior

3. **Example**:
   ```python
   def test_new_case():
       """RULE-NAME: what the test verifies

       Key insight or expected outcome.
       """
   ```

This ensures the specification is comprehensive while keeping the test code focused and maintainable.