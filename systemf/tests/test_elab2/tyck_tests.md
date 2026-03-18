# Bidirectional Type Checker Test Specification

Based on "Practical Type Inference for Arbitrary-Rank Types" (Peyton Jones et al., 2007)

## Notation

- **Source types**: `τ` (monomorphic), `σ` (polymorphic), `ρ` (weak prenex)
- **Core terms**: `e` (System F terms)
- **Wrappers**: `f` (coercions as wrapper structures)
- **Skolems**: `sk_a`, `sk_b` (rigid type constants)
- **Metas**: `?1`, `?2` (unification variables)

---

## Figure 8: Bidirectional Type Checking Rules

### 1. INT — Integer Literal

| Aspect | Value |
|--------|-------|
| **Rule** | `Γ ⊢↑ n : Int` |
| **Source** | `42` |
| **Expected Type (Infer)** | `Int` |
| **Core Term** | `42` |
| **Wrapper** | `WP_HOLE` |

#### Test Case: INT with Instantiation
| Aspect | Value |
|--------|-------|
| **Context** | `Γ ⊢↑ 42 : ρ` where expectation is `?1` (mono) |
| **Unification** | `?1 = Int` |
| **Result** | `42 : Int` |

---

### 2. VAR — Variable

| Aspect | Value |
|--------|-------|
| **Rule** | `x:σ ∈ Γ,  Γ ⊢inst_↑ σ ≤ ρ  /  Γ ⊢↑ x : ρ` |
| **Source** | `x` where `x : ∀a. a → a` in Γ |
| **Expected Type (Infer)** | `?1 → ?1` (after instantiation) |
| **Core Term** | `x[?1]` (type application) |
| **Wrapper** | `WpTyApp(?1)` |

#### Test Case: VAR with skolemization context
| Aspect | Value |
|--------|-------|
| **Context** | `x : ∀a. a → a ∈ Γ`, expectation `sk_x → sk_x` |
| **Instantiation** | `a ↦ sk_x` |
| **Core Term** | `x[sk_x]` |
| **Wrapper Chain** | `WP_HOLE` (already at target) |

---

### 3. ABS1 — Lambda (Infer Mode)

| Aspect | Value |
|--------|-------|
| **Rule** | `Γ, x:τ ⊢↑ t : ρ  /  Γ ⊢↑ λx.t : τ → ρ` |
| **Source** | `λx. x` |
| **Expected Type (Infer)** | `?1 → ?1` |
| **Unification** | `arg = ?1`, `res = ?1` (occurs check passes) |
| **Core Term** | `λx:?1. x` |
| **Wrapper** | `WP_HOLE` |

#### Test Case: ABS1 with nested function
| Aspect | Value |
|--------|-------|
| **Source** | `λf. λx. f x` |
| **Inference** | `f : ?1`, need `?1 = ?2 → ?3`, `x : ?2`, body `?3` |
| **Result Type** | `(?2 → ?3) → ?2 → ?3` |
| **Core Term** | `λf:(?2→?3). λx:?2. f x` |

---

### 4. ABS2 — Lambda (Check Mode)

| Aspect | Value |
|--------|-------|
| **Rule** | `Γ, x:τ ⊢↓ t : ρ  /  Γ ⊢↓ λx.t : τ → ρ` |
| **Source** | `λx. x` |
| **Check Against** | `Int → Int` |
| **Decomposition** | `arg_ty = Int`, `res_ty = Int` |
| **Core Term** | `λx:Int. x` |
| **Wrapper** | `WP_HOLE` |

#### Test Case: ABS2 with polymorphic expectation
| Aspect | Value |
|--------|-------|
| **Source** | `λx. x` |
| **Check Against** | `∀a. a → a` |
| **Skolemization** | `sk_a → sk_a` |
| **Core Term** | `Λsk_a. λx:sk_a. x` |
| **Note** | GEN2 applies, see below |

---

### 5. AABS1 — Annotated Lambda (Infer)

| Aspect | Value |
|--------|-------|
| **Rule** | `Γ, x:σ ⊢↑ t : ρ  /  Γ ⊢↑ (λx:σ.t) : σ → ρ` |
| **Source** | `λx:Int. x` |
| **Annotation** | `σ = Int` |
| **Expected Type (Infer)** | `Int → Int` |
| **Core Term** | `λx:Int. x` |

---

### 6. AABS2 — Annotated Lambda (Check with Subsumption)

