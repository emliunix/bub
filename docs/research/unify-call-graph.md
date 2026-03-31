# Every Path to `unify` - Complete Call Graph

## Mermaid Graph

```mermaid
flowchart TD
    %% Leaf node
    UNIFY["`**unify**`"]
    
    %% Level 1: Direct callers
    MONO["`subsCheckRho (MONO rule)`"]
    UNIFY_VAR["`unifyVar`"]
    UNIFY_UNBOUND["`unifyUnboundVar`"]
    UNIFY_FUN["`unifyFun`"]
    
    UNIFY <-- chain following --> UNIFY_VAR
    UNIFY <-- alias chains --> UNIFY_UNBOUND
    UNIFY <-- decompose Fun --> UNIFY
    
    %% Level 2: Subsumption
    SUBS_CHECK_RHO["`subsCheckRho`"]
    SUBS_CHECK["`subsCheck (DEEP-SKOL)`"]
    SUBS_CHECK_FUN["`subsCheckFun (FUN rule)`"]
    
    MONO --> SUBS_CHECK_RHO
    UNIFY_FUN --> MONO
    SUBS_CHECK_FUN --> SUBS_CHECK
    SUBS_CHECK_FUN --> SUBS_CHECK_RHO
    SUBS_CHECK --> SUBS_CHECK_RHO
    
    %% Level 3: Instantiation
    INST_SIGMA["`instSigma`"]
    INST2["`INST2 (Check mode)`"]
    
    INST_SIGMA --> INST2
    INST2 --> SUBS_CHECK_RHO
    
    %% Level 4: Type checking rules (tcRho)
    TC_RHO["`tcRho`"]
    INT["`INT rule`"]
    VAR["`VAR rule`"]
    APP["`APP rule`"]
    ABS2["`ABS2 rule`"]
    AABS2["`AABS2 rule`"]
    ANNOT["`ANNOT rule`"]
    
    TC_RHO --> INT
    TC_RHO --> VAR
    TC_RHO --> APP
    TC_RHO --> ABS2
    TC_RHO --> AABS2
    TC_RHO --> ANNOT
    
    INT --> INST_SIGMA
    VAR --> INST_SIGMA
    ANNOT --> INST_SIGMA
    
    APP --> UNIFY_FUN
    APP --> INST_SIGMA
    
    ABS2 --> UNIFY_FUN
    
    AABS2 --> UNIFY_FUN
    AABS2 --> SUBS_CHECK
    
    %% Level 5: Entry points
    INFER_RHO["`inferRho`"]
    CHECK_RHO["`checkRho`"]
    TYPECHECK["`typecheck`"]
    
    TYPECHECK --> INFER_SIGMA
    INFER_SIGMA --> INFER_RHO
    
    INFER_RHO --> TC_RHO
    CHECK_RHO --> TC_RHO
    
    %% Special: LET rule
    LET["`LET rule`"]
    INFER_SIGMA["`inferSigma (GEN1)`"]
    
    TC_RHO --> LET
    LET --> INFER_SIGMA
    INFER_SIGMA --> INFER_RHO
    
    %% Styling
    classDef leaf fill:#ff6b6b,stroke:#333,stroke-width:3px,color:#fff
    classDef rule fill:#4ecdc4,stroke:#333,stroke-width:2px
    classDef entry fill:#ffe66d,stroke:#333,stroke-width:2px
    
    class UNIFY leaf
    class INT,VAR,APP,ABS2,AABS2,ANNOT,LET rule
    class TYPECHECK,INFER_RHO,CHECK_RHO entry
```

## Alternative: Rules-First View

```mermaid
flowchart TB
    subgraph "Type Checking Rules"
        INT["`INT`"]
        VAR["`VAR`"]
        APP["`APP`"]
        ABS1["`ABS1`"]
        ABS2["`ABS2`"]
        AABS2["`AABS2`"]
        ANNOT["`ANNOT`"]
        LET["`LET`"]
    end
    
    subgraph "Instantiation"
        INST1["`INST1 (Inference)`"]
        INST2["`INST2 (Checking)`"]
    end
    
    subgraph "Subsumption"
        DEEPSKOL["`DEEP-SKOL`"]
        SPEC["`SPEC`"]
        FUN["`FUN`"]
        MONO["`MONO`"]
    end
    
    subgraph "Unification"
        UNIFYFUN["`unifyFun`"]
        UNIFYVAR["`unifyVar`"]
        UNIFYUNBOUND["`unifyUnboundVar`"]
        UNIFY["`**unify**`"]
    end

    subgraph "Meta Variable Creation"
        INSTANTIATE["`instantiate
        N metas per ∀`"]
        NEWTYVARTY["`**newTyVarTy**`"]
    end
    
    %% INT, VAR, ANNOT -> INST2 -> MONO
    INT --> INST2
    VAR --> INST2
    ANNOT --> INST2
    
    %% APP branches
    APP --> INST2
    APP --> UNIFYFUN
    
    %% ABS1 creates a fresh meta directly
    ABS1 --> NEWTYVARTY
    
    %% ABS2 only uses unifyFun
    ABS2 --> UNIFYFUN
    
    %% AABS2 branches
    AABS2 --> UNIFYFUN
    AABS2 --> DEEPSKOL
    
    %% INST2 path
    INST2 --> MONO
    
    %% DEEP-SKOL paths
    DEEPSKOL --> SPEC
    DEEPSKOL --> FUN
    DEEPSKOL --> MONO
    
    %% FUN recursion
    FUN --> UNIFYFUN
    FUN --> DEEPSKOL
    
    %% SPEC and INST1 instantiate ∀-bound vars
    SPEC --> INSTANTIATE
    INST1 --> INSTANTIATE
    INSTANTIATE --> NEWTYVARTY
    
    %% unifyFun creates demand metas (non-Fun case)
    UNIFYFUN --> NEWTYVARTY
    
    %% To unify
    UNIFYFUN --> UNIFY
    MONO --> UNIFY
    
    %% Internal unify recursion
    UNIFY --> UNIFYVAR
    UNIFY --> UNIFYUNBOUND
    UNIFYVAR --> UNIFY
    UNIFYUNBOUND --> UNIFY
```

