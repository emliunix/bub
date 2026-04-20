# Lower Your Guards 2020 - Paper Text Index (Line Numbers)

**Paper**: "Lower Your Guards: A Compositional Pattern-Match Coverage Checker"
**Authors**: Sebastian Graf, Simon Peyton Jones, Ryan G. Scott (2020)
**Source**: `lower-your-guards-2020.txt`

---

## How to use this index

```bash
# Jump to a specific section
sed -n '32,225p' lower-your-guards-2020.txt       # Read Section 1 (Introduction)
sed -n '960,1467p' lower-your-guards-2020.txt      # Read Section 3 (Core algorithm)
grep -n "guard tree" lower-your-guards-2020.txt    # Search within sections
```

**Note**: The PDF extraction contains interspersed page numbers and header noise. Content lines are interleaved with numeric-only lines.

---

## Main Sections

| Section | Line | Description |
|---------|------|-------------|
| Title/Abstract | 1 | Paper title, authors, abstract |
| **1 Introduction** | 50 | Motivating examples, coverage checking overview |
| **2 Key challenges** | 215 | Language features that complicate coverage checking |
| 2.1 Guards | 225 | Pattern guards and boolean guards |
| 2.2 View patterns and pattern synonyms | 326 | Arbitrary computation in patterns |
| 2.2.1 View patterns | 333 | View pattern desugaring |
| 2.2.2 Pattern synonyms | 389 | Abstracting over patterns |
| 2.3 Strictness | 434 | Strict fields, bang patterns, exhaustiveness |
| 2.3.1 Redundancy vs inaccessibility | 498 | Distinguishing unreachable cases |
| 2.3.2 Bang patterns | 530 | Strictness in pattern matching |
| 2.4 Type-equality constraints | 566 | GADTs and equality constraints |
| **3 The algorithm** | 960 | Core LYG algorithm |
| 3.1 Desugarring to guard trees | 975 | Source language → guard trees |
| 3.2 Coverage checking | 1308 | U and A functions over guard trees |
| 3.3 Reporting errors | 1422 | Missing equations and error reporting |
| 3.4 Generating inhabitants | 1667 | G function for refinement types |
| 3.5 Expanding ∇ to pattern | 1760 | E function for presenting uncovered patterns |
| 3.6 Normalisation | 1998 | C function, ⊕φ and ⊕δ (core constraint solving) |
| 3.7 Testing for inhabitation | 2071 | ⊢Inst and ⊢NoCpl judgements |
| **4 Extensions** | 2230 | Handling additional language features |
| 4.1 Long-distance information | 2238 | Nested case, cross-equation info |
| 4.2 Term equalities | 2283 | Reasoning about x == y |
| 4.3 Let bindings | 2325 | Flattening constructor applications |
| 4.4 Negative constraints | 2394 | Efficient representation of uncovered sets |
| 4.5 COMPLETE pragmas | 2526 | User-specified complete sets |
| 4.6 Other extensions | 2608 | Overloaded literals, newtypes, strict-by-default |
| **5 Implementation** | 2653 | Practical considerations |
| 5.1 Interleaving U and A | 2653 | Combining uncovered and annotated sets |
| 5.2 Throttling for graceful degradation | 2677 | NP-hard cases, conservative approximation |
| 5.3 Maintaining residual COMPLETE sets | 2874 | Efficient inhabitation testing |
| 5.4 Better pattern pretty-printing | 2938 | Improving warning messages |
| 5.5 head.hackage evaluation | ~3000 | Real-world testing on 361 libraries |
| **6 Evaluation** | 2962 | Performance benchmarks vs GHC 8.8.3 |
| **7 Related work** | 3214 | Comparison with GMTM and other approaches |
| 7.1 Comparison with GADTs Meet Their Match | 3215 | GMTM limitations |
| 7.1.1 Laziness | 3233 | GMTM doesn't consider laziness fully |
| 7.1.2 Shallow guard treatment | 3239 | GMTM's limited guard reasoning |
| 7.2 Other related work | 3301 | Maranget, Cockx & Abel, etc. |
| **8 Conclusion** | ~3544 | Summary and future work |

---

## Figures

| Figure | Line | Description |
|--------|------|-------------|
| Fig. 1 | 615 | Source syntax |
| Fig. 2 | 744 | Bird's eye view of pattern match checking |
| Fig. 3 | 901 | IR syntax (intermediate representation) |
| Fig. 4 | 1151 | Desugarring from source language to Gdt |
| Fig. 5 | 1272 | Coverage checking (U and A functions) |
| Fig. 6 | 1651 | Generating inhabitants via ∇ |
| Fig. 7 | 1988 | Adding constraint to normalised refinement type (∇ ⊕φ) |
| Fig. 8 | 2185 | Testing for inhabitation |
| Fig. 9 | 2762 | Fast coverage checking |
| Fig. 10 | 3079 | Compile-time performance comparison (GHC 8.8.3 vs HEAD) |

---

## Key Definitions

| Term | Line | Description |
|------|------|-------------|
| Guard trees | 960 | Core IR: only 3 constructs (GRHS, Guard, concatenation) |
| Refinement types Θ | 1308 | ⟨ x₁:τ₁, ..., xₙ:τₙ \| Φ ⟩ |
| Uncovered set U | 1272 | Values not covered by the match |
| Annotated tree A | 1243 | Redundancy/inaccessibility annotations |
| Normalised refinement type ∇ | 1651 | Compact canonical form of Θ |
| Inhabitation test ⊢Inst | 2185 | Is the refinement type inhabited? |
| ⊕φ (add constraint) | 1998 | Core constraint solving operation |
| ⊕δ (prime unification) | ~2100 | Unification of constructor constraints |
| COMPLETE pragmas | 2526 | User-specified sets of complete constructors |

---

## Important Examples

| Example | Line | Description |
|---------|------|-------------|
| f 0 = True; f 0 = False | 64 | Redundant + non-exhaustive |
| Guards demo | 225 | Pattern guards and boolean guards |
| GADT examples | 566 | Type-equality constraints |
| v : Maybe Void → Int | ~3450 | Strictness in inhabitation testing |
| h A1 = 1; h A1 = 2 | ~3400 | Negative constraints for efficiency |