| Aspect | Value |
|--------|-------|
| **Rule** | `Γ ⊢poly_↑ σ_a ≤ σ_x,  Γ, x:σ_x ⊢↓ t : ρ  /  Γ ⊢↓ (λx:σ_x.t) : σ_a → ρ` |
| **Source** | `λx:(∀a.a→a). x` |
| **Check Against** | `(Int→Int) → (Int→Int)` |
| **Subsumption** | `Int→Int ≤ ∀a.a→a` — **FAILS!** (polymorphic type not subsumed by monomorphic) |
| **Note** | Direction matters: `∀a.a→a ≤ Int→Int` succeeds |

#### Test Case: AABS2 with coercion
| Aspect | Value |
|--------|-------|
| **Source** | `λx:(Int→Int). x` |
| **Check Against** | `(∀a.a→a) → (Int→Int)` |
| **Subsumption** | `∀a.a→a ≤ Int→Int` (instantiate `a` to `Int`) |
| **Wrapper** | `WpFun(∀a.a→a, WpTyApp(Int), WP_HOLE)` |
| **Core Term** | `λx:(Int→Int). let d = x[Int] in λy:Int. d y` |

---

### 7. APP — Application

| Aspect | Value |
|--------|-------|
| **Rule** | `Γ ⊢↑ t : σ → σ',  Γ ⊢poly_↓ u : σ  /  Γ ⊢↑ t u : σ'` |
| **Source** | `(λx:Int. x) 42` |
| **Fun Type** | `Int → Int` |
| **Arg Check** | `42` against `Int` |
| **Result** | `Int` |
| **Core Term** | `(λx:Int. x) 42` |

#### Test Case: APP with polymorphic function
| Aspect | Value |
|--------|-------|
| **Source** | `id 42` where `id : ∀a. a → a` |
| **Fun Type** | `?1 → ?1` (after instantiation) |
| **Unification** | `?1 = Int` |
| **Arg Check** | `42` against `Int` |
| **Result** | `Int` |
| **Core Term** | `id[Int] 42` |

---

### 8. ANNOT — Type Annotation

| Aspect | Value |
|--------|-------|
| **Rule** | `Γ ⊢poly_↓ t : σ,  Γ ⊢inst_δ σ ≤ ρ  /  Γ ⊢δ t::σ : ρ` |
| **Source** | `42 :: Int` |
| **Annotation** | `σ = Int` |
| **Check** | `42` against `Int` |
| **Instantiation** | identity (already `Int`) |
| **Core Term** | `42` |

#### Test Case: ANNOT with polymorphic type
| Aspect | Value |
|--------|-------|
| **Source** | `λx. x :: ∀a. a → a` |
| **Check** | `λx. x` against `sk_a → sk_a` |
| **Generalization** | `Λsk_a. λx:sk_a. x` |
| **Wrapper** | `WpTyLam(sk_a)` |
| **Result** | `Λsk_a. λx:sk_a. x : ∀a. a → a` |

---

### 9. LET — Let Binding

| Aspect | Value |
|--------|-------|
| **Rule** | `Γ ⊢poly_δ t : σ,  Γ, x:σ ⊢δ u : ρ  /  Γ ⊢δ let x=t in u : ρ` |
| **Source** | `let id = λx. x in id 42` |
| **id Type** | `∀a. a → a` (generalized) |
| **Body Check** | `id 42` with `id : ∀a. a → a` |
| **Core Term** | `let id : ∀a.a→a = (Λa. λx:a. x) in id[Int] 42` |

---

### 10. GEN1 — Generalization (Infer)

| Aspect | Value |
|--------|-------|
| **Rule** | `Γ ⊢↑ t : ρ,  ā = ftv(ρ) - ftv(Γ)  /  Γ ⊢↑ t : ∀ā.ρ` |
| **Source** | `λx. x` (in empty Γ) |
| **Inferred** | `?1 → ?1` where `?1` is unsolved |
| **Generalization** | `∀a. a → a` (promote `?1` to `a`) |
| **Core Term** | `Λa. λx:a. x` |
| **Wrapper** | `WpTyLam(a)` |

---

### 11. GEN2 — Generalization (Check)

