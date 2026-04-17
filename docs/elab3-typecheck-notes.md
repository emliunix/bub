# elab3 Typechecker Architecture Notes

**Status:** **⚠️ WIP - INCOMPLETE**  
**Last Updated:** 2026-04-10  
**Central Question:** Understanding elab3 bidirectional type inference and its correspondence to GHC's type inference algorithm (2007 paper implementation)

> **⚠️ IMPORTANT:** The elab3 implementation is **WIP/Incomplete** and should **NOT** be used as a reference for implementation. Use **GHC upstream** as the authoritative source instead.

> **📁 Prior Analysis:** The `upstream/ghc/analysis/` folder contains records of prior exploration results. These were created using the **exploration skill** and should be checked before new code exploration. For new findings, follow the same evidence-based, claim-attributed principles.

> **🔍 GHC Type Hierarchy:** See [`upstream/ghc/analysis/GHC_TYPE_HIERARCHY.md`](../upstream/ghc/analysis/GHC_TYPE_HIERARCHY.md) for detailed documentation of GHC's Var, TcTyVar, TyVar, MetaTv, and SkolemTv relationships.

---

## Thinking Model: Tiered Analysis Framework

> **Skill Reference:** See [`.agents/skills/topic-thinking/TIERED_ANALYSIS_FRAMEWORK.md`](../.agents/skills/topic-thinking/TIERED_ANALYSIS_FRAMEWORK.md) for the complete thinking model.

**This document applies the Tiered Analysis Framework with the following base dimensions:**

| Dimension | Description | Key Invariant |
|-----------|-------------|---------------|
| **LEVELS** | TcLevel tracking (N, N+1, N+2) | Metas only unify at creation level |
| **EXPECT** | Check vs Infer mode dispatch | Check=skolems, Infer=metas |
| **CLOSURE** | CPS pattern with thing_inside | Brackets compose sequentially |
| **META/SKOLEM** | Variable classification | Metas unify, skolems rigid |

**Application to GHC Type Inference:** All function analyses in this document follow the 3-tier structure (Base → Main → Detailed) with cross-tier validation.

1. **tcInstSig creates TyVarTvs (metas!), NOT skolems**
   - Base theme violation if called skolems
   - Evidence: `newMetaTyVarTyVarX` in TcMType.hs:995

2. **matchExpectedFunTys behavior differs by Expect mode**
   - Infer mode: creates TauTv metas
   - Check mode: may create SkolemTvs via skolemiseRequired
   - Evidence: Unify.hs:809 vs 835

3. **NoGen is INFER mode without generalization**
   - Creates metas like InferGen
   - But does NOT call simplifyInfer/quantifyTyVars
   - Result remains monomorphic

---

## Table of Contents

