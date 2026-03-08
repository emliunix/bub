# Manifest: Names Defined in putting-2007-implementation.hs

Extracted from: Practical type inference for arbitrary-rank types  
Peyton Jones, Vytiniotis, Weirich, Shields (2007)  
Appendix A: Complete implementation in Haskell

## Table of Contents
1. [Types](#types)
2. [Type Aliases](#type-aliases)
3. [Data Constructors](#data-constructors)
4. [Functions and Values](#functions-and-values)
5. [Type Class Instances](#type-class-instances)
6. [Operators](#operators)

---

## Types

### Term (Source Language AST)
```haskell
data Term
  = Var Name
  | Lit Int
  | App Term Term
  | Lam Name Term
  | ALam Name Sigma Term   -- annotated lambda
  | Let Name Term Term
  | Ann Term Sigma         -- type annotation
```

### Type (Type Language)
```haskell
data Type
  = ForAll [TyVar] Rho     -- polymorphic type
  | Fun Type Type          -- function type
  | TyCon TyCon            -- type constant
  | TyVar TyVar            -- type variable
  | MetaTv MetaTv          -- meta type variable
```

### TyVar (Type Variables)
```haskell
data TyVar
  = BoundTv String         -- bound type variable
  | SkolemTv String Uniq   -- skolem constant
```

### MetaTv (Meta Type Variables)
```haskell
data MetaTv = Meta Uniq TyRef
```

### TcEnv (Type Checking Environment)
```haskell
data TcEnv = TcEnv
  { uniqs :: IORef Uniq
  , var_env :: Map.Map Name Sigma
  }
```

### Tc (Type Checking Monad)
```haskell
newtype Tc a = Tc (TcEnv -> IO (Either Doc a))
```

### Expected (Bidirectional Checking)
```haskell
data Expected a
  = Infer (IORef a)
  | Check a
```

---

## Type Aliases

| Alias | Definition | Description |
|-------|-----------|-------------|
| `Name` | `String` | Variable names |
| `Sigma` | `Type` | Polymorphic types (∀a.ρ) |
| `Rho` | `Type` | Rho types (no outer ∀) |
| `Tau` | `Type` | Monomorphic types |
| `TyCon` | `String` | Type constructor names |
| `TyRef` | `IORef (Maybe Tau)` | Mutable reference for unification |
| `Uniq` | `Int` | Unique identifiers |

---

## Data Constructors

### Term constructors:
- `Var :: Name -> Term`
- `Lit :: Int -> Term`
- `App :: Term -> Term -> Term`
- `Lam :: Name -> Term -> Term`
- `ALam :: Name -> Sigma -> Term -> Term`
- `Let :: Name -> Term -> Term -> Term`
- `Ann :: Term -> Sigma -> Term`

### Type constructors:
- `ForAll :: [TyVar] -> Rho -> Type`
- `Fun :: Type -> Type -> Type`
- `TyCon :: TyCon -> Type`
- `TyVar :: TyVar -> Type`
- `MetaTv :: MetaTv -> Type`

### TyVar constructors:
- `BoundTv :: String -> TyVar`
- `SkolemTv :: String -> Uniq -> TyVar`

### MetaTv constructor:
- `Meta :: Uniq -> TyRef -> MetaTv`

### Expected constructors:
- `Infer :: IORef a -> Expected a`
- `Check :: a -> Expected a`

---

## Functions and Values

### Type Constructors
| Name | Type | Description |
|------|------|-------------|
| `intType` | `Tau` | Type constant `Int` |

### Tc Monad Operations
| Name | Type | Description |
|------|------|-------------|
| `unTc` | `Tc a -> TcEnv -> IO (Either Doc a)` | Unwrap Tc monad |
| `failTc` | `Doc -> Tc a` | Fail with error message |
| `check` | `Bool -> Doc -> Tc ()` | Assert condition |
| `runTc` | `[(Name,Sigma)] -> Tc a -> IO (Either Doc a)` | Run type checker |
| `lift` | `IO a -> Tc a` | Lift IO into Tc |

### Reference Cells
| Name | Type | Description |
|------|------|-------------|
| `newTcRef` | `a -> Tc (IORef a)` | Create new reference |
| `readTcRef` | `IORef a -> Tc a` | Read reference |
| `writeTcRef` | `IORef a -> a -> Tc ()` | Write reference |

### Environment Operations
| Name | Type | Description |
|------|------|-------------|
| `getEnv` | `Tc (Map.Map Name Sigma)` | Get type environment |
| `extendVarEnv` | `Name -> Sigma -> Tc a -> Tc a` | Extend environment |
| `lookupVar` | `Name -> Tc Sigma` | Lookup variable |
| `getEnvTypes` | `Tc [Type]` | Get all types in env |

### Meta Type Variables
| Name | Type | Description |
|------|------|-------------|
| `newTyVarTy` | `Tc Tau` | Create fresh meta type var |
| `newMetaTyVar` | `Tc MetaTv` | Create new meta var |
| `newSkolemTyVar` | `TyVar -> Tc TyVar` | Create skolem constant |
| `readTv` | `MetaTv -> Tc (Maybe Tau)` | Read meta var binding |
| `writeTv` | `MetaTv -> Tau -> Tc ()` | Write meta var binding |
| `newUnique` | `Tc Uniq` | Generate fresh unique |

### Instantiation and Skolemisation
| Name | Type | Description |
|------|------|-------------|
| `instantiate` | `Sigma -> Tc Rho` | Instantiate ∀ with fresh metas |
| `skolemise` | `Sigma -> Tc ([TyVar], Rho)` | Weak prenex conversion |

### Quantification
| Name | Type | Description |
|------|------|-------------|
| `quantify` | `[MetaTv] -> Rho -> Tc Sigma` | Generalize (GEN1) |
| `allBinders` | `[TyVar]` | Infinite supply of type var names |

### Free Variables
| Name | Type | Description |
|------|------|-------------|
| `getMetaTyVars` | `[Type] -> Tc [MetaTv]` | Get flexible type vars |
| `getFreeTyVars` | `[Type] -> Tc [TyVar]` | Get bound type vars |

### Zonking
| Name | Type | Description |
|------|------|-------------|
| `zonkType` | `Type -> Tc Type` | Eliminate substitutions |

### Unification
| Name | Type | Description |
|------|------|-------------|
| `unify` | `Tau -> Tau -> Tc ()` | Robinson unification |
| `unifyVar` | `MetaTv -> Tau -> Tc ()` | Unify meta var |
| `unifyUnboundVar` | `MetaTv -> Tau -> Tc ()` | Unify unbound meta var |
| `unifyFun` | `Rho -> Tc (Sigma, Rho)` | Expect function type |
| `occursCheckErr` | `MetaTv -> Tau -> Tc ()` | Occurs check error |
| `badType` | `Tau -> Bool` | Check for invalid types |

### Type Substitution Utilities
| Name | Type | Description |
|------|------|-------------|
| `tyVarName` | `TyVar -> String` | Get variable name |
| `tyVarBndrs` | `Type -> [TyVar]` | Get bound variables |
| `metaTvs` | `[Type] -> [MetaTv]` | Extract meta vars |
| `freeTyVars` | `[Type] -> [TyVar]` | Extract free vars |
| `substTy` | `[TyVar] -> [Type] -> Type -> Type` | Substitute types |

### Type Inference
| Name | Type | Description |
|------|------|-------------|
| `typecheck` | `Term -> Tc Sigma` | Top-level entry point |
| `checkRho` | `Term -> Rho -> Tc ()` | Check mode (⊢⇓) |
| `inferRho` | `Term -> Tc Rho` | Inference mode (⊢⇑) |
| `tcRho` | `Term -> Expected Rho -> Tc ()` | Main bidirectional checker |
| `inferSigma` | `Term -> Tc Sigma` | Polymorphic inference (GEN1) |
| `checkSigma` | `Term -> Sigma -> Tc ()` | Polymorphic checking (GEN2) |

### Subsumption Checking
| Name | Type | Description |
|------|------|-------------|
| `subsCheck` | `Sigma -> Sigma -> Tc ()` | Deep skolemization (DEEP-SKOL) |
| `subsCheckRho` | `Sigma -> Rho -> Tc ()` | Subsumption to rho (⊢^dsk*) |
| `subsCheckFun` | `Sigma -> Rho -> Sigma -> Rho -> Tc ()` | Function subsumption |

### Instantiation
| Name | Type | Description |
|------|------|-------------|
| `instSigma` | `Sigma -> Expected Rho -> Tc ()` | Instantiation (⊢^inst) |

### Main
| Name | Type | Description |
|------|------|-------------|
| `main` | `IO ()` | Program entry point |

---

## Type Class Instances

| Instance | Type | Methods |
|----------|------|---------|
| `Show MetaTv` | `MetaTv` | `show :: MetaTv -> String` |
| `Functor Tc` | `Tc` | `fmap :: (a -> b) -> Tc a -> Tc b` |
| `Applicative Tc` | `Tc` | `pure :: a -> Tc a`, `(<*>) :: Tc (a -> b) -> Tc a -> Tc b` |
| `Monad Tc` | `Tc` | `(>>=) :: Tc a -> (a -> Tc b) -> Tc b` |

---

## Operators

| Operator | Type | Fixity | Description |
|----------|------|--------|-------------|
| `(-->)` | `Type -> Type -> Type` | Right-associative | Function type constructor |

---

## Summary Statistics

- **Type definitions**: 6 (Term, Type, TyVar, MetaTv, TcEnv, Expected)
- **Type aliases**: 6 (Name, Sigma, Rho, Tau, TyCon, TyRef, Uniq)
- **Data constructors**: 26
- **Functions**: 45
- **Type class instances**: 4
- **Operators**: 1
- **Total lines**: 654

---

## Paper References

- **Figure 8**: Bidirectional rules (tcRho, inferSigma, checkSigma, subsCheck, instSigma)
- **Section 4.5**: Prenex conversion (skolemise)
- **Section 4.6**: Subsumption (subsCheck, subsCheckRho)
- **Section 4.7**: Polymorphism (quantify, instantiate)
- **Section 5.2**: The Tc monad
- **Section 5.6**: Unification (unify, unifyVar, unifyUnboundVar)
- **Appendix A**: Complete implementation