## Path Summary Table

| Rule | Path to `unify` | Paper Rules |
|------|----------------|-------------|
| **INT** | INT → INST2 → MONO → **unify** | Direct mono unification |
| **VAR** | VAR → INST2 → MONO → **unify** | Direct mono unification |
| **APP** | APP → UNIFYFUN → **unify** | Function decomposition |
| **APP (result)** | APP → INST2 → MONO → **unify** | Result instantiation |
| **ABS2** | ABS2 → UNIFYFUN → **unify** | Expected arrow decomposition |
| **AABS2 (arrow)** | AABS2 → UNIFYFUN → **unify** | Expected arrow decomposition |
| **AABS2 (subsumption)** | AABS2 → DEEP-SKOL → MONO → **unify** | Annotation subsumption |
| **ANNOT** | ANNOT → INST2 → MONO → **unify** | Annotation instantiation |
| **FUN (contra)** | FUN → DEEP-SKOL → MONO → **unify** | Contravariant arg check |
| **FUN (co)** | FUN → MONO → **unify** | Covariant result check |
| **SPEC** | SPEC → INST1 → ... → MONO → **unify** | Instantiate outer foralls |

## Key Patterns

### Pattern 1: Direct Unification (INT, VAR, ANNOT)
```
Rule → INST2 → MONO → unify
```
Simple type instantiation followed by mono unification.

### Pattern 2: Function Decomposition (APP, ABS2)
```
Rule → UNIFYFUN → unify
```
Creates/extracts function components via unification.

### Pattern 3: Subsumption Checking (AABS2, FUN)
```
Rule → DEEP-SKOL → (SPEC/FUN/MONO) → unify
```
Full subsumption with skolemization and recursive checking.

### Pattern 4: Polymorphic Instantiation (SPEC)
```
SPEC → INST1 → ... → MONO → unify
```
Instantiates foralls and recurses.

---

## Every Path to `newTyVarTy` - Meta Variable Creation

Fresh meta type variables are the "unknowns" that unification solves.
There are exactly **3 creation points** in the implementation, reached
through different paths. These are shown in the Rules-First View above
(the "Meta Variable Creation" subgroup).

### Creation Points

| # | Function | What it creates | Line |
|---|----------|----------------|------|
| 1 | `unifyFun` (non-Fun case) | 2 metas: `arg_ty`, `res_ty` | L329-330 |
| 2 | `ABS1` rule in `tcRho` | 1 meta: `var_ty` for λ parameter | L464 |
| 3 | `instantiate` | N metas: one per ∀-bound variable | L197 |

### Path Summary Table

| Rule | Path to `newTyVarTy` / `newMetaTyVar` | What gets created |
|------|---------------------------------------|-------------------|
| **APP** | APP → unifyFun → **newTyVarTy** ×2 | arg/res metas for inferred function |
| **ABS2** | ABS2 → unifyFun → **newTyVarTy** ×2 | arg/res metas when expected type isn't Fun |
| **AABS2 (arrow)** | AABS2 → unifyFun → **newTyVarTy** ×2 | arg/res metas when expected type isn't Fun |
| **ABS1** | ABS1 → **newTyVarTy** ×1 | mono meta for unannotated λ parameter |
| **INT (infer)** | INT → INST1 → instantiate → **newMetaTyVar** ×N | metas replacing ∀-bound vars (N=0 for Int) |
| **VAR (infer)** | VAR → INST1 → instantiate → **newMetaTyVar** ×N | metas replacing ∀-bound vars in σ |
| **ANNOT (infer)** | ANNOT → INST1 → instantiate → **newMetaTyVar** ×N | metas replacing ∀-bound vars in annotation |
| **APP (result, infer)** | APP → INST1 → instantiate → **newMetaTyVar** ×N | metas for result type's ∀ vars |
| **SPEC** | SPEC → instantiate → **newMetaTyVar** ×N | metas replacing outer ∀ in subsumption |
| **FUN (lhs/rhs)** | FUN → unifyFun → **newTyVarTy** ×2 | arg/res metas when one side isn't Fun |

### Creation Semantics

**`newTyVarTy`** (via `unifyFun`, `ABS1`): Creates a fresh `MetaTv` wrapped in a
`MetaTv` type constructor. The IORef starts as `Nothing` (unsolved). These are
"demand" metas — created because the algorithm needs an arrow type but doesn't
have one yet.

**`newMetaTyVar`** (via `instantiate`): Creates a fresh `MetaTv` directly.
These are "instantiation" metas — created to replace ∀-bound variables so
the polymorphic type can participate in unification.

Both end up as `Meta Uniq (IORef (Maybe Tau))` — the distinction is purely
about *why* the meta was created:

| Kind | Created by | Purpose | Example |
|------|-----------|---------|---------|
| **Demand** | `unifyFun`, `ABS1` | Force structure to exist | `_a` in `_a → _b` when checking `f x` |
| **Instantiation** | `instantiate` | Replace ∀-bound var | `_a` in `_a → _a` from `∀a. a → a` |

Both kinds are solved by `unify` (via `writeTv`) and generalized by `quantify`
(GEN1: `ftv(ρ) - ftv(Γ)`) if they survive unconstrained by the environment.