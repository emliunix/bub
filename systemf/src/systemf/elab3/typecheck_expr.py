"""
bidirectional type checking for the surface language.
supports:
    - data types
    - patterns
    - recursion groups (discovered by SCC analysis)
"""

from abc import ABC
from dataclasses import dataclass
from functools import reduce
import itertools

from systemf.elab3.scc import SccGroup
from systemf.elab3.types import ast
from systemf.elab3.types.ast import AnnotName, Expr
from systemf.elab3.types.core import CoreBuilder

from .types import Name, NameGenerator, REPLContext
from systemf.elab3.types.ty import BoundTv, MetaTv, Ref, Ty, TyForall, TyVar, zonk_type


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
        raise TyCkException("Inference failed")
    return ty, out

# ---
# TyCk - new style: just a function from (Env, Expect) to OUT

type TyCk[OUT] = Callable[[Env, Expect], OUT]
type Defer[OUT] = Callable[[], OUT]

# ---
# TypecheckExpr

class TypecheckExpr:
    mod_name: str
    ctx: REPLContext
    name_gen: NameGenerator
    core: CoreBuilder

    def __init__(self, mod_name: str, ctx: REPLContext, name_gen: NameGenerator, core: CoreBuilder):
        self.mod_name = mod_name
        self.ctx = ctx
        self.name_gen = name_gen
        self.core = core

    def tc_expr(self, expr: Expr) -> TyCk[Defer[OUT]]:
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

    def bindings(self, bindings: list[tuple[AnnotName, Expr]]):
        sccs = compute_sccs(bindings)
        def _go(scc: SccGroup[tuple[Name | AnnotName, Expr]]):
            match scc:
                case SccGroup([b], False):
                    pass
                case SccGroup(grp, True):
                    pass
                case _:
                    raise Exception("impossible")

        reduce(reversed([_go(scc) for scc in sccs]), lambda acc, f: lambda: f() or acc(), lambda: None)

    @override
    def lit(self, value: Lit) -> TyCk[Defer[OUT]]:
        def _go(env: Env, exp: Expect) -> Defer[OUT]:
            match exp:
                case Infer(ref):
                    ref.set(value.ty)
                case Check(ty):
                    unify(value.ty, ty)
                case _:
                    raise Exception("impossible")
            return lambda: self.core.lit(value)
        return _go

    @override
    def var(self, name: str) -> TyCk[Defer[OUT]]:
        def _go(env: Env, exp: Expect) -> Defer[OUT]:
            ty = lookup_env(name, env)
            wrap = self.inst(ty)(env, exp)
            def _core():
                return self.core.var(name, ty)
            return self.with_wrapper(wrap, _core)
        return _go

    @override
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
                case _:
                    raise Exception("impossible")
        return _go

    @override
    def alam(self, name: str, sigma: Ty, body: TyCk[Defer[OUT]]) -> TyCk[Defer[OUT]]:
        def _go(env: Env, exp: Expect) -> Defer[OUT]:
            match exp:
                case Infer(ref):
                    # Infer: sigma is the arg type
                    res_ty, e_body = run_infer(extend_env(name, sigma, env), body)
                    result_ty = TyFun(sigma, res_ty)
                    ref.set(result_ty)
                    return lambda: self.core.lam(name, sigma, e_body())
                case Check(ty2):
                    # Check: decompose function type, check sigma <: arg_ty, check body
                    (arg_ty, res_ty) = self.unify_fun(ty2)
                    arg_wrap = self.subs_check(arg_ty, sigma)
                    res_e = self.poly(body)(extend_env(name, sigma, env), Check(res_ty))
                    def _core():
                        fresh_var = self.make_name("d")
                        arg_co = self.with_wrapper(arg_wrap, lambda: self.core.var(name, sigma))()
                        body = self.core.subst(name, self.core.var(fresh_var, arg_ty), res_e())
                        return self.core.lam(name, sigma,
                            self.core.let(fresh_var, arg_ty, arg_co, body))
                    return _core
                case _:
                    raise Exception("impossible")
        return _go

    @override
    def app(self, fun: TyCk[Defer[OUT]], arg: TyCk[Defer[OUT]]) -> TyCk[Defer[OUT]]:
        def _go(env: Env, exp: Expect) -> Defer[OUT]:
            # First infer the function type
            fun_ty, fun_core = run_infer(env, fun)
            # Decompose to arg and result types
            (arg_ty, res_ty) = self.unify_fun(fun_ty)
            # Check argument against expected arg type
            arg_core = self.poly(arg)(env, Check(arg_ty))
            # inst res_ty
            res_wrap = self.inst(res_ty)(env, exp)
            return self.with_wrapper(res_wrap, lambda: self.core.app(fun_core(), arg_core()))
        return _go

    @override
    def annot(self, expr: TyCk[Defer[OUT]], sigma: Ty) -> TyCk[Defer[OUT]]:
        def _go(env: Env, exp: Expect) -> Defer[OUT]:
            # Check expression against annotated type
            e = self.poly(expr)(env, Check(sigma))
            wrap = self.inst(sigma)(env, exp)
            return self.with_wrapper(wrap, e)
        return _go

    @override
    def let(self, name: str, expr: TyCk[Defer[OUT]], body: TyCk[Defer[OUT]]) -> TyCk[Defer[OUT]]:
        def _go(env: Env, exp: Expect) -> Defer[OUT]:
            # Infer polymorphic type for expr
            sigma, e_expr = run_infer(env, self.poly(expr))
            # Extend environment and continue with body
            env_ = extend_env(name, sigma, env)
            e_body = body(env_, exp)
            return lambda: self.core.let(name, sigma, e_expr(), e_body())
        return _go

    # ---
    # poly (GEN1, GEN2)

    def poly(self, term: TyCk[Defer[OUT]]) -> TyCk[Defer[OUT]]:
        """
        The poly judgment - for checking polymorphic types.
        """
        def _go(env: Env, exp: Expect) -> Defer[OUT]:
            match exp:
                case Infer(ref):
                    ty, e = run_infer(env, term)
                    env_tys = env_types(env)
                    env_tvs = get_meta_vars(env_tys)
                    res_tvs = get_meta_vars([ty])
                    # ftv(ρ) - ftv(Γ)
                    # it's metavars cause it's metavars that are created
                    # when encountering unknown type during infer
                    # not in Gamma means they are local to ty
                    # and get_meta_vars call zonk so we're not fooled by linked metas
                    forall_tvs = [tv for tv in res_tvs if tv not in env_tvs]
                    binders, sigma_ty = quantify(forall_tvs, ty)
                    ref.set(sigma_ty)
                    return self.with_wrapper(mk_wp_ty_lams(binders, WP_HOLE), e)
                case Check(ty2):
                    # Skolemise and check
                    sks, rho2, sk_wrap = self.skolemise(ty2)
                    # sk_wrap: rho ~~> sigma
                    e = term(env, Check(rho2))
                    # Check skolem var escape
                    env_tys = env_types(env)
                    env_tvs = get_free_vars([ty2] + env_tys)
                    esc_tvs = set(sks).intersection(env_tvs)
                    if esc_tvs:
                        raise TyCkException(f"Skolem var escapes: {esc_tvs}")
                    return self.with_wrapper(sk_wrap, e)
                case _:
                    raise Exception("impossible")
        return _go

    # ---
    # inst (INST1, INST2)

    def inst(self, ty: Ty) -> TyCk[Wrapper]:
        """
        The inst judgment - instantiate a polymorphic type.
        """
        def _go(env: Env, exp: Expect) -> Wrapper:
            match exp:
                case Infer(ref):
                    instantiated, wrap = self.instantiate(ty)
                    ref.set(instantiated)
                    return wrap
                case Check(ty2):
                    wrap = self.subs_check_rho(ty, ty2)
                    return wrap
                case _:
                    raise Exception("impossible")
        return _go

    # ---
    # subsumption check

    def subs_check(self, sigma1: Ty, sigma2: Ty) -> Wrapper:
        """
        Subsumption check between two types.

        sigma1 can be instantiated to sigma2.
        The wrapper is sigma1 ~~> sigma2.
        """
        sks, rho2, sks_wrap = self.skolemise(sigma2)  # rho2 ~~> sigma2
        subs_wrap = self.subs_check_rho(sigma1, rho2)  # sigma1 ~~> rho2
        # check skolem var escape
        # this is more like a covering test, that skolem vars are all used
        esc_tvs = set(sks).intersection(get_free_vars([sigma1, sigma2]))
        if esc_tvs:
            raise TyCkException(f"Skolem var  escapes: {esc_tvs}")
        return wp_compose(sks_wrap, subs_wrap)

    def subs_check_rho(self, sigma: Ty, rho: Ty) -> Wrapper:
        match (sigma, rho):
            case (TyForall(), _):          # DSK/SPEC
                in_rho, in_wrap = self.instantiate(sigma)
                res_wrap = self.subs_check_rho(in_rho, rho)
                return wp_compose(res_wrap, in_wrap)
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
        # a2 ~> a1
        arg_wrap =self.subs_check(a2, a1)      # contravariant
        # r1 ~> r2
        res_wrap = self.subs_check_rho(r1, r2) # covariant
        # (a1 -> r1) ~> (a2 -> r2)
        return wp_fun(a2, arg_wrap, res_wrap)

    # ---
    # uniq vars

    def make_meta(self) -> MetaTv:
        return TY.meta(self.uniq.make_uniq())

    def make_skolem(self, name: str) -> SkolemTv:
        return TY.skolem(name, self.uniq.make_uniq())

    # ---
    # helpers

    def skolemise(self, ty: Ty) -> tuple[list[SkolemTv], Ty, Wrapper]:
        """
        Create weak prenex formed rho type with skolemise type vars filled

        The wrapper created is the witness of rho to sigma.
        eg. sa → sb → sa ~~> ∀a. a → ∀b. b → a
        where sa, sb are skolem vars
        """
        match ty:
            case TyForall(tvs, body):
                sks1 = [self.make_skolem(name) for name in varnames(tvs)]
                sks2, ty2, sk_wrap = self.skolemise(subst_ty(tvs, sks1, body))
                # /\sk1. /\sk2. ... /\ skn. sk_wrap body
                res_wrap = reduce(lambda acc, w: wp_compose(WpTyLam(w), acc), reversed(sks1), sk_wrap)
                return sks1 + sks2, ty2, res_wrap
            case TyFun(arg_ty, res_ty):
                sks, res_ty2, wrap = self.skolemise(res_ty)
                # a -> rho
                # => a -> sigma
                res_wrap = wp_fun(arg_ty, WP_HOLE, wrap)
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
                wrap = functools.reduce(lambda acc, ty: wp_compose(WpTyApp(ty), acc), mvs, WP_HOLE)
                return inst_ty, wrap
            case _:  # not a sigma type
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

    def with_wrapper(self, w: Wrapper, f: Defer[OUT]) -> Defer[OUT]:
        def _go() -> OUT:
            # the defer is intended to be called after full type inference
            # finished, when all meta vars are fully unified.
            w2 = zonk_wrapper(w)
            return run_wrapper(w2, self.uniq, self.core, f())
        return _go

    def make_name(self, prefix: str) -> str:
        return f"{prefix}{self.uniq.make_uniq()}"


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


def quantify(tvs: list[MetaTv], ty: Ty) -> tuple[list[TyVar], Ty]:
    """
    Quantify a type over a list of meta type variables.
    """
    if not tvs:
        return [], ty

    used_names = varnames(binders_of_ty(ty))
    binders: list[TyVar] = list(itertools.islice(
        (BoundTv(n) for n in allnames() if n not in used_names),
        len(tvs)
    ))

    # bind meta to bound vars
    for tv, n in zip(tvs, binders):
        tv.ref.set(n)

    return binders, TyForall(binders, zonk_type(ty))


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
