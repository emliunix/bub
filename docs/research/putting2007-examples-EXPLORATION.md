# Type Inference Research Collection — Examples Analysis

**Status:** Validated
**Last Updated:** 2026-04-12
**Central Question:** What examples demonstrate the key ideas across the type inference research collection, and what does each example teach?

## Summary

This document catalogs and analyzes every code example across 8 research papers in the type inference collection. Examples are organized by paper and cross-referenced by the concept they demonstrate.

---

## Papers Covered

| # | Paper | Short Name | Examples | Source |
|---|-------|-----------|----------|--------|
| 1 | Peyton Jones et al. 2007 | Putting 2007 | ~130 | `docs/research/putting-2007.txt` |
| 2 | Vytiniotis et al. 2011 | OutsideIn(X) | ~76 | `docs/research/vytiniotis-2011-outsidein.txt` |
| 3 | Weirich et al. 2013 | System FC | ~67 | `docs/research/weirich-2013-system-fc.txt` |
| 4 | Carnier et al. 2024 | Type Inference Logics | ~46 | `docs/research/carnier-2023.txt` |
| 5 | Graf et al. 2020 | Lower Your Guards | ~43 | `docs/research/lower-your-guards-2020.txt` |
| 6 | Eisenberg et al. 2016 | Visible Type App | ~58 | `systemf/docs/research/eisenberg-2016-visible-type-application.txt` |
| 7 | Jones & Shields 2002 | Scoped Type Vars | ~55 | `systemf/docs/research/jones-shields-2002-scoped-type-variables.txt` |
| 8 | Fan, Xu, Xie 2025 | Levels | ~41 | `docs/research/fan-xu-xie-2025-practical-type-inference-with-levels.txt` |

---

## Cross-Cutting Concept Index

Examples grouped by the concept they demonstrate, across papers.

### A. Higher-Rank Polymorphism

| Example | Paper | Lines | What It Demonstrates |
|---------|-------|-------|---------------------|
| `f :: (forall a. [a] -> [a]) -> ([Bool], [Char])` | Putting §1 | 99–104 | A type annotation enables higher-rank inference |
| `data Monad m = Mon { return :: a -> m a, ... }` | Putting §2 | 177–179 | Rank-2 record fields simulate type classes |
| `runST :: forall a. (forall s. ST s a) -> a` | Putting §2 | 217 | Rank-2 type for state encapsulation |
| `build :: forall a. (forall b. (a -> b -> b) -> b -> b) -> [a]` | Putting §2 | 214 | Rank-2 type for short-cut deforestation |
| `gmapT :: forall a. Data a => (forall b. Data b => b -> b) -> a -> a` | Putting §2 | 225–226 | Rank-2 type for generic programming |
| `foldT` with rank-2 arguments | Putting §2 | 243–246 | Fold over nested data type with rank-2 args |
| `fixMT :: (MapT -> MapT) -> MapT` (rank-3) | Putting §2 | 251–261 | Rank-3 type for term-mapping fixpoint |
| `foo :: (∀ a. a → a) → (Int, Bool)` | Eisenberg §6 | 916–920 | Higher-rank + visible type application |
| `pair :: ∀ a. a → ∀ b. b → (a, b)` | Eisenberg §6 | 928–929 | Non-prenex quantification |
| `f :: (∀c. c → ∀d. d → d) → ...` (rejected) | Levels §2.2 | 213–215 | Subtyping failure with higher-rank types |

### B. Bidirectional Type Checking

| Example | Paper | Lines | What It Demonstrates |
|---------|-------|-------|---------------------|
| `foo = (\i. (i 3, i True)) :: (∀a.a → a) → (Int, Bool)` | Putting §4.7 | 1510 | Annotation pushed inward via checking mode |
| `\x -> (x True, x 'a')` checkable but not inferable | Putting §4.7 | 1535 | Checking mode is strictly more powerful |
| `f : (∀ab.Int → a → b → b) ⊢⇓ f 3 : Bool → ∀c.c → c` | Putting §4.7 | 1795 | gen2 requires weak prenex conversion |
| `Γ ⊢δ` rules (Figure 8) | Putting §4.7 | 1558–1683 | Complete bidirectional rule set |
| `Γ ⊢δ t : ρ ↝ e` (Figure 10) | Putting §4.8 | 1918–2041 | Bidirectional rules with System F translation |
| `synth` / `check` functions | Carnier §2.2 | 320–344 | Monadic constraint generation + elaboration |
| Level-based bidirectional rules | Levels §4.1 | 575–730 | Bidirectional checking indexed by level |

