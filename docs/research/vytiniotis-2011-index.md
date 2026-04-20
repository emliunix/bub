# OutsideIn(X) 2011 - Paper Text Index (Line Numbers)

**Paper**: "OutsideIn(X): Modular type inference with local assumptions"  
**Authors**: Vytiniotis, Peyton Jones, Schrijvers, Sulzmann (2011)  
**Source**: `vytiniotis-2011-outsidein.txt`

---

## How to use this index

```bash
# Jump to a specific section
sed -n '153,300p' vytiniotis-2011-outsidein.txt     # Read Section 1-2
sed -n '482,1338p' vytiniotis-2011-outsidein.txt    # Read Section 3
sed -n '1872,2580p' vytiniotis-2011-outsidein.txt   # Read Section 5 (main algorithm)
grep -n "GADT" vytiniotis-2011-outsidein.txt        # Search within sections
```

---

## Main Sections

| Section | Line | Description |
|---------|------|-------------|
| Title/Abstract | 1 | Paper title and abstract |
| **1 Introduction** | 153 | Overview and contributions |
| **2 The challenge we address** | 200 | Modular inference, principal types, local constraints |
| 2.1 Modular type inference | 208 | Principal types in HM |
| 2.2 The challenge of local constraints | 245 | GADT patterns, existential variables |
| 2.3 The challenge of axiom schemes | 289 | Type families, top-level axioms |
| 2.4 Recovering principal types | 319 | Enriching type syntax |
| **3 Constraint-based type systems** | 482 | Formal framework (HM(X) style) |
| 3.1 Syntax | 500 | Language syntax (Figure 1) |
| 3.2 Typing rules | 643 | Vanilla constraint system (Figure 2) |
| 3.3 Type soundness | 715 | Entailment conditions (Figure 3) |
| 3.4 Type inference, informally | 746 | Constraint generation idea |
| 3.5 Type inference, precisely | 757 | Axiom schemes (Figure 4) |
| 3.6 Soundness and principality | 1086 | Main theorems |
| **4 Constraint-based systems with local assumptions** | 1338 | GADTs and existential constraints |
| 4.1 Data constructors with local constraints | 1349 | Extended syntax (Figure 9) |
| 4.2 let should not be generalized | 1728 | No generalization for local let |
| 4.3 The lack of principal types | 1845 | Examples of non-principal types |
| **5 Type inference with OutsideIn(X)** | 1872 | **Main algorithm** |
| 5.1 Type inference, informally | 1878 | Overview of the approach |
| 5.2 Overview of the solving algorithm | 1944 | Simplification strategy |
| 5.3 Top-level algorithmic rules | 2088 | **Figure 12: main inference rules** |
| 5.4 Generating constraints | 2158 | **Figure 13: constraint generation** |
| 5.5 Solving constraints | 2265 | **Figure 14: constraint solver** |
| 5.6 Variations on the design | 2545 | Alternative designs |
| 5.7 Soundness and principality | 2658 | Theorems for algorithm |
| **6 Incompleteness and ambiguity** | 2680 | When inference fails |
| 6.1 Incompleteness due to ambiguity | 2683 | Ambiguous types |
| 6.2 Incompleteness due to inconsistency | 2731 | Insoluble constraints |
| 6.3 Incompleteness of the strategy | 2749 | Algorithmic limitations |
| 6.4 Guess-free completeness | 2763 | Stronger completeness notion |
| 6.5 Position on incompleteness | 2809 | Design philosophy |
| **7 Instantiating X** | 2828 | GADTs + type classes + type families |
| 7.1 The entailment relation | 2836 | Concrete entailment |
| 7.2 Solving equality constraints | 2882 | Unification with GADTs |
| 7.3 The simplifier | 2915 | Simplification rules |
| 7.4 Rewriting constraints | 2940 | Canonicalization |
| 7.5 The rule SIMPLES | 2998 | Simple constraint solving |
| 7.6 Soundness and principality | 3066 | Concrete solver theorems |
| 7.7 Termination | 3086 | Proof of termination |
| **8 Implementation** | 3904 | GHC implementation details |
| 8.1 Evidence | 3908 | Type-class dictionaries |
| 8.2 Brief sketch of implementation | 3943 | Practical notes |
| **9 Related work** | 4107 | Comparisons |
| **10 Conclusion** | 4185 | Summary |
| References | 4197 | Bibliography |

---

## Key Figures