| Aspect | Value |
|--------|-------|
| **Rule** | `pr(σ) = ∀ā.ρ ↦ f,  ā ∉ ftv(Γ),  Γ ⊢↓ t : ρ  /  Γ ⊢↓ t : σ ↦ f(Λā.e)` |
| **Source** | `λx. x` |
| **Check Against** | `∀a. a → a` |
| **Skolemization** | `pr(∀a.a→a) = sk_a → sk_a` with `f = Λsk_a. [HOLE]` |
| **Check Body** | `λx:sk_a. x` against `sk_a → sk_a` |
| **Core Term** | `Λsk_a. λx:sk_a. x` |
| **Wrapper Application** | `f(Λsk_a. e)` where `e = λx:sk_a. x`, result `Λsk_a. λx:sk_a. x` |

#### Test Case: GEN2 with nested foralls
| Aspect | Value |
|--------|-------|
| **Source** | `λf. λx. f x` |
| **Check Against** | `∀a. (∀b. b→b) → a → a` |
| **Skolemization** | `(∀b. b→b) → sk_a → sk_a` |
| **Note** | The `∀b` remains in argument position (higher-rank) |

---

## Figure 9: Subsumption and Skolemization

### PRMONO — Monomorphic Type

| Aspect | Value |
|--------|-------|
| **Rule** | `pr(τ) = τ ↦ λx.x` |
| **Input** | `Int` |
| **Output** | `([], Int, WP_HOLE)` |
| **Wrapper Meaning** | `λx:Int. x` |

---

### PRPOLY — Polymorphic Type

| Aspect | Value |
|--------|-------|
| **Rule** | `pr(∀a.ρ) = ∀a.pr(ρ)` with wrapper `Λa.f` |
| **Input** | `∀a. a → a` |
| **Skolemization** | `sk_a → sk_a` |
| **Wrapper** | `WpTyLam(sk_a)` |
| **Wrapper Meaning** | `λx:(∀a.a→a). Λsk_a. x[sk_a]` |

#### Test Case: Nested PRPOLY
| Aspect | Value |
|--------|-------|
| **Input** | `∀a. ∀b. a → b → a` |
| **Skolemization** | `sk_a → sk_b → sk_a` |
| **Skolems** | `[sk_a, sk_b]` |
| **Wrapper** | `WpTyLam(sk_a) ∘ WpTyLam(sk_b)` |
| **Wrapper Meaning** | `λx:(∀a.∀b.a→b→a). Λsk_a. Λsk_b. x[sk_a][sk_b]` |

---

### PRFUN — Function Type with Prenex Result

| Aspect | Value |
|--------|-------|
| **Rule** | `pr(σ₂) = ∀ā.ρ₂ ↦ f  /  pr(σ₁→σ₂) = ∀ā.(σ₁→ρ₂) ↦ λx.λy.f(x[ā]y)` |
| **Input** | `Int → ∀a. a` |
| **Skolemization** | `Int → sk_a` |
| **Inner (PRPOLY)** | `pr(∀a.a) = sk_a` with `f = Λsk_a. [HOLE]` |
| **Wrapper** | `WpFun(Int, WP_HOLE, WpTyLam(sk_a))` |
| **Wrapper Meaning** | `λg:(Int→sk_a). λy:Int. Λsk_a. g y` |

#### Test Case: PRFUN with forall in argument
| Aspect | Value |
|--------|-------|
| **Input** | `(∀a. a→a) → Int` |
| **Skolemization** | `(∀a. a→a) → Int` (no change, forall stays in arg) |
| **Wrapper** | `WpFun(∀a.a→a, WP_HOLE, WP_HOLE)` |
| **Note** | Contravariant position preserves polymorphism |

---

### DEEP-SKOL — Deep Skolemization

| Aspect | Value |
|--------|-------|
| **Rule** | `pr(σ₂) = ∀ā.ρ₂ ↦ f,  ā ∉ ftv(σ₁),  Γ,ā ⊢sub σ₁ ≤ ρ₂ ↦ e  /  Γ ⊢sub σ₁ ≤ σ₂ ↦ f(Λā.e)` |
| **Input** | `Int → Int ≤ ∀a. a → a` |
| **Skolemization** | `pr(∀a.a→a) = sk_a → sk_a` with `f = Λsk_a. [HOLE]` |
| **Subsumption Check** | `Int → Int ≤ sk_a → sk_a` |
| **Unification** | `sk_a = Int` (succeeds, skolem = Int) |
| **Result Wrapper** | `Λsk_a. (λx. x)` — applied to `e` gives `Λsk_a. e` |

