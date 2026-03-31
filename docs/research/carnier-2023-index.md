# Carnier-Pottier-Keuchel 2024 - Paper Text Index (Line Numbers)

**Paper**: "Type Inference Logics"  
**Authors**: Denis Carnier, François Pottier, Steven Keuchel  
**Venue**: Proc. ACM Program. Lang., Vol. 8, No. OOPSLA2, Article 346 (October 2024)  
**Source**: `carnier-2023.txt`

---

## How to use this index

```bash
# Jump to a specific section
sed -n '26,151p' carnier-2023.txt         # Read Section 1 (Introduction)
sed -n '467,782p' carnier-2023.txt        # Read Section 3 (Monadic Constraint Generation)
grep -n "constraint" carnier-2023.txt     # Search within sections
```

---

## Main Sections

| Section | Line | Description |
|---------|------|-------------|
| Abstract | 1 | Overview: constraint-based type inference with elaboration |
| **1 Introduction** | 26 | Motivation, related work, contributions |
| **2 Overview** | 152 | High-level approach with simply-typed λ-calculus (λB) |
| 2.1 Propositional Constraints | 246 | Constraint generation as truth values |
| 2.2 Monadic API | 277 | Constraints with semantic values (CstrM type class) |
| 2.3 Free Monad Implementation | 305 | Free monad for constraint syntax |
| 2.4 Generator Correctness | 379 | Predicate transformer semantics (WP/WLP) |
| **3 Monadic Constraint Generation** | 467 | World-indexed types and first-order representation |
| 3.1 Abstract Interface | 497 | Correct-by-construction metavariable handling |
| 3.2 Free Monad Instance | 621 | World-indexed monad definition |
| 3.3 First-Order Generator | 675 | synth/check with explicit existential variables |
| 3.4 Synthesizing Open Types | 690 | Open modality and applicative interface |
| 3.5 Prenex Form | 717 | Quantifier manipulation |
| 3.6 Putting It Together | 739 | Closed algorithmic typing relation |
| **4 Type Inference Logics** | 783 | Domain-specific base logic and program logic |
| 4.1 Base Logic | 799 | Assignment predicates and entailment |
| 4.2 Assignment Predicates | 811 | Pred abstraction, substitutions |
| 4.3 Semantics of Constraints | 919 | Predicate transformers for Free monad |
| 4.4 Program Logic | 991 | Reasoning rules for constraint generation |
| 4.5 Correctness Proofs | 1033 | Soundness and completeness theorems |
| 4.6 Logical Relation | 1133 | Relating higher-order and first-order |
| 4.7 Bidirectional Generator | 1157 | Checking mode added to synthesis |
| **5 Mechanization and Evaluation** | 1272 | Coq formalization and benchmarks |
| **6 Related Work** | 1558 | Comparison with PureCake, CakeML, etc. |
| **References** | ~1700 | Bibliography |

---

## Key Figures

| Figure | Line | Contents |
|--------|------|----------|
| Fig. 1 | 119 | λB: Simply typed λ-calculus with Booleans (syntax) |
| Fig. 2 | 167 | Declarative typing and elaboration rules |
| Fig. 3 | 220 | Propositional constraint generator (check) |
| Fig. 4 | 229 | CstrM: Monad interface for constraints |
| **Fig. 5** | **320** | **Monadic constraint generation with elaboration (synth)** |
| Fig. 6 | 347 | Free monad definition (Free A) |
| Fig. 7 | 353 | Weakest preconditions for Free |
| Fig. 8 | 421 | Weakest liberal preconditions (WLP) |
| Fig. 9 | 465 | World-indexed types (World → Type) |
| Fig. 10 | 529 | Free monad with world indices (F̂ree) |
| Fig. 11 | 531 | Parallel substitutions |
| Fig. 12 | 550 | Notations (Open, Prenex modalities) |
| Fig. 13 | 552 | Free monad bind operation |
| Fig. 14 | 592 | Monadic interface for constraint generation |
| Fig. 15 | 601 | Open modality and applicative interface |
| Fig. 16 | 657 | First-order constraint generator (ŝynth) |
| Fig. 17 | 779 | Closed algorithmic typing relation (⊢A) |
| Fig. 18 | 781 | Assignment predicates (Pred) and entailment |
| Fig. 19 | 901 | Substitution predicate transformers |
| Fig. 20 | 911 | Weakest preconditions for F̂ree |
| Fig. 21 | 978 | Program logic interface for constraint monads |
| Fig. 22 | 1210 | Logical relation (higher-order ↔ first-order) |
| Fig. 23 | 1211 | Logical relation for Free monad |
| Fig. 24 | 1541 | Benchmark execution times (Church numerals, Y combinator) |

