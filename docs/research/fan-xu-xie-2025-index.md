# Fan et al. 2025 - Paper Text Index (Line Numbers)

**Paper**: "Practical Type Inference with Levels"  
**Authors**: Andong Fan, Han Xu, Ningning Xie (PLDI 2025)  
**Source**: `fan-xu-xie-2025-practical-type-inference-with-levels.txt`

---

## How to use this index

```bash
# Jump to a specific section
sed -n '313,528p' fan-xu-xie-2025-practical-type-inference-with-levels.txt    # Read Section 3 (Declarative system)
sed -n '1089,1280p' fan-xu-xie-2025-practical-type-inference-with-levels.txt  # Read Section 6.1 (Algorithmic typing)
sed -n '1294,1360p' fan-xu-xie-2025-practical-type-inference-with-levels.txt  # Read Figure 6 (Subtyping rules)

# Search within sections
grep -n "as-solveL" fan-xu-xie-2025-practical-type-inference-with-levels.txt
grep -n "ftv_{n+1}" fan-xu-xie-2025-practical-type-inference-with-levels.txt
```

---

## Main Sections

| Section | Line | Description |
|---------|------|-------------|
| Title/Abstract | 1 | Paper title, authors, and abstract |
| **1 Introduction** | 21 | Motivation: gap between theory and implementation, levels overview |
| **2 Overview** | 111 | Key ideas illustrated with examples |
| 2.1 Hindley-Milner and Let Generalization | 116 | Standard HM, rule HM-let vs level-based rule let |
| 2.2 Levels for Higher-Rank Polymorphism | 200 | Skolem escape checking with levels |
| 2.3 Type Regions | 260 | Local datatype declarations with levels |
| 2.4 This Work | 295 | Summary of contributions |
| **3 Declarative Type System** | 313 | Non-level-based base system |
| 3.1 Syntax | 321 | Figure 1: expressions, types, contexts |
| 3.2 Typing | 335 | Figure 2: bidirectional rules (t-lam, t-app, t-let, subtyping) |
| **4 Level-Based Declarative Type System** | 528 | Core level-based formalism |
| 4.1 Typing | 542 | **Figure 3: level-based typing rules** (lt-let with ftv_{n+1}) |
| 4.2 Examples | 739 | Generalization and subtyping examples |
| **5 Coq Mechanization** | 879 | Soundness and completeness proofs |
| 5.1 Coq Representation | 887 | Explicit level contexts Δ, lct-let rule |
| 5.2 Soundness and Completeness | 934 | Theorems 5.2, 5.7; level compatibility definitions |
| **6 Algorithmic Type System with Levels** | 1089 | **Main algorithmic system** |
| 6.1 Algorithmic Typing | 1107 | **Figure 5: algorithmic typing rules** (at-let, at-app, matching) |
| 6.2 Subtyping | 1486 | **Figure 6: subtyping rules** (as-solveL, as-solveR) |
| 6.3 Soundness | 1808 | Theorem 6.3, context extension |
| 6.4 Completeness | 1855 | Theorem 6.6 |
| **7 Implementation** | 1896 | Koka compiler implementation and evaluation |
| **8 Language Extensions** | 2010 | GHC, OCaml, GADTs, kind polymorphism |
| **9 Related Work and Conclusion** | 2081 | Summary and future work |
| References | 2108 | Bibliography |

---

## Key Figures

| Figure | Line | Contents |
|--------|------|----------|
| Figure 1 | 383 | Syntax: expressions, types, contexts |
| Figure 2 | 499 | Declarative type system (selected rules) |
| **Figure 3** | **730** | **Level-based declarative type system (main rules)** |
| Figure 4 | 1087 | Algorithmic syntax, context application, well-formedness |
| **Figure 5** | **1279** | **Algorithmic typing rules (at-let, at-app, at-lam)** |
| **Figure 6** | **1360** | **Algorithmic subtyping rules (as-solveL, as-solveR)** |
| **Figure 7** | **1449** | **Polymorphic promotion judgment (pr-uvarPr, pr-forallPos/Neg)** |
| Figure 8 | 1583 | Example derivation showing promotion in action |
| Figure 9 | 1757 | Well-formedness of contexts |
| Figure 10 | 1806 | Context extension |
| Figure 11 | 1999 | Evaluation results (Level Koka vs Koka) |

---

## Critical Concepts

| Concept | Line | Description |
|---------|------|-------------|
| **ftv_{n+1} generalization** | 165, 555, 636 | Key insight: generalize only vars at level n+1 |
| Level numbers / TcLevel | 182-191 | Integer n indexing typing judgments |
| **Polymorphic promotion** | 1362-1449 | Figure 7: promoting types to resolve level constraints |
| pr-uvarPr rule | 1410-1415 | Promoting unification variable to lower level |
| pr-forallPos | 1428-1443 | Promoting ∀ under positive polarity |
| pr-forallNeg | 1430-1447 | Promoting ∀ under negative polarity |
| **as-solveL / as-solveR** | 1342-1358 | Solving unification variables in subtyping |
| Skolem escape prevention | 247-252 | Using levels to prevent skolem escape |
| Touchability/untouchability | 2031-2048 | GHC's use of levels for untouchable variables |
| **Subtyping rules** | 473-498, 706-730 | s-forallR/s-forallL, ls-forallR/ls-forallL |
| Contravariant function subtyping | 1320-1324 | as-func rule |
| Level compatibility (⊗) | 964-986 | Definitions 5.3-5.5 for merging contexts |
| Soundness (Theorem 5.2) | 948-952 | Level typing sound wrt non-level system |
| Completeness (Theorem 5.7) | 993-996 | Existence of level assignment |

---

## Quick Topic Reference

| Topic | Where to find |
|-------|---------------|
| Standard HM let-generalization | Lines 140-157 (rule HM-let, ftv(τ) - ftv(Ψ)) |
| Level-based let-generalization | Lines 162-191 (rule let, ftv_{n+1}) |
| Bidirectional typing modes (⇒, ⇐) | Lines 339-342, 385-498 |
| Subtyping judgment (<:) | Lines 471-498 (declarative), 706-730 (level-based), 1294-1360 (algorithmic) |
| Unification variables (α̂) | Lines 1005-1026, 1094-1106 |
| Algorithmic context (Γ) | Lines 1005-1042 |
| Matching judgment (⊲) | Lines 460-469, 691-702, 1255-1278 |
| Promotion with polarity (+/-) | Lines 1362-1449, 1504-1535 |
| Skolemization with levels | Lines 733-738, 811-823 |
| Performance evaluation | Lines 1941-2008 (2.9-3.7x faster generalization) |