| Figure | Line | Contents |
|--------|------|----------|
| Figure 1 | 500 | Syntax of types, terms, and constraints |
| Figure 2 | 643 | Vanilla constraint-based typing rules |
| Figure 3 | 715 | Entailment conditions |
| Figure 4 | 757 | Typing rules with axiom schemes |
| Figure 5 | 872 | Algorithmic syntax (simple types) |
| Figure 6 | 901 | Constraint generation rules |
| Figure 7 | 1032 | Top-level inference algorithm |
| Figure 8 | 1028 | Simplifier conditions |
| Figure 9 | 1341 | Extended syntax for local constraints |
| Figure 10 | 1353 | Typing rules with GADTs |
| Figure 11 | 1947 | Algorithmic syntax (extended) |
| **Figure 12** | **2088** | **Top-level inference with local assumptions** |
| **Figure 13** | **2158** | **Constraint generation for GADTs** |
| **Figure 14** | **2265** | **Constraint solver (solve)** |
| Figure 15 | 2314 | Touchable-aware simplifier conditions |

---

## Critical Rules and Judgments

| Rule/Judgment | Figure | Line | Purpose |
|---------------|--------|------|---------|
| `Γ ⊢ e : σ` | Figure 2 | 643+ | Specification typing |
| `Q ; Γ ⊢ prog` | Figure 4 | 757+ | Program typing with axioms |
| `Γ ⊢_I prog` | Figure 7 | 1032+ | Algorithmic inference |
| `τ, C = [[e]]_Γ` | Figure 6 | 901+ | Constraint generation |
| `solve(Q_t, Q_w, C)` | Figure 14 | 2265+ | Constraint solving |
| `simplify(Q_t, Q_w, C)` | Figure 14 | 2293+ | Constraint simplification |
| `Q ; Γ ⊢_I prog` | Figure 12 | 2088+ | Inference with local assumptions |
| `[[e]]_Γ = (τ, C)` | Figure 13 | 2158+ | Generation with GADTs |

---

## Key Concepts and Where to Find Them

| Concept | Section | Line | Description |
|---------|---------|------|-------------|
| **GADT patterns** | 2.2 | 245-288 | Pattern matching brings local constraints |
| **Existential variables** | 2.2 | 264-270 | Variables bound by data constructors |
| **Axiom schemes** | 2.3 | 289-318 | Type families, type class instances |
| **Touchable variables** | 5.2 | 1944+ | Variables eligible for unification |
| **Wanted vs Given** | 5.2 | 1955+ | Q_w (to solve) vs Q_t (assumed) |
| **Implication constraints** | 4.1 | 1350+ | `C ⊃ D` (C implies D) |
| **Generalization restriction** | 4.2 | 1728+ | No let-generalization with GADTs |
| **Principal types** | 2.1, 4.3 | 208, 1845 | When they exist and when they don't |
| **Type families** | 2.3 | 325 | Type-level functions |
| **Evidence** | 8.1 | 3908+ | Dictionary passing for type classes |

---

## Comparison with Putting 2007

| Aspect | Putting 2007 | OutsideIn(X) 2011 |
|--------|-------------|-------------------|
| **Main focus** | Higher-rank polymorphism | Local assumptions (GADTs, type families) |
| **Approach** | Bidirectional type checking | Constraint-based inference |
| **Constraints** | Unification only | General constraint framework X |
| **GADTs** | Not covered | Primary motivation |
| **Generalization** | HM-style at let-bindings | Restricted (no local let-generalization) |
| **Meta variables** | IORef for unification | Touchable/unification variables |
| **Solver** | Robinson unification | Modular constraint solver |

---

## Quick Topic Reference

| Topic | Where to find |
|-------|---------------|
| Why GADTs break principal types | Lines 1845-1871 |
| The solve algorithm | Lines 2265-2313 |
| The simplify conditions | Lines 1028-1145 |
| Constraint generation for case | Lines 2216-2264 |
| Touchable variables explained | Lines 1944-2087 |
| Type family axioms | Lines 289-318 |
| No let-generalization rule | Lines 1728-1844 |
| Evidence construction | Lines 3908-3942 |
| Unification with GADTs | Lines 2882-2914 |
| Termination proof | Lines 3086-3200 |

---

## Reading Order for Implementation

1. **Sections 1-2**: Understand the problem (GADTs, local constraints, why principal types fail)
2. **Section 3**: The vanilla constraint framework (HM(X))
3. **Section 4**: How local assumptions extend the system
4. **Section 5**: The OutsideIn(X) algorithm (Figures 12-14)
5. **Section 7**: Concrete instantiation for GADTs + type classes + type families
6. **Section 8**: GHC implementation notes

---

## Key Insight: Touchable Variables

The critical innovation for handling GADTs is identifying which type variables can be unified:

```haskell
-- Variables in scope before pattern match = untouchable
-- Variables introduced by pattern match = touchable

case e of
  T2 x -> ...  -- x : a, but 'a' is existential (local)
               -- can unify 'a' with concrete types here
```

This prevents accidental unification with variables from the outer scope that should remain polymorphic.
