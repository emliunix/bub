# ReaderEnv Architecture — Validation Report

**Validated against:** `/home/liu/Documents/bub/upstream/ghc/` source
**Date:** 2026-03-30
**Method:** Every cited source file + line number read directly; code snippets compared character-by-character; logical claims checked against the actual code semantics.

## Summary

| Claim | Status | Source | Logic |
|-------|--------|--------|-------|
| 1  | VALIDATED | Exact match | Sound |
| 2  | PARTIAL | Data decl at 433-434, not 415-428 | Sound |
| 3  | VALIDATED | Exact match | Sound |
| 4  | VALIDATED | Exact match (comments stripped) | Sound |
| 5  | VALIDATED | Exact match | Sound |
| 6  | VALIDATED | Exact match | Sound |
| 7  | PARTIAL | Exact match, but ambiguity error is in caller | Minor imprecision |
| 8  | VALIDATED | Exact match | Sound |
| 9  | VALIDATED | Match (added comment not in source) | Sound |
| 10 | VALIDATED | Paraphrased with `...` | Sound |
| 11 | VALIDATED | Minor comment text diff | Sound |
| 12 | VALIDATED | Paraphrased with `...` | Sound |
| 13 | VALIDATED | Same source as Claim 8 | Sound (deductive) |
| 14 | VALIDATED | Exact match | Sound |
| 15 | VALIDATED | Exact match | Sound |

**Contradictions between claims:** None found.

---

## Per-Claim Validation

### Claim 1: Two-Tier Lookup (LocalRdrEnv then GlobalRdrEnv)
- **VALIDATED:** Yes
- **Source Check:** Verified — code at `Env.hs:1327-1338` matches exactly (one inline comment omitted: `-- Elements in the LocalRdrEnv are always Vanilla GREs` at line 1335).
- **Logic Check:** Sound. `msum` with `map MaybeT` tries `lookupLocalOccRn_maybe` first; if it returns `Just`, `msum` short-circuits and the global lookup is never attempted. If local returns `Nothing`, the `MaybeT` wrapper propagates `Nothing` and `msum` falls through to `globalLookup`.
- **Notes:** The exploration snippet is missing the comment on line 1335. Functionally identical.

---

### Claim 2: LocalRdrEnv Contains Only Lexical Bindings
- **VALIDATED:** Partial
- **Source Check:** The Note `[LocalRdrEnv]` is at `Reader.hs:415-428` ✓. The comment text in the exploration is **paraphrased** — it omits the External name hack mention (`"...but (hackily) it can be External too for top-level pattern bindings"`) and the `lre_in_scope` explanation. The `data LocalRdrEnv` declaration is at **lines 433-434**, outside the cited range of 415-428.
- **Logic Check:** Sound. The Note confirms local bindings only. The claim about "Data constructors, type constructors, and imports are NOT in LocalRdrEnv" is a correct inference but not directly stated in the cited lines — it follows from what IS stored (local bindings) and the separate existence of GlobalRdrEnv.
- **Notes:** Correct line range for the data decl is 433-434. The paraphrase drops important nuance about External names in LocalRdrEnv.

---

### Claim 3: GlobalRdrEnv = OccEnv [GlobalRdrElt]
- **VALIDATED:** Yes
- **Source Check:** Verified — `Reader.hs:527` has `type GlobalRdrEnv = GlobalRdrEnvX GREInfo`, and `Reader.hs:556` has `type GlobalRdrEnvX info = OccEnv [GlobalRdrEltX info]`. Code matches exactly.
- **Logic Check:** Sound. INVARIANT 1 (line 537-538) explicitly states "All the members of the list have distinct 'gre_name' fields; that is, no duplicate Names", confirming the claim that multiple GREs per OccName = different Names, not different provenance.
- **Notes:** None.

---

### Claim 4: GRE Has Five Fields
- **VALIDATED:** Yes
- **Source Check:** Verified — `Reader.hs:577-591`. The data declaration has exactly the five fields listed: `gre_name`, `gre_par`, `gre_lcl`, `gre_imp`, `gre_info`. Exploration omits inline comments but the code is structurally identical.
- **Logic Check:** Sound. `IfGlobalRdrEnv = GlobalRdrEnvX ()` at line 551 confirms the `info` param can be forced to `()`.
- **Notes:** None.

---

### Claim 5: Bag Is O(1) Merge via TwoBags
- **VALIDATED:** Yes
- **Source Check:** Verified — `Bag.hs:48-87`. The `data Bag` declaration (lines 48-53) and `unionBags` (lines 84-87) match exactly.
- **Logic Check:** Sound. `unionBags b1 b2 = TwoBags b1 b2` is O(1) for two non-empty bags — just allocates a constructor node. The claim about why `gre_imp` uses Bag is a design rationale inference, not directly stated in source, but logically follows.
- **Notes:** None.

