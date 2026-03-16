from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Generic, Protocol, TypeVar, override

T = TypeVar("T")

@dataclass
class Ref(Generic[T]):
    inner: T | None = field(default=None)

    def set(self, value: T):
        self.inner = value

    def get(self) -> T | None:
        return self.inner

# ---
# shared "type" defintions

@dataclass(frozen=True, repr=False)
class Ty:
    @override
    def __repr__(self) -> str:
        return TP.show_prec(self, 0)

@dataclass(frozen=True, repr=False)
class TyVar(Ty):
    pass

@dataclass(frozen=True, repr=False)
class BoundTv(TyVar):
    name: str

@dataclass(frozen=True, repr=False)
class SkolemTv(TyVar):
    name: str
    uniq: int

@dataclass(frozen=True, repr=False)
class TyCon(Ty):
    name: str

INT = TyCon("Int")
STRING = TyCon("String")

@dataclass(frozen=True, repr=False)
class TyFun(Ty):
    arg: Ty
    result: Ty

@dataclass(frozen=True, repr=False)
class TyForall(Ty):
    vars: list[TyVar]
    body: Ty

@dataclass(frozen=True, repr=False)
class MetaTv(Ty):
    uniq: int
    ref: Ref[Ty]

# ---
# type printer

class PrettyPrinter(Protocol[T]):
    def show_prec(self, v: T, prec: int) -> str: ...

class TyPrinter(PrettyPrinter[Ty]):
    def show_prec(self, v: Ty, prec: int) -> str:
        def _show() -> tuple[int, str]:
            match v:
                case BoundTv():
                    return 1, v.name
                case SkolemTv():
                    return 1, f"${v.name}"
                case TyCon():
                    return 1, v.name
                case TyFun(arg, res):
                    return 1, f"{self.show_prec(arg, 1)} -> {self.show_prec(res, 0)}"
                case TyForall(vars, body):
                    return 0, f"forall {' '.join(name for name in varnames(vars))}. {self.show_prec(body, 0)}"
                case MetaTv():
                    return 1, f"#m{v.uniq}"
                case _:
                    raise TypeError(f"Unexpected type: {v}")
        p, s = _show()
        if p < prec:
            return f"({s})"
        return s

TP = TyPrinter()

def varnames(vars: list[TyVar]) -> list[str]:
    def _name(v: TyVar) -> str:
        match v:
            case BoundTv(name=name) | SkolemTv(name=name):
                return name
            case _:
                raise TypeError(f"Expected a bound type variable, got {v}")
    return [_name(v) for v in vars]

# ---
# type helpers

def zonk_type(ty: Ty) -> Ty:
    match ty:
        case TyVar() | TyCon():
            return ty
        case TyFun():
            return TyFun(zonk_type(ty.arg), zonk_type(ty.result))
        case TyForall():
            return TyForall(ty.vars, zonk_type(ty.body))
        case MetaTv(ref=ref) if ref.inner:
            ty = zonk_type(ref.inner)
            ref.set(ty)
            return ty
        case MetaTv():
            return ty
        case _:
            raise ValueError(f"Unknown type: {ty}")

def get_free_vars(tys: list[Ty]) -> list[Ty]:
    def _free_tv(ty: Ty) -> Generator[Ty, None, None]:
        match ty:
            case TyVar(): # BoundTv | Skolem
                yield ty
            case TyFun(arg, res):
                yield from _free_tv(arg)
                yield from _free_tv(res)
            case TyForall(vars, body):
                for var in _free_tv(body):
                    if var not in vars:  # ignore bound variables
                        yield var
            case MetaTv():
                pass
            case _:
                pass

    return [
        v
        for ty in tys
        for v in _free_tv(zonk_type(ty))
    ]


def get_meta_vars(tys: list[Ty]) -> list[MetaTv]:
    def _meta_tv(ty: Ty) -> Generator[MetaTv, None, None]:
        match ty:
            case MetaTv():
                yield ty
            case TyFun(arg, res):
                yield from _meta_tv(arg)
                yield from _meta_tv(res)
            case TyForall(_, body):
                yield from _meta_tv(body)
            case _:
                pass

    return [
        v
        for ty in tys
        for v in _meta_tv(zonk_type(ty))
    ]