#### Test Case: DEEP-SKOL with function
| Aspect | Value |
|--------|-------|
| **Input** | `(∀a. a→a) → Int ≤ (∀b. b→b) → Int` |
| **Skolemization (right)** | `(∀b. b→b) → Int` — no skolems introduced |
| **Subsumption** | Check `(∀a. a→a) → Int ≤ (∀b. b→b) → Int` |
| **Contravariant arg** | `(∀b. b→b) ≤ (∀a. a→a)` — succeeds (alpha equiv) |
| **Covariant res** | `Int ≤ Int` — succeeds |
| **Wrapper** | `WpFun((∀b.b→b), WP_HOLE, WP_HOLE)` |

---

### FUN — Function Subsumption

| Aspect | Value |
|--------|-------|
| **Rule** | `Γ ⊢sub τ₂ ≤ σ₁ ↦ e₁,  Γ ⊢sub σ₁' ≤ τ₁ ↦ e₂  /  Γ ⊢sub σ₁→σ₁' ≤ τ₂→τ₂' ↦ λx.e₂(x(e₁))` |
| **Input** | `(Int→Int) → Int ≤ (Int→Bool) → Int` |
| **Contravariant arg** | `Int→Bool ≤ Int→Int` — **FAILS** (`Bool` not ≤ `Int`) |
| **Note** | Contravariance reverses the order! |

#### Test Case: FUN success
| Aspect | Value |
|--------|-------|
| **Input** | `Int → (∀a.a→a) ≤ Bool → (Int→Int)` |
| **Contravariant arg** | `Bool ≤ Int` — **FAILS** |
| **Fixed** | `(∀a.a→a) → Int ≤ (Int→Int) → Int` |
| **Arg check** | `Int→Int ≤ ∀a.a→a` — instantiate `a` to `Int` |
| **Res check** | `Int ≤ Int` — ok |
| **Wrapper** | `WpFun((Int→Int), WpTyApp(Int), WP_HOLE)` |

---

## Complex Integration Tests

### Higher-Rank Function Application

| Aspect | Value |
|--------|-------|
| **Source** | `runInt (λx:Int. x + 1)` where `runInt : (∀a. a→a) → Int` |
| **Fun Type** | `(∀a. a→a) → Int` |
| **Arg Type** | `Int → Int` |
| **Subsumption** | `Int→Int ≤ ∀a.a→a` — instantiate `a` to `Int` |
| **Arg Wrapper** | `WpTyApp(Int)` on the forall-bound function |
| **Core Term** | `runInt (Λa. λx:a. (λy:Int. y+1) (x[Int] (coerce...)))` |
| **Note** | Complex coercion required |

### Nested Polymorphism

| Aspect | Value |
|--------|-------|
| **Source** | `choose (λx. x) (λx. x) :: ∀a. a → a` |
| **where** | `choose : ∀a. a → a → a` |
| **Inference** | Both args have type `?1 → ?1`, unified |
| **Generalization** | `∀a. a → a` for both args |
| **Result** | `∀a. a → a` |

### Impredicative Instantiation

| Aspect | Value |
|--------|-------|
| **Source** | `id (id :: ∀a. a → a)` |
| **Outer id** | `?1 → ?1` |
| **Arg type** | `∀a. a → a` |
| **Unification** | `?1 = ∀a. a → a` — **higher-rank unification!** |
| **Note** | Requires higher-rank types support |

---

## Summary Table: Rules to Implement

| Rule | Implementation Status | Test Coverage |
|------|----------------------|---------------|
| INT | ✅ | `test_int_literal` |
| VAR | ✅ | `test_var_mono`, `test_var_poly` |
| ABS1 | ✅ | `test_lam_infer` |
| ABS2 | ✅ | `test_lam_check` |
| AABS1 | ✅ | `test_ann_lam_infer` |
| AABS2 | ✅ | `test_ann_lam_coercion` |
| APP | ✅ | `test_app_mono`, `test_app_poly` |
| ANNOT | ✅ | `test_annot_simple`, `test_annot_poly` |
| LET | ✅ | `test_let_poly` |
| GEN1 | ✅ | `test_gen_infer` |
| GEN2 | ✅ | `test_gen_check` |
| PRMONO | ✅ | `test_skolem_mono` |
| PRPOLY | ✅ | `test_skolem_poly` |
| PRFUN | ✅ | `test_skolem_fun` |
| DEEP-SKOL | ✅ | `test_subs_poly` |
| FUN | ✅ | `test_subs_fun_contravariant` |
| MONO | ✅ | `test_subs_mono` |
