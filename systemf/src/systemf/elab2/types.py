from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass, field
import functools
from typing import Generic, Protocol, TypeVar, override
from typing_extensions import Callable

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
                case SkolemTv(name, uniq):
                    return 1, f"$s{uniq}_{name}"
                case TyCon(name):
                    return 1, name
                case TyFun(arg, res):
                    return 1, f"{self.show_prec(arg, 1)} -> {self.show_prec(res, 0)}"
                case TyForall(vars, body):
                    return 0, f"forall {' '.join(name for name in varnames(vars))}. {self.show_prec(body, 0)}"
                case MetaTv(uniq):
                    return 1, f"$m{uniq}"
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

def get_free_vars(tys: list[Ty]) -> list[TyVar]:
    def _free_tv(ty: Ty) -> Generator[TyVar, None, None]:
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

    seen: set[int] = set()  # for deduplication
    result: list[MetaTv] = []
    for ty in tys:
        for v in _meta_tv(zonk_type(ty)):
            if v.uniq not in seen:
                seen.add(v.uniq)
                result.append(v)
    return result

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
NAME = TypeVar("NAME")

class SyntaxDSL(Protocol[NAME, REPR]):
    def lit(self, value: Lit) -> REPR: ...
    # de brujin var
    def var(self, name: NAME) -> REPR: ...
    def lam(self, name: NAME, body: REPR) -> REPR: ...
    def alam(self, name: NAME, sigma: Ty, body: REPR) -> REPR: ...
    def annot(self, expr: REPR, sigma: Ty) -> REPR: ...
    def app(self, fun: REPR, arg: REPR) -> REPR: ...
    def let(self, name: NAME, expr: REPR, body: REPR) -> REPR: ...

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
    var: TyVar
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
    expr_ty: Ty
    expr: CoreTm
    body: CoreTm

@dataclass
class Id:
    name: str
    ty: Ty
    uniq: int

# ---
# Core term builder protocol and implementation

OUT = TypeVar("OUT")

class SyntaxCore(Protocol[OUT]):
    """Protocol for building core terms."""
    def lit(self, value: Lit) -> OUT: ...
    def var(self, name: str, ty: Ty) -> OUT: ...
    def tyapp(self, fun: OUT, tyarg: Ty) -> OUT: ...
    def tylam(self, var: TyVar, body: OUT) -> OUT: ...
    def lam(self, name: str, ty: Ty, body: OUT) -> OUT: ...
    def app(self, fun: OUT, arg: OUT) -> OUT: ...
    def let(self, name: str, expr_ty: Ty, expr: OUT, body: OUT) -> OUT: ...

class SyntaxCoreSubst(SyntaxCore[OUT], Protocol):
    """with substituting support."""
    def subst(self, name: str, to: OUT, expr: OUT) -> OUT: ...


class CoreBuilder(SyntaxCoreSubst[CoreTm]):
    """
    A builder for constructing core terms, directly derived from CoreTm dataclasses.
    Implements SyntaxCore[CoreTm].
    """
    def lit(self, value: Lit) -> CoreTm:
        return CoreLit(value)
    def var(self, name: str, ty: Ty) -> CoreTm:
        return CoreVar(name, zonk_type(ty))
    def tyapp(self, fun: CoreTm, tyarg: Ty) -> CoreTm:
        return CoreTyApp(fun, zonk_type(tyarg))
    def tylam(self, var: TyVar, body: CoreTm) -> CoreTm:
        return CoreTyLam(var, body)
    def lam(self, name: str, ty: Ty, body: CoreTm) -> CoreTm:
        return CoreLam(name, zonk_type(ty), body)
    def app(self, fun: CoreTm, arg: CoreTm) -> CoreTm:
        return CoreApp(fun, arg)
    def let(self, name: str, expr_ty: Ty, expr: CoreTm, body: CoreTm) -> CoreTm:
        return CoreLet(name, zonk_type(expr_ty), expr, body)
    def subst(self, name: str, to: CoreTm, expr: CoreTm) -> CoreTm:
        return subst_coretm(name, to, expr)

def subst_coretm(name: str, to: CoreTm, expr: CoreTm) -> CoreTm:
    def _go(expr: CoreTm) -> CoreTm:
        match expr:
            case CoreVar(n, _) if n == name:
                return to
            case CoreTyApp(fun, ty_arg):
                return CoreTyApp(_go(fun), ty_arg)
            case CoreTyLam(n, body):
                return CoreTyLam(n, _go(body))
            case CoreLam(name=n) if n == name: # otherwise
                return expr
            case CoreLam(n, ty, body):
                return CoreLam(n, ty, _go(body))
            case CoreApp(fun, arg):
                return CoreApp(_go(fun), _go(arg))
            case CoreLet(n, expr_ty, expr, body) if n == name:
                return CoreLet(n, expr_ty, _go(expr), body)
            case CoreLet(n, expr_ty, expr, body):
                return CoreLet(n, expr_ty, _go(expr), _go(body))
            case _:
                return expr
    return _go(expr)

# A convenience variable for the core builder.
C = CoreBuilder()

# ---
# Unit core builder for type-checking only