---

## Critical Concepts and Functions

| Concept | Section | Line | Purpose |
|---------|---------|------|---------|
| `CstrM` | 2.2, 3.1 | 229, 592 | Monad type class for constraints with semantic values |
| `synth` | 2.2 | 320 | Constraint generator with type synthesis + elaboration |
| `check` | 2.1 | 220 | Propositional constraint generator (Boolean result) |
| `Free A` | 2.3 | 347 | Free monad representing constraint syntax |
| `WP` | 2.4 | 353 | Weakest precondition (total correctness) |
| `WLP` | 2.4 | 421 | Weakest liberal precondition (partial correctness) |
| `pick` | 2.2 | 299 | Non-deterministic choice (existential quantification) |
| `(_∼_)` | 2.2 | 297 | Equality combinator (unification) |
| `World` | 3 | 497 | Type contexts with explicit existential variables |
| `Open` | 3.4 | 601 | Modality for synthesizing open types |
| `Prenex` | 3.5 | 717 | Modality for quantifier manipulation |
| `subsCheck` | 4.2 | 901 | Substitution as predicate transformer |
| `⊢A` (algorithmic) | 3.6 | 779 | Algorithmic typing relation |
| `⊢D` (declarative) | 2 | 167 | Declarative typing relation |

---

## Quick Topic Reference

| Topic | Where to find |
|-------|---------------|
| **Constraint-based type inference** | Lines 65-74, 250-269 |
| **Constraints with semantic values** | Lines 281-301, 320-345 |
| **Monadic vs applicative interface** | Lines 290-291, 601-610 |
| **Free monad implementation** | Lines 305-378, 529-532 |
| **Predicate transformer semantics** | Lines 383-434, 911-930 |
| **Hoare-style reasoning** | Lines 409-414 |
| **Soundness direction (WP → WLP)** | Lines 415-428 |
| **Completeness direction** | Lines 409-411 |
| **World-indexed types** | Lines 497-508, 529-532 |
| **Existential variable representation** | Lines 371-378, 657-677 |
| **First-order vs higher-order HOAS** | Lines 371-378 |
| **Bidirectional type checking** | Lines 1157-1263 |
| **Elaboration to System F** | Lines 320-345, 402-408 |

---

## Theorems and Lemmas

| Theorem | Line | Statement |
|---------|------|-----------|
| Theorem 2.1 | 271 | Propositional generator correctness: `check Γ e τ ↔ Γ ⊢D e : τ` |
| Theorem 2.2 | 409 | Constraint generator correctness: `Γ ⊢A e : τ { e' ↔ Γ ⊢D e : τ { e'` |
| Lemma 2.3 | 425 | Constraint generator soundness (WLP formulation) |

---

## Pattern Matching / Type Inference Connection

**Note**: This paper focuses on constraint-based type inference for the simply-typed λ-calculus with Booleans (λB). It does **not** cover pattern matching specifically. However, the framework established here (constraint generation with semantic values, world-indexed types, elaboration) provides the foundation for handling pattern matching in type inference.

Key insights for pattern matching from this paper:
- **Constraint generation**: Patterns elaborate to constraints (lines 250-269)
- **Bidirectional checking**: Checking mode can handle pattern scrutinees (lines 1157-1263)
- **Existential variables**: World-indexed representation handles unknown types (lines 497-508)
- **Elaboration**: Explicitly-typed terms are constructed during inference (lines 320-345)

For papers specifically on **pattern matching with type inference**, see:
- Peyton Jones et al. "Simple Unification-based Type Inference for GADTs" (2006)
- Sulzmann et al. "Wobbly Types" (2006)
- Pottier & Régis-Gianas "Stratified Type Inference For Generalized Algebraic Data Types" (2006)
