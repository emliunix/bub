# Dunfield & Krishnaswami 2022 - Paper Text Index (Line Numbers)

**Paper**: "Bidirectional Typing"  
**Authors**: Jana Dunfield, Neelakantan R. Krishnaswami (2022)  
**Source**: `dunfield-2022.txt`  
**Venue**: ACM Computing Surveys (CSUR), Volume 54, Issue 5, Article 98 (June 2022)

---

## How to use this index

```bash
# Jump to a specific section
sed -n '87,220p' dunfield-2022.txt    # Read Section 1 (Introduction)
sed -n '221,444p' dunfield-2022.txt   # Read Section 3 (Elements of Bidirectional)
grep -n "pattern" dunfield-2022.txt    # Search for pattern matching
```

---

## Main Sections

| Section | Line | Description |
|---------|------|-------------|
| **1 INTRODUCTION** | 87 | Overview, motivation, goals of the survey |
| **2 BIDIRECTIONAL SIMPLY TYPED LAMBDA CALCULUS** | 144 | Core bidirectional system with simple types |
| 2.1 Variable rule | 175 | How Var is bidirectionalized |
| 2.2 Annotation rule | 179 | Anno⇒ for synthesis |
| 2.3 Unit introduction | 183 | Unit checks |
| 2.4 Arrow introduction | 185 | →I checks (why synthesis fails) |
| 2.5 Arrow elimination | 199 | →E synthesizes the principal judgment |
| 2.6 Type equality | 205 | TypeEq bidirectionalized |
| **3 ELEMENTS OF BIDIRECTIONAL TYPING** | 221 | Design criteria for bidirectional systems |
| 3.1 Mode correctness | 228 | Outputs must not be guessed |
| 3.2 Annotatability | 247 | Completeness with annotations |
| 3.3 Subformula property | 259 | Finding types from context |
| 3.4 Annotation character | 361 | Quantity/quality of annotations |
| **4 A BIDIRECTIONAL RECIPE** | 418 | The Pfenning recipe for designing systems |
| 4.1 Introduction and Elimination Rules | 438 | Step-by-step recipe for connectives |
| 4.2 Annotations | 435 | Handling type annotations |
| 4.3 Variables | ~500 | Variables and subsumption |
| 4.4 Subsumption | 784 | Subtyping in bidirectional systems |
| 4.5 Meeting the criteria | 793 | How recipe satisfies design criteria |
| 4.6 Principal typing | 720 | Stationary rules and principality |
| **5 POLYMORPHISM** | 841 | Combining implicit polymorphism with bidirectional typing |
| 5.1 Hindley-Milner | 849 | Bidirectionalizing HM |
| 5.2 Higher-rank polymorphism | 1023 | Bidirectional type inference for rank-N |
| 5.2.1 Declarative system | 1048 | Bidirectional ∀-elimination |
| 5.2.2 Systems and Judgments | 1162 | Declarative vs algorithmic |
| 5.2.3 Ordered contexts | 1173 | Information gain and context extension |
| 5.2.4 Contexts as substitutions | 1193 | Using contexts as substitutions |
| 5.2.5 Historical notes | 1212 | Related approaches (GHC, etc.) |
| 5.3 Extensions to polymorphism | 1239 | GADTs, impredicativity |
| **6 VARIATIONS ON BIDIRECTIONAL TYPING** | 1262 | Alternative bidirectional approaches |
| 6.1 Mixed-direction types | 1268 | Inherited vs synthesized types in syntax |
| 6.2 Directional logic programming | 1286 | Modes in logic programming |
| 6.3 Mode annotations | 1318 | Programmer-specified synthesis/checking |
| 6.4 Simultaneous input and output | 1344 | Combined ⇐A⇒B judgment |
| 6.5 Backwards bidirectional typing | 1362+ | Linear type theory connections |
| **7 PROOF THEORY, NORMAL FORMS, AND TYPE ANNOTATIONS** | 1524 | Connection to proof theory and CBPV |
| 7.1 Focusing and polarity | ~1560 | Focused sequent calculus |
| 7.2 Call-by-push-value | ~1699 | CBPV type system |
| 8.x Spine forms | 1808+ | Application and pattern matching |
| 8.3.3 Typing terms | 1813 | Pattern-style lambda |
| **9 OTHER APPLICATIONS OF BIDIRECTIONAL TYPING** | 1900 | Survey of practical applications |
| 9.1 Dependent, refinement, intersection types | 1901 | DML, refinement types |
| 9.2 Program synthesis | ~1950 | Synthesis work using bidirectional typing |
| **10 HISTORICAL NOTES** | ~2000 | Prehistory and evolution |
| **11 SUMMARY OF BIDIRECTIONAL TYPING NOTATION** | 2009 | Notation reference |
| **12 CONCLUSION** | 2022 | Summary and future directions |

