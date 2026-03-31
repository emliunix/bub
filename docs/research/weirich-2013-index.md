# Weirich 2013 - System FC with Explicit Kind Equality - Index

**Paper**: "System FC with Explicit Kind Equality"  
**Authors**: Stephanie Weirich, Justin Hsu, Richard A. Eisenberg (University of Pennsylvania)  
**Venue**: ICFP 2013  
**Source**: `weirich-2013-system-fc.txt`

---

## How to use this index

```bash
# Jump to a specific section
sed -n '539,620p' weirich-2013-system-fc.txt    # Read Section 4 intro
sed -n '1227,1232p' weirich-2013-system-fc.txt  # Read Section 5.1

# Search within sections
grep -n "Preservation" weirich-2013-system-fc.txt
grep -n "kind equality" weirich-2013-system-fc.txt
```

---

## Main Sections

| Section | Line | Description |
|---------|------|-------------|
| Abstract | 12 | Paper overview: extending FC with kind equalities |
| **1 Introduction** | 38 | Haskell as dependently typed, motivation for kind equalities |
| **2 Why kind equalities?** | 118 | Extended examples demonstrating need |
| 2 (shallow indexing) | 134 | TyRep GADT, kind-indexed GADTs |
| 2 (deep indexing) | 198 | Promoted GADTs, kind families, Ty universe |
| **3 System FC** | 329 | Background on FC intermediate language |
| 3 (grammar H) | 359 | Type constants, arrow, kind indicator |
| 3 (grammar σ,τ,κ) | 399 | Types and kinds syntax |
| 3 (grammar φ) | 417 | Propositions (coercion kinds) |
| 3 (grammar γ,η) | 421 | Coercions syntax |
| 3 (grammar e,u) | 461 | Expressions syntax |
| **4 System FC with kind equalities** | 541 | Main contribution: extending FC |
| 4.1 Type system overview | 622 | Judgements and syntax overview |
| 4.2 Type and kind formation | 665 | Figure 2: kind formation rules |
| 4.3 Coercions | 769 | Figure 4: coercion formation rules |
| 4.3.1 Congruence rules | 905 | Quantified types, CT_ALLT rule |
| 4.3.2 Coercion irrelevance | 959 | Proof irrelevance, coherence rule |
| 4.4 Datatypes | 983 | Telescopes, constructor types |
| **5 Push rules & preservation** | 1026 | Operational semantics |
| 5.1 Pushing coercions | 1037 | SK_PUSH rule, lifting contexts |
| 5.2 Type preservation | 1231 | Theorem 5.6 |
| 5.3 Type erasure theorem | 1129 | Erasure operation, Theorem 5.7 |
| **6 Consistency & progress** | 1164 | Soundness metatheory |
| 6 (Good contexts) | 1415 | Definition 6.5: context consistency |
| 6 (Consistency lemma) | 1352 | Lemma 6.6: completeness of joinability |
| **7 Discussion & related work** | 1450 | Type-in-Type, heterogeneous equality |
| **8 Conclusions & future work** | 1548 | Summary, future extensions |
| Acknowledgments | 1583 | |
| References | 1589 | |

---

## Key Figures

| Figure | Line | Contents |
|--------|------|----------|
| Figure 1 | 550 | Basic grammar (H, w, στκ, φ, γη, e, p, ∆) |
| Figure 2 | 688 | Kind and type formation rules (K_VAR, K_ARROW, etc.) |
| Figure 3 | 721 | Proposition formation rule (PROP_EQUALITY) |
| Figure 4 | 769 | Coercion formation rules (CT_REFL, CT_SYM, CT_TRANS, etc.) |
| Figure 5 | 855 | Context formation rules (GWF_*) |
| Figure 6 | 1057 | SK_PUSH rule for pattern matching |
| Figure 7 | 1371 | Rewrite relation for consistency |

---

## Key Judgements

| Judgment | Line | Description |
|----------|------|-------------|
| `Γ ⊢wf Γ` | 639 | Context validity |
| `Γ ⊢ty τ : κ` | 640 | Type/kind validity |
| `Γ ⊢pr φ ok` | 641 | Proposition validity |
| `Γ ⊢tm e : τ` | 642 | Expression typing |
| `Γ ⊢co γ : φ` | 643 | Coercion validity |
| `Γ ⊢tel ρ ⇐ Δ` | 644 | Telescope argument validity |

---

## Key Theorems

| Theorem | Line | Statement |
|---------|------|-----------|
| Theorem 5.6 | 1237 | **Preservation**: If Γ ⊢ e : τ and e → e', then Γ ⊢ e' : τ |
| Theorem 5.7 | 1156 | **Type erasure**: If e → e', then |e| → |e'| or |e| = |e'| |
| Theorem 6.1 | 1199 | **Progress**: Closed consistent context: e diverges or steps |
| Lemma 5.3 | 1159 | **Lifting lemma**: Equality is congruent |
| Lemma 6.6 | 1355 | **Completeness**: Joinability of rewrite relation |
| Definition 6.5 | 1415 | **Good contexts**: Sufficient condition for consistency |

---

## Critical Coercion Forms

| Form | Line | Description |
|------|------|-------------|
| `sym γ` | 427 | Symmetry |
| `γ1 # γ2` | 428 | Transitivity |
| `∀a: κ. γ` | 429 | Type abstraction congruence |
| `∀c: φ. γ` | 430 | Coercion abstraction congruence |
| `γ1 γ2` | 431 | Application congruence |
| `γ(γ2, γ2')` | 432 | Coercion application congruence |
| `γ . γ'` | 433 | Coherence |
| `γ @ γ'` | 434 | Type/kind instantiation |
| `nthi γ` | 436 | Nth argument projection |
| `kind γ` | 437 | Kind equality extraction |

---

## Quick Topic Reference

| Topic | Where to find |
|-------|---------------|
| Kind equalities motivation | Lines 118-265 (Section 2) |
| Unifying types and kinds (Type-in-Type) | Lines 552-570, 1452-1471 |
| Heterogeneous equality | Lines 571-581, 1472-1506 |
| Coercion irrelevance | Lines 586-595, 961-981 |
| Dependent coercion abstraction | Lines 596-619 |
| Lifting contexts (Ψ) | Lines 1069-1177 |
| SK_PUSH rule | Lines 1037-1058 |
| Good contexts definition | Lines 1415-1430 |
| Consistency proof outline | Lines 1261-1277 |
| Extended version reference | Line 116 |

---

## Key Contributions Summary

1. **Explicit kind equality proofs**: Adding kind coercions to FC
2. **Unified types and kinds**: Using pure type systems approach with Type-in-Type
3. **Heterogeneous equality**: Types with different kinds can be equal
4. **Extended preservation proof**: Covers new features including lifting
5. **Progress theorem**: With new consistency conditions for kind equalities

---

## Relationship to Other Papers

| Paper | Relationship |
|-------|--------------|
| Sulzmann et al. 2007 | Original FC definition |
| Weirich et al. 2011 | FC↑ extension (datatype promotion) |
| Yorgey et al. 2012 | Kind polymorphism, promoted datatypes |
| Eisenberg 2016 | Visible type application (builds on this work) |