_CO_TY = TypeVar("_CO_TY", covariant=True, bound=Ty)

def subst_ty(vars: list[TyVar], tys: list[_CO_TY], ty: Ty) -> Ty:
    def _subst(env: dict[TyVar, _CO_TY], ty: Ty) -> Ty:
        match ty:
            case TyVar():
                return env.get(ty, ty)
            case TyFun(arg, res):
                return TyFun(_subst(env, arg), _subst(env, res))
            case TyForall(vars_, body):
                env_ = {n: t for n, t in env.items() if n not in vars_}
                return TyForall(vars_, _subst(env_, body))
            case _:
                return ty

    return _subst({n: t for n, t in zip(vars, tys)}, ty)

# ---
# type builder

class TypeBuilder:
    def int_ty(self) -> TyCon:
        return INT

    def string_ty(self) -> TyCon:
        return STRING

    def bound_var(self, name: str) -> BoundTv:
        return BoundTv(name)

    def skolem(self, name: str, uniq: int) -> SkolemTv:
        return SkolemTv(name, uniq)

    def fun(self, arg: Ty, res: Ty) -> TyFun:
        return TyFun(arg, res)

    def forall(self, vars: list[TyVar], body: Ty) -> TyForall:
        return TyForall(vars, body)

    def meta(self, uniq: int) -> MetaTv:
        return MetaTv(uniq, Ref())

TY = TypeBuilder()

# ---
# tagless final style surface syntax

REPR = TypeVar("REPR")

class SyntaxDSL(Protocol[REPR]):
    def lit(self, value: Lit) -> REPR: ...
    # de brujin var
    def dbi(self, dbi: int) -> REPR: ...
    def lam(self, name: str, body: REPR) -> REPR: ...
    def alam(self, name: str, sigma: Ty, body: REPR) -> REPR: ...
    def annot(self, expr: REPR, sigma: Ty) -> REPR: ...
    def app(self, fun: REPR, arg: REPR) -> REPR: ...
    def let(self, name: str, expr: REPR, body: REPR) -> REPR: ...

# ---
# runtime value

class Lit(ABC):
    @property
    @abstractmethod
    def ty(self) -> Ty: ...

@dataclass
class LitInt(Lit):
    value: int

    @property
    @override
    def ty(self) -> Ty:
        return INT

@dataclass
class LitString(Lit):
    value: str

    @property
    @override
    def ty(self) -> Ty:
        return STRING

# --
# system f core terms

class CoreTm: ...

@dataclass
class CoreLit(CoreTm):
    value: Lit

@dataclass
class CoreVar(CoreTm):
    name: str
    ty: Ty

@dataclass
class CoreTyLam(CoreTm):
    name: str
    body: CoreTm

@dataclass
class CoreTyApp(CoreTm):
    fun: CoreTm
    tyarg: Ty

@dataclass
class CoreLam(CoreTm):
    name: str
    ty: Ty
    body: CoreTm

@dataclass
class CoreApp(CoreTm):
    fun: CoreTm
    arg: CoreTm

@dataclass
class CoreLet(CoreTm):
    name: str
    expr: CoreTm
    expr_ty: Ty
    body: CoreTm

class CoreBuilder:
    """
    A builder for constructing core terms, directly derived from CoreTm dataclasses.
    """
    def lit(self, value: Lit, ty: Ty) -> CoreTm:
        return CoreLit(value, ty)
    def var(self, name: str, ty: Ty) -> CoreTm:
        return CoreVar(name, ty)
    def tyapp(self, fun: CoreTm, tyarg: Ty) -> CoreTm:
        return CoreTyApp(fun, tyarg)
    def tylam(self, name: str, body: CoreTm) -> CoreTm:
        return CoreTyLam(name, body)
    def lam(self, name: str, ty: Ty, body: CoreTm) -> CoreTm:
        return CoreLam(name, ty, body)
    def app(self, fun: CoreTm, arg: CoreTm) -> CoreTm:
        return CoreApp(fun, arg)
    def let(self, name: str, expr: CoreTm, expr_ty: Ty, body: CoreTm) -> CoreTm:
        return CoreLet(name, expr, expr_ty, body)

# A convenience variable for the core builder.
C = CoreBuilder()

class TyCkException(Exception):
    pass