### C. Subsumption / Subtyping

| Example | Paper | Lines | What It Demonstrates |
|---------|-------|-------|---------------------|
| `k :: ∀ab.a → b → b; f2 :: (∀x.x → x → x) → Int` | Putting §3.3 | 351–357 | `k` is more polymorphic than `f2` requires |
| `g :: ((∀b.[b] → [b]) → Int) → Int` (contravariance) | Putting §3.3 | 371–373 | Co/contra-variance reversal |
| Shallow subsumption examples (rank-1) | Putting §4.4 | 915–934 | `∀a.a → a ≤ Int → Int`, etc. |
| `Bool → (∀a.a → a) ≤ Bool → Int → Int` | Putting §4.5 | 1138 | Deep subsumption with nested ∀ |
| `∀ab.a → b → b ≤ ∀a.a → (∀b.b → b)` (deep skolemization) | Putting §4.6 | 1436 | Isomorphic types should be mutually subsumable |
| HMV subsumption examples (Figure 5) | Eisenberg §4.2 | 526–532 | 7 examples including `∀{a}. a → a ≰hmv ∀a. a → a` |
| Level-based subtyping derivation | Levels §4.2 | 787–876 | Levels control skolem escape for subtyping |

### D. Predicativity vs Impredicativity

| Example | Paper | Lines | What It Demonstrates |
|---------|-------|-------|---------------------|
| `revapp (\x->x) poly` — is it legal? | Putting §3.4 | 391–397 | Impredicative instantiation question |
| `fix :: (a -> a) -> a` with `MapT` | Putting §3.4 | 399–400 | Fix at polymorphic type needs impredicativity |
| `data Tree a = Leaf a \| ...` with `Tree (∀a.a → a)` | Putting §3.4 | 403–405 | Data constructors and predicativity |
| `fst (id :: ∀a.a → a, Int)` rejected | Putting §7.4 | 4016–4019 | Ordinary polymorphic functions are predicative |
| Koka impredicativity promotion rule | Levels §7 | 1921–1923 | `∀a.σ ⇝ ∀a.σ'` — promoting to polymorphic type |

### E. Pattern Matching & Coverage

| Example | Paper | Lines | What It Demonstrates |
|---------|-------|-------|---------------------|
| `data T = MkT (forall a. a -> a); case x of MkT v -> (v 3, v True)` | Putting §7.3 | 3893–3901 | Higher-rank constructor patterns |
| `tcPat` for `PCon`, `PVar`, `PWild`, `PAnn` | Putting §7.2 | 3844–3865 | Complete pattern typing implementation |
| `f (x::Int->Int) :: (∀a.a → a) → Int → Int` (pattern coercion) | Putting §8.2 | 4102–4113 | Patterns may require non-trivial coercions |
| `data T a b where T1 :: T Int Bool; T2 :: T Char Bool` | LYG §2.4 | 620–622 | GADT pattern matching with type equalities |
| `g1 :: T Int b → b → Int` | LYG §2.4 | 662–664 | GADT refines type variables |
| `g2 :: T a b → T a b → Int` | LYG §2.4 | 666–668 | Cross-argument GADT constraints |
| `f 0 = True; f 0 = False` | LYG §1 | 64–66 | Redundant + non-exhaustive clauses |
| `v :: SMaybe Void → Int` | LYG §2.3 | 455–459 | Strict fields make clauses redundant |
| `u` vs `u'` (redundant vs inaccessible) | LYG §2.3.1 | 502–511 | Distinguishing redundancy from inaccessibility |
| `safeLast` with view patterns | LYG §2.2.1 | 373–376 | Provable exhaustiveness via expression equivalence |

### F. GADTs & Local Assumptions

| Example | Paper | Lines | What It Demonstrates |
|---------|-------|-------|---------------------|
| `data T :: * -> * where T1 :: Int -> T Bool; T2 :: T a` | OutsideIn §1 | 173–175 | Canonical GADT introducing local equalities |
| `test (T1 n) _ = n > 0; test T2 r = r` | OutsideIn §1 | 176–178 | Pattern match brings local constraints |
| Two incomparable principal types for `test` | OutsideIn §1 | 185–186 | Loss of principal types with GADTs |
| `data Showable where MkShowable :: Show a => a -> Showable` | OutsideIn §4.1 | 1498–1502 | Existential package with class constraint |
| `data X where Pack :: forall b. b -> (b -> Int) -> X` | OutsideIn §4.1 | 1480–1487 | Existential escape check |
| `fr :: a -> T a -> Bool` (local let with GADT) | OutsideIn §4.2 | 1541–1546 | No let-generalization under GADTs |
| `data R a where R1 :: (a ~ Int) => a -> R a; R2 :: (a ~ Bool) => a -> R a` | OutsideIn §6.2 | 2632–2642 | Inconsistent local assumptions (dead code) |
| `data T :: * → * where TInt :: T Int` (FC target) | Weirich §3 | 389–390 | GADT compiled to FC with explicit equality |
| `f = Λa. λx:T a. case x of TInt (c: a ∼ Int) → (3 ▷ sym c)` | Weirich §3 | 520–521 | FC pattern matching binds coercion proof |
| `data T :: ★ → ★ where T1 :: Int → T Bool; T2 :: T a` | Levels §7 | 2024–2031 | GADTs with levels for untouchability |

