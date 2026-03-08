-- Extracted from: Practical type inference for arbitrary-rank types
-- Peyton Jones, Vytiniotis, Weirich, Shields (2007)
-- Appendix A: Complete implementation in Haskell
-- This is the actual working code from the paper
--
-- Paper Reference: "Practical Type Inference for Arbitrary-Rank Types"
-- Journal of Functional Programming, 2007
-- Section 4: The type system and inference algorithm
-- Appendix A: Complete implementation
--
-- To run: cabal run putting-2007-implementation.hs

{-# LANGUAGE GADTs, RankNTypes, FlexibleContexts #-}

{- cabal:
build-depends: base
            , containers
            , pretty
-}

module Main where

import Data.IORef (IORef, newIORef, readIORef, writeIORef)
import Data.List ((\\), nub, elem)
import Data.Maybe (fromMaybe)
import qualified Data.Map as Map
import Text.PrettyPrint (Doc, text, nest, vcat, quotes, (<+>), ($$))


-- ============================================================
-- A.3 BasicTypes.hs - Type definitions
-- ============================================================
-- Paper Section 4.2: Syntax
-- σ ::= ∀a.ρ    (Polymorphic types)
-- ρ ::= τ | σ→σ'  (Rho types - no top-level forall)
-- τ ::= a | τ→τ   (Monomorphic types)

type Name = String
type Sigma = Type      -- ^ σ: Polymorphic type (may have outer ∀)
type Rho = Type        -- ^ ρ: Rho type (no top-level ∀, but can contain σ in arrows)
type Tau = Type        -- ^ τ: Monomorphic type (no ∀ at all)

data Term = Var Name
          | Lit Int
          | App Term Term
          | Lam Name Term
          | ALam Name Sigma Term   -- ^ \x::σ.t : annotated lambda
          | Let Name Term Term
          | Ann Term Sigma         -- ^ (t :: σ) : type annotation
          deriving (Show)

data Type = ForAll [TyVar] Rho    -- ^ ∀a.ρ : polymorphic type
          | Fun Type Type         -- ^ σ₁ → σ₂ : function type
          | TyCon TyCon           -- ^ Type constant (Int, etc.)
          | TyVar TyVar           -- ^ Type variable
          | MetaTv MetaTv         -- ^ Meta type variable (unification variable)
          deriving (Show)

data TyVar = BoundTv String       -- ^ Bound type variable (from forall)
           | SkolemTv String Uniq -- ^ Skolem constant (rigid, existential)
           deriving (Eq, Show)

type TyCon = String
type TyRef = IORef (Maybe Tau)    -- ^ Mutable reference for unification
type Uniq = Int

data MetaTv = Meta Uniq TyRef     -- ^ Flexible type variable for inference
            deriving (Eq)

instance Show MetaTv where
    show (Meta u _) = "t" ++ show u

-- Type constructors
intType :: Tau
intType = TyCon "Int"

(-->) :: Type -> Type -> Type
arg --> res = Fun arg res

-- ============================================================
-- A.2 TcMonad.hs - The type checking monad
-- ============================================================
-- Paper Section 5.2: The monad
-- The Tc monad provides:
-- 1. Mutable state for unification variables (via IORef)
-- 2. Type environment for term variables
-- 3. Error handling

data TcEnv = TcEnv { uniqs :: IORef Uniq      -- ^ Fresh name supply
                   , var_env :: Map.Map Name Sigma }  -- ^ Type environment Γ

newtype Tc a = Tc (TcEnv -> IO (Either Doc a))

unTc :: Tc a -> (TcEnv -> IO (Either Doc a))
unTc (Tc a) = a

instance Functor Tc where
    fmap f m = m >>= return . f

instance Applicative Tc where
    pure x = Tc (\_env -> return (Right x))
    mf <*> mx = do { f <- mf; x <- mx; return (f x) }

instance Monad Tc where
    m >>= k = Tc (\env -> do
        r1 <- unTc m env
        case r1 of
            Left err -> return (Left err)
            Right v -> unTc (k v) env)

failTc :: Doc -> Tc a
failTc d = Tc (\_env -> return (Left d))

check :: Bool -> Doc -> Tc ()
check True _ = return ()
check False d = failTc d

runTc :: [(Name,Sigma)] -> Tc a -> IO (Either Doc a)
runTc binds (Tc tc) = do
    ref <- newIORef 0
    let env = TcEnv { uniqs = ref, var_env = Map.fromList binds }
    tc env

lift :: IO a -> Tc a
lift st = Tc (\_env -> do { r <- st; return (Right r) })

-- Reference cells for Expected type (bidirectional checking)
newTcRef :: a -> Tc (IORef a)
newTcRef v = lift (newIORef v)

readTcRef :: IORef a -> Tc a
readTcRef r = lift (readIORef r)

writeTcRef :: IORef a -> a -> Tc ()
writeTcRef r v = lift (writeIORef r v)

-- Environment manipulation
getEnv :: Tc (Map.Map Name Sigma)
getEnv = Tc (\ env -> return (Right (var_env env)))

extendVarEnv :: Name -> Sigma -> Tc a -> Tc a
extendVarEnv var ty (Tc m) = Tc (\env -> m (extend env))
    where
    extend env = env { var_env = Map.insert var ty (var_env env) }

lookupVar :: Name -> Tc Sigma
lookupVar n = do
    env <- getEnv
    case Map.lookup n env of
        Just ty -> return ty
        Nothing -> failTc (text "Not in scope:" <+> quotes (text n))

getEnvTypes :: Tc [Type]
getEnvTypes = do
    env <- getEnv
    return (Map.elems env)

-- Meta type variables
newTyVarTy :: Tc Tau
newTyVarTy = do
    tv <- newMetaTyVar
    return (MetaTv tv)

newMetaTyVar :: Tc MetaTv
newMetaTyVar = do
    uniq <- newUnique
    tref <- newTcRef Nothing
    return (Meta uniq tref)

newSkolemTyVar :: TyVar -> Tc TyVar
newSkolemTyVar tv = do
    uniq <- newUnique
    return (SkolemTv (tyVarName tv) uniq)

readTv :: MetaTv -> Tc (Maybe Tau)
readTv (Meta _ ref) = readTcRef ref

writeTv :: MetaTv -> Tau -> Tc ()
writeTv (Meta _ ref) ty = writeTcRef ref (Just ty)

newUnique :: Tc Uniq
newUnique = Tc (\(TcEnv {uniqs = ref}) -> do
    uniq <- readIORef ref
    writeIORef ref (uniq + 1)
    return (Right uniq))

-- ============================================================
-- Instantiation and Skolemisation
-- ============================================================
-- Paper Section 4.5: Prenex conversion and skolemization
-- pr(σ) = ∀ā.ρ  -- Convert to weak prenex form

-- | Instantiate top-level foralls with fresh meta variables
-- Used in: VAR rule (Fig 8), SPEC rule (Fig 8)
instantiate :: Sigma -> Tc Rho
instantiate (ForAll tvs ty) = do
    tvs' <- mapM (\_ -> newMetaTyVar) tvs
    return (substTy tvs (map MetaTv tvs') ty)
instantiate ty = return ty

-- | Weak prenex conversion: pr(σ) = ∀ā.ρ
-- Returns skolem constants and the rho body
-- Used in: GEN2 rule, DEEP-SKOL rule (Fig 8)
-- 
-- PRPOLY: pr(∀ā.σ) = ∀āb̄.ρ  where pr(σ) = ∀b̄.ρ
-- PRFUN:  pr(σ₁→σ₂) = ∀ā.(σ₁→ρ₂)  where pr(σ₂) = ∀ā.ρ₂, ā ∉ fv(σ₁)
-- PRMONO: pr(τ) = τ
skolemise :: Sigma -> Tc ([TyVar], Rho)
skolemise (ForAll tvs ty) = do           -- Rule PRPOLY
    sks1 <- mapM newSkolemTyVar tvs
    (sks2, ty') <- skolemise (substTy tvs (map TyVar sks1) ty)
    return (sks1 ++ sks2, ty')
skolemise (Fun arg_ty res_ty) = do       -- Rule PRFUN
    (sks, res_ty') <- skolemise res_ty
    return (sks, Fun arg_ty res_ty')
skolemise ty = return ([], ty)           -- Rule PRMONO

-- ============================================================
-- Quantification (GEN1)
-- ============================================================
-- Paper Section 4.7.3: Instantiation and generalisation
-- GEN1: If Γ ⊢⇑ t : ρ and ā = ftv(ρ) - ftv(Γ), then Γ ⊢⇑^poly t : ∀ā.ρ

-- | Generalize: quantify over free vars not in environment
-- Implements GEN1 rule (Figure 8)
quantify :: [MetaTv] -> Rho -> Tc Sigma
quantify tvs ty = do
    mapM_ bind (tvs `zip` new_bndrs)
    ty' <- zonkType ty
    return (ForAll new_bndrs ty')
    where
    used_bndrs = tyVarBndrs ty
    new_bndrs = take (length tvs) (allBinders \\ used_bndrs)
    bind (tv, name) = writeTv tv (TyVar name)

allBinders :: [TyVar]
allBinders = [ BoundTv [x] | x <- ['a'..'z'] ] ++
             [ BoundTv (x : show i) | i <- [1 :: Integer ..], x <- ['a'..'z']]

-- ============================================================
-- Free and meta type variables
-- ============================================================

-- | Get all meta type variables (flexible vars) in types
-- Used in GEN1 to find generalizable variables
getMetaTyVars :: [Type] -> Tc [MetaTv]
getMetaTyVars tys = do
    tys' <- mapM zonkType tys
    return (metaTvs tys')

-- | Get all free type variables (bound vars) in types
-- Used in GEN2 to check skolem escape
getFreeTyVars :: [Type] -> Tc [TyVar]
getFreeTyVars tys = do
    tys' <- mapM zonkType tys
    return (freeTyVars tys')

-- ============================================================
-- Zonking - Eliminate any substitutions in the type
-- ============================================================
-- Follows substitution links to get the concrete type

zonkType :: Type -> Tc Type
zonkType (ForAll ns ty) = do
    ty' <- zonkType ty
    return (ForAll ns ty')
zonkType (Fun arg res) = do
    arg' <- zonkType arg
    res' <- zonkType res
    return (Fun arg' res')
zonkType (TyCon tc) = return (TyCon tc)
zonkType (TyVar n) = return (TyVar n)
zonkType (MetaTv tv) = do
    mb_ty <- readTv tv
    case mb_ty of
        Nothing -> return (MetaTv tv)
        Just ty -> do
            ty' <- zonkType ty
            writeTv tv ty'
            return ty'

-- ============================================================
-- Unification
-- ============================================================
-- Paper Section 5.6: Subsumption checking
-- Robinson unification algorithm with occurs check

-- | Standard unification for monomorphic types
-- Used in MONO rule (Figure 8)
unify :: Tau -> Tau -> Tc ()
unify ty1 ty2
    | badType ty1 || badType ty2
    = failTc (text "Panic! Unexpected types in unification:" <+> text (show ty1) <+> text (show ty2))
unify (TyVar tv1) (TyVar tv2) | tv1 == tv2 = return ()
unify (MetaTv tv1) (MetaTv tv2) | tv1 == tv2 = return ()
unify (MetaTv tv) ty = unifyVar tv ty
unify ty (MetaTv tv) = unifyVar tv ty
unify (Fun arg1 res1) (Fun arg2 res2) = do
    unify arg1 arg2
    unify res1 res2
unify (TyCon tc1) (TyCon tc2) | tc1 == tc2 = return ()
unify ty1 ty2 = failTc (text "Cannot unify types:" <+> text (show ty1) <+> text "vs" <+> text (show ty2))

unifyVar :: MetaTv -> Tau -> Tc ()
unifyVar tv1 ty2 = do
    mb_ty1 <- readTv tv1
    case mb_ty1 of
        Just ty1 -> unify ty1 ty2
        Nothing -> unifyUnboundVar tv1 ty2

unifyUnboundVar :: MetaTv -> Tau -> Tc ()
unifyUnboundVar tv1 ty2@(MetaTv tv2) = do
    mb_ty2 <- readTv tv2
    case mb_ty2 of
        Just ty2' -> unify (MetaTv tv1) ty2'
        Nothing -> writeTv tv1 ty2
unifyUnboundVar tv1 ty2 = do
    tvs2 <- getMetaTyVars [ty2]
    if tv1 `elem` tvs2 then
        occursCheckErr tv1 ty2
    else
        writeTv tv1 ty2

-- | Expect function type: either it is one, or create fresh vars
-- Used in APP, ABS1, ABS2, AABS1, AABS2 rules (Figure 8)
unifyFun :: Rho -> Tc (Sigma, Rho)
unifyFun (Fun arg res) = return (arg, res)
unifyFun tau = do
    arg_ty <- newTyVarTy
    res_ty <- newTyVarTy
    unify tau (arg_ty --> res_ty)
    return (arg_ty, res_ty)

occursCheckErr :: MetaTv -> Tau -> Tc ()
occursCheckErr tv ty = failTc (text "Occurs check for" <+> quotes (text (show tv)) <+> text "in:" <+> text (show ty))

badType :: Tau -> Bool
badType (TyVar (BoundTv _)) = True
badType _ = False

-- ============================================================
-- Type substitution utilities
-- ============================================================

tyVarName :: TyVar -> String
tyVarName (BoundTv n) = n
tyVarName (SkolemTv n _) = n

tyVarBndrs :: Type -> [TyVar]
tyVarBndrs ty = nub (bndrs ty)
    where
    bndrs (ForAll tvs ty) = tvs ++ bndrs ty
    bndrs (Fun arg res) = bndrs arg ++ bndrs res
    bndrs _ = []

metaTvs :: [Type] -> [MetaTv]
metaTvs tys = nub (concatMap metaTvsInType tys)
    where
    metaTvsInType (MetaTv tv) = [tv]
    metaTvsInType (Fun arg res) = metaTvsInType arg ++ metaTvsInType res
    metaTvsInType (ForAll _ ty) = metaTvsInType ty
    metaTvsInType _ = []

freeTyVars :: [Type] -> [TyVar]
freeTyVars tys = nub (concatMap freeTyVarsInType tys)
    where
    freeTyVarsInType (TyVar tv) = [tv]
    freeTyVarsInType (MetaTv _) = []
    freeTyVarsInType (Fun arg res) = freeTyVarsInType arg ++ freeTyVarsInType res
    freeTyVarsInType (ForAll tvs ty) = freeTyVarsInType ty \\ tvs
    freeTyVarsInType _ = []

substTy :: [TyVar] -> [Type] -> Type -> Type
substTy tvs tys ty = subst ty
    where
    env = zip tvs tys
    subst (ForAll tvs' ty') = ForAll tvs' (subst ty')
    subst (Fun arg res) = Fun (subst arg) (subst res)
    subst ty@(TyVar tv) = fromMaybe ty (lookup tv env)
    subst ty = ty

-- ============================================================
-- A.1 TcTerm.hs - Type inference
-- ============================================================
-- Paper Section 4.7: The bidirectional type system
-- Figure 8: Bidirectional version of Odersky-Läufer

-- | Top-level type checking
-- Entry point: typecheck :: Term -> Tc Sigma
typecheck :: Term -> Tc Sigma
typecheck e = do
    ty <- inferSigma e
    zonkType ty

-- | Expected type for bidirectional checking
-- Infer: Create ref cell to hold inferred type
-- Check: Check against known type
-- Used throughout Figure 8 rules
data Expected a = Infer (IORef a) | Check a

-- | Check mode: Γ ⊢⇓ t : ρ
-- Push the type inward
-- See ABS2, AABS2 rules (Figure 8)
checkRho :: Term -> Rho -> Tc ()
checkRho expr ty = tcRho expr (Check ty)

-- | Inference mode: Γ ⊢⇑ t : ρ
-- Pull type outward
-- See ABS1, AABS1 rules (Figure 8)
inferRho :: Term -> Tc Rho
inferRho expr = do
    ref <- newTcRef (error "inferRho: empty result")
    tcRho expr (Infer ref)
    readTcRef ref

-- | Main bidirectional checker
-- Implements all rules from Figure 8:
-- INT, VAR, ABS1, ABS2, AABS1, AABS2, APP, ANNOT, LET
--
-- Invariant: For Check mode, ρ is in weak-prenex form
tcRho :: Term -> Expected Rho -> Tc ()

-- INT rule (Figure 8)
-- Γ ⊢δ n : Int  for any δ
tcRho (Lit _) exp_ty = instSigma intType exp_ty

-- VAR rule (Figure 8)
-- Γ, x:σ ⊢δ x : ρ  where ⊢^inst_δ σ ≤ ρ
-- Look up variable, instantiate its polymorphic type
tcRho (Var v) exp_ty = do
    v_sigma <- lookupVar v
    instSigma v_sigma exp_ty

-- APP rule (Figure 8)
-- Γ ⊢⇑ t : σ→σ'    Γ ⊢^poly_⇓ u : σ    ⊢^inst_δ σ' ≤ ρ
-- ----------------------------------------------------
--             Γ ⊢δ t u : ρ
--
-- Inference: infer function type, poly-check argument, inst result
-- Checking: same (note: always infers function type, ignores expected ρ)
tcRho (App fun arg) exp_ty = do
    fun_ty <- inferRho fun              -- Infer t : σ→σ'
    (arg_ty, res_ty) <- unifyFun fun_ty -- Extract σ, σ'
    checkSigma arg arg_ty               -- Poly-check u : σ
    instSigma res_ty exp_ty             -- Inst σ' ≤ ρ

-- ABS2 rule (Figure 8) - Checking mode
-- Γ, x:σ_a ⊢^poly_⇓ t : σ_r
-- --------------------------------
-- Γ ⊢⇓ λx.t : σ_a → σ_r
--
-- Check λ against arrow type, bind x at domain type, check body
tcRho (Lam var body) (Check exp_ty) = do
    (var_ty, body_ty) <- unifyFun exp_ty  -- Expect σ_a → σ_r
    extendVarEnv var var_ty (checkRho body body_ty)

-- ABS1 rule (Figure 8) - Inference mode
-- Γ, x:τ ⊢⇑ t : ρ
-- ------------------------
-- Γ ⊢⇑ λx.t : τ → ρ
--
-- Infer: fresh mono var for arg, infer body, return arrow
tcRho (Lam var body) (Infer ref) = do
    var_ty <- newTyVarTy                     -- Fresh τ
    body_ty <- extendVarEnv var var_ty (inferRho body)
    writeTcRef ref (var_ty --> body_ty)      -- Return τ → ρ

-- AABS2 rule (Figure 8) - Checking mode
-- ⊢^dsk σ_a ≤ σ_x    Γ, x:σ_x ⊢^poly_⇓ t : σ_r
-- -----------------------------------------------
-- Γ ⊢⇓ λ(x::σ_x).t : σ_a → σ_r
--
-- Check annotated λ: subtype check + poly-check body
tcRho (ALam var var_ty body) (Check exp_ty) = do
    (arg_ty, body_ty) <- unifyFun exp_ty     -- Get σ_a, σ_r
    subsCheck arg_ty var_ty                  -- σ_a ≤ σ_x (contravariant!)
    extendVarEnv var var_ty (checkRho body body_ty)

-- AABS1 rule (Figure 8) - Inference mode
-- Γ, x:σ ⊢⇑ t : ρ
-- --------------------------
-- Γ ⊢⇑ λ(x::σ).t : σ → ρ
--
-- Infer annotated λ: extend with annotation, infer body
tcRho (ALam var var_ty body) (Infer ref) = do
    body_ty <- extendVarEnv var var_ty (inferRho body)
    writeTcRef ref (var_ty --> body_ty)

-- LET rule (Figure 8)
-- Γ ⊢^poly_⇑ u : σ    Γ, x:σ ⊢δ t : ρ
-- ----------------------------------
-- Γ ⊢δ let x=u in t : ρ
--
-- Poly-synth RHS, extend env, check body
tcRho (Let var rhs body) exp_ty = do
    var_ty <- inferSigma rhs                 -- GEN1: infer σ
    extendVarEnv var var_ty (tcRho body exp_ty)

-- ANNOT rule (Figure 8)
-- Γ ⊢^poly_⇓ t : σ    ⊢^inst_δ σ ≤ ρ
-- ----------------------------------
-- Γ ⊢δ (t :: σ) : ρ
--
-- Check against annotation, inst to expected
tcRho (Ann body ann_ty) exp_ty = do
    checkSigma body ann_ty                   -- Poly-check t : σ
    instSigma ann_ty exp_ty                  -- Inst σ ≤ ρ

-- ============================================================
-- Polymorphic generalization: GEN1, GEN2
-- ============================================================
-- Paper Section 4.7.3, Figure 8

-- | GEN1 rule (Figure 8)
-- Γ ⊢⇑ t : ρ    ā = ftv(ρ) - ftv(Γ)
-- ----------------------------------
-- Γ ⊢⇑^poly t : ∀ā.ρ
--
-- Generalize: quantify over free vars not in environment
inferSigma :: Term -> Tc Sigma
inferSigma e = do
    exp_ty <- inferRho e
    env_tys <- getEnvTypes
    env_tvs <- getMetaTyVars env_tys
    res_tvs <- getMetaTyVars [exp_ty]
    let forall_tvs = res_tvs \\ env_tvs
    quantify forall_tvs exp_ty

-- | GEN2 rule (Figure 8)
-- pr(σ) = ∀ā.ρ    ā ∉ ftv(Γ)    Γ ⊢⇓ t : ρ
-- -----------------------------------------
-- Γ ⊢⇓^poly t : σ
--
-- Skolemize expected type, check against body, verify no escape
checkSigma :: Term -> Sigma -> Tc ()
checkSigma expr sigma = do
    (skol_tvs, rho) <- skolemise sigma       -- pr(σ) = ∀ā.ρ
    checkRho expr rho                        -- Check t : ρ
    env_tys <- getEnvTypes
    esc_tvs <- getFreeTyVars (sigma : env_tys)
    let bad_tvs = filter (\x -> x `elem` esc_tvs) skol_tvs
    check (null bad_tvs) (text "Type not polymorphic enough")

-- ============================================================
-- Subsumption checking: DEEP-SKOL, SPEC, FUN, MONO
-- ============================================================
-- Paper Section 4.6, Figure 8
-- ⊢^dsk : Deep skolemization for subsumption
-- ⊢^dsk* : Deep skolemization to rho type

-- | DEEP-SKOL rule (Figure 8)
-- pr(σ₂) = ∀ā.ρ    ā ∉ ftv(σ₁)    ⊢^dsk* σ₁ ≤ ρ
-- ----------------------------------------------
-- ⊢^dsk σ₁ ≤ σ₂
--
-- Check that σ₁ is at least as polymorphic as σ₂
subsCheck :: Sigma -> Sigma -> Tc ()
subsCheck sigma1 sigma2 = do
    (skol_tvs, rho2) <- skolemise sigma2     -- Skolemize σ₂
    subsCheckRho sigma1 rho2                 -- Check σ₁ ≤ ρ₂
    esc_tvs <- getFreeTyVars [sigma1, sigma2]
    let bad_tvs = filter (\x -> x `elem` esc_tvs) skol_tvs
    check (null bad_tvs) (text "Subsumption check failed")

-- | Deep skolemization to rho type: ⊢^dsk*
-- Implements SPEC, FUN, MONO rules (Figure 8)
subsCheckRho :: Sigma -> Rho -> Tc ()

-- SPEC rule (Figure 8)
-- ⊢^dsk* [ā↦τ]ρ₁ ≤ ρ₂
-- --------------------
-- ⊢^dsk* ∀ā.ρ₁ ≤ ρ₂
--
-- Instantiate outer foralls and continue
subsCheckRho sigma1@(ForAll _ _) rho2 = do
    rho1 <- instantiate sigma1
    subsCheckRho rho1 rho2

-- FUN rules (Figure 8) - function subsumption
-- ⊢^dsk σ₃ ≤ σ₁    ⊢^dsk* σ₂ ≤ σ₄
-- --------------------------------
-- ⊢^dsk* (σ₁→σ₂) ≤ (σ₃→σ₄)
-- Note: contravariant in argument!
subsCheckRho rho1 (Fun a2 r2) = do
    (a1, r1) <- unifyFun rho1
    subsCheckFun a1 r1 a2 r2

subsCheckRho (Fun a1 r1) rho2 = do
    (a2, r2) <- unifyFun rho2
    subsCheckFun a1 r1 a2 r2

-- MONO rule (Figure 8)
-- Unify monomorphic types
subsCheckRho tau1 tau2 = unify tau1 tau2

-- | Helper for function subsumption
-- Contravariant in argument, covariant in result
subsCheckFun :: Sigma -> Rho -> Sigma -> Rho -> Tc ()
subsCheckFun a1 r1 a2 r2 = do
    subsCheck a2 a1      -- σ₃ ≤ σ₁ (contravariant)
    subsCheckRho r1 r2   -- σ₂ ≤ σ₄ (covariant)

-- ============================================================
-- Instantiation: INST1, INST2
-- ============================================================
-- Paper Section 4.7.3, Figure 8
-- ⊢^inst_δ : Instantiation judgment

-- | INST2 rule (Figure 8) - Checking mode
-- ⊢^dsk σ ≤ ρ
-- -----------
-- ⊢^inst_⇓ σ ≤ ρ
--
-- Subsumption check in instantiation
instSigma :: Sigma -> Expected Rho -> Tc ()
instSigma t1 (Check t2) = subsCheckRho t1 t2

-- | INST1 rule (Figure 8) - Inference mode
-- ------------------------
-- ⊢^inst_⇑ ∀ā.ρ ≤ [ā↦τ̄]ρ
--
-- Instantiate with fresh meta variables
instSigma t1 (Infer r) = do
    t1' <- instantiate t1
    writeTcRef r t1'

-- ============================================================
-- End of Implementation
-- ============================================================
-- 
-- Key design patterns from the paper:
--
-- 1. Bidirectional checking: synthesis (⊢⇑) vs checking (⊢⇓)
--    - Use checking when type is known (annotations, applications)
--    - Use synthesis when type must be inferred (literals, variables)
--
-- 2. Weak prenex conversion (skolemise)
--    - Hoists quantifiers to top level
--    - Enables algorithmic subsumption checking
--
-- 3. Deep skolemization
--    - Handles higher-rank polymorphism
--    - Contravariant in function arguments
--
-- 4. Meta type variables
--    - Mutable references for unification
--    - Zonking to eliminate indirections
--
-- References:
-- - Paper: Peyton Jones et al., JFP 2007
-- - Figure 8: Bidirectional type rules
-- - Appendix A: This implementation
main :: IO ()
main = return ()