1. [Overview](#overview)
2. [Key Types and Data Structures](#key-types)
3. [Bidirectional Type Inference Model](#bidirectional)
4. [TcLevel and Scope Management](#tclevel)
5. [Meta/Skolem Duality and Bidirectional Modes](#duality)
6. [Meta Variable Lifecycle](#meta-lifecycle)
7. [Core Algorithm Components](#algorithm-components)
8. [GHC Correspondence](#ghc-correspondence)
9. [Source Reference Index](#source-reference)
10. [Thinking Model](#thinking-model)

---

## Overview

**elab3** is a GHC-style bidirectional type inferencer built for the systemf project. It aims to implement:

- **Bidirectional type checking**: `Check` (top-down, expected type known) and `Infer` (bottom-up, type synthesized)
- **Polymorphic let bindings** via generalization (quantification of free meta variables)
- **Type application/instantiation** for higher-rank types
- **Pattern matching** with proper type coordination across branches

**Implementation Source (GHC):**
- GHC's type inference system (particularly `GHC/Tc/Gen/*`)
- "Putting 2007" paper implementation rules

**This Document** is for understanding the architecture and mapping between GHC and elab3. elab3 is **incomplete** - use GHC as the authoritative implementation source.

---

## Quick Reference

| Concept | Direction | Use | Evidence |
|---------|-----------|-----|----------|
| **Check** mode | Outside-in (top-down) | Verify term against known type | Creates Skolems |
| **Infer** mode | Inside-out (bottom-up) | Synthesize type from term | Creates Metas (`Ref[Ty]`) |
| **Instantiation** | `∀a.ρ → [a/?]ρ` | Function arguments | Fresh **meta** vars, `WpTyApp` |
| **Skolemisation** | `∀a.ρ → [a/sk]ρ` | Type annotations | Fresh **rigid** vars, `WpTyLam` |
| **Generalization** | `ftv(ρ) - ftv(Γ)` | Let bindings | Quantify free metas |
| **Touchability** | Meta.level == Ctx.level | Same-level unification | Prevents outer metas from inner capture |
| **Escape check** | Skolem.level > Ctx.level | Post-hoc validation | Ensures skolems don't leak |
| **Promotion** | Lift metas to outer level | Cross-level type flow | Maintains level invariant |

---

## Key Types

### elab3 Type Hierarchy

**Source**: `systemf/src/systemf/elab3/types/ty.py`

#### Type Variables

```python
# Line 125-131: BoundTv - bound type variable (local binder in forall)
@dataclass(frozen=True, repr=False)
class BoundTv(TyVar):
    name: Name

# Line 134-142: SkolemTv - rigid variable from type signature instantiation
@dataclass(frozen=True, repr=False)
class SkolemTv(TyVar):
    name: Name
    uniq: int

# Line 145-153: MetaTv - unification variable (mutable, exists during inference)
@dataclass(frozen=True, repr=False)
class MetaTv(Ty):
    uniq: int
    ref: Ref[Ty]  # Mutable cell - set when unified
```

#### Reference Cell

```python
# Line 28-37: Ref[T] - mutable reference for meta variable unification
@dataclass
class Ref(Generic[T]):
    inner: T | None = field(default=None)
    def set(self, value: T) -> None: ...
    def get(self) -> T | None: ...
```

#### Type Constructors

```python
# Line 156-167: TyConApp - type constructor application
@dataclass(frozen=True, repr=False)
class TyConApp(Ty):
    name: Name
    args: list[Ty]

# Line 170-174: TyFun - function type
@dataclass(frozen=True, repr=False)
class TyFun(Ty):
    arg: Ty
    result: Ty

# Line 177-181: TyForall - universally quantified type
@dataclass(frozen=True, repr=False)
class TyForall(Ty):
    vars: list[TyVar]
    body: Ty
```

### Expect Type (Bidirectional Mode)

**Source**: `systemf/src/systemf/elab3/typecheck_expr.py:28-38`

```python
class Expect(ABC): ...  # Line 28

@dataclass
class Infer(Expect):
    ref: Ref[Ty]  # Hole to fill with inferred type

@dataclass
class Check(Expect):
    ty: Ty  # Expected type to check against
```

This mirrors GHC's `ExpType`:

**Source**: `upstream/ghc/compiler/GHC/Tc/Utils/TcType.hs:403-427`

```haskell
-- Line 403-427
data ExpType = Check TcType      -- Expected type provided
             | Infer !InferResult  -- Hole to fill

data InferResult = IR {
    ir_uniq :: Unique,           -- Debug identifier
    ir_lvl  :: TcLevel,          -- Level for untouchable tracking
    ir_ref  :: IORef (Maybe TcType),  -- Mutable hole
    ir_inst :: InferInstFlag,     -- Instantiation control (IIF_Sigma, IIF_Rho)
    ir_frr  :: InferFRRFlag     -- Fixed RuntimeRep checking
}
```

**Key Design**: `InferResult` is a **typed hole** - a mutable cell that starts empty and gets filled during type inference. The same hole is shared across multiple branches (case alternatives, function equations) to coordinate their result types.

### fillInferResult - Hole Filling and Branch Coordination

**Source**: `upstream/ghc/compiler/GHC/Tc/Utils/Unify.hs:1122-1169`

```haskell
fillInferResultNoInst :: TcType -> InferResult -> TcM TcCoercionN
fillInferResultNoInst act_res_ty (IR { ir_ref = ref, ir_lvl = res_lvl, ... })
  = do { mb_exp_res_ty <- readTcRef ref
       ; case mb_exp_res_ty of
            Just exp_res_ty  -- HOLE ALREADY FILLED (2nd+ branch)
               -> do { traceTc "Joining inferred ExpType" ...
                     ; unifyType Nothing act_res_ty exp_res_ty }  -- UNIFY!
            Nothing          -- FIRST FILL
               -> do { (prom_co, act_res_ty) <- promoteTcType res_lvl act_res_ty
                     ; writeTcRef ref (Just act_res_ty)  -- FILL HOLE
                     ; return prom_co } }
```

**The Pattern**: When multiple branches need to coordinate types:
1. **Create one `InferResult` hole** before typechecking branches
2. **Each branch calls `fillInferResult`** with its inferred type
3. **First branch**: Fills the hole (`writeTcRef ref (Just ty)`)
4. **Subsequent branches**: Unify with existing type (`unifyType new_ty existing_ty`)

**Example** (from GHC Note):
```haskell
\ x -> case y of 
  True  -> x       -- First: fills hole with type of x
  False -> 3       -- Second: unifies type of x with Int
-- Result: hole contains unified type (Int if x used as Int)
```

This enables **branch type coordination** without explicit joins:
- Case expressions: all alternatives share the same result hole
- Function equations: all clauses share the same result hole
- If expressions: both branches share the same hole

**Promotion**: When filling from a different level (e.g., inside a GADT pattern match at level N+1, filling hole from level N), `promoteTcType` creates a fresh meta at the hole's level and emits an equality constraint.

### Wrapper (Evidence for Type Transformations)

**Source**: `systemf/src/systemf/elab3/types/wrapper.py`

```python
# Line 18-22: Wrapper base + WpHole (identity)
class Wrapper(ABC): ...
@dataclass class WpHole(Wrapper): ...
WP_HOLE = WpHole()

# Line 29-38: WpCast - type cast
@dataclass
class WpCast(Wrapper):
    ty_from: Ty
    ty_to: Ty

# Line 42-50: WpFun - function wrapper (for contravariant argument wrapping)
@dataclass
class WpFun(Wrapper):
    arg_ty: Ty
    wp_arg: Wrapper  # contravariant
    wp_res: Wrapper  # covariant

# Line 79-81: WpTyApp - type application
@dataclass
class WpTyApp(Wrapper):
    ty_arg: Ty

# Line 84-86: WpTyLam - type abstraction
@dataclass
class WpTyLam(Wrapper):
    ty_var: TyVar

# Line 95-103: WpCompose - composition
@dataclass
class WpCompose(Wrapper):
    wp_g: Wrapper  # apply f first, then g
    wp_f: Wrapper
```

This corresponds to GHC's `HsWrapper`:

**Source**: `upstream/ghc/compiler/GHC/Tc/Types/Evidence.hs`

```haskell
-- Lines around 156-167
data HsWrapper
  = WpHole                              -- Identity
  | WpCast TcCoercionR                  -- Type coercion
  | WpTyApp KindOrType                  -- Type application: e @ty
  | WpEvApp EvTerm                      -- Dictionary application
  | WpEvLam EvVar                       -- Dictionary lambda
  | WpTyLam TyVar                       -- Type lambda: /\a. e
  | WpFun SubMultCo Wp Wp TcType TcType -- Function wrapper
  | WpCompose HsWrapper HsWrapper        -- Composition
```

---

## Bidirectional Type Inference Model

### Core Principle

Each expression node is processed **exactly once** in **exactly one mode**. Mode switches occur at **parent-child boundaries**.

**Source**: `upstream/ghc/compiler/GHC/Tc/Gen/Expr.hs:290-310`

```haskell
-- tcExpr is the main dispatcher
tcExpr :: HsExpr GhcRn -> ExpRhoType -> TcM (HsExpr GhcTc)

-- Applications go through tcApp for Quick Look impredicativity
tcExpr e@(HsApp {}) res_ty = tcApp e res_ty

-- Lambdas go directly to tcLambdaMatches
tcExpr e@(HsLam {}) res_ty = tcLambdaMatches e lam_variant matches [] res_ty
```

### Two Modes

| Mode | Direction | Creates | Use Case |
|------|-----------|---------|----------|
| **Check** | Outside-in | `Check ty` | Known expected type |
| **Infer** | Inside-out | `Infer(ref)` | Unknown type, synthesize |

**Source**: `systemf/src/systemf/elab3/typecheck_expr.py:75-88`

```python
def tc_expr(self, expr: Expr, exp: Expect) -> TyCk[Defer[OUT]]:
    match expr:
        case ast.LitExpr(value):
            return self.lit(value)
        case ast.Var(name):
            return self.var(name)
        case ast.Lam(args, body):
            return self.lam(args, body)
        # ...
```

### Mode Semantics by Expression

**Lambda** (`lam` method, line 160-177):

```python
# Infer mode: create fresh meta for arg, infer body, construct function type
case Infer(ref):
    arg_ty = self.make_meta()
    body_ty, e_body = run_infer(extend_env(name, arg_ty, env), body)
    result_ty = TyFun(arg_ty, body_ty)
    ref.set(result_ty)

# Check mode: decompose function type, check body against result
case Check(ty2):
    (arg_ty, res_ty) = self.unify_fun(ty2)
    e = self.poly(body)(extend_env(name, arg_ty, env), Check(res_ty))
```

**Application** (`app` method, line 206-217):

```python
def _go(env: Env, exp: Expect) -> Defer[OUT]:
    # 1. Infer function type
    fun_ty, fun_core = run_infer(env, fun)
    # 2. Decompose to arg and result types
    (arg_ty, res_ty) = self.unify_fun(fun_ty)
    # 3. Check argument against expected arg type
    arg_core = self.poly(arg)(env, Check(arg_ty))
    # 4. Instantiate result type
    res_wrap = self.inst(res_ty)(env, exp)
    return self.with_wrapper(res_wrap, lambda: self.core.app(fun_core(), arg_core()))
```

---

## TcLevel and Scope Management

### The TcLevel Hierarchy

GHC uses a **level system** to control unification scope and prevent type variables from escaping their intended context.

```
Level 0: Module top-level (topTcLevel)
    ↓ pushLevelAndCaptureConstraints
Level 1: Implication scope (let bindings, case expressions, lambdas)
    ↓ pushLevelAndCaptureConstraints
Level 2: Nested scope
    ↓ ...
```

**Source**: `upstream/ghc/compiler/GHC/Tc/Utils/TcType.hs:870-885`

```haskell
newtype TcLevel = TcLevel Int  -- 0 = outermost

topTcLevel :: TcLevel
topTcLevel = TcLevel 0

pushTcLevel :: TcLevel -> TcLevel
pushTcLevel (TcLevel n) = TcLevel (n + 1)
```

### Bracket Pattern for Level Management

Levels are managed via **functional bracket pattern** (not mutation):

**Source**: `upstream/ghc/compiler/GHC/Tc/Utils/Monad.hs:508-524`

```haskell
pushLevelAndCaptureConstraints :: TcM a -> TcM (TcLevel, WantedConstraints, a)
pushLevelAndCaptureConstraints thing_inside
  = do { tclvl <- getTcLevel                    -- Get current level
       ; let tclvl' = pushTcLevel tclvl         -- Increment
       ; (res, lie) <- updLclEnv (setLclEnvTcLevel tclvl') $  -- Bracket
                       captureConstraints thing_inside
       ; return (tclvl', lie, res) }            -- Auto-restore after
```

### Type Variable Placement by Level

| Variable Type | Created At | Level Stored In |
|---------------|-----------|-----------------|
| **MetaTv** | Current level | `mtv_tclvl :: TcLevel` |
| **SkolemTv** | Current level + 1 (anticipation) | Level in `SkolemTv` |

**Key distinction**: Skolems are created at level N+1 *while still at level N*, in anticipation of the scope that will run at level N+1. The actual level push happens separately via `checkConstraints` or `pushLevelAndCaptureConstraints`.

**Source**: `upstream/ghc/compiler/GHC/Tc/Utils/Instantiate.hs:620-624`

```haskell
tcInstSkolTyVarsPushLevel skol_info overlappable subst tvs
  = do { tc_lvl <- getTcLevel                    -- Get current level N
       ; let !pushed_lvl = pushTcLevel tc_lvl    -- Compute N+1
       ; tcInstSkolTyVarsAt skol_info pushed_lvl overlappable subst tvs }
       -- ^ Create skolems at level N+1, BUT we're still at level N!
```

**Source**: `upstream/ghc/compiler/GHC/Tc/Utils/TcType.hs:634-650`

```haskell
data TcTyVarDetails
  = SkolemTv SkolemInfo TcLevel Bool  -- Level = binding scope
  | MetaTv { mtv_info :: MetaInfo
           , mtv_ref :: IORef MetaDetails
           , mtv_tclvl :: TcLevel }    -- Level = creation scope
```

### Touchability Check

Metas can only be unified when **at the same level** as the current context:

**Source**: `upstream/ghc/compiler/GHC/Tc/Utils/TcType.hs:1213-1222`

```haskell
isTouchableMetaTyVar :: TcLevel -> TcTyVar -> Bool
isTouchableMetaTyVar ctxt_tclvl tv
  | MetaTv { mtv_tclvl = tv_tclvl } <- tcTyVarDetails tv
  = tv_tclvl `sameDepthAs` ctxt_tclvl  -- Same level = touchable
  | otherwise = False
```

This prevents **outer metas** from being unified with **inner types**, enforcing scope boundaries.

### Skolem Escape Detection

After typechecking at level N+1, skolems must not appear **free** in results at level N:

```python
# Conceptual escape check
def check_escape(sks, result_ty, current_level):
    free_vars = get_free_vars(result_ty)
    for sk in sks:
        if sk in free_vars and sk.level > current_level:
            raise SkolemEscapeError(f"{sk} escapes from level {sk.level} to {current_level}")
```

**When It Triggers**: After `tcSkolemise` completes and we exit the bracket:
- Skolems created at level N+1
- Must be bound by forall or not appear in level N results
- Unbound skolems = escape error

### Promotion

When a type from level N+1 needs to escape to level N, deeper metas are **promoted**:

**Source**: `upstream/ghc/compiler/GHC/Tc/Utils/Unify.hs:1155-1161`

```haskell
-- Before filling hole at level N with type from level N+1:
(prom_co, act_res_ty) <- promoteTcType res_lvl act_res_ty
-- Creates fresh meta at level N, emits equality
```

This allows types to cross level boundaries while maintaining the level invariant.

---

## Meta Variable Lifecycle

### 1. Creation

Meta variables are created when inference needs to defer fixing a type:

**Source**: `systemf/src/systemf/elab3/typecheck_expr.py:431-432` (Unifier) **⚠️ WIP**

```python
def make_meta(self) -> MetaTv:
    return MetaTv(self.uniq.make_uniq(), Ref())
```

**Source**: `upstream/ghc/compiler/GHC/Tc/Utils/TcMType.hs:433-441` (GHC)

```haskell
new_inferExpType :: InferInstFlag -> InferFRRFlag -> TcM ExpType
new_inferExpType iif ifrr
  = do { u <- newUnique
       ; tclvl <- getTcLevel
       ; ref <- newMutVar Nothing
       ; return (Infer (IR { ir_uniq = u, ir_lvl = tclvl
                           , ir_inst = iif, ir_frr  = ifrr
                           , ir_ref  = ref })) }
```

### 2. Filling (Unification)

Meta variables are unified via `Ref.set()` or `writeMetaTyVar`:

**Source**: `systemf/src/systemf/elab3/typecheck_expr.py:537-565`

```python
def unify_var(m: MetaTv, ty: Ty):
    match m:
        case MetaTv(ref=Ref(inner=inner)) if inner:
            unify(inner, ty)  # Follow chain
        case MetaTv(ref=Ref(inner=None)):
            unify_unbound_var(m, ty)  # Bind

def unify_unbound_var(m: MetaTv, ty: Ty):
    match ty:
        case MetaTv(ref=Ref(inner=None)):  # Bind meta to meta
            m.ref.set(ty)
        case _:
            if m in get_meta_vars([ty]):
                raise Exception(f"Occurrence check failed")
            m.ref.set(ty)  # Bind meta to type
```

**Source**: `upstream/ghc/compiler/GHC/Tc/Utils/Unify.hs:1122-1169` (GHC fillInferResult)

```haskell
fillInferResultNoInst act_res_ty ir@(IR { ir_ref = ref, ir_lvl = res_lvl, ... })
  = do { mb_exp_res_ty <- readTcRef ref
       ; case mb_exp_res_ty of
            Just exp_res_ty  -- HOLE ALREADY FILLED: unify with existing
               -> do { traceTc "Joining inferred ExpType" ...
                     ; unifyType Nothing act_res_ty exp_res_ty }
            Nothing          -- HOLE EMPTY: fill it (with promotion if needed)
               -> do { (prom_co, act_res_ty) <- promoteTcType res_lvl act_res_ty
                     ; writeTcRef ref (Just act_res_ty) 
                     ; return prom_co } }
```

**Branch Coordination via Hole Filling**: The key insight is that `InferResult` holes are **shared across branches**:
- First branch fills the hole with its type
- Subsequent branches unify their types with the already-filled hole
- This naturally implements type joining without explicit meet/join operations

### 3. Instantiation

Converting `∀a.ρ` → `[a/?]ρ` where `?` is a fresh meta:

**Source**: `systemf/src/systemf/elab3/typecheck_expr.py:382-394` (Unifier.instantiate) **⚠️ WIP**

```python
def instantiate(self, sigma: Ty) -> tuple[Ty, Wrapper]:
    match sigma:
        case TyForall(vars, ty):
            mvs = [self.make_meta() for _ in vars]
            inst_ty = subst_ty(vars, mvs, ty)
            wrap = functools.reduce(
                lambda acc, ty: wp_compose(WpTyApp(ty), acc), mvs, WP_HOLE)
            return inst_ty, wrap
        case _:
            return sigma, WP_HOLE
```

**Source**: `upstream/ghc/compiler/GHC/Tc/Utils/Instantiate.hs:275-310` (GHC topInstantiate)

```haskell
topInstantiate :: CtOrigin -> TcSigmaType -> TcM (HsWrapper, TcRhoType)
topInstantiate orig sigma
  = do { (subst, inst_tvs) <- newMetaTyVarsX empty_subst tvs
       ; inst_theta <- instCall orig (mkTyVarTys inst_tvs) theta
       ; (wrap2, inner_body) <- topInstantiate orig inst_body
       ; return (wrap2 <.> wrap1, inner_body) }
```

### 4. Skolemisation (GHC Reference)

> **📁 Prior Analysis:** See `upstream/ghc/analysis/SKOLEMISE_TRACE.md` for detailed step-by-step trace of `deeplySkolemise` (created via exploration skill).

Converting `∀a.ρ` → `[a/sk]ρ` where `sk` is a **rigid** skolem.

#### Core Skolemise Functions

| Function | Location | Description |
|----------|----------|-------------|
| `topSkolemise` | `Instantiate.hs:205` | Skolemises top-level foralls and theta (en-bloc) |
| `deeplySkolemise` | `Unify.hs:2281` | Skolemises nested foralls under arrows (deep) |
| `tcSkolemiseGeneral` | `Unify.hs:435` | High-level wrapper; calls topSkolemise or deeplySkolemise + checkConstraints |
| `tcSkolemise` | `Unify.hs:495` | Main entry point; calls tcSkolemiseGeneral |
| `tcSkolemiseCompleteSig` | `Unify.hs:470` | For user-written complete type signatures |
| `tcSkolemiseExpectedType` | `Unify.hs:489` | For expected types from context (e.g., `f e`) |
| `tcSkolemiseInvisibleBndrs` | `Instantiate.hs:639` | Skolemises only invisible binders |
| `skolemiseRequired` | `Instantiate.hs:237` | Skolemises up to N visible binders + trailing invisibles |
| `checkConstraints` | `Unify.hs:508` | Builds implication constraint after skolemisation |
| `tcInstSkolTyVarBndrsX` | `Instantiate.hs:594` | Creates SkolemTv at pushed level (helper) |

#### Call Sites Summary

**tcSkolemise** (main entry):
- `GHC.Tc.Gen.Expr.hs:219` — lambda with deep skolemisation
- `GHC.Tc.Gen.Expr.hs:964` — syntax argument type checking
- `GHC.Tc.Gen.Sig.hs:1063` — SPECIALISE pragma wrapper
- `GHC.Tc.Gen.App.hs:563` — Quick Look value argument evaluation
- `GHC.Tc.Utils.Unify.hs:1581` — subsumption checking

**tcSkolemiseCompleteSig**:
- `GHC.Tc.Gen.Expr.hs:206` — expression with complete sig (`e :: sig`)
- `GHC.Tc.Gen.Bind.hs:585` — function binding with signature

**tcSkolemiseExpectedType**:
- `GHC.Tc.Gen.Expr.hs:200` — expression with expected type

**tcSkolemiseInvisibleBndrs**:
- `GHC.Tc.Gen.HsType.hs:729` — deriving clause type checking
- `GHC.Tc.TyCl.Instance.hs:1045` — instance declaration kind checking

**skolemiseRequired**:
- `GHC.Tc.Utils.Unify.hs:838` — matchExpectedFunTys for required forall binders

**checkConstraints**:
- `GHC.Tc.Utils.Unify.hs:440,455` — within tcSkolemiseGeneral
- `GHC.Tc.Utils.Unify.hs:845` — within matchExpectedFunTys
- `GHC.Tc.Gen.Bind.hs:237` — pattern bindings with implicit parameters
- `GHC.Tc.Gen.Pat.hs:1252,1341` — pattern match GADT constraints
- `GHC.Tc.TyCl.Class.hs:301` — class default method signatures
- `GHC.Tc.Module.hs:1979` — top-level signature checking

#### Call Hierarchy

```
tcSkolemise (entry)
  └── tcSkolemiseGeneral
        ├── Shallow mode
        │     └── topSkolemise
        │           └── tcInstSkolTyVarBndrsX
        │                 └── tcInstSkolTyVarsPushLevel → tcInstSkolTyVarsAt
        │                       └── mkTcTyVar (creates SkolemTv)
        └── Deep mode
              └── deeplySkolemise
                    └── (same helper chain)

checkConstraints (after skolemisation)
  └── pushLevelAndCaptureConstraints
  └── buildImplicationFor
```

#### topSkolemise (Instantiate.hs:205)

```haskell
topSkolemise skolem_info ty
  = go init_subst idHsWrapper [] [] ty
  where
    go subst wrap tv_prs ev_vars ty
      | (bndrs, theta, inner_ty) <- tcSplitSigmaTyBndrs ty
      , not (null tvs && null theta)
      = do { (subst', bndrs1) <- tcInstSkolTyVarBndrsX skolem_info subst bndrs
           ; ev_vars1 <- newEvVars theta
           ; go subst'
                (wrap <.> mkWpTyLams tvs1 <.> mkWpEvLams ev_vars1)
                (tv_prs ++ ...) inner_ty }
```

**Key**: Skolemises en-bloc (loops to handle nested foralls), returns wrapper + skolems + ev_vars + rho.

#### deeplySkolemise (Unify.hs:2281)

```haskell
deeplySkolemise skol_info ty
  = go init_subst ty
  where
    go subst ty
      | Just (arg_tys, bndrs, theta, ty') <- tcDeepSplitSigmaTy_maybe ty
      = do { ids1 <- newSysLocalIds (fsLit "dk") arg_tys'
           ; (subst', bndrs1) <- tcInstSkolTyVarBndrsX skol_info subst bndrs
           ; ev_vars1 <- newEvVars (substTheta subst' theta)
           ; (wrap, tvs_prs2, ev_vars2, rho) <- go subst' ty'
           ; return ( mkWpEta ty ids1 (mkWpTyLams tvs1 <.> mkWpEvLams ev_vars1 <.> wrap)
                    , tv_prs1 ++ tvs_prs2
                    , ev_vars1 ++ ev_vars2
                    , mkScaledFunTys arg_tys' rho ) }
```

**Key**: Skolemises under arrows (for deep subsumption), creates lambdas for args.

#### Deep vs Shallow Skolemisation

| Mode | Scope | Use Case |
|------|-------|----------|
| **Shallow** (`topSkolemise`) | Only top-level foralls | Simple subsumption, local signatures |
| **Deep** (`deeplySkolemise`) | Nested foralls under arrows | Deep subsumption, higher-rank types |

See Note [Deep skolemisation] in `Unify.hs:1773` for examples:
```
deeplySkolemise (Int -> forall a. Ord a => blah)
  = ( \x:Int. /\a. \(d:Ord a). <hole> x, [a], [d:Ord a], Int -> blah )
```

### 5. Generalization (at Let Bindings)

Free meta variables become quantified type variables:

**Source**: `systemf/src/systemf/elab3/typecheck_expr.py:243-277` (poly method)

```python
def poly(self, term: TyCk[Defer[OUT]]) -> TyCk[Defer[OUT]]:
    def _go(env: Env, exp: Expect) -> Defer[OUT]:
        match exp:
            case Infer(ref):
                ty, e = run_infer(env, term)
                env_tys = env_types(env)
                env_tvs = get_meta_vars(env_tys)
                res_tvs = get_meta_vars([ty])
                # ftv(ρ) - ftv(Γ): meta vars in result but not in env
                forall_tvs = [tv for tv in res_tvs if tv not in env_tvs]
                binders, sigma_ty = quantify(forall_tvs, ty)
                ref.set(sigma_ty)
                return self.with_wrapper(mk_wp_ty_lams(binders, WP_HOLE), e)
            case Check(ty2):
                sks, rho2, sk_wrap = self.skolemise(ty2)
                e = term(env, Check(rho2))
                # Check skolem var escape
                ...
```

**Source**: `upstream/ghc/compiler/GHC/Tc/Gen/Bind.hs:714-766` (GHC tcPolyInfer)

```haskell
tcPolyInfer top_lvl rec_tc prag_fn tc_sig_fn bind_list
  = do { (tclvl, wanted, (binds', mono_infos))
             <- pushLevelAndCaptureConstraints $
                tcMonoBinds rec_tc tc_sig_fn LetLclBndr bind_list
       ; ((qtvs, givens, ev_binds, insoluble), residual)
             <- captureConstraints $
                simplifyInfer top_lvl tclvl infer_mode sigs name_taus wanted
       ; scaled_exports <- mapM (mkExport ...) mono_infos
       ; let abs_bind = AbsBinds { abs_tvs = qtvs, ... }
       ; return ([abs_bind], scaled_poly_ids) }
```

---

## Algorithm Components

### tcExpr - Expression Dispatcher

**GHC Source**: `upstream/ghc/compiler/GHC/Tc/Gen/Expr.hs:290-369`

```haskell
tcExpr :: HsExpr GhcRn -> ExpRhoType -> TcM (HsExpr GhcTc)

-- Applications: Quick Look impredicativity support
tcExpr e@(HsVar {})     res_ty = tcApp e res_ty
tcExpr e@(HsApp {})     res_ty = tcApp e res_ty
tcExpr e@(OpApp {})     res_ty = tcApp e res_ty

-- Lambda: decompose expected type into patterns + result
tcExpr e@(HsLam {}) res_ty 
  = do { (wrap, matches') <- tcLambdaMatches e lam_variant matches [] res_ty
       ; return (mkHsWrap wrap $ HsLam x lam_variant matches') }
```

**elab3 Source**: `systemf/src/systemf/elab3/typecheck_expr.py:75-88`

```python
def tc_expr(self, expr: Expr, exp: Expect) -> TyCk[Defer[OUT]]:
    match expr:
        case ast.LitExpr(value):
            return self.lit(value)
        case ast.Var(name):
            return self.var(name)
        case ast.Lam(args, body):
            return self.lam(args, body)
        case ast.App(fun, arg):
            return self.app(fun, arg)
        case ast.Ann(expr, sigma):
            return self.annot(expr, sigma)
        case ast.Let(bindings, body):
            return self.let(bindings, body)
```

### tcApp - Application Handler

**GHC Source**: `upstream/ghc/compiler/GHC/Tc/Gen/App.hs:353-415`

```haskell
tcApp rn_expr exp_res_ty
  = do { -- Step 1: Split application chain
       ; (fun@(rn_fun, fun_ctxt), rn_args) <- splitHsApps rn_expr
       
       -- Step 2: Infer type of head
       ; (tc_fun, fun_sigma) <- tcInferAppHead fun
       
       -- Step 3: Instantiate function type (Quick Look as needed)
       ; (inst_args, app_res_rho) <- tcInstFun do_ql inst_final tc_head fun_sigma rn_args

       ; case do_ql of
            NoQL -> do { -- Step 4.1: unify result type BEFORE checking arguments
                       ; res_wrap <- checkResultTy rn_expr tc_head inst_args app_res_rho exp_res_ty
                       -- Step 4.2: typecheck arguments
                       ; tc_args <- tcValArgs NoQL inst_args
                       -- Step 4.3: wrap up
                       ; finishApp tc_head tc_args app_res_rho res_wrap }
            DoQL -> ...  -- Quick Look path
```

**Key insight**: `checkResultTy` unifies the result type **before** checking arguments. This is critical for better error messages:

**Source**: `upstream/ghc/compiler/GHC/Tc/Gen/App.hs:325-350`

```text
Note [Unify with expected type before typechecking arguments]
Consider:
  data Pair a b = Pair a b
  baz = MkPair "yes" "no"

If we first unify result type (Pair alpha beta) with expected (Pair Int Bool),
we push informative types Int/Bool into arguments.
Otherwise we'd get confusing error about [Char] vs Bool at wrong position.
```

### tcLambdaMatches - Lambda Handler

**GHC Source**: `upstream/ghc/compiler/GHC/Tc/Gen/Match.hs:145-162`

```haskell
tcLambdaMatches e lam_variant matches invis_pat_tys res_ty
  = do { arity <- checkArgCounts matches
       ; (wrapper, r)
           <- matchExpectedFunTys herald GenSigCtxt arity res_ty $ \ pat_tys rhs_ty ->
              tcMatches ctxt tc_body (invis_pat_tys ++ pat_tys) rhs_ty matches
       ; return (wrapper, r) }
```

**elab3 Source**: `systemf/src/systemf/elab3/typecheck_expr.py:160-177`

```python
def lam(self, name: str, body: TyCk[Defer[OUT]]) -> TyCk[Defer[OUT]]:
    def _go(env: Env, exp: Expect) -> Defer[OUT]:
        match exp:
            case Infer(ref):
                # Infer: create fresh meta for arg, infer body, construct fun type
                arg_ty = self.make_meta()
                body_ty, e_body = run_infer(extend_env(name, arg_ty, env), body)
                result_ty = TyFun(arg_ty, body_ty)
                ref.set(result_ty)
                return lambda: self.core.lam(name, arg_ty, e_body())
            case Check(ty2):
                # Check: decompose function type and check body against result
                (arg_ty, res_ty) = self.unify_fun(ty2)
                e = self.poly(body)(extend_env(name, arg_ty, env), Check(res_ty))
                return lambda: self.core.lam(name, arg_ty, e())
```

### tcMatches - Branch Coordination via Shared Hole

**GHC Source**: `upstream/ghc/compiler/GHC/Tc/Gen/Match.hs:222-258`

```haskell
tcMatches ctxt tc_body pat_tys rhs_ty (MG { mg_alts = L l matches })
  | null matches  -- Empty case handled specially
  = ...
  | otherwise
  = do { umatches <- mapM (tcMatch tc_body pat_tys rhs_ty) matches
       -- All branches use SAME rhs_ty - shared mutable hole!
       ; ...
       ; rhs_ty <- readExpType rhs_ty  -- Read after all branches complete
       ; return (MG { mg_alts = L l matches', mg_ext = MatchGroupTc pat_tys rhs_ty origin }) }
```

**Key mechanism** - shared hole filling:

**Source**: `upstream/ghc/compiler/GHC/Tc/Utils/Unify.hs:1127-1148`

```haskell
fillInferResultNoInst act_res_ty (IR { ir_ref = ref })
  = do { mb_exp_res_ty <- readTcRef ref
       ; case mb_exp_res_ty of
            Just exp_res_ty  -- HOLE FILLED: unify with existing type
               -> unifyType act_res_ty exp_res_ty
            Nothing          -- HOLE EMPTY: fill with inferred type
               -> writeTcRef ref (Just act_res_ty) }
```

**The Pattern**:
1. **Create shared hole**: Before typechecking branches, create one `Infer` hole
2. **First branch**: Infers its type, calls `fillInferResult`, hole is empty → fills it
3. **Second branch**: Infers its type, calls `fillInferResult`, hole is filled → unifies
4. **Result**: All branches must agree on type (or be unifiable)

**Example**:
```haskell
case e of
  True  -> 1      -- fill hole with Int
  False -> 2      -- unify Int with Int (success)
  
case e of
  True  -> 1      -- fill hole with Int  
  False -> 'a'    -- unify Int with Char (FAIL - type error!)
```

This is how **case branches**, **if expressions**, and **function equations** coordinate their result types.

### tcFunBindMatches - Function Binding

**GHC Source**: `upstream/ghc/compiler/GHC/Tc/Gen/Match.hs:103-137`

```haskell
tcFunBindMatches ctxt fun_name mult matches invis_pat_tys exp_ty
  = do { arity <- checkArgCounts matches
       ; (wrap_fun, r)
             <- matchExpectedFunTys herald ctxt arity exp_ty $ \ pat_tys rhs_ty ->
                tcScalingUsage mult $
                tcMatches mctxt tcBody (invis_pat_tys ++ pat_tys) rhs_ty matches
       ; return (wrap_fun, r) }
```

### tcPolyBinds - Let Binding Generalization

**GHC Source**: `upstream/ghc/compiler/GHC/Tc/Gen/Bind.hs:255-470`

Three generalization plans:

| Plan | When | Key Function |
|------|------|-------------|
| `NoGen` | MonoLocalBinds, no sigs | No generalization |
| `InferGen` | Infer polymorphism | `tcPolyInfer` → `simplifyInfer` |
| `CheckGen` | Has complete sig | `tcPolyCheck` → skolemise |

**Source**: `upstream/ghc/compiler/GHC/Tc/Gen/Bind.hs:470-495`

```haskell
tcPolyBinds top_lvl sig_fn prag_fn rec_group rec_tc closed bind_list
  = do { plan <- decideGeneralisationPlan dflags top_lvl closed sig_fn bind_list
       ; case plan of
            NoGen              -> tcPolyNoGen ...
            InferGen           -> tcPolyInfer ...
            CheckGen lbind sig -> tcPolyCheck ...
```

---

## GHC Correspondence

| Concept | elab3 | GHC |
|---------|-------|-----|
| Expected type mode | `Expect = Infer \| Check` | `ExpType = Infer \| Check` |
| Meta variable | `MetaTv(uniq, Ref[Ty])` | `MetaTv(IORef MetaDetails, TcLevel)` |
| Skolem variable | `SkolemTv(name, uniq)` | `SkolemTv(SkolemInfo, TcLevel, Bool)` |
| TcLevel | Not tracked | `TcLevel = TcLevel Int` |
| Level push | N/A | `pushLevelAndCaptureConstraints` |
| Hole to fill | `Infer(ref: Ref[Ty])` | `Infer(IR { ir_ref :: IORef, ir_lvl :: TcLevel })` |
| **Fill hole** | `ref.set(ty)` | `fillInferResult ty hole` |
| **Branch coordination** | Shared `Ref[Ty]` | `fillInferResult` with shared `IR` |
| Touchability | N/A | `isTouchableMetaTyVar` |
| Escape check | Manual | `checkConstraints` with level validation |
| Instantiate | `Unifier.instantiate()` → WpTyApp | `topInstantiate()` → mkWpTyApps |
| Skolemise | `Unifier.skolemise()` → WpTyLam | `topSkolemise()` → mkWpTyLams |
| Generalize | `quantify()` in `poly` | `simplifyInfer()` |
| Subsumption | `subs_check()` | `tcSubType` |
| App typecheck | `app()` | `tcApp()` |
| Lambda typecheck | `lam()` | `tcLambdaMatches()` |
| Branch coordination | shared Ref[Ty] | shared `InferResult.ir_ref` |
| Wrapper evidence | `Wrapper` hierarchy | `HsWrapper` hierarchy |

---

## Source Reference Index

### elab3 Source Files

| File | Key Content |
|------|-------------|
| `systemf/src/systemf/elab3/typecheck_expr.py` | Main typechecker: `TypecheckExpr`, `Unifier` classes |
| `systemf/src/systemf/elab3/types/ty.py` | Type hierarchy: `Ty`, `MetaTv`, `SkolemTv`, `TyFun`, `TyForall`, `Ref` |
| `systemf/src/systemf/elab3/types/ast.py` | AST definitions: `Expr`, `Pat`, `Lam`, `App`, `Let` |
| `systemf/src/systemf/elab3/types/wrapper.py` | Evidence wrappers: `Wrapper`, `WpTyApp`, `WpTyLam`, `WpCast`, `WpFun` |
| `systemf/src/systemf/elab2/tyck.py` | Previous implementation (reference) |
| `systemf/src/systemf/elab3/typecheck.py` | Module-level orchestration |

### GHC Upstream Source Files

| File | Key Content | Lines |
|------|-------------|-------|
| `compiler/GHC/Tc/Gen/Expr.hs` | `tcExpr` dispatcher | 290-369 |
| `compiler/GHC/Tc/Gen/App.hs` | `tcApp` application handler | 353-415 |
| `compiler/GHC/Tc/Gen/Match.hs` | `tcLambdaMatches`, `tcMatches` | 145-258 |
| `compiler/GHC/Tc/Gen/Bind.hs` | `tcPolyInfer`, `tcPolyCheck`, `tcPolyBinds` | 255-766 |
| `compiler/GHC/Tc/Utils/Unify.hs` | **fillInferResult**, subsumption, promotion | 1122-1186 |
| `compiler/GHC/Tc/Utils/Instantiate.hs` | `topInstantiate`, `topSkolemise` | 198-310 |
| `compiler/GHC/Tc/Utils/TcMType.hs` | `ExpType`, `InferResult`, meta var creation | 361-500 |
| `compiler/GHC/Tc/Utils/TcType.hs` | `ExpType`, `TcLevel`, `TcTyVarDetails` | 491-498, 634-650, 870-885 |
| `compiler/GHC/Tc/Utils/Monad.hs` | `pushLevelAndCaptureConstraints`, `updLclEnv` | 508-524 |
| `compiler/GHC/Tc/Types/LclEnv.hs` | `TcLclEnv`, `TcLclCtxt` | 76-122 |

### Analysis Documents (Prior Explorations)

Records of prior exploration results created with the **exploration skill**. Check these **first** before doing new exploration.

| File | Key Content |
|------|-------------|
| `upstream/ghc/analysis/GHC_TYPE_HIERARCHY.md` | **Var, TcTyVar, TyVar, MetaTv, SkolemTv relationships** - Type hierarchy documentation |
| `upstream/ghc/analysis/SKOLEMISE_TRACE.md` | Detailed trace of `deeplySkolemise` |
| `upstream/ghc/analysis/TYPE_INFERENCE.md` | Comprehensive GHC type inference overview |
| `upstream/ghc/analysis/HIGHERRANK_POLY.md` | Higher-rank polymorphism and subsumption |
| `upstream/ghc/analysis/HSWRAPPER_ARCHITECTURE.md` | `HsWrapper` evidence construction |
| `upstream/ghc/analysis/FLOW_DIAGRAMS.md` | Control flow diagrams for type inference |
| `upstream/ghc/analysis/SIGNATURE_CODE_PATH.md` | Signature type-checking code paths |
| `upstream/ghc/analysis/PATTERN_TC_ANALYSIS.md` | Pattern type-checking analysis |
| `analysis/PATTERN_TC_FACTS.md` | Pattern matching type checking facts |
| `analysis/TCTYPE_ENV_EXPLORATION.md` | TypeEnv architecture |

---

## Meta/Skolem Duality and Bidirectional Modes

### The Core Duality

| Aspect | **MetaTv** (Infer Mode) | **SkolemTv** (Check Mode) |
|--------|-------------------------|---------------------------|
| **Philosophy** | "What type should this be?" | "Does this work for all types?" |
| **Mutability** | Mutable (can unify) | Rigid (cannot unify FROM) |
| **Created at** | Current level N | Level N+1 (created at N, anticipating N+1 scope) |
| **Use case** | Synthesize unknown types | Verify against known polymorphic types |
| **Wrapper** | `WpTyApp` (instantiation) | `WpTyLam` (skolemisation) |

### Meta Variables → Infer Mode

**When to use**: Bottom-up type synthesis

```python
# Infer mode creates a hole to be filled
def infer(expr: Expr) -> tuple[Ty, CoreTm]:
    ref = Ref[Ty]()  # Create meta hole
    core = tc_expr(expr, Infer(ref))  # Typecheck, filling the hole
    return ref.get(), core  # Return inferred type
```

**Key property**: Metas are **touchable only at their creation level**:
```haskell
isTouchable :: MetaTv -> TcLevel -> Bool
isTouchable meta ctx = meta.level == ctx  -- Same level only!
```

### Skolem Variables → Check Mode

**When to use**: Top-down type checking against polymorphic types

**Creation mechanism**: Skolems are created at level N+1 while the typechecker is still at level N (anticipating the level N+1 scope that will be entered by `checkConstraints`):

```python
# Conceptual flow for skolemisation
def skolemise_and_check(sigma: Ty, check_fn) -> CoreTm:
    # At level N: create skolems at level N+1 (anticipation)
    sks = make_skolems_at_level(current_level + 1, sigma)
    rho = instantiate_sigma_with_skolems(sigma, sks)
    
    # checkConstraints pushes to level N+1 and runs the check
    result = check_constraints(
        skolems=sks,
        thing_inside=lambda: check_fn(rho)  # runs at level N+1
    )
    
    # Back at level N
    check_escape(sks, result)  # ensure skolems stayed in scope
    return result
```

**Actual sequence from GHC source**:
1. `tcSkolemiseGeneral` calls `topSkolemise` → creates skolems at level N+1 (still at level N)
2. `checkConstraints` receives skolems → pushes to level N+1 → runs `thing_inside`
3. Returns to level N → escape check

**Key distinction**: The level push happens INSIDE `checkConstraints`, not as a separate step between skolem creation and the closure.

**Key property**: Skolems are **rigid** - they can be unified INTO but not FROM:
```python
unify(sk_a, Int)    # ERROR: Cannot unify rigid skolem
unify(?m, sk_a)     # OK: Meta absorbs skolem
```

### The Administrative Guard: Levels

The **TcLevel system** enforces the boundary between these two worlds:

1. **Touchability**: Metas can only unify at their creation level
   - Prevents outer-scope metas from capturing inner-scope types

2. **Escape Check**: Skolems must not appear free in outer-scope results
   - Prevents rigid variables from leaking into broader contexts

3. **Promotion**: When types must cross level boundaries, deeper metas are lifted
   - Maintains the level invariant while allowing information flow

### Decision Matrix

| Scenario | Mode | Variable Type | Operation |
|----------|------|---------------|-----------|
| Type annotation `(e :: σ)` | Check | Skolem | Skolemise σ, check e |
| Variable lookup `x` | Infer | Meta | Return σ, defer instantiation |
| Function application `f x` | Mixed | Both | Instantiate f, check x, unify result |
| Lambda `\x -> e` | Check | Skolem | Decompose expected, check body |
| Lambda `\x -> e` | Infer | Meta | Create arg meta, infer body |
| Let binding | Infer | Meta | Infer RHS, generalise free metas |

---

## Thinking Model

Understanding this system requires thinking in **levels of abstraction**:

### Level 1: Meta Variable as Deferred Choice

Think of a meta variable (`MetaTv` / `InferResult`) as a **question mark in a type**:

```text
When inferring `f x` where `f` has unknown type:
  f : ?  (meta variable, not yet decided)
  
After seeing `f` applied to `x`:
  ? → ?  (meta unified with function type)
  
After seeing result used as Int:
  ? → Int  (result position unified)
  
After full inference:
  (Int → Int) → Int  (concrete type)
```

### Level 2: Hole Filling as Commitment

The `Infer(ref)` mode creates a **hole** that gets filled during type inference. This hole is **shared across branches** to coordinate types:

```text
λx → case e of 
  True → x       -- First branch: fills hole with type of x
  False → 3      -- Second branch: unifies type of x with Int

Workflow:
1. Create one shared hole H for the case result
2. True branch:  infer x as Int, call fill(H, Int) → H is empty, fills it
3. False branch: infer 3 as Int, call fill(H, Int) → H filled, unifies Int~Int
4. Result: H contains Int
```

**Key**: Multiple branches **coordinate** by filling/unifying with the same hole. This implements type joining without explicit meet/join operations.

**GHC's `fillInferResult`**:
```haskell
fillInferResult ty hole = do
  mb_ty <- readRef hole
  case mb_ty of
    Just existing -> unify ty existing  -- Join types
    Nothing       -> writeRef hole ty   -- First fill
```

### Level 3: Instantiation vs Skolemisation

Two ways to handle `∀`:

| | Instantiation | Skolemisation |
|--|--|--|
| Creates | Fresh **meta** vars | Fresh **rigid** skolem vars |
| Direction | `∀a.ρ` → `[a/?]ρ` | `∀a.ρ` → `[a/sk]ρ` |
| Purpose | Argument position | Expected type checking |
| Evidence | `WpTyApp` | `WpTyLam` |

**Rule of thumb**:
- **Instantiate** when going *into* polymorphism (function call)
- **Skolemise** when going *against* polymorphism (type annotation)

### Level 4: Wrapper as Proof Term

The `Wrapper` / `HsWrapper` is evidence that a type transformation occurred:

```text
subs_check(σ1, σ2) → wrap where wrap :: σ1 ~~> σ2

If σ1 = ∀a.a → a  (instantiated)
and σ2 = Int → Int (expected)
then wrap = WpTyLam a . WpTyApp Int  (witnesses the instantiation)
```

The wrapper is applied to the Core term to witness the type coercion.

### Level 5: Generalization as Closure

At let bindings, the **free meta variables** of the RHS become quantified:

```python
# In env with x :: Int
let f = λy → y  # infers f :: ? → ?
# ? is a meta var created during inference

# When generalizing at let:
env_tvs = {Int}       # free vars in environment  
res_tvs = {?}          # free vars in inferred type (including meta)
forall_tvs = res_tvs - env_tvs  # metas not in env = quantify these

# Result: f :: ∀a. a → a
```

This is `ftv(ρ) - ftv(Γ)` from the paper.

### Putting It Together: Application Type Inference

When inferring `(f 3)`:

```text
1. tcApp splits into head f and args [3]
2. Infer f's type: creates meta m1
3. matchActualFunTy sees m1, creates metas m2, m3 for arg/result
4. Unifies m1 with m2 → m3 (function type shape)
5. Check arg 3 against m2 (Check mode)
6. Unify result with expected type (or leave as meta if Infer mode)
7. f's inferred type = m2 → m3 = ? → ?
```

The meta variables allow **incremental shape construction** without committing to concrete types early.

### Level 6: TcLevel as Scope Discipline

The level system provides **administrative control** over type variable scope:

```text
Level 0 (Module)
  └─ x : Int
  └─ Let binding at Level 0
      └─ pushLevelAndCaptureConstraints → Level 1
      └─ f = \y -> y        -- Infers f :: ? -> ? at Level 1
      └─ Generalise: ? → ∀a. a -> a
      └─ Back to Level 0
  └─ f : ∀a. a -> a

Level 1 (Let RHS, checking against sig)
  └─ Check (\y -> y) :: ∀a. a -> a
      └─ At Level 1: skolemise creates a_sk at Level 2 (anticipating scope)
      └─ pushLevelAndCaptureConstraints → Level 2
      └─ Check \y -> y :: a_sk -> a_sk at Level 2
      └─ Back to Level 1: escape check ensures a_sk not in result ✓
      └─ Quantify: a_sk → ∀a. a -> a
```

**Key insight**: The skolems are created at Level 2 *while still at Level 1*, before the level push. This anticipatory creation ensures the skolems have the correct level for the escape check when returning to Level 1.

**Levels enforce that:**
- **Metas** can't be unified from outer scopes (touchability)
- **Skolems** can't escape their defining scope (escape check)
- **Types** are promoted when they must cross level boundaries

---

## GHC Let Binding Level Hierarchy (Detailed)

This section documents the exact level structure for let bindings in GHC's type checker.

### Overview

```
Level N
│
├─► tcValBinds
│   │
│   ├─► tcTySigs [Level N]                    ─┐
│   │   ├─ Creates poly_ids (complete sigs)    │
│   │   └─ Returns sig_fn                      │ No level push
│   │                                          │ No expect mode
│   ├─► tcExtendSigIds [Level N]               │ (pure processing)
│   │   └─ Adds complete sigs to env           │
│   │                                          │
│   └─► tcBindGroups [Level N]                ─┘
│       │
│       ├─► For each SCC group:
│       │   └─► tc_group
│       │       │
│       │       ├─► decideGeneralisationPlan    ─┐ PLAN SELECTION
│       │       │   │                            │
│       │       │   ├─ Exactly 1 binding with    │ CheckGen
│       │       │   │   complete signature       │ (Check mode)
│       │       │   └──────► tcPolyCheck ────────┤
│       │       │                                │
│       │       │   ├─ Partial sigs OR           │ InferGen
│       │       │   │   generalization enabled   │ (Infer mode)
│       │       │   └──────► tcPolyInfer ────────┤
│       │       │                                │
│       │       │   └─ MonoLocalBinds,           │ NoGen
│       │       │       no signatures            │ (Infer, but
│       │       │       └──► tcPolyNoGen ────────┘  no gen)
│       │       │
│       │       └─► tcExtendLetEnv [Level N]
│       │           └─ Adds results to env for next group
│       │
│       └─► thing_inside [Level N, full env]
│
│
├─► tcPolyCheck (CheckGen plan)               ─┐
│   │   ^                                      │
│   │   └─ One binding with complete sig       │ Level: N → N+1
│   │                                           │ Expect: CHECK
│   ├─► tcSkolemiseCompleteSig                  │ Closure: thing_inside
│   │   ├─ Instantiates sig (creates SKOLEMS!)  │ Meta/Skolem: Skolems
│   │   └─ checkConstraints [Level N+1]         │
│   │       └─ tcFunBindMatches                 │
│   │           └─ Checks body against rho_ty   │
│   │                                           │
│   └─ Returns poly_id [Level N]               ─┘
│
│
└─► tcPolyInfer (InferGen plan)               ─┐
    │   ^                                       │
    │   └─ Infer + generalize                   │ Level: N → N+1 → N
    │       (no/partial sigs)                   │ Expect: INFER
    │                                           │ Closure: bracketed
    ├─► pushLevelAndCaptureConstraints          │ Meta/Skolem: Metas
    │   │                                       │   → quantified
    │   └─► tcMonoBinds [Level N+1]            │
    │       │                                   │
    │       ├─► tcLhs                           │
    │       │   ├─ No sig: new TauTv META      │
    │       │   └─ Partial sig: TyVarTv META   │
    │       │                                   │
    │       ├─► tcExtendRecIds [Level N+1]     │
    │       │                                   │
    │       └─► tcRhs [Level N+1]              │
    │           └─► matchExpectedFunTys        │
    │               ├─ Infer mode: METAS       │
    │               └─ Check mode: SKOLEMS     │
    │                                           │
    ├─► simplifyInfer [Returns to Level N]    │
    │   └─ quantifyTyVars                       │
    │       └─ Metas → Skolems (quantified)    │
    │                                           │
    └─► mkExport [Level N]                     ─┘
        └─ Creates poly bindings
```

### Key Level Invariants

| Invariant | Description |
|-----------|-------------|
| **Meta creation** | MetaTvs created at current level N can only be unified at level N |
| **Skolem creation** | Skolems are created at level N+1 (anticipating the scope they will be used in) |
| **Level push** | `pushLevelAndCaptureConstraints` increments level and captures constraints |
| **Escape check** | Skolems must not appear free in results when returning to outer level |
| **Generalization** | Happens when returning from N+1 to N (quantifying metas at N+1) |

### Critical Distinctions

**1. tcInstSig creates TyVarTvs (METAs), NOT skolems:**

```haskell
-- In tcInstSig / tcInstTypeBndrs
newMetaTyVarTyVarX subst tv  -- Creates TyVarTv META, not skolem!
```

TyVarTvs are meta variables that can only unify with type variables, but they are NOT rigid skolems.

**2. matchExpectedFunTys behavior differs by Expect mode:**

```haskell
-- INFER MODE: Creates fresh MetaTvs
matchExpectedFunTys ... (Infer inf_res) ...
  = do { arg_tys <- mapM (new_infer_arg_ty herald) [1 .. arity]  -- Metas!
       ; res_ty  <- newInferExpType (ir_inst inf_res) }           -- Meta!

-- CHECK MODE: May skolemise
matchExpectedFunTys ... (Check top_ty) ...
  = check ...
  where check ... | isSigmaTy ty = do { ...; skolemiseRequired ... }  -- Skolems!
```

**3. Three generalization plans:**

| Plan | Condition | Mode | Result |
|------|-----------|------|--------|
| **CheckGen** | Exactly 1 binding with complete sig | CHECK | Check against signature |
| **InferGen** | Partial sigs or generalization enabled | INFER | Infer + quantify |
| **NoGen** | MonoLocalBinds, no signatures | INFER | Infer, no quantification |

**4. NoGen is INFER mode but without generalization:**

NoGen bindings are typechecked in INFER mode (synthesizing types with metas), but the metas are NOT quantified - the binding remains monomorphic.

---

## Complete Call Chain: tcValBinds to RHS

This section documents the complete flow from `tcValBinds` through to the RHS typechecking, showing how the 4 aspects (Levels, Expect, Closure, Meta/Skolem) apply at each step.

### The Flow (InferGen Plan Path)

```
Level N
│
├─► tcValBinds
│   ├─► tcTySigs [Level N] - Process complete sigs
│   ├─► tcExtendSigIds [Level N] - Add to env
│   └─► tcBindGroups [Level N]
│       └─► tc_group → decideGeneralisationPlan → tcPolyInfer
│
├─► tcPolyInfer [Level N → N+1 → N]
│   └─► pushLevelAndCaptureConstraints
│       └─► tcMonoBinds [Level N+1] ←── INFER mode (creates metas)
│           ├─► tcLhs
│           │   ├─ No sig: new TauTv META
│           │   └─ Partial sig: tcInstSig → TyVarTv META (not skolem!)
│           ├─► tcExtendRecIds [Level N+1] - For recursive refs
│           └─► mapM tcRhs [Level N+1]
│               └─► TcFunBind case
│                   ├─► tcExtendIdBinderStackForRhs
│                   ├─► tcExtendTyVarEnvForRhs (partial sig skolems)
│                   └─► tcFunBindMatches [Level N+1] ←── CHECK mode!
│                       └─► matchExpectedFunTys CHECK mono_ty
│                           ├─► Check mode: Decomposes mono_ty (meta!)
│                           │   If mono_ty is TauTv: just uses it
│                           │   If mono_ty is sigma: would skolemise
│                           └─► thing_inside callback
│                               └─► tcMatches [Level N+1]
│                                   └─► tcBody [Level N+1]
│                                       └─► Typecheck RHS expressions
│
└─► simplifyInfer [Level N] - Quantify metas to skolems
    └─► mkExport - Create poly bindings
```

### Critical Insight: Expect Mode Transition

The **key transition** happens at `tcRhs`:

- **tcLhs** runs in **INFER mode** - creates metas (TauTv, TyVarTv)
- **tcRhs** calls `tcFunBindMatches` with `mkCheckExpType mono_ty` - **CHECK mode**!

But since `mono_ty` is a meta (not a sigma type), `matchExpectedFunTys` in Check mode just decomposes it without skolemising.

### 4 Aspects Applied to Complete Chain

| Function | Level | Expect | Closure | Meta/Skolem |
|----------|-------|--------|---------|-------------|
| **tcValBinds** | N | N/A | tcBindGroups | N/A |
| **tcPolyInfer** | N→N+1→N | INFER | pushLevelAndCaptureConstraints | Metas→Quantified |
| **tcMonoBinds** | N+1 | INFER | tcExtendRecIds | TauTv/TyVarTv |
| **tcLhs** | N+1 | INFER | N/A | Creates metas |
| **tcRhs** | N+1 | CHECK | tcExtendIdBinderStackForRhs | Checks against meta |
| **tcFunBindMatches** | N+1 | CHECK | matchExpectedFunTys callback | Decomposes meta |
| **matchExpectedFunTys** | N+1 | CHECK | thing_inside | Handles Check mode |
| **tcMatches** | N+1 | CHECK | N/A | Pattern→RHS coordination |
| **tcBody** | N+1 | Mixed | N/A | Expression typechecking |

### Why Check Mode in tcRhs?

In `tcRhs` (Bind.hs:1593):
```haskell
tcFunBindMatches ... (mkCheckExpType mono_ty)
```

The mono_ty comes from the mono_id created by tcLhs. Since we already have a type (even if it's a meta), we CHECK against it rather than inferring a new type. This ensures:

1. **Consistency**: All equations check against the same mono_ty
2. **Coordination**: If mono_ty is `?1 → ?2`, each equation decomposes it the same way
3. **Generalization**: Metas in mono_ty will be quantified later by simplifyInfer

### The Environment Substitution Trick

Note how `tcExtendRecIds` works:

```haskell
tcExtendRecIds rhs_id_env $ mapM tcRhs tc_binds
```

The `rhs_id_env` maps **Name → ATcId (mono_id)**. So when the RHS references "f", it looks up the Name and gets the mono_id (with its meta type). This is how recursive calls typecheck against the monomorphic type during inference.

**Evidence:** `compiler/GHC/Tc/Utils/Env.hs:tcExtendRecIds`

---

## Inside the Closure: From Patterns to RHS Type Coordination

After `matchExpectedFunTys` creates the closure, it calls `thing_inside pat_tys rhs_ty`. Here's what happens inside:

### The Closure Chain

```
matchExpectedFunTys callback
│
├─► tcFunBindMatches callback
│   └─► tcMatches mctxt tcBody (invis_pat_tys ++ pat_tys) rhs_ty matches
│       │
│       ├─► For each match: tcMatch tc_body pat_tys rhs_ty match
│       │   │
│       │   └─► tcMatchPats ctxt pats pat_tys $
│       │       └─► tcGRHSs ctxt tc_body grhss rhs_ty  ←-- SAME rhs_ty!
│       │           │
│       │           └─► tcGRHSNE ctxt tc_body grhss res_ty  ←-- ALL branches share res_ty
│       │               │
│       │               └─► For each GRHS: tc_body rhs  ←-- tcBody calls tcPolyLExpr
│       │                   │
│       │                   └─► tcPolyLExpr body res_ty  ←-- Typecheck RHS against res_ty
│       │
│       └─► After all branches: readExpType rhs_ty  ←-- Read final coordinated type
```

### Critical: Shared ExpType Enables Branch Coordination

**Key insight:** The SAME `rhs_ty` (ExpRhoType) is passed to **all branches**.

From `tcMatches` (Match.hs:250):
```haskell
umatches <- mapM (tcCollectingUsage . tcMatch tc_body pat_tys rhs_ty) matches
```

And from `tcGRHSNE` (Match.hs:359):
```haskell
tc_alt (GRHS _ guards rhs)
  = tcCollectingUsage $
    do { (guards', rhs')
             <- tcStmtsAndThen stmt_ctxt tcGuardStmt guards res_ty $
                tc_body rhs  }  -- <-- tc_body is tcBody, rhs is the expression
```

### How Coordination Works

1. **Infer mode (hole filling):**
   - `rhs_ty = Infer (IR { ir_ref = ref, ... })`
   - First branch: `tcBody expr (Infer ref)` → infers type, calls `fillInferResult`, ref is empty → **fills it**
   - Second branch: `tcBody expr (Infer ref)` → infers type, calls `fillInferResult`, ref is filled → **unifies with existing**

2. **Check mode (validation):**
   - `rhs_ty = Check expected_ty`
   - Each branch: `tcBody expr (Check expected_ty)` → checks expr against expected_ty
   - If mismatches, type error

### Evidence from GHC Source

**tcMatches passes same rhs_ty to all matches** (Match.hs:250):
```haskell
-- Line 250
umatches <- mapM (tcCollectingUsage . tcMatch tc_body pat_tys rhs_ty) matches
```

**tcGRHSNE processes all guarded RHS with same res_ty** (Match.hs:359):
```haskell
-- Line 359
tcGRHSNE ctxt tc_body grhss res_ty
   = do { (usages, grhss') <- unzip <$> traverse (wrapLocSndMA tc_alt) grhss
        ; ... }
  where
    tc_alt (GRHS _ guards rhs)
      = tcCollectingUsage $
        do { ...
             <- tcStmtsAndThen stmt_ctxt tcGuardStmt guards res_ty $
                tc_body rhs  -- <-- res_ty shared across all GRHS
```

**tcBody receives res_ty and typechecks** (Match.hs:418-421):
```haskell
-- Line 418-421
tcBody :: LHsExpr GhcRn -> ExpRhoType -> TcM (LHsExpr GhcTc)
tcBody body res_ty
  = do  { traceTc "tcBody" (ppr res_ty)
        ; tcPolyLExpr body res_ty }  -- <-- Typechecks against res_ty
```

### Example: Multiple Function Equations

```haskell
f :: Bool -> Int
f True  = 1    -- Branch 1: fills hole with Int
f False = 2    -- Branch 2: unifies Int with Int (success)

-- Workflow:
1. matchExpectedFunTys creates res_ty hole (Infer ref)
2. tcMatches maps over both equations with SAME res_ty
3. Equation 1: infers Int, fills ref with Int
4. Equation 2: infers Int, unifies with ref's Int
5. Result: All equations agree on Int -> Int
```

### Example: Type Mismatch Across Branches

```haskell
f :: Bool -> Int
f True  = 1      -- fills hole with Int
f False = 'a'    -- ERROR: cannot unify Int with Char

-- Workflow:
1. matchExpectedFunTys creates res_ty hole (Infer ref)
2. Equation 1: fills ref with Int
3. Equation 2: tries to fill ref with Char, but ref has Int
4. ERROR: Int ~ Char unification failure
```

### 4 Aspects in the Closure

| Function | Level | Expect | Closure | Meta/Skolem |
|----------|-------|--------|---------|-------------|
| **tcMatchPats** | N+1 | Check (pattern types) | tcGRHSs | Pattern vars |
| **tcGRHSs** | N+1 | Check/Infer (rhs_ty) | tcGRHSNE | Shared res_ty |
| **tcGRHSNE** | N+1 | Check/Infer | tc_body | Guards → RHS |
| **tcBody** | N+1 | Check/Infer | tcPolyLExpr | Expression type |
| **tcPolyLExpr** | N+1 | Check/Infer | tcExpr | Final dispatch |

---

## Research Papers Directory

The `docs/research/` directory contains papers and reference materials related to the elab3 typechecker implementation. Below is a summary of each major paper and resource:

### Core Type Inference Papers

| File | Paper | Authors | Description |
|------|-------|---------|-------------|
| `putting-2007.txt` | **Practical Type Inference for Arbitrary-Rank Types** | Peyton Jones, Vytiniotis, Weirich, Shields (2007) | The foundational paper for elab3. Presents a complete, implementable bidirectional type inference algorithm for higher-rank polymorphism. Key concepts: bidirectional checking (Check/Infer modes), instantiation vs skolemisation, subsumption checking, and the `ftv(ρ) - ftv(Γ)` generalization rule. See `putting2007-index.md` for line-by-line navigation and `putting2007-reading.md` for detailed notes. |
| `carnier-2023.txt` | **Type Inference Logics** | Carnier, Pottier, Keuchel (OOPSLA 2024) | Constraint-based type inference with elaboration using free monads. Introduces a monadic API (`CstrM`) for constraint generation with semantic values, world-indexed types, and predicate transformer semantics (WP/WLP) for proving correctness. See `carnier-2023-index.md` for detailed navigation. |
| `fan-xu-xie-2025-practical-type-inference-with-levels.txt` | **Practical Type Inference with Levels** | Fan, Xu, Xie (PLDI 2025) | First comprehensive formalization of **TcLevel-based** type inference. Shows how level numbers provide O(\|type\|) generalization (vs O(\|context\|)), efficient skolem escape prevention, and type regions. Key: `ftv_{n+1}` generalization rule and polymorphic promotion. See `fan-xu-xie-2025-index.md` and `fan-xu-xie-2025-reading.md`. |
| `vytiniotis-2011-outsidein.txt` | **OutsideIn(X): Modular Type Inference with Local Assumptions** | Vytiniotis, Peyton Jones, Schrijvers, Sulzmann (2011) | Constraint-based inference for GADTs and type families. Introduces "touchable" vs "untouchable" variables for handling local constraints from pattern matching. Key innovation: restricting let-generalization with GADTs to maintain soundness. See `vytiniotis-2011-index.md`. |
| `weirich-2013-system-fc.txt` | **System FC with Explicit Kind Equality** | Weirich, Hsu, Eisenberg (ICFP 2013) | Extends GHC's intermediate language (System FC) with explicit kind equalities. Covers heterogeneous equality, coercion irrelevance, and preservation/progress proofs. Important for understanding GHC's core representation. See `weirich-2013-index.md`. |

### Implementation References

| File | Description |
|------|-------------|
| `putting-2007.txt` (Appendix) | Complete Haskell implementation of the higher-rank type inference algorithm (Sections 5-6 and Appendix A) |
| `putting2007-reading.md` | Detailed reading notes covering bidirectional type checking, rank-N polymorphism, and subsumption |
| `fan-xu-xie-2025-reading.md` | Comprehensive notes on level-based inference, including the level invariant, promotion rules, and Coq mechanization |

### Local Research Documents

| File | Description |
|------|-------------|
| `system-sb.tex` | Local development: System SB type system formalization (syntax and typing rules) |
| `system-sb-visible-type-application.tex` | Extension of System SB with visible type application |
| `VALIDATION-REPORT.md` | Validation results and testing outcomes |
| `unify-call-graph.md` | Documentation of unification algorithm call graph |

### Other Type System Resources

| File | Description |
|------|-------------|
| `CoreSyn.ott`, `CoreLint.ott` | Ott specifications for GHC Core syntax and lint rules |
| `ghc-core-spec.mng` | GHC Core specification document |
| `ftv-examples.hs` | Examples of free type variable calculations |
| `let-trace.hs` | Tracing examples for let-binding inference |
| `system-sb-2016-reference.hs` | Reference Haskell implementation for System SB |
| `putting-2007-implementation.hs` | Extracted implementation from Putting 2007 |
| `idris2-recursive-types.md` | Notes on recursive types in Idris 2 |
| `lean4-recursive-types.md`, `lean4-docstring-analysis.md` | Lean 4 type system analysis |

### Navigation Tips

- **Index files** (`*-index.md`): Line-number references for jumping to specific sections in the text files using `sed -n 'start,endp' filename.txt`
- **Reading files** (`*-reading.md`): Detailed notes and summaries of the papers
- **Text files** (`*.txt`): Extracted text from papers for searching and reference

- [ ] How does Quick Look impredicativity work in elab3?
- [ ] Pattern matching exhaustiveness checking integration
- [ ] Typeclass constraint handling (elab2 had this)
- [ ] Core linter pass

---

## 2007 vs 2025 Paper Comparison: Key Differences

### Prenex Invariant

**2007 (Putting):** Does NOT guarantee inference produces prenex rho types.
- They chose `inst1` (shallow instantiation) over `deep-inst1` (would guarantee prenex)
- From lines 1773-1781: "Adopting this rule would give an interesting invariant... However, there seems to be no other reason to complicate inst1, so we use the simpler version."

**2025 (Fan-Xu-Xie):** Inference produces sigma types directly.
- `Γ p Σ ⊢ₙ e ⇒ σ ⊣ Δ` — inference judgment produces polymorphic σ
- `Γ p Σ ⊢ₙ e ⇐ σ ⊣ Δ` — checking judgment takes sigma, skolemizes via `at-forall`

### Instantiation Rules

**2007 inst rules:**
- `inst1` (infer): Instantiate outermost ∀s with fresh meta vars → `WpTyApp`
- `inst2` (check): Calls `dsk` subsumption, expecting rho on right side

**2025 instantiation:**
- `as-forallL`: Instantiate ∀ with fresh unification var at current level
- `pr-forallPos`: Promote under (+) — instantiate with meta at promotion level
- `pr-forallNeg`: Promote under (-) — instantiate with skolem at level+1

### Generalization

**2007:**
- `gen1` (poly infer): Let generalization — quantify free meta vars `ftv(ρ) - ftv(Γ)` → produces ∀a.ρ
- `gen2` (poly check): Skolemize σ, check body at n+1

**2025:**
- `at-let`: Generalization at let bindings — collects `fuvₙ₊₁(σ₁)` at n+1, quantifies with fresh type vars
- `at-forall`: Poly check — skolemizes the sigma type, increments level, checks body

### Where Subtyping (`<:`) Appears

**2025:** `<:` rules appear ONLY in checking mode:
- `at-tlamC`: Checking against ∀a.σ — subtyping required
- `at-sub`: First infers σ₁, then checks `σ₁ <: σ₂` — subtyping is the bridge

**Key insight:** The subtyping judgment (`as-solveL`, `as-solveR`) is what generates substitutions/unification:
- `as-solveL`: Unifies `𝛼̂ <: σ` — promotes σ, sets `𝛼̂ = τ`
- `as-solveR`: Unifies `σ <: 𝛼̂` — promotes σ, sets `𝛼̂ = τ`

So in 2025, checking mode is the "driver" that calls subtyping, which performs unification.

### Sigma Type Appearances

In 2007, sigma appears in only two places:
1. **AABS2** — User annotation `(e :: σ)` — supplies sigma directly
2. **var** — Left side of subsumption, but only calls `inst2` with rho on right, so it's safe

In 2025, inference naturally produces sigma types, and checking mode handles them via `at-forall` skolemization.

### Rule Correspondence Table

| 2007 Rule | 2025 Rule | Description |
|-----------|-----------|-------------|
| `inst1` | `as-forallL`, `pr-forallPos` | Instantiate ∀ with fresh metas |
| `inst2` + `dsk` | `as-solveL/R` + promotion | Subtype check with level-based unification |
| `gen2` (poly check) | `at-forall` | Skolemize σ, check body at n+1 |
| `gen1` (let) | `at-let` | Generalize free metas at let binding |
| `deep-inst1` (not chosen) | N/A | Would guarantee prenex, but 2007 rejected for simplicity |

### Key Insight: Checking as Driver

In 2025:
- **Inference** (`⇒`): Produces sigma types, but does NOT perform unification directly
- **Checking** (`⇐`): Calls `at-sub` which performs `σ₁ <: σ₂`, triggering `as-solveL/R` for unification
- This means **checking mode is the main driver for unification**, not inference

In 2007:
- Inference (`⊢⇑`): Produces rho types, uses `inst1` for instantiation
- Checking (`⊢⇓`): Uses `gen2` skolemization and `inst2` subsumption

---

## References

- "Putting 2007" - GHC's bidirectional type inference paper
- GHC User's Guide: Type inference

---

## Path Resolution Notes

File paths in this document are relative to the repository root and resolve as follows:

| Path Prefix | Resolves Relative To | Notes |
|-------------|---------------------|-------|
| `systemf/...` | `./` (repo root) | Project source files |
| `analysis/...` | `./analysis/` or `./upstream/ghc/analysis/` | Check both locations |
| `compiler/GHC/...` | `./upstream/ghc/` | GHC upstream source files |
| `upstream/ghc/...` | `./` (repo root) | GHC upstream source files |

**Analysis directories:** Both `./analysis/` and `./upstream/ghc/analysis/` contain analysis documents. When looking up `analysis/TYPE_INFERENCE.md`, check `./upstream/ghc/analysis/TYPE_INFERENCE.md` first.
