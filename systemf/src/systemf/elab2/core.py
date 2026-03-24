from dataclasses import dataclass

@dataclass
class Id:
    name: str
    uniq: int

@dataclass
class Var(Id):
    type: Ty

# ---
# types

@dataclass
class Ty:
    pass

@dataclass
class TyLit(Ty):
    pass

@dataclass
class TyFun(Ty):
    arg: Ty
    ret: Ty

@dataclass
class TyVar(Ty):
    name: Id

@dataclass
class TyForall(Ty):
    var: Id
    body: Ty

@dataclass
class TyApp(Ty):
    fun: Ty
    arg: Ty

# ---
# literals

@dataclass
class Lit:
    pass

@dataclass
class LitNum(Lit):
    value: int

@dataclass
class TyLitNum(TyLit):
    pass

@dataclass
class LitStr(Lit):
    value: str

@dataclass
class TyLitStr(TyLit):
    pass

# ---
# data types

@dataclass
class TyData(Ty):
    name: Id
    args: list[Ty]
    data_cons: list[DataCon]

@dataclass
class DataCon:
    name: Id
    ty_con: TyData
    args: list[Ty]

# ---
# GlobalEnvs

@dataclass
class GlobalEnv:
    ty_cons: list[TyData]
    data_cons: list[DataCon]
    val_defs: list[ValDef]

@dataclass
class ValDef:
    name: Id
    type: Ty
    val: CoreTm

# ---
# terms

@dataclass
class CoreTm:
    pass

@dataclass
class CoreLit(CoreTm):
    value: Lit

@dataclass
class CoreVar(CoreTm):
    var: Var

@dataclass
class CoreLam(CoreTm):
    var: Id
    type: Ty
    body: CoreTm

@dataclass
class CoreApp(CoreTm):
    fun: CoreTm
    arg: CoreTm

@dataclass
class CoreTyLam(CoreTm):
    var: Id
    body: CoreTm

@dataclass
class CoreTyApp(CoreTm):
    term: CoreTm
    ty_arg: Ty

@dataclass
class CoreLet(CoreTm):
    var: Id
    type: Ty
    val: CoreTm
    body: CoreTm

@dataclass
class CoreCase(CoreTm):
    scrutinee: CoreTm
    branches: list[CaseBranch]
    default: CoreTm

@dataclass
class CaseBranch:
    data_con: DataCon
    vars: list[tuple[Id, Ty]]
    body: CoreTm
