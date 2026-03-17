from abc import ABC
from collections.abc import Generator
from dataclasses import dataclass
from functools import reduce
import itertools
from typing import Callable, TypeVar, override

from systemf.elab2.types import (
    WP_HOLE, BoundTv, Cons, Lit, INT, MetaTv, OUT, Ref, SkolemTv, SyntaxCore, SyntaxDSL,
    Ty, TyForall, TyFun, TyVar, TY, WpCast, WpFun, WpTyLam, Wrapper, cons,
    get_free_vars, get_meta_vars, mk_wp_eta, subst_ty, varnames, zonk_type
)
from systemf.elab2.unify import WpCompose, unify

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

# ---
# expectation

class Expect(ABC): ...

@dataclass
class Infer(Expect):
    ref: Ref[Ty]

@dataclass
class Check(Expect):
    ty: Ty

def run_infer(env: Env, term: TyCk[OUT]) -> tuple[Ty, OUT]:
    """Run inference on a term and return the inferred type."""
    ref = Ref[Ty]()
    out = term(env, Infer(ref))
    ty = ref.get()
    if ty is None:
        raise TypeError("Inference failed")
    return ty, out

# ---
# TyCk - new style: just a function from (Env, Expect) to OUT

type TyCk[OUT] = Callable[[Env, Expect], OUT]
type Defer[OUT] = Callable[[], OUT]

# ---
# TyCkImpl