---

### Claim 6: Per-OccName List vs Per-GRE Bag Are Different Tiers
- **VALIDATED:** Yes
- **Source Check:** Verified — `Reader.hs:1663-1670`. The `plusGRE` function matches exactly.
- **Logic Check:** Sound. `plusGRE` merges two GREs with the same Name by `unionBags` on their `gre_imp` fields and `||` on `gre_lcl`. The list-level `insertGRE` (lines 1655-1661) calls `plusGRE` when Names match, otherwise extends the list — confirming the two-tier distinction.
- **Notes:** None.

---

### Claim 7: Lookup Dispatches on List Length
- **VALIDATED:** Partial
- **Source Check:** Verified — `GreLookupResult` at `Env.hs:1719-1721` and `lookupGreRn_helper` at `Env.hs:1767-1776` both match. The exploration snippet omits the comment `-- Don't record usage for ambiguous names -- until we know which is meant` between the `[gre]` and `(gre:others)` cases.
- **Logic Check:** Minor imprecision. The claim says `lookupGreRn_helper` returns "MultipleNames (ambiguity error + pick head for recovery)". In reality, `lookupGreRn_helper` **does not emit an ambiguity error** — it merely returns `MultipleNames`. The error is emitted by the **caller** `lookupGreRn_maybe` (lines 1734-1737): `addNameClashErrRn rdr_name gres`. The "pick head for recovery" is also in the caller: `return $ Just (NE.head gres)`.
- **Notes:** The ambiguity error behavior is correct but attributed to the wrong function. It's in `lookupGreRn_maybe`, not `lookupGreRn_helper`.

---

