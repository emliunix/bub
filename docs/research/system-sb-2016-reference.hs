-- System SB 2016 reference implementation
-- Based on Eisenberg et al., "Visible Type Application" (2016)
-- and the 2007 Peyton Jones et al. executable reference.
--
-- This is intentionally a compact, single-file checker for the
-- core System SB ideas:
--   * split judgments for phi/upsilon/sigma
--   * lazy instantiation of specified foralls
--   * visible type application (@)
--   * deep-skolem-style checking against specified polytypes
--   * scoped type variables through annotations
--
-- Simplifications relative to the paper:
--   * no parser: examples are constructed directly as ASTs
--   * no explicit elaboration target language
--   * generalized quantifiers only appear at the outer sigma level
--   * the executable focuses on the main checking algorithm and uses
--     <=_dsk directly at checking boundaries
--
-- To run:
--   ~/.ghcup/bin/cabal run --allow-newer docs/research/system-sb-2016-reference.hs

{-# LANGUAGE FlexibleContexts #-}

{- cabal:
build-depends: base
             , containers
-}

module Main where

import Control.Monad (unless, when)
import Data.IORef (IORef, newIORef, readIORef, writeIORef)
import Data.List ((\\), intercalate, isInfixOf, nub)
import Data.Maybe (fromMaybe)
import qualified Data.Map as Map

type Name = String
type Sigma = Type
type Upsilon = Type
type Rho = Type
type Phi = Type
type Tau = Type
type Uniq = Int

data Term
    = Var Name
    | Lit Int
    | Lam Name Term
    | App Term Term
    | TApp Term Type
    | Let Name Term Term
    | Ann Term Type
    deriving (Eq, Show)

data Type
    = GenForAll [TyVar] Type
    | SpecForAll [TyVar] Type
    | Fun Type Type
    | TyCon String
    | TyVar TyVar
    | MetaTv MetaTv

data TyVar
    = BoundTv Name
    | SkolemTv Name Uniq
    deriving (Eq, Ord)

type TyRef = IORef (Maybe Tau)

data MetaTv = Meta Uniq TyRef

instance Eq MetaTv where
    Meta u1 _ == Meta u2 _ = u1 == u2

instance Eq Type where
    GenForAll as t1 == GenForAll bs t2 = as == bs && t1 == t2
    SpecForAll as t1 == SpecForAll bs t2 = as == bs && t1 == t2
    Fun a1 r1 == Fun a2 r2 = a1 == a2 && r1 == r2
    TyCon c1 == TyCon c2 = c1 == c2
    TyVar v1 == TyVar v2 = v1 == v2
    MetaTv v1 == MetaTv v2 = v1 == v2
    _ == _ = False

instance Show MetaTv where
    show (Meta u _) = "_" ++ show u

instance Show TyVar where
    show (BoundTv n) = n
    show (SkolemTv n u) = n ++ "#" ++ show u

instance Show Type where
    show = prettyType

infixr 5 -->
(-->) :: Type -> Type -> Type
(-->) = Fun

data TcEnv = TcEnv
    { uniqs :: IORef Uniq
    , varEnv :: Map.Map Name Sigma
    , tyEnv :: Map.Map Name Type
    }

newtype Tc a = Tc {unTc :: TcEnv -> IO (Either String a)}

instance Functor Tc where
    fmap f m = m >>= (pure . f)

instance Applicative Tc where
    pure x = Tc (\_ -> pure (Right x))
    mf <*> mx = do
        f <- mf
        x <- mx
        pure (f x)

instance Monad Tc where
    m >>= k = Tc $ \env -> do
        r <- unTc m env
        case r of
            Left err -> pure (Left err)
            Right x -> unTc (k x) env

failTc :: String -> Tc a
failTc msg = Tc (\_ -> pure (Left msg))

liftTc :: IO a -> Tc a
liftTc action = Tc (\_ -> Right <$> action)

ensure :: Bool -> String -> Tc ()
ensure cond msg = unless cond (failTc msg)

runTc :: [(Name, Sigma)] -> Tc a -> IO (Either String a)
runTc binds m = do
    uniqRef <- newIORef 0
    let env = TcEnv {uniqs = uniqRef, varEnv = Map.fromList binds, tyEnv = Map.empty}
    unTc m env

newUnique :: Tc Uniq
newUnique = Tc $ \TcEnv {uniqs = ref} -> do
    u <- readIORef ref
    writeIORef ref (u + 1)
    pure (Right u)

newTcRef :: a -> Tc (IORef a)
newTcRef = liftTc . newIORef

readTcRef :: IORef a -> Tc a
readTcRef = liftTc . readIORef

writeTcRef :: IORef a -> a -> Tc ()
writeTcRef ref = liftTc . writeIORef ref

extendVarEnv :: Name -> Sigma -> Tc a -> Tc a
extendVarEnv x ty (Tc m) = Tc $ \env ->
    m env {varEnv = Map.insert x ty (varEnv env)}

extendTyEnv :: [(Name, Type)] -> Tc a -> Tc a
extendTyEnv pairs (Tc m) = Tc $ \env ->
    m env {tyEnv = Map.union (Map.fromList pairs) (tyEnv env)}

getVarEnv :: Tc (Map.Map Name Sigma)
getVarEnv = Tc (\env -> pure (Right (varEnv env)))

getTyEnv :: Tc (Map.Map Name Type)
getTyEnv = Tc (\env -> pure (Right (tyEnv env)))

lookupVar :: Name -> Tc Sigma
lookupVar x = do
    env <- getVarEnv
    case Map.lookup x env of
        Just ty -> pure ty
        Nothing -> failTc ("not in scope: " ++ x)

getEnvTypes :: Tc [Type]
getEnvTypes = Map.elems <$> getVarEnv

newMetaTyVar :: Tc MetaTv
newMetaTyVar = do
    u <- newUnique
    ref <- newTcRef Nothing
    pure (Meta u ref)

newTyVarTy :: Tc Tau
newTyVarTy = MetaTv <$> newMetaTyVar

freshSkolem :: TyVar -> Tc TyVar
freshSkolem tv = do
    u <- newUnique
    pure (SkolemTv (tyVarName tv) u)

readTv :: MetaTv -> Tc (Maybe Tau)
readTv (Meta _ ref) = readTcRef ref

writeTv :: MetaTv -> Tau -> Tc ()
writeTv (Meta _ ref) = writeTcRef ref . Just

tyVarName :: TyVar -> Name
tyVarName (BoundTv n) = n
tyVarName (SkolemTv n _) = n

prettyType :: Type -> String
prettyType = go False
  where
    go _ (TyCon c) = c
    go _ (TyVar v) = show v
    go _ (MetaTv v) = show v
    go p (Fun a r) =
        parensIf p (go True a ++ " -> " ++ go False r)
    go p (SpecForAll vs ty) =
        parensIf p ("forall " ++ unwords (map show vs) ++ ". " ++ go False ty)
    go p (GenForAll vs ty) =
        parensIf p ("forall{" ++ unwords (map show vs) ++ "}. " ++ go False ty)

    parensIf True s = "(" ++ s ++ ")"
    parensIf False s = s

prettyTerm :: Term -> String
prettyTerm (Var x) = x
prettyTerm (Lit n) = show n
prettyTerm (Lam x body) = "(\\" ++ x ++ " -> " ++ prettyTerm body ++ ")"
prettyTerm (App f x) = "(" ++ prettyTerm f ++ " " ++ prettyTerm x ++ ")"
prettyTerm (TApp e ty) = "(" ++ prettyTerm e ++ " @" ++ prettyType ty ++ ")"
prettyTerm (Let x e1 e2) =
    "(let " ++ x ++ " = " ++ prettyTerm e1 ++ " in " ++ prettyTerm e2 ++ ")"
prettyTerm (Ann e ty) = "(" ++ prettyTerm e ++ " :: " ++ prettyType ty ++ ")"

-- ------------------------------------------------------------
-- Type utilities
-- ------------------------------------------------------------

substTy :: [TyVar] -> [Type] -> Type -> Type
substTy tvs tys = go (zip tvs tys)
  where
    go env (GenForAll vs ty) =
        GenForAll vs (go (filter (\(v, _) -> v `notElem` vs) env) ty)
    go env (SpecForAll vs ty) =
        SpecForAll vs (go (filter (\(v, _) -> v `notElem` vs) env) ty)
    go env (Fun a r) = Fun (go env a) (go env r)
    go env ty@(TyVar v) = fromMaybe ty (lookup v env)
    go _ ty = ty

resolveScopedType :: Type -> Tc Type
resolveScopedType ty = do
    env <- getTyEnv
    pure (go env ty)
  where
    go tenv (GenForAll vs body) =
        GenForAll vs (go (dropBound tenv vs) body)
    go tenv (SpecForAll vs body) =
        SpecForAll vs (go (dropBound tenv vs) body)
    go tenv (Fun a r) = Fun (go tenv a) (go tenv r)
    go tenv (TyVar (BoundTv n)) = fromMaybe (TyVar (BoundTv n)) (Map.lookup n tenv)
    go _ ty' = ty'

    dropBound tenv vs = foldr (Map.delete . tyVarName) tenv vs

zonkType :: Type -> Tc Type
zonkType (GenForAll vs ty) = GenForAll vs <$> zonkType ty
zonkType (SpecForAll vs ty) = SpecForAll vs <$> zonkType ty
zonkType (Fun a r) = Fun <$> zonkType a <*> zonkType r
zonkType ty@(TyCon _) = pure ty
zonkType ty@(TyVar _) = pure ty
zonkType (MetaTv tv) = do
    mb <- readTv tv
    case mb of
        Nothing -> pure (MetaTv tv)
        Just ty -> do
            ty' <- zonkType ty
            writeTv tv ty'
            pure ty'

metaTvs :: [Type] -> [MetaTv]
metaTvs = nub . concatMap go
  where
    go (MetaTv tv) = [tv]
    go (Fun a r) = go a ++ go r
    go (GenForAll _ ty) = go ty
    go (SpecForAll _ ty) = go ty
    go _ = []

getMetaTyVars :: [Type] -> Tc [MetaTv]
getMetaTyVars tys = metaTvs <$> mapM zonkType tys

tyVarBinders :: Type -> [TyVar]
tyVarBinders = nub . go
  where
    go (GenForAll vs ty) = vs ++ go ty
    go (SpecForAll vs ty) = vs ++ go ty
    go (Fun a r) = go a ++ go r
    go _ = []

allBinders :: [TyVar]
allBinders =
    [BoundTv [c] | c <- ['a' .. 'z']]
        ++ [BoundTv (c : show i) | i <- [(1 :: Int) ..], c <- ['a' .. 'z']]

quantify :: [MetaTv] -> Type -> Tc Sigma
quantify tvs ty = do
    let used = tyVarBinders ty
        names = take (length tvs) (allBinders \\ used)
    mapM_ (uncurry writeMetaAsRigid) (zip tvs names)
    ty' <- zonkType ty
    pure (rebuildGen names ty')
  where
    writeMetaAsRigid tv v = writeTv tv (TyVar v)

rebuildGen :: [TyVar] -> Type -> Type
rebuildGen [] ty = ty
rebuildGen vs ty = GenForAll vs ty

rebuildSpec :: [TyVar] -> Type -> Type
rebuildSpec [] ty = ty
rebuildSpec vs ty = SpecForAll vs ty

prenex :: Upsilon -> ([TyVar], Rho)
prenex (SpecForAll vs ty) =
    let (more, rho) = prenex ty
     in (vs ++ more, rho)
prenex (Fun a r) =
    let (more, rho) = prenex r
     in (more, Fun a rho)
prenex ty = ([], ty)

skolemisePrenex :: Upsilon -> Tc ([(Name, Type)], Rho)
skolemisePrenex ty = do
    let (vs, rho) = prenex ty
    sks <- mapM freshSkolem vs
    let rho' = substTy vs (map TyVar sks) rho
        scope = zip (map tyVarName vs) (map TyVar sks)
    pure (scope, rho')

instantiateWithFreshMetas :: [TyVar] -> Type -> Tc Type
instantiateWithFreshMetas vs ty = do
    fresh <- mapM (const newTyVarTy) vs
    pure (substTy vs fresh ty)

instantiateGeneralized :: Sigma -> Tc Upsilon
instantiateGeneralized (GenForAll vs ty) = instantiateWithFreshMetas vs ty >>= instantiateGeneralized
instantiateGeneralized ty = pure ty

instantiateSpecifiedAll :: Upsilon -> Tc Phi
instantiateSpecifiedAll (SpecForAll vs ty) = instantiateWithFreshMetas vs ty >>= instantiateSpecifiedAll
instantiateSpecifiedAll ty = pure ty

instantiateForDsk :: Sigma -> Tc Type
instantiateForDsk (GenForAll vs ty) = instantiateWithFreshMetas vs ty >>= instantiateForDsk
instantiateForDsk (SpecForAll vs ty) = instantiateWithFreshMetas vs ty >>= instantiateForDsk
instantiateForDsk ty = pure ty

instantiateVisible :: Upsilon -> Type -> Tc Upsilon
instantiateVisible (SpecForAll [] ty) _ = pure ty
instantiateVisible (SpecForAll (v : vs) ty) arg =
    pure (rebuildSpec vs (substTy [v] [arg] ty))
instantiateVisible ty _ =
    failTc ("visible type application expects a specified forall, got " ++ prettyType ty)

isTau :: Type -> Bool
isTau (TyCon _) = True
isTau (TyVar _) = True
isTau (MetaTv _) = True
isTau (Fun a r) = isTau a && isTau r
isTau _ = False

-- ------------------------------------------------------------
-- Unification
-- ------------------------------------------------------------

unify :: Tau -> Tau -> Tc ()
unify t1 t2 = do
    a <- zonkType t1
    b <- zonkType t2
    unifyZonked a b

unifyZonked :: Tau -> Tau -> Tc ()
unifyZonked (TyVar v1) (TyVar v2)
    | v1 == v2 = pure ()
unifyZonked (MetaTv tv1) (MetaTv tv2)
    | tv1 == tv2 = pure ()
unifyZonked (MetaTv tv) ty = unifyVar tv ty
unifyZonked ty (MetaTv tv) = unifyVar tv ty
unifyZonked (Fun a1 r1) (Fun a2 r2) = unify a1 a2 >> unify r1 r2
unifyZonked (TyCon c1) (TyCon c2)
    | c1 == c2 = pure ()
unifyZonked ty1 ty2 =
    failTc ("cannot unify " ++ prettyType ty1 ++ " with " ++ prettyType ty2)

unifyVar :: MetaTv -> Tau -> Tc ()
unifyVar tv ty = do
    mb <- readTv tv
    case mb of
        Just ty' -> unify ty' ty
        Nothing -> bindUnboundMeta tv ty

bindUnboundMeta :: MetaTv -> Tau -> Tc ()
bindUnboundMeta tv ty@(MetaTv tv2) = do
    mb <- readTv tv2
    case mb of
        Just ty' -> unify (MetaTv tv) ty'
        Nothing -> writeTv tv ty
bindUnboundMeta tv ty = do
    metas <- getMetaTyVars [ty]
    if tv `elem` metas
        then failTc ("occurs check failed: " ++ show tv ++ " in " ++ prettyType ty)
        else writeTv tv ty

unifyFun :: Type -> Tc (Type, Type)
unifyFun ty = do
    ty' <- zonkType ty
    case ty' of
        Fun a r -> pure (a, r)
        MetaTv tv -> do
            mb <- readTv tv
            case mb of
                Just t -> unifyFun t
                Nothing -> do
                    a <- newTyVarTy
                    r <- newTyVarTy
                    writeTv tv (Fun a r)
                    pure (a, r)
        _ -> failTc ("expected a function type, got " ++ prettyType ty')

-- ------------------------------------------------------------
-- System SB judgments
-- ------------------------------------------------------------

typecheck :: Term -> Tc Sigma
typecheck = synthSigma

-- Γ ⊢sb e ⇒ φ
synthPhi :: Term -> Tc Phi
synthPhi (Lit _) = pure intType
synthPhi (Lam x body) = do
    argTy <- newTyVarTy
    bodyTy <- extendVarEnv x argTy (synthUpsilon body)
    pure (argTy --> bodyTy)
synthPhi term = synthUpsilon term >>= instantiateSpecifiedAll

-- Γ ⊢*sb e ⇒ υ
synthUpsilon :: Term -> Tc Upsilon
synthUpsilon (Var x) = lookupVar x >>= instantiateGeneralized
synthUpsilon (App fun arg) = do
    funTy <- synthPhi fun
    (argTy, resTy) <- unifyFun funTy
    checkUpsilon arg argTy
    pure resTy
synthUpsilon (TApp fun tyArg) = do
    tyArg' <- resolveScopedType tyArg >>= zonkType
    ensure (isTau tyArg') ("visible type argument must be monomorphic, got " ++ prettyType tyArg')
    funTy <- synthUpsilon fun
    instantiateVisible funTy tyArg'
synthUpsilon (Ann body annTy) = do
    annTy' <- resolveScopedType annTy
    checkUpsilon body annTy'
    pure annTy'
synthUpsilon (Let x rhs body) = do
    sigma <- synthSigma rhs
    extendVarEnv x sigma (synthUpsilon body)
synthUpsilon term = synthPhi term

-- Γ ⊢gensb e ⇒ σ
synthSigma :: Term -> Tc Sigma
synthSigma term = do
    upsilon <- synthUpsilon term
    envTys <- getEnvTypes
    envMetas <- getMetaTyVars envTys
    resMetas <- getMetaTyVars [upsilon]
    quantify (resMetas \\ envMetas) upsilon

-- Γ ⊢sb e ⇐ ρ
checkRho :: Term -> Rho -> Tc ()
checkRho (Let x rhs body) rho = do
    sigma <- synthSigma rhs
    extendVarEnv x sigma (checkRho body rho)
checkRho (Lam x body) rho = do
    (argTy, resTy) <- unifyFun rho
    extendVarEnv x argTy (checkUpsilon body resTy)
checkRho term rho = do
    inferred <- synthUpsilon term
    subsumeDsk inferred rho

-- Γ ⊢*sb e ⇐ υ
checkUpsilon :: Term -> Upsilon -> Tc ()
checkUpsilon term upsilon = do
    upsilon' <- resolveScopedType upsilon
    (scope, rho) <- skolemisePrenex upsilon'
    extendTyEnv scope (checkRho term rho)

-- σ1 <=dsk σ2
subsumeDsk :: Sigma -> Upsilon -> Tc ()
subsumeDsk sigma upsilon = do
    left <- instantiateForDsk sigma
    (_, rho) <- skolemisePrenex upsilon
    subsumeDskRho left rho

subsumeDskRho :: Type -> Rho -> Tc ()
subsumeDskRho sigma rho = do
    sigma' <- zonkType sigma
    rho' <- zonkType rho
    case (sigma', rho') of
        (_, Fun a2 r2) -> do
            (a1, r1) <- unifyFun sigma'
            subsumeDsk a2 a1
            subsumeDsk r1 r2
        (Fun a1 r1, _) -> do
            (a2, r2) <- unifyFun rho'
            subsumeDsk a2 a1
            subsumeDsk r1 r2
        _ -> unify sigma' rho'

-- ------------------------------------------------------------
-- Example suite
-- ------------------------------------------------------------

intType :: Type
intType = TyCon "Int"

boolType :: Type
boolType = TyCon "Bool"

tvar :: Name -> Type
tvar = TyVar . BoundTv

sforall :: [Name] -> Type -> Type
sforall names = SpecForAll (map BoundTv names)

gforall :: [Name] -> Type -> Type
gforall names = GenForAll (map BoundTv names)

identityAnn :: Term
identityAnn = Ann (Lam "x" (Var "x")) (sforall ["a"] (tvar "a" --> tvar "a"))

scopedAnnotation :: Term
scopedAnnotation =
    Ann
        (Lam "x" (Ann (Var "x") (tvar "a")))
        (sforall ["a"] (tvar "a" --> tvar "a"))

visibleTypeApplication :: Term
visibleTypeApplication =
    Let
        "sid"
        identityAnn
        (App (TApp (Var "sid") intType) (Lit 42))

generalizedVisibleTypeApplication :: Term
generalizedVisibleTypeApplication =
    Let
        "id"
        (Lam "x" (Var "x"))
        (App (TApp (Var "id") intType) (Lit 0))

applyToInt :: Term
applyToInt =
    Let
        "sid"
        identityAnn
        ( Let
            "applyToInt"
            (Lam "f" (App (Var "f") (Lit 0)))
            (App (Var "applyToInt") (Var "sid"))
        )

lazyLookupEnv :: [(Name, Sigma)]
lazyLookupEnv = [("sid", sforall ["a"] (tvar "a" --> tvar "a"))]

dskExampleLeft :: Type
dskExampleLeft = intType --> sforall ["a", "b"] (tvar "a" --> tvar "b")

dskExampleRight :: Type
dskExampleRight = intType --> sforall ["b"] (boolType --> tvar "b")

data Test
    = InferSigma Name [(Name, Sigma)] Term Type
    | InferUpsilon Name [(Name, Sigma)] Term Type
    | ExpectFailure Name [(Name, Sigma)] (Tc Type) String
    | ExpectDsk Name Type Type

tests :: [Test]
tests =
    [ InferSigma
        "generalizes an unannotated lambda to a generalized sigma"
        []
        (Lam "x" (Var "x"))
        (gforall ["a"] (tvar "a" --> tvar "a"))
    , InferUpsilon
        "lazy variable synthesis preserves specified forall"
        lazyLookupEnv
        (Var "sid")
        (sforall ["a"] (tvar "a" --> tvar "a"))
    , InferUpsilon
        "annotation scopes type variables over the term"
        []
        scopedAnnotation
        (sforall ["a"] (tvar "a" --> tvar "a"))
    , InferUpsilon
        "visible type application specializes a specified binder"
        []
        visibleTypeApplication
        intType
    , InferUpsilon
        "deep skolemization allows passing a specified-polymorphic value to a monomorphic consumer"
        []
        applyToInt
        intType
    , ExpectFailure
        "visible type application rejects generalized binders"
        []
        (synthUpsilon generalizedVisibleTypeApplication)
        "visible type application expects a specified forall"
    , ExpectDsk
        "deep skolemization handles out-of-order specified instantiation"
        dskExampleLeft
        dskExampleRight
    ]

runTest :: Test -> IO Bool
runTest (InferSigma name env term expected) = do
    result <- runTc env (typecheck term >>= zonkType)
    reportTypeResult name expected result
runTest (InferUpsilon name env term expected) = do
    result <- runTc env (synthUpsilon term >>= zonkType)
    reportTypeResult name expected result
runTest (ExpectFailure name env action needle) = do
    result <- runTc env action
    case result of
        Left msg
            | needle `isInfixOf` msg -> do
                putStrLn ("[pass] " ++ name)
                pure True
            | otherwise -> do
                putStrLn ("[fail] " ++ name)
                putStrLn ("  expected error containing: " ++ needle)
                putStrLn ("  but got: " ++ msg)
                pure False
        Right ty -> do
            putStrLn ("[fail] " ++ name)
            putStrLn ("  expected failure, but inferred: " ++ prettyType ty)
            pure False
runTest (ExpectDsk name left right) = do
    result <- runTc [] (subsumeDsk left right)
    case result of
        Left msg -> do
            putStrLn ("[fail] " ++ name)
            putStrLn ("  deep-skolemization failed: " ++ msg)
            pure False
        Right () -> do
            putStrLn ("[pass] " ++ name)
            pure True

reportTypeResult :: Name -> Type -> Either String Type -> IO Bool
reportTypeResult name expected result =
    case result of
        Left msg -> do
            putStrLn ("[fail] " ++ name)
            putStrLn ("  unexpected type error: " ++ msg)
            pure False
        Right ty ->
            if prettyType ty == prettyType expected
                then do
                    putStrLn ("[pass] " ++ name)
                    pure True
                else do
                    putStrLn ("[fail] " ++ name)
                    putStrLn ("  expected: " ++ prettyType expected)
                    putStrLn ("  but got:  " ++ prettyType ty)
                    pure False

main :: IO ()
main = do
    putStrLn "System SB 2016 reference implementation"
    putStrLn "Running representative examples..."
    results <- mapM runTest tests
    let passed = length (filter id results)
        total = length results
    putStrLn ""
    putStrLn ("Passed " ++ show passed ++ " / " ++ show total ++ " tests")
    when (passed /= total) $
        fail "one or more System SB examples failed"