class TyCkImpl(SyntaxDSL[str, TyCk[Defer[OUT]]]):
    def __init__(self, core: SyntaxCore[OUT]):
        self.uniq: int = 0
        self.core: SyntaxCore[OUT] = core

    @override
    def lit(self, value: Lit) -> TyCk[Defer[OUT]]:
        def _go(_: Env, exp: Expect) -> Defer[OUT]:
            match exp:
                case Infer(ref):
                    ref.set(value.ty)
                case Check(ty):
                    if ty != value.ty:
                        raise TypeError(f"Expected {value.ty}, got {ty}")
            return self.core.lit(value, value.ty)  # TODO use refined core later
        return _go

    @override
    def var(self, name: str) -> TyCk[Defer[OUT]]:
        def _go(env: Env, exp: Expect) -> Defer[OUT]:
            ty = lookup_env(name, env)
            return self.inst(ty)(env, exp)
        return _go

    @override
    def lam(self, name: str, body: TyCk[OUT]) -> TyCk[Defer[OUT]]:
        def _go(env: Env, exp: Expect) -> Defer[OUT]:
            match exp:
                case Infer(ref):
                    # Infer: create fresh meta for arg, infer body, construct fun type
                    arg_ty = self.make_meta()
                    res_ty, res_out = run_infer(extend_env(name, arg_ty, env), body)
                    result_ty = TyFun(arg_ty, res_ty)
                    ref.set(result_ty)
                    return self.core.lam(name, arg_ty, body(extend_env(name, arg_ty, env), Check(res_ty)))
                case Check(ty2):
                    # Check: decompose function type and check body against result
                    (arg_ty, res_ty) = self.unify_fun(ty2)
                    return self.core.lam(name, arg_ty, body(extend_env(name, arg_ty, env), Check(res_ty)))
        return _go

    @override
    def alam(self, name: str, sigma: Ty, body: TyCk[Defer[OUT]]) -> TyCk[Defer[OUT]]:
        def _go(env: Env, exp: Expect) -> Defer[OUT]:
            match exp:
                case Infer(ref):
                    # Infer: sigma is the arg type
                    res_ty, _ = run_infer(extend_env(name, sigma, env), body)
                    result_ty = TyFun(sigma, res_ty)
                    ref.set(result_ty)
                    return self.core.lam(name, sigma, body(extend_env(name, sigma, env), Check(res_ty)))
                case Check(ty2):
                    # Check: decompose function type, check sigma <: arg_ty, check body
                    (arg_ty, res_ty) = self.unify_fun(ty2)
                    self.subs_check(arg_ty, sigma)
                    return self.core.lam(name, sigma, body(extend_env(name, sigma, env), Check(res_ty)))
        return _go

    @override
    def app(self, fun: TyCk[OUT], arg: TyCk[OUT]) -> TyCk[OUT]:
        def _go(env: Env, exp: Expect) -> OUT:
            # First infer the function type
            fun_ty, fun_core = run_infer(env, fun)

            # Decompose to get arg and result types
            (arg_ty, res_ty) = self.unify_fun(fun_ty)

            # Check argument against expected arg type
            arg_core = self.poly(arg)(env, Check(arg_ty))

            # Handle expectation for result
            match exp:
                case Infer(ref):
                    ref.set(res_ty)
                case Check(expected_ty):
                    self.subs_check_rho(res_ty, expected_ty)

            return self.core.app(fun_core, arg_core)
        return _go

    @override
    def annot(self, expr: TyCk[OUT], sigma: Ty) -> TyCk[OUT]:
        def _go(env: Env, exp: Expect) -> OUT:
            # Check expression against annotated type
            expr_core = self.poly(expr)(env, Check(sigma))

            # Handle expectation
            match exp:
                case Infer(ref):
                    ref.set(sigma)
                case Check(expected_ty):
                    self.subs_check(sigma, expected_ty)

            return expr_core
        return _go

    @override
    def let(self, name: str, expr: TyCk[OUT], body: TyCk[OUT]) -> TyCk[OUT]:
        def _go(env: Env, exp: Expect) -> OUT:
            # Infer polymorphic type for expr
            sigma = self.poly_infer(expr, env)

            # Extend environment and continue with body
            env_ = extend_env(name, sigma, env)
            return body(env_, exp)
        return _go

    # ---
    # poly (GEN1, GEN2)

    def poly(self, term: TyCk[OUT]) -> TyCk[OUT]:
        """
        The poly judgment - for checking polymorphic types.
        """
        def _go(env: Env, exp: Expect) -> OUT:
            match exp:
                case Infer(ref):
                    ty = self.poly_infer(term, env)
                    ref.set(ty)
                    # Need to rebuild term with the inferred type
                    # This is a bit tricky - we call term again to get the core term
                    # But we need to do poly inference first
                    return term(env, Check(ty))
                case Check(ty2):
                    # Skolemise and check
                    sks, rho2 = self.skolemise(ty2)
                    term(env, Check(rho2))
                    # Check skolem var escape
                    env_tys = env_types(env)
                    esc_tvs = get_free_vars([ty2] + env_tys)
                    for sk in sks:
                        if sk in esc_tvs:
                            raise TypeError(f"Skolem var {sk} escapes")
                    return term(env, Check(rho2))
        return _go

    def poly_infer(self, term: TyCk[OUT], env: Env) -> Ty:
        """
        Infer a polymorphic type for term.
        """
        ty, _ = run_infer(env, term)
        env_tys = get_meta_vars(env_types(env))
        mvs = [m for m in get_meta_vars([ty]) if m not in env_tys]
        return quantify(mvs, ty)

    # ---
    # inst (INST1, INST2)

    def inst(self, ty: Ty) -> TyCk[OUT]:
        """
        The inst judgment - instantiate a polymorphic type.
        """
        def _go(env: Env, exp: Expect) -> OUT:
            instantiated = self.instantiate(ty)
            match exp:
                case Infer(ref):
                    ref.set(instantiated)
                case Check(ty2):
                    self.subs_check_rho(instantiated, ty2)
            return None  # type: ignore
        return _go

    # ---
    # subsumption check

    def subs_check(self, sigma1: Ty, sigma2: Ty) -> Wrapper:
        sks, rho2, sks_wrap = self.skolemise(sigma2)
        subs_wrap = self.subs_check_rho(sigma1, rho2)  # sigma1 inst-to rho2
        # check skolem var escape
        esc_tvs = get_free_vars([sigma1, sigma2])
        for sk in sks:
            if sk in esc_tvs:
                raise TypeError(f"Skolem var {sk} escapes")
        return WpCompose(sks_wrap, subs_wrap)

    def subs_check_rho(self, sigma: Ty, rho: Ty) -> Wrapper:
        match (sigma, rho):
            case (TyForall(), _):          # DSK/SPEC
                in_rho, in_wrap = self.instantiate(sigma)
                res_wrap = self.subs_check_rho(in_rho, rho)
                return WpCompose(res_wrap, in_wrap)
            case (rho1, TyFun(a2, r2)):    # DSK/FUN
                (a1, r1) = self.unify_fun(rho1)
                return self.subs_check_fun(a1, r1, a2, r2)
            case (TyFun(a1, r1), rho2):
                (a2, r2) = self.unify_fun(rho2)
                return self.subs_check_fun(a1, r1, a2, r2)
            case (tau1, tau2):             # DSK/MONO
                unify(tau1, tau2)
                return WpCast(tau1, tau2)

    def subs_check_fun(self, a1: Ty, r1: Ty, a2: Ty, r2: Ty) -> Wrapper:
        # a2 -> a1
        arg_wrap =self.subs_check(a2, a1)     # contravariant
        # r1 -> r2
        res_wrap = self.subs_check_rho(r1, r2) # covariant
        # a2 -> r2
        return WpFun(a2, arg_wrap, res_wrap)

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

    def skolemise(self, ty: Ty) -> tuple[list[SkolemTv], Ty, Wrapper]:
        """
        Create weak prenex formed rho type with skolemise type vars filled
        """
        match ty:
            case TyForall(tvs, body):
                sks1 = [self.make_skolem(name) for name in varnames(tvs)]
                sks2, ty2, sk_wrap = self.skolemise(subst_ty(tvs, sks1, body))
                res_wrap = reduce(lambda acc, w: WpCompose(WpTyLam(w), acc), reversed(sks1), sk_wrap)
                return sks1 + sks2, ty2, res_wrap
            case TyFun(arg_ty, res_ty):
                sks, res_ty2, wrap = self.skolemise(res_ty)
                # a -> rho to a -> sigma
                res_wrap = WpFun(arg_ty, WP_HOLE, wrap)
                return sks, TY.fun(arg_ty, res_ty2), res_wrap
            case _:
                # TODO: subst_ty _ ty for type constructor
                return [], ty, WP_HOLE

    def instantiate(self, sigma: Ty) -> tuple[Ty, Wrapper]:
        """
        Instantiate top-level forall type variables in sigma with fresh meta variables.
        sigma -> rho
        """
        match sigma:
            case TyForall(vars, ty):
                mvs = [self.make_meta() for _ in vars]
                inst_ty = subst_ty(vars, mvs, ty)
                return inst_ty, WP_HOLE
            case _:
                return sigma, WP_HOLE

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