### F2. Type Families & Constraint Solving

| Example | Paper | Lines | What It Demonstrates |
|---------|-------|-------|---------------------|
| `type family F a; type instance F Bool = Int` | Weirich §3 | 348–349 | Source-level type family |
| `axF : F Bool ∼ Int` (FC axiom) | Weirich §3 | 351 | FC axiom from type family |
| `g True 3` → `g Bool True (3 ▷ sym axF)` | Weirich §3 | 383 | FC translation uses coercions |
| `type family F :: * -> *; type instance F [a] = F a` | OutsideIn §2.3 | 308–310 | Recursive type family |
| `F (G Int) ~ Int` flattening | OutsideIn §7.4 | 3359 | Canonicalization lifts nested applications |
| `F Int beta /\ F Int gamma /\ delta ~ gamma` (SIMPLES) | OutsideIn §7.5 | 3742 | Solving with touchable variables |
| `f :: ∀ a. (a ~ [F a]) => a -> Bool` | OutsideIn §7.2 | 2974 | Tricky interaction of type families and local assumptions |

### G. Visible Type Application

| Example | Paper | Lines | What It Demonstrates |
|---------|-------|-------|---------------------|
| `(id :: Int → Int)` vs `id @Int` | Eisenberg §1 | 62, 67 | Annotation vs visible application |
| `normalize @Expr` replacing Proxy | Eisenberg §2 | 196–199 | Clean visible type application |
| `pid @Int @Bool` ambiguous across 3 types | Eisenberg §3.1 | 227–261 | Principal type ambiguity for VTA |
| `∀{a}. a → a ≰hmv ∀a. a → a` | Eisenberg §4.2 | 532 | Generalized less general than specified |
| `let x = (...) in x @Int` (lazy instantiation) | Eisenberg §5.2 | 859 | VTA after let requires lazy instantiation |
| `pair 'x' @Bool` | Eisenberg §6 | 932 | VTA after partial application |
| `eqT @a @b` replacing type annotation | Eisenberg A.1 | 1722–1726 | VTA simplifies constraint deferral |
| `fact @(Eval e1) @(Eval e2) @s` | Eisenberg A.2 | 1871–1874 | VTA eliminates Proxy in dependent programming |
| `MkG @b` (future: visible type patterns) | Eisenberg B.6 | 2045–2048 | VTA in patterns |

### H. Scoped Type Variables

| Example | Paper | Lines | What It Demonstrates |
|---------|-------|-------|---------------------|
| `prefix x yss = let xcons ys = x : ys in map xcons yss` | J&S §1 | 50–55 | Cannot annotate `xcons` without scoped vars |
| `prefix (x::a) yss = let xcons :: [a] -> [a] = ...` | J&S §4 | 628–633 | Pattern type signature brings `a` into scope |
| `(\x::a -> (x,True) :: (a,Bool))` | J&S §4 | 559 | Type sharing: `a` names x's type |
| `implies (x::a) (y::a) = not x \|\| y` | J&S §4 | 596 | Scoped vars accept monomorphic instantiation |
| `Λα. λx:α. x` (System F) | J&S §3 | 211–212 | Type-lambda approach contrast |
| SML `fun 'a prefix (x : 'a) yss` | J&S §3 | 240–244 | SML explicit type parameter |
| `case v of { (x::a, y) -> (x, x) :: (a,a) }` | J&S §5 | 1009 | Scoped vars in case expressions |

### I. Levels & Generalization