---

## Key Figures

| Figure | Line | Contents |
|--------|------|----------|
| Fig. 1 | 171 | Simply typed λ-calculus vs bidirectional version |
| Fig. 2 | ~283 | Bidirectional rules for STLC |
| Fig. 3 | ~360 | Design criteria illustration |
| Fig. 4 | ~438 | Recipe steps for introduction/elimination |
| Fig. 5 | ~500 | Product/sum rules |
| Fig. 6 | ~600 | Subsumption rules |
| Fig. 7 | ~700 | Higher-rank bidirectional system |
| Fig. 8 | ~900 | Polymorphic bidirectional rules |

---

## Pattern Matching Content

| Topic | Line | Description |
|-------|------|-------------|
| Pattern-matching term (case) | 498 | `case(e, inj1 x1 . e1, inj2 x2 . e2)` |
| Pattern matching for pairs/unit | 1406 | `let () = e in e` style elimination |
| Pattern-style lambda | 1834-1847 | `λpi → ti` checking at type P → N |
| Pattern judgment `p : P ; Δ` | 1847-1862 | Pattern typing for bindings |
| Unit pattern `()` | 1850 | Yields no variables |
| Pair pattern `(p1, p2)` | 1854 | Returns variables of components |
| Injection pattern `inji p` | 1861 | Returns sub-pattern variables |
| Thunk pattern `{x}` | 1856,1865 | At type ↓N returns x at N |
| Complete pattern matching | 1866 | Omitted judgment (see Krishnaswami 2009) |
| ML-style pattern matching | 1880-1891 | Focused calculus proof terms |
| GADTs and pattern matching | 1889 | Dunfield & Krishnaswami 2019 system |

---

## Key Concepts and Where to Find Them

| Concept | Section | Line | Description |
|---------|---------|------|-------------|
| **Synthesis (⇒)** | 2 | 159-161 | Type as output |
| **Checking (⇐)** | 2 | 159-161 | Type as input |
| **Mode correctness** | 3.1 | 228 | Outputs not guessed |
| **Annotatability** | 3.2 | 247 | Completeness w/ annotations |
| **Subformula property** | 3.3 | 259 | Finding types from context |
| **Pfenning recipe** | 4 | 418 | Design methodology |
| **Principal judgment** | 4.1 | 441 | Connective in conclusion/premise |
| **Introduction → checking** | 4.1 | 457 | Recipe step 2 |
| **Elimination → synthesis** | 4.1 | 458 | Recipe step 2 |
| **Higher-rank types** | 5.2 | 1023-1230 | Rank-N polymorphism |
| **Greedy instantiation** | 5.2.1 | 1048 | ∀-elimination by guessing |
| **Ordered contexts** | 5.2.3 | 1173 | Information gain ordering |
| **GADTs** | 5.3 | 1244-1257 | Non-uniform polymorphism |
| **Focusing/polarity** | 7.1 | 1560+ | Proof theory connection |
| **CBPV** | 7.2 | 1699+ | Call-by-push-value |
| **Spine judgment** | 8.3 | 1808 | Managing argument lists |
| **Pattern typing** | 8.3.3 | 1847 | `p : P ; Δ` judgment |

---

## Comparison with Other Papers

| Aspect | Dunfield 2022 | Putting 2007 |
|--------|---------------|--------------|
| **Type** | Survey article | Research paper |
| **Focus** | Bidirectional typing methodology | Higher-rank inference |
| **Pattern matching** | Surveyed broadly | Section 7+8 detailed |
| **GADTs** | Referenced | Not covered |
| **Implementation** | Not focus | Full algorithm given |

---

## Quick Topic Reference

| Topic | Where to find |
|-------|---------------|
| Recipe for bidirectional rules | Lines 418-437, 438-500 |
| Sum type elimination | Lines 498-520 |
| Subsumption | Lines 784-800 |
| Higher-rank inference | Lines 1023-1230 |
| Context extension (−→) | Lines 1183-1192 |
| Backwards bidirectional | Lines 1362-1523 |
| Focusing connection | Lines 1524-1699 |
| Pattern matching formalization | Lines 1834-1891 |
| Historical notes (folklore) | Lines 2000-2008 |

---

## Relationship to Other Papers in Collection

| Paper | Relationship |
|-------|--------------|
| **Putting 2007** | Uses bidirectional framework from Dunfield 2022 survey; implements higher-rank inference |
| **Vytiniotis 2011** | Uses bidirectional ideas; extends to GADTs with local constraints |
| **Fan et al. 2025** | Builds on higher-rank bidirectional inference |
| **Carnier 2024** | Verified bidirectional type inference with elaboration |
| **Lower Your Guards 2020** | Pattern match coverage checking (separate from bidirectional typing) |

(End of file - total lines: 2282)