### Claim 8: Bag Filtering Drives Qualified/Unqualified Resolution
- **VALIDATED:** Yes
- **Source Check:** Verified — `Reader.hs:1576-1607` and `Reader.hs:2145-2151` all match. `pickGREs` dispatches on `Unqual`/`Qual`. `pickUnqualGRE` uses `filterBag unQualSpecOK`. `pickQualGRE` uses `filterBag (qualSpecOK mod)`. `unQualSpecOK` and `qualSpecOK` at lines 2145-2151 match.
- **Logic Check:** Sound. The claim accurately describes the filtering pipeline. The description is slightly simplified (says "filterBag unQualSpecOK" for Unqual, but actually it's `mapMaybe pickUnqualGRE` which internally does `filterBag unQualSpecOK`), but this is a fair summary.
- **Notes:** None.

---

### Claim 9: gre_lcl Needed Because Local Defs Have Empty Bag
- **VALIDATED:** Yes
- **Source Check:** Verified — `Reader.hs:1589-1602`. The `pickUnqualGRE` code matches. The exploration adds the inline comment `-- both channels empty = not in scope` which is NOT in the source (the source has no comment on that guard).
- **Logic Check:** Sound. If `gre_lcl` were removed, a locally-defined name with `gre_imp = emptyBag` would satisfy `not lcl && null iss'` and be discarded — it would be invisible. The `gre_lcl` flag is the "local definition" channel that survives even when the import bag is empty.
- **Notes:** The comment `-- both channels empty = not in scope` is editorial, not from source.

---

### Claim 10: ImportSpec Is Two-Layer (Shared Decl + Per-Item)
- **VALIDATED:** Yes
- **Source Check:** Verified — `Reader.hs:1982-2051`. `ImportSpec` at 1982-1983, `ImpDeclSpec` at 1993-2007, `ImpItemSpec` at 2036-2051. Exploration uses `...` to abbreviate `ImpDeclSpec` (which has 7 fields: `is_mod`, `is_as`, `is_pkg_qual`, `is_qual`, `is_dloc`, `is_isboot`, `is_level`).
- **Logic Check:** Sound. The two-layer structure is explicit: `ImpSpec { is_decl :: !ImpDeclSpec, is_item :: !ImpItemSpec }`.
- **Notes:** `ImpDeclSpec` has 7 fields, not just the 4 shown. The exploration's `...` is acceptable paraphrasing.

---

### Claim 11: shadowNames Converts Older GREs to Qualified-Only
- **VALIDATED:** Yes
- **Source Check:** Verified — `Reader.hs:1778-1847`. The `shadow` function (lines 1817-1832), `mk_fake_imp_spec` (1834-1844), and `set_qual` (1846-1847) all match. Minor comment text differences: source says "Old name is Internal; do not shadow" vs exploration's "Internal names: do not shadow"; source has `-- Nothing remains` on a separate line vs exploration inline.
- **Logic Check:** Sound. All three claimed behaviors are confirmed:
  1. `gre_lcl = False` — line 1827 ✓
  2. `set_qual` sets `is_qual = True` — line 1847 ✓
  3. `mk_fake_imp_spec` creates a fake ImportSpec for local GREs with `is_qual = True` and `is_as = old_mod_name` — lines 1834-1844 ✓
- **Notes:** None.

---

### Claim 12: REPL Uses shadowNames on Interactive Env Then Merges with Import Env
- **VALIDATED:** Yes
- **Source Check:** Verified — `Context.hs:459-481`. `replaceImportEnv` at 459-463 matches exactly. `icExtendGblRdrEnv` at 467-481 is **paraphrased** — the exploration omits the `is_sub_bndr` guard and the `foldl' extendGlobalRdrEnv` step, using `...` instead. But the core `foldr add env tythings` and `shadowNames` usage are correct.
- **Logic Check:** Sound. `replaceImportEnv`: (1) shadows import_env with prompt_env, (2) merges result with prompt_env. `icExtendGblRdrEnv`: uses `foldr` so front-of-list shadows back, and calls `shadowNames` for each new TyThing.
- **Notes:** The `foldr` comment "foldr: front shadows back" is editorial but correct — the source comment says "Foldr makes things in the front of the list shadow things at the back".

---

### Claim 13: After shadowNames, Lookup Order Doesn't Matter
- **VALIDATED:** Yes
- **Source Check:** Same citation as Claim 8 (`Reader.hs:1576-1607`). The source shows `pickGREs` using `mapMaybe` which processes each GRE independently — confirmed.
- **Logic Check:** Sound (deductive). After `shadowNames`, each GRE is self-contained: its `gre_imp` bag reflects its own import provenance, and `gre_lcl` is either True (new) or False (shadowed). `pickGREs` filters each GRE independently via `mapMaybe`. If multiple GREs survive filtering, they have genuinely different Names → real ambiguity. The claim about list order mattering only for `shadowNames` itself is correct — `shadowNames` processes the new GREs as a set and the old GREs individually.
- **Notes:** This is a logical deduction, not directly stated in source. The reasoning holds.

---

### Claim 14: RdrName Has Four Constructors
- **VALIDATED:** Yes
- **Source Check:** Verified — `Reader.hs:173-210`. The four constructors `Unqual`, `Qual`, `Orig`, `Exact` match exactly with their field types.
- **Logic Check:** Sound. The descriptions of each constructor match the source comments: `Unqual` = unqualified, `Qual` = user-written qualified (module is import source, not defining module), `Orig` = compiler-generated pinned to defining module, `Exact` = already resolved (built-in syntax, TH). The `deriving Data` at line 210 confirms the declaration boundary.
- **Notes:** The elab3 design opinion ("only Unqual and Qual needed") is a design claim, not a factual validation target.

---

### Claim 15: OccName = NameSpace + FastString
- **VALIDATED:** Yes
- **Source Check:** Verified — `Occurrence.hs:366-372`. The `data OccName` declaration at 366-369 and the `Eq` instance at 371-372 match exactly.
- **Logic Check:** Sound. Equality checks both `s1 == s2` (FastString) and `sp1 == sp2` (NameSpace). The elab3 simplification claim is a design opinion.
- **Notes:** None.

---

## Cross-Claim Consistency

No contradictions found between claims:

- **Claims 1 & 7** (lookup ordering): Claim 1 describes the two-tier dispatch. Claim 7 describes the global tier's result handling. Consistent.
- **Claims 3 & 6** (list vs bag): Claim 3 says the list holds different Names. Claim 6 shows `plusGRE` merges same-Name GREs via bag union. Consistent — `insertGRE` (1655-1661) is the bridge: it calls `plusGRE` when Names match, otherwise extends the list.
- **Claims 8 & 9** (pickUnqualGRE): Both describe the same function from different angles. Consistent.
- **Claims 9 & 11** (gre_lcl semantics): Claim 9 says `gre_lcl` is needed because local defs have empty bags. Claim 11 shows `shadowNames` sets `gre_lcl = False`. After shadowing, the formerly-local GRE survives via its fake qualified ImportSpec, not via `gre_lcl`. Consistent — the two channels (`gre_lcl` and `gre_imp`) serve different purposes, and `shadowNames` converts from one to the other.
- **Claims 12 & 11** (REPL shadowing): Claim 12 shows `replaceImportEnv` calling `shadowNames`. Claim 11 shows what `shadowNames` does. Consistent.