class UnitCore:
    """A core builder that just returns None - for type checking only."""
    def lit(self, value: Lit, ty: Ty) -> None:
        return None
    def lam(self, name: str, ty: Ty, body: None) -> None:
        return None
    def app(self, fun: None, arg: None) -> None:
        return None


# ---
# Wrapper
#
# like HsWrapper, the translation snippets from Surface to Core
# produced by type inference
#
class Wrapper: ...

@dataclass
class WpHole(Wrapper): ...

WP_HOLE = WpHole()

@dataclass
class WpCast(Wrapper):
    """
    A type cast wrapper.

    TODO: I think it's just temporary to witness the fact that meta tv == some type.
          which after type inference should be equivalent to WpHole. Needs confirmation.
    """
    ty_from: Ty
    ty_to: Ty

@dataclass
class WpFun(Wrapper):
    """
    This wraps a function.
    say it's e: a -> b, then builds: \\x:arg_ty -> wp_res (e (wp_arg x))
    """
    arg_ty: Ty
    wp_arg: Wrapper
    wp_res: Wrapper

def wp_fun(arg_ty: Ty, wp_arg: Wrapper, wp_res: Wrapper) -> Wrapper:
    if wp_arg == WP_HOLE and wp_res == WP_HOLE:
        return WP_HOLE
    return WpFun(arg_ty, wp_arg, wp_res)

def mk_wp_eta(ty: Ty, wp_body: Wrapper) -> Wrapper:
    """
    Constructs Eta conversion wrapper with WpFun.
    eg. a -> b -> c, wp_body creates \\x:a -> \\y:b -> wp_body (e x y)
    binders are not relevant here, it's created and used all by us.
    but should be not in fv(e)
    """
    # supose to be used in skolemise, but our skolemise process layer by layer
    # so each layer it constructs it's own WpFun
    def _go(ty: Ty) -> Wrapper:
        match ty:
            case TyFun(arg_ty, res_ty):
                return wp_fun(arg_ty, WP_HOLE, _go(res_ty))
            case _:
                return wp_body
    return _go(ty)

@dataclass
class WpTyApp(Wrapper):
    ty_arg: Ty

@dataclass
class WpTyLam(Wrapper):
    ty_var: TyVar

def mk_wp_ty_lams(tvs: list[TyVar], w: Wrapper) -> Wrapper:
    if tvs:
        return functools.reduce(lambda acc, tv: WpCompose(WpTyLam(tv), acc), reversed(tvs), w)
    return w

@dataclass
class WpCompose(Wrapper):
    """
    apply f first, then g.
    g . f
    """
    wp_g: Wrapper
    wp_f: Wrapper

def wp_compose(wp_g: Wrapper, wp_f: Wrapper) -> Wrapper:
    """
    Smart WpCompose that simplifies WP_HOLE cases.
    """
    if wp_g == WP_HOLE:
        return wp_f
    if wp_f == WP_HOLE:
        return wp_g
    return WpCompose(wp_g, wp_f)

def zonk_wrapper(wp: Wrapper) -> Wrapper:
    match wp:
        case WpCompose(wp_g, wp_f):
            return wp_compose(zonk_wrapper(wp_g), zonk_wrapper(wp_f))
        case WpFun(arg_ty, wp_arg, wp_res):
            return wp_fun(zonk_type(arg_ty), zonk_wrapper(wp_arg), zonk_wrapper(wp_res))
        case WpTyApp(ty_arg):
            return WpTyApp(zonk_type(ty_arg))
        case WpCast(ty_from, ty_to):
            zty_from = zonk_type(ty_from)
            zty_to = zonk_type(ty_to)
            if zty_from == zty_to:
                return WP_HOLE
            return WpCast(zty_from, zty_to)
        case _:
            return wp

def run_wrapper(wp: Wrapper, make_uniq: Callable[[], int], sytx: SyntaxCore[OUT], e: OUT) -> OUT:
    # TODO: fix dummy names
    def _go(wp, e) -> OUT:
        match wp:
            case WpHole():
                return e
            case WpCast(ty_from, ty_to):
                # FIX
                if ty_from == ty_to:
                    return e
                else:
                    raise TyCkException(f"type mismatch: expected {ty_from}, got {ty_to}")
            case WpFun(arg_ty, wp_arg, wp_res):
                arg = _go(wp_arg, e)
                res = _go(wp_res, sytx.app(e, arg))
                 # FIX
                return sytx.lam("dummy", arg_ty, res)
            case WpTyApp(ty_arg):
                # FIX
                return sytx.tyapp(e, ty_arg)
            case WpTyLam(ty_var):
                # FIX: make core have proper type var type
                return sytx.tylam(ty_var, e)
            case WpCompose(wp_g, wp_f):
                return _go(wp_g, _go(wp_f, e))
            case _:
                raise Exception("impossible")
    return _go(wp, e)

# ---
# misc
#

class TyCkException(Exception):
    pass

@dataclass
class Cons[T]:
    fst: T
    snd: Cons[T] | None

    def to_list(self) -> list[T]:
        def _go(xs: Cons[T]) -> Generator[T, None, None]:
            yield xs.fst
            if xs.snd:
                yield from _go(xs.snd)
        return list(_go(self))

def cons(x: T, xs: Cons[T] | None) -> Cons[T]:
    return Cons(x, xs)