| Example | Paper | Lines | What It Demonstrates |
|---------|-------|-------|---------------------|
| `let f = λx → x in (f 1, f True)` | Levels §2.1 | 125–128 | Let-generalization makes `f` polymorphic |
| `λx → let y = x in (y + 1, not y)` (error) | Levels §2.1 | 133–135 | Escaping variable blocks generalization |
| Level-based `let` rule with `n+1` increment | Levels §2.1 | 163–174 | No context traversal needed for generalization |
| `data Tree = Leaf Int \| Node Tree Tree in ...` | Levels §2.3 | 267–269 | Local datatype with level-based scoping |
| Promotion: `∀b. b → b <: α̂⁰` succeeds, `α̂⁰ <: ∀b. b → b` fails | Levels §6.2 | 1591–1617 | Polarity controls skolem vs unification |
| `(λx. let y = f x in y)` full derivation | Levels §6.2 | 1619–1660 | Levels track generalization through let |

### J. Constraint-Based Inference

| Example | Paper | Lines | What It Demonstrates |
|---------|-------|-------|---------------------|
| `check Γ e τ` propositional generator | Carnier §2.1 | 210–219 | Propositional constraints for simply-typed λ |
| `synth Γ e` monadic generator | Carnier §2.2 | 320–344 | Monadic synthesis with elaboration |
| `WP (synth Γ e) Q` weakest preconditions | Carnier §2.4 | 353–360 | Predicate transformer semantics |
| World-indexed types: `T̂y w` | Carnier §3 | 457–461 | First-order representation of existentials |
| `ŝynth` with explicit substitutions | Carnier §3.3 | 643–656 | Substitution-threaded constraint generation |
| `Γ̂ ⊢Â e : τ̂ ⟦ ê` open typing relation | Carnier §4.5 | 1039 | WP-based correctness for open types |
| `R⟦Free A, F̂ree Â⟧w` logical relation | Carnier §4.7 | 1191–1208 | Relating HOAS to first-order |

### K. Coercions & System FC

| Example | Paper | Lines | What It Demonstrates |
|---------|-------|-------|---------------------|
| `Γ ⊢co γ : τ1 ∼ τ2` | Weirich §3 | 331 | Core FC coercion judgment |
| `g Bool True (3 ▷ sym axF)` | Weirich §3 | 383 | Cast `3` from `Int` to `F Bool` |
| `TyInt : ∀k:*. ∀ c1:k∼*, c2:t∼Int. TyRep k t` | Weirich §4 | 1015 | FC type with kind+type coercions |
| `SK_PUSH` rule | Weirich §5 | 1047–1056 | Pushing coercions through pattern matching |
| Lifting context `Ψ` | Weirich §5 | 1082–1096 | Maps type vars to coercion proofs |
| `∀ c1: Int ∼ b. Int` vs `∀ c2: Int ∼ b. b` | Weirich §6 | 1440 | Types that cannot be proven equivalent |

### L. Error Messages & Implementation

| Example | Paper | Lines | What It Demonstrates |
|---------|-------|-------|---------------------|
| `f :: (Int -> Int) -> Bool` context in Algorithm W | Putting §5.4 | 2974 | Opaque unification failures in W |
| `checkRho` for better error messages (Algorithm M) | Putting §5.4 | 3004 | Push expected type inward for locality |
| LOC comparison: 650 vs 695 lines | Putting §6.6 | 3612–3631 | Only ~45 extra lines for higher-rank |
| Refinement types `⟨x:Bool \| ⊤⟩` | LYG §3.2 | 1337–1350 | Concrete denotation of uncovered sets |
| Exponential blowup with `N` GRHSs | LYG §5.2 | 2780–2801 | Motivation for throttling |
| COMPLETE set with 1000 constructors | LYG §5.3 | 2890–2917 | Residual COMPLETE set caching for efficiency |
| Church numeral `λf.λx.f (f (f x))` benchmark | Carnier §5 | 1487 | Synthetic benchmark for reconstruction |

---

## Per-Paper Example Highlights

### Putting 2007 — Key Teaching Examples

1. **The `foo` example** (§1, lines 73–104): The canonical motivating example. First rejected, then accepted with a type annotation. Teaches: DM restriction limits lambda-bound arguments to monotypes; annotations enable higher-rank types.

2. **The `mapM` with explicit Monad record** (§2, lines 196–205): A rank-2 data type simulates type classes. Teaches: higher-rank types have practical applications.

3. **The `foo` with bidirectional inference** (§4.7, line 1510): `foo = (\i. (i 3, i True)) :: (∀a.a → a) → (Int, Bool)`. Teaches: type annotations push information inward; bidirectional inference makes annotations optional when context suffices.

4. **The `concat` System F translation** (§4.8, lines 1861–1876): Shows implicit → explicit transformation. Teaches: type-directed translation fills in `Λa.`, `@τ`, and binder annotations.

