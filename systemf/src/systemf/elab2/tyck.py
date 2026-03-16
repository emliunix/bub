from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
import itertools
from typing import Callable, TypeVar, override

from systemf.elab2.types import (
    BoundTv, Lit, INT, MetaTv, SkolemTv, SyntaxDSL, Ty, TyForall, TyFun,
    TyVar, get_free_vars, get_meta_vars, subst_ty, varnames, zonk_type, TY
)
from systemf.elab2.unify import unify

T = TypeVar("T")

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

# ---
# environment

type Env = Cons[tuple[str, Ty]] | None

def extend_env(name: str, ty: Ty, env: Env) -> Env:
    return cons((name, ty), env)

def lookup_env(name: str, env: Env) -> Ty:
    match env:
        case Cons((n, t), _) if n == name:
            return t
        case Cons(_, xs):
            return lookup_env(name, xs)
        case None:
            raise NameError(f"Unbound variable {name}")

def lookup_dbi(dbi: int, env: Env) -> Ty:
    match env:
        case Cons((_, t), _) if dbi == 0:
            return t
        case Cons(_, xs):
            return lookup_dbi(dbi - 1, xs)
        case None:
            raise NameError(f"Unbound variable {dbi}")

def env_types(env: Env) -> list[Ty]:
    return [ty for (_, ty) in env.to_list()] if env else []

@dataclass
class TyCk:
    infer: Callable[[Env], Ty]
    check: Callable[[Env, Ty], None]

    @staticmethod
    def from_env(f: Callable[[Env], TyCk]) -> TyCk:
        def _infer(env: Env) -> Ty:
            return f(env).infer(env)
        def _check(env: Env, ty: Ty) -> None:
            f(env).check(env, ty)
        return TyCk(_infer, _check)

    def with_env(self, f: Callable[[Env], Env]) -> TyCk:
        def _infer(env: Env) -> Ty:
            return self.infer(f(env))
        def _check(env: Env, ty: Ty) -> None:
            self.check(f(env), ty)
        return TyCk(_infer, _check)