5. **The `runST (newRef 'c')` escape check** (§6.4, lines 3499–3515): A subtle example where a skolem constant escapes. Teaches: escape checking must include `sigma2` in the free variable check.

### OutsideIn(X) 2011 — Key Teaching Examples

1. **GADT `data T` with `test`** (§1, lines 173–186): Pattern matching introduces local equalities; two incomparable principal types arise.

2. **`fr :: a -> T a -> Bool`** (§4.2, lines 1541–1558): Local let-binding under GADT match should not be generalized. Principal type uses local equality constraint.

3. **`data R a where RBool :: (a ~ Bool) => R a; foo rx = case rx of RBool -> 42`** (§6.3, lines 2695): OutsideIn(X) rejects a program with a valid principal type because the return type is not fixed from outside.

4. **`F Int beta /\ F Int gamma /\ delta ~ gamma`** (§7.5, lines 3742): The SIMPLES rule extracts a substitution from touchable constraints.

### Lower Your Guards 2020 — Key Teaching Examples

1. **`not` via pattern guards** (§2.1, lines 294–311): Three definitions of `not` (pattern guards, structural, lazy guard) — all semantically equivalent, all provably exhaustive by LYG.

2. **`v :: SMaybe Void → Int`** (§2.3, lines 455–459): Strict fields + uninhabited type make a clause unreachable. Teaches: coverage checking must account for strictness.

3. **`u` vs `u'`** (§2.3.1, lines 502–511): The only difference is `True` vs `False` in a guard, but it changes redundant → inaccessible. Teaches: redundancy (deletable) ≠ inaccessibility (RHS never reached).

4. **`g2 :: T a b → T a b → Int`** (§2.4, lines 666–668): Cross-argument type equality: `T1 T2` and `T2 T1` would imply `Int ~ Char`. Teaches: GADT coverage requires reasoning about equalities across arguments.

### Eisenberg 2016 — Key Teaching Examples

1. **`pid (x,y) = (x,y)` with three types** (§3.1, lines 227–261): The core ambiguity: visible type application requires unique designation of type parameters.

2. **`∀{a}. a → a ≰hmv ∀a. a → a`** (§4.2, line 532): Generalized variables are less general than specified. This is the key distinction enabling visible type application.

3. **`assume @(b ∼ Unbranched)` replacing Proxy** (A.1, lines 1727–1728): The payoff: visible type application eliminates the Proxy pattern entirely.

4. **`fact @(Eval e1) @(Eval e2) @s`** (A.2, lines 1871–1874): The complete motivating example: a dependently-typed stack compiler where VTA replaces 3 Proxy arguments with 3 visible type arguments.

### Jones & Shields 2002 — Key Teaching Examples

1. **`prefix (x::a) yss = let xcons :: [a] -> [a] = ...`** (§4, lines 628–633): The type-sharing approach: pattern signature `(x::a)` brings `a` into scope, enabling the inner annotation.

2. **`implies (x::a) (y::a) = not x || y`** (§4, line 596): Accepted by type-sharing (a names Bool) but rejected by type-lambda (claims false polymorphism).

3. **`revap (Ap (xs::[a]) f) = f ys where ys :: [a]; ys = reverse xs`** (§4, lines 819–823): Scoped type variables in pattern matching on existentials.

### Fan, Xu, Xie 2025 — Key Teaching Examples

1. **Level-based `let` rule** (§2.1, lines 163–174): Increment level to n+1 for RHS; generalize only variables at level n+1. No context traversal needed.

2. **Polarity: `∀b. b → b <: α̂⁰` succeeds, `α̂⁰ <: ∀b. b → b` fails** (§6.2, lines 1591–1617): Positive polarity instantiates with unification variable; negative polarity skolemizes and fails level check.

3. **`(λx. let y = f x in y)` full derivation** (§6.2, lines 1619–1660): Shows how promotion lowers variable levels, affecting what gets generalized at `let`.

---

## Open Questions

- [ ] How do the levels in Fan 2025 relate to the touchable/untouchable distinction in OutsideIn(X)?
- [ ] Can the LYG guard tree representation be combined with bidirectional type checking from Putting 2007?
- [ ] What is the precise relationship between Carnier's predicate transformers and Putting's subsCheck coercion generation?

## Related Topics

- [`putting2007-pattern-matching.md`](putting2007-pattern-matching.md) — Detailed pattern matching analysis for Putting 2007
- [`putting2007-reading.md`](putting2007-reading.md) — Full reading notes for Putting 2007
- [`putting2007-index.md`](putting2007-index.md) — Line number index for Putting 2007