class TyCkImpl(SyntaxDSL[TyCk]):
    def __init__(self):
        self.env: dict[str, list[Ty]] = {} # TODO: this is wrong
        self.env_names: list[str] = []
        self.uniq: int = 0

    @override
    def lit(self, value: Lit) -> TyCk:
        def _infer(_: Env) -> Ty:
            return INT
        def _check(_: Env, ty: Ty) -> None:
            if ty != INT:
                raise TypeError(f"Expected INT, got {ty}")
        return TyCk(_infer, _check)

    @override
    def dbi(self, dbi: int) -> TyCk:
        return TyCk.from_env(lambda env: self.inst(lookup_dbi(dbi, env)))

    @override
    def lam(self, name: str, body: TyCk) -> TyCk:
        def _infer(env: Env) -> Ty:
            tau = self.make_meta()
            rho = body.infer(extend_env(name, tau, env))
            return TyFun(tau, rho)
        def _check(env: Env, ty2: Ty):
            (arg_ty, res_ty) = self.unify_fun(ty2)
            self.poly(body).check(extend_env(name, arg_ty, env), res_ty)
        return TyCk(_infer, _check)

    @override
    def alam(self, name: str, sigma: Ty, body: TyCk) -> TyCk:
        # ty is sigma
        def _infer(env: Env) -> Ty:
            rho = body.infer(extend_env(name, sigma, env))
            return TyFun(sigma, rho)
        def _check(env: Env, ty2: Ty):
            (arg_ty, res_ty) = self.unify_fun(ty2)
            self.subs_check(arg_ty, sigma)
            self.poly(body).check(extend_env(name, sigma, env), res_ty)
        return TyCk(_infer, _check)

    @override
    def app(self, fun: TyCk, arg: TyCk) -> TyCk:
        def _go(env: Env) -> TyCk:
            (arg_ty, res_ty) = self.unify_fun(fun.infer(env))
            self.poly(arg).check(env, arg_ty)
            return self.inst(res_ty)
        return TyCk.from_env(_go)

    @override
    def annot(self, expr: TyCk, sigma: Ty) -> TyCk:
        def _go(env: Env) -> TyCk:
            self.poly(expr).check(env, sigma)
            return self.inst(sigma)
        return TyCk.from_env(_go)

    @override
    def let(self, name: str, expr: TyCk, body: TyCk) -> TyCk:
        def _go(env: Env) -> Env:
            sigma = self.poly(expr).infer(env)
            env_ = extend_env(name, sigma, env)
            return env_
        return body.with_env(_go)

    # ---
    # poly (GEN1, GEN2)

    def poly(self, term: TyCk) -> TyCk:
        """
        the poly judgment, in the same form, but not part of the syntax
        """
        def _infer(env: Env) -> Ty:
            ty = term.infer(env)
            env_tys = get_meta_vars(env_types(env))
            mvs = [m for m in get_meta_vars([ty]) if m not in env_tys]
            return quantify(mvs, ty)
        def _check(env: Env, ty2: Ty):
            sks, rho2 = self.skolemise(ty2)
            term.check(env, rho2)
            env_tys = env_types(env)
            esc_tvs = get_free_vars([ty2] + env_tys)
            for sk in sks:
                if sk in esc_tvs:
                    raise TypeError(f"Skolem var {sk} escapes")
        return TyCk(_infer, _check)

    # ---
    # inst (INST1, INST2)

    def inst(self, ty: Ty) -> TyCk:
        """
        the inst judgment
        """
        def _infer(env: Env) -> Ty:
            return self.instantiate(ty)
        def _check(env: Env, ty2: Ty) -> None:
            self.subs_check_rho(ty, ty2)
        return TyCk(_infer, _check)

    # ---
    # subsumption check

    def subs_check(self, sigma1: Ty, sigma2: Ty):
        sks, rho2 = self.skolemise(sigma2)
        self.subs_check_rho(sigma1, rho2)  # sigma1 inst-to rho2
        # check skolem var escape
        esc_tvs = get_free_vars([sigma1, sigma2])
        for sk in sks:
            if sk in esc_tvs:
                raise TypeError(f"Skolem var {sk} escapes")

    def subs_check_rho(self, sigma: Ty, rho: Ty):
        match (sigma, rho):
            case (TyForall(), _):          # DSK/SPEC
                self.subs_check_rho(self.instantiate(sigma), rho)
            case (rho1, TyFun(a2, r2)):    # DSK/FUN
                (a1, r1) = self.unify_fun(rho1)
                self.subs_check_fun(a1, r1, a2, r2)
            case (TyFun(a1, r1), rho2):
                (a2, r2) = self.unify_fun(rho2)
                self.subs_check_fun(a1, r1, a2, r2)
            case (tau1, tau2):             # DSK/MONO
                unify(tau1, tau2)

    def subs_check_fun(self, a1: Ty, r1: Ty, a2: Ty, r2: Ty):
        self.subs_check(a2, a1)     # contravariant
        self.subs_check_rho(r1, r2) # covariant

    # ---
    # uniq vars

    def make_uniq(self) -> int:
        n = self.uniq
        self.uniq += 1
        return n

    def make_meta(self) -> MetaTv:
        return TY.meta(self.make_uniq())

    def make_skolem(self, name: str) -> SkolemTv:
        return TY.skolem(name, self.make_uniq())

    # ---
    # helpers

    def skolemise(self, ty: Ty) -> tuple[list[SkolemTv], Ty]:
        """
        Create weak prenex formed rho type with skolemise type vars filled
        """
        match ty:
            case TyForall(tvs, body):
                sks1 = [self.make_skolem(name) for name in varnames(tvs)]
                sks2, ty2 = self.skolemise(subst_ty(tvs, sks1, body))
                return sks1 + sks2, ty2
            case TyFun(arg_ty, res_ty):
                sks, res_ty2 = self.skolemise(res_ty)
                return sks, TY.fun(arg_ty, res_ty2)
            case _:
                return [], ty

    def instantiate(self, sigma: Ty) -> Ty:
        """
        Instantiate top-level forall type variables in sigma with fresh meta variables.
        sigma -> rho
        """
        match sigma:
            case TyForall(vars, ty):
                mvs = [self.make_meta() for _ in vars]
                return subst_ty(vars, mvs, ty)
            case _:
                return sigma

    def unify_fun(self, ty: Ty) -> tuple[Ty, Ty]:
        """
        Match a function type, or unify it to a function
        with new meta argument and result.
        """
        match ty:
            case TyFun(ty1, ty2):
                return (ty1, ty2)
            case _: # it must be a meta
                arg_ty = self.make_meta()
                res_ty = self.make_meta()
                unify(ty, TyFun(arg_ty, res_ty))
                return (arg_ty, res_ty)

def binders_of_ty(ty: Ty) -> list[TyVar]:
    """
    Oppose to get_free_vars, this function returns the forall bound variables.
    """
    def _go(ty: Ty) -> Generator[TyVar, None, None]:
        match ty:
            case TyForall(vars, ty2):
                yield from vars
                yield from _go(ty2)
            case TyFun(arg_ty, res_ty):
                yield from _go(arg_ty)
                yield from _go(res_ty)
            case _:
                return None
    return list(_go(ty))

def quantify(tvs: list[MetaTv], ty: Ty) -> Ty:
    """
    Quantify a type over a list of meta type variables.
    """
    used_names = varnames(binders_of_ty(ty))
    binders: list[TyVar] = list(itertools.islice(
        (BoundTv(n) for n in allnames() if n not in used_names),
        len(tvs)
    ))

    # bind meta to bound vars
    for tv, n in zip(tvs, binders):
        tv.ref.set(n)

    return TyForall(binders, zonk_type(ty))

def allnames():
    CHARS = "abcdefghijklmnopqrstuvwxyz"
    charidx = 0
    num = 0
    while True:
        if num:
            name = f"{CHARS[charidx]}{num}"
        else:
            name = f"{CHARS[charidx]}"
        charidx += 1
        if charidx >= len(CHARS):
            num += 1
            charidx = 0
        yield name
