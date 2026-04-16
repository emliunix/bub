"""
bidirectional type checking for the surface language.
supports:
    - data types
    - patterns
    - recursion groups (discovered by SCC analysis)
"""

import functools
import itertools

from abc import ABC, abstractmethod
from contextlib import contextmanager
from collections.abc import Generator, Sequence
from dataclasses import dataclass
from typing import Callable, TypeVar, cast, override

from systemf.utils import capture_return

from .scc import SccGroup
from .reader_env import ReaderEnv
from .types import ast, Name, NameGenerator, REPLContext
from .types.ast import AnnotName, Expr, Pat, ConPat, VarPat, LitPat, WildcardPat
from .types.core import C, CoreTm
from .types.tything import ACon, ATyCon, TyThing, TypeEnv
from .types.wrapper import WP_HOLE, WpCast, WpTyApp, WpTyLam, Wrapper, WrapperRunner, mk_wp_ty_lams, wp_compose, wp_fun, zonk_wrapper
from .types.ty import BoundTv, Lit, MetaTv, Ref, SkolemTv, Ty, TyConApp, TyForall, TyFun, TyVar, get_free_vars, get_meta_vars, subst_ty, varnames, zonk_type

from systemf.utils.uniq import Uniq


class Expect(ABC):
    @abstractmethod
    def read(self) -> Ty: ...


@dataclass
class Infer(Expect):
    lvl: int
    ref: Ref[Ty]

    def set(self, ty: Ty):
        self.ref.set(ty)

    def read(self) -> Ty:
        ty = self.ref.get()
        if ty is None:
            raise Exception("Inference failed")
        return ty

@dataclass
class Check(Expect):
    ty: Ty

    def read(self) -> Ty:
        return self.ty


T = TypeVar('T')


def run_infer(fun: Callable[[Infer], T]) -> tuple[Ty, T]:
    """Run inference on a term and return the inferred type."""
    ref = Ref[Ty]()
    out = fun(Infer(ref))
    ty = ref.get()
    if ty is None:
        raise Exception("Inference failed")
    return ty, out


type TyCk[T] = Callable[[], T]


type TyCkRes = TyCk[CoreTm]


class TcCtx(ABC):
    uniq: Uniq
    type_env: TypeEnv
    tc_level: int

    def __init__(self, uniq: Uniq):
        self.uniq = uniq
        self.type_env = {}
        self.tc_level = 0

    @contextmanager
    def extend_env(self, name_things: list[tuple[Name, TyThing]]) -> Generator[None, None, None]:
        for (name, thing) in name_things:
            self.type_env[name] = thing
        try:
            yield
        finally:
            for (name, _) in name_things:
                if name in self.type_env:
                    del self.type_env[name]

    @contextmanager
    def push_level(self) -> Generator[None, None, None]:
        self.tc_level += 1
        try:
            yield
        finally:
            self.tc_level -= 1

    # ---
    # type env

    @abstractmethod
    def lookup_gbl(self, name: Name) -> TyThing: ...

    def lookup_local(self, name: Name) -> TyThing | None:
        return self.type_env.get(name)

    def lookup(self, name: Name) -> TyThing:
        if (th := self.lookup_local(name)) is not None:
            return th
        return self.lookup_gbl(name)

    def lookup_tycon(self, name: Name) -> ATyCon:
        match self.lookup(name):
            case ATyCon() as a:
                return a
            case a:
                raise Exception(f"Expected tycon, but got: {a}")
            
    def lookup_datacon(self, name: Name) -> ACon:
        match self.lookup(name):
            case ACon() as a:
                return a
            case a:
                raise Exception(f"Expected datacon, but got: {a}")

    # ---
    # uniq vars

    def make_meta(self, gv_lvl: int | None = None) -> MetaTv:
        lvl = gv_lvl if gv_lvl is not None else self.tc_level
        return MetaTv(self.uniq.make_uniq(), lvl, Ref())

    def make_skolem(self, name: Name, gv_lvl: int | None = None) -> SkolemTv:
        lvl = gv_lvl if gv_lvl is not None else self.tc_level
        return SkolemTv(name, self.uniq.make_uniq(), lvl)


class Unifier(TcCtx, ABC):

    def __init__(self, uniq: Uniq):
        super().__init__(uniq)

    # ---
    # subsumption check

    def subs_check(self, sigma1: Ty, sigma2: Ty) -> Wrapper:
        """
        Subsumption check between two types.

        sigma1 can be instantiated to sigma2.
        The wrapper is sigma1 ~~> sigma2.
        """
        with self.push_level():
            sks, rho2, sks_wrap = self.skolemise(sigma2)  # rho2 ~~> sigma2
            subs_wrap = self.subs_check_rho(sigma1, rho2)  # sigma1 ~~> rho2
        # skolem var escape is not possible by construction with levels
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
                self.unify(tau1, tau2)
                return WpCast(tau1, tau2)

    def subs_check_fun(self, a1: Ty, r1: Ty, a2: Ty, r2: Ty) -> Wrapper:
        # a2 ~> a1
        arg_wrap = self.subs_check(a2, a1)     # contravariant
        # r1 ~> r2
        res_wrap = self.subs_check_rho(r1, r2) # covariant
        # (a1 -> r1) ~> (a2 -> r2)
        return wp_fun(a2, arg_wrap, res_wrap)

    # ---
    # helpers

    def skolemise_shallow(self, ty: Ty, gv_lvl: int | None) -> tuple[list[SkolemTv], Ty, Wrapper]:

        def _split_foralls(ty: Ty) -> tuple[list[TyVar], Ty]:
            match ty:
                case TyForall(tvs, body):
                    tvs2, body2 = _split_foralls(body)
                    return tvs + tvs2, body2
                case _: return [], ty

        tvs, body = _split_foralls(ty)
        sks = [self.make_skolem(name, gv_lvl) for name in varnames(tvs)]
        sks_ty = subst_ty(tvs, cast(list[Ty], sks), body)
        wrap = functools.reduce(lambda acc, w: wp_compose(WpTyLam(w), acc), reversed(sks), WP_HOLE)
        return sks, sks_ty, wrap
    
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
                sks2, ty2, sk_wrap = self.skolemise(subst_ty(tvs, cast(list[Ty], sks1), body))
                # /\sk1. /\sk2. ... /\ skn. sk_wrap body
                res_wrap = functools.reduce(lambda acc, w: wp_compose(WpTyLam(w), acc), reversed(sks1), sk_wrap)
                return sks1 + sks2, ty2, res_wrap
            case TyFun(arg_ty, res_ty):
                sks, res_ty2, wrap = self.skolemise(res_ty)
                # a -> rho
                # => a -> sigma
                res_wrap = wp_fun(arg_ty, WP_HOLE, wrap)
                return sks, TyFun(arg_ty, res_ty2), res_wrap
            case _:
                # ~~subst_ty _ ty for type constructor~~
                # never gonna be the case, TyConApp args are always mono types
                return [], ty, WP_HOLE

    def instantiate(self: TcCtx, sigma: Ty) -> tuple[Ty, Wrapper]:
        """
        Instantiate top-level forall type variables in sigma with fresh meta variables.
        sigma -> rho
        """
        match sigma:
            case TyForall(vars, ty):
                mvs: list[Ty] = [self.make_meta() for _ in vars]
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
            case MetaTv(level=lvl) as m: # it must be a meta
                arg_ty = self.make_meta(gv_lvl=lvl)
                res_ty = self.make_meta(gv_lvl=lvl)
                self.unify(ty, TyFun(arg_ty, res_ty))
                return (arg_ty, res_ty)
            case _: raise Exception(f"Cant unify to function type, got: {ty}")

    def exp_to_ty(self, exp: Expect) -> Ty:
        match exp:
            case Infer(ref):
                if (ty := ref.get()) is not None:
                    return ty
                mty = self.make_meta()
                ref.set(mty)
                return mty
            case Check(ty):
                return ty
            case _:
                raise Exception("impossible")

    def unify(self, ty1: Ty, ty2: Ty):
        match ty1, ty2:
            case (BoundTv(), _) | (_, BoundTv()):
                raise Exception(f"Unexpected bound type variables to unify, got {ty1} and {ty2}")
            case (SkolemTv() as sk1, SkolemTv() as sk2) if sk1 == sk2:
                pass
            case (MetaTv() as m1, MetaTv() as m2) if m1 == m2:
                pass
            case (TyConApp(n1, args1), TyConApp(n2, args2)) if n1 == n2 and len(args1) == len(args2):
                # get arity from the real tycon to check args length with
                for a1, a2 in zip(args1, args2):
                    self.unify(a1, a2)
            case (MetaTv() as m, ty):
                self.unify_var(m, ty)
            case (ty, MetaTv() as m):
                self.unify_var(m, ty)
            case TyFun(a1, r1), TyFun(a2, r2):
                # that means on construction, fun type are probed and
                # fun of metas created instead of a single meta
                self.unify(a1, a2)
                self.unify(r1, r2)
            case _:
                raise Exception(f"Cannot unify types, got {ty1} and {ty2}")

    def unify_var(self, m: MetaTv, ty: Ty):
        """
        unify meta var to other type
        """
        match m:
            case MetaTv(ref=Ref(inner=None)):
                # bind right
                self.unify_unbound_var(m, ty)
            case MetaTv(ref=Ref(inner)) if inner:
                # unwrap left
                self.unify(inner, ty)

    def unify_unbound_var(self, m: MetaTv, ty: Ty):
        """
        unify unbound meta var to other type
        """
        if m in get_meta_vars([ty]):
            raise Exception(f"Occurrence check failed: got {m} in {ty}")
        match ty:
            case MetaTv(level=lvl2) as m2 if lvl2 > m.level:
                # promote
                mt = self.make_meta(m.level)
                m2.ref.set(mt)
                m.ref.set(mt)
            case SkolemTv(level=lvl2) as sk if lvl2 > m.level:
                raise Exception(f"Cannot unify meta variable {m} with skolem variable {sk}")
            case _:
                m.ref.set(ty)

    def fill_infer(self, infer: Infer, ty: Ty):
        match infer:
            case Infer(ref=Ref(ty2)) if ty2 is not None:
                self.unify(ty2, ty)
            case Infer(ref):
                ref.set(ty)


# ---
# TypecheckExpr


class TypecheckExpr(Unifier):
    ctx: REPLContext
    name_gen: NameGenerator
    mod_name: str
    wrapper_runner: WrapperRunner
    reader_env: ReaderEnv
    gbl_type_env: TypeEnv

    def __init__(self,
                 ctx: REPLContext, mod_name: str,
                 name_gen: NameGenerator,
                 reader_env: ReaderEnv,
                 gbl_type_env: TypeEnv,
                 ):
        super().__init__(ctx.uniq)
        self.mod_name = mod_name
        self.ctx = ctx
        self.name_gen = name_gen
        self.wrapper_runner = WrapperRunner(name_gen)
        self.reader_env = reader_env
        self.gbl_type_env = gbl_type_env

    def bindings(self, bindings: list[tuple[Name | AnnotName, Expr]], cb: Callable[[]]):
        sccs = compute_sccs(bindings)
        def _go(scc: SccGroup[tuple[Name | AnnotName, Expr]]):
            match scc:
                case SccGroup(grp, False):
                    pass
                case SccGroup(grp, True):
                    pass
                case _:
                    raise Exception("impossible")

        functools.reduce(reversed([_go(scc) for scc in sccs]), lambda acc, f: lambda: f() or acc(), lambda: None)

    def patterns(self, pat: Pat, exp_ty: Expect) -> TypeEnv:
        type_env = {}
        def _go(pat, exp_ty):
            match pat:
                case VarPat(AnnotName(name, ty)) :
                    match exp_ty:
                        case Infer(ref):
                            pass
                        case Check(ty2):
                            sub_wrap = self.subs_check(ty2, ty)
                    yield (name, ty)
                    pass
                case VarPat(name):
                    yield (name, self.exp_to_ty(exp_ty))
                    pass
                case ConPat(con, pats):
                    pats_ty = self.unify_tycon(con, pat_ty)
                    for pat, pat_ty in zip(pats, pats_ty):
                        yield from _go(pat, pat_ty)
                    pass
                case LitPat(lit):
                    self.lit(lit, pat_ty)
        _go(pat, self.exp_to_ty(exp_ty))
        return type_env

    def pat_con(self, con: Name, exp: Expect, cb: Callable[[], T]) -> tuple[Wrapper, T]:
        dcon: ACon = self.lookup_datacon(con)
        def _go(exps: list[Expect]):
            pass
        return self.match_tycon(dcon.parent, exp, _go)

    def match_tycon(self, tycon_n: Name, exp: Expect, cb: Callable[list[Expect], T]) -> T:
        match exp:
            case Infer(ref):
                tycon = self.lookup_tycon(tycon_n)
                tyvar_infs = [tycon.tyvars]
                pass
            case Check(ty):
                pass
        pass

    def match_datacon(self, datacon_n: Name, exps: list[Expect], cb: Callable[[list[Expect]], T]) -> T:
        pass

    def expr(self, expr: Expr, exp: Expect) -> TyCk[CoreTm]:
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

    def _lam(self, args, body, exp: Expect):
        pass

    def _app(self, fun_, arg):
        fun, args = split_app(fun_, arg)
        fun_ty, fun_core = run_infer(lambda inf: self.expr(fun, inf))
        def _arg_tys(ty, args):
            for _ in args:
                (arg_ty, res_ty) = self.unify_fun(ty)
                yield arg_ty
                ty = res_ty
            return ty
        with capture_return(_arg_tys(fun_ty, args)) as (arg_tys_gen, res):
            arg_tys = list(arg_tys_gen)
            ret_ty = res[0]

        for arg, arg_ty in zip(args, arg_tys):
            args_core = self.poly_check_expr(arg, Check(arg_ty))

        # functools.reduce(C.)

        # for zip(args, arg_tys)

    def lit(self, v: Lit, exp: Expect) -> TyCkRes:
        match exp:
            case Infer(ref):
                ref.set(v.ty)
            case Check(ty):
                unify(v.ty, ty)
        return self.out(lambda: C.lit(v))

    @override
    def var(self, name: str) -> TyCkRes:
        def _go(env: Env, exp: Expect) -> Defer[OUT]:
            ty = lookup_env(name, env)
            wrap = self.inst(ty)(env, exp)
            def _core():
                return self.core.var(name, ty)
            return self.with_wrapper(wrap, _core)
        return _go

    def lam(self, args: list[Name | AnnotName], body: Expr, exp: Expect) -> TyCkRes:
        def _go(arg_exps: Sequence[Expect], ret_exp: Expect):
            def _go_body(env: TypeEnv) -> TyCkRes:
                return self.expr(body, ret_exp)

            w, e = self.matches([cast(Pat, VarPat(a)) for a in args], arg_exps, _go_body)
            return self.wrapped_out(w, e)

        w, e = self.match_expected_fun_tys(exp, len(args), _go)
        return self.wrapped_out(w, e)

    def match_expected_fun_tys(self, exp: Expect, arity: int, cb: Callable[[Sequence[Expect], Expect], T]) -> tuple[Wrapper, T]:
        """
        Compared to unify_fun, this function propagates mode.
        """
        match exp:
            case Infer() as inf:
                return self._match_fun_tys_infer(inf, arity, cb)
            case Check(ty):
                return self._match_fun_tys_check(ty, arity, cb)
            case _: raise Exception("impossible")

    @staticmethod
    def _check_not_none(t: T | None) -> T:
        if t is None:
            raise Exception("unexpected None")
        return t

    def _match_fun_tys_infer(self, inf: Infer, arity: int, cb: Callable[[list[Infer], Infer], T]) -> tuple[Wrapper, T]:
        args_infs = [Infer(Ref()) for _ in range(arity)]
        res_inf = Infer(Ref())

        res = cb(args_infs, res_inf)

        args_tys = [self._check_not_none(arg_inf.ref.get()) for arg_inf in args_infs]
        res_ty = self._check_not_none(res_inf.ref.get())

        self.fill_infer_or_check(inf, functools.reduce(lambda acc, arg_ty: TyFun(arg_ty, acc), reversed(args_tys), res_ty))
        return WP_HOLE, res

    def _match_fun_tys_check(self, check_ty: Ty, arity: int, cb: Callable[[list[Check], Check], T]) -> tuple[Wrapper, T]:
        def _go(ty, ar, acc):
            match (ty, ar):
                case (TyForall() as ty2, n):
                    # skolemize
                    skvs, rho, w = self.skolemise1(ty2, self.tc_level + 1)
                    (arg_ty, res_ty) = self.unify_fun(rho)
                    acc.append(Check(arg_ty))
                    return _go(res_ty, n, acc)
                case (TyFun(arg_ty, res_ty), n) if n > 0:
                    acc.append(Check(arg_ty))
                    return _go(res_ty, n - 1, acc)
                case (_, 0):
                    return WP_HOLE, (list(reversed(acc)), Check(ty))
                case _: raise Exception("impossible")

        if not (arity > 0):
            raise Exception("arity must be at least 1")

        w, (arg_exps, ret_exp) = _go(check_ty, arity, [])
        with self.push_level():
            return (w, cb(arg_exps, ret_exp))

    def matches(self, pats: list[Pat], pat_tys: Sequence[Expect], cb: Callable[[TypeEnv], T]) -> tuple[Wrapper, T]:
        pass

    # @override
    # def lam(self, name: str, body: TyCkRes) -> TyCkRes:
    #     def _go(env: Env, exp: Expect) -> Defer[OUT]:
    #         match exp:
    #             case Infer(ref):
    #                 # Infer: create fresh meta for arg, infer body, construct fun type
    #                 arg_ty = self.make_meta()
    #                 body_ty, e_body = run_infer(extend_env(name, arg_ty, env), body)
    #                 result_ty = TyFun(arg_ty, body_ty)
    #                 ref.set(result_ty)
    #                 return lambda: self.core.lam(name, arg_ty, e_body())
    #             case Check(ty2):
    #                 # Check: decompose function type and check body against result
    #                 (arg_ty, res_ty) = self.unify_fun(ty2)
    #                 e = self.poly(body)(extend_env(name, arg_ty, env), Check(res_ty))
    #                 return lambda: self.core.lam(name, arg_ty, e())
    #             case _:
    #                 raise Exception("impossible")
    #     return _go

    # @override
    # def alam(self, name: str, sigma: Ty, body: TyCkRes) -> TyCkRes:
    #     def _go(env: Env, exp: Expect) -> Defer[OUT]:
    #         match exp:
    #             case Infer(ref):
    #                 # Infer: sigma is the arg type
    #                 res_ty, e_body = run_infer(extend_env(name, sigma, env), body)
    #                 result_ty = TyFun(sigma, res_ty)
    #                 ref.set(result_ty)
    #                 return lambda: self.core.lam(name, sigma, e_body())
    #             case Check(ty2):
    #                 # Check: decompose function type, check sigma <: arg_ty, check body
    #                 (arg_ty, res_ty) = self.unify_fun(ty2)
    #                 arg_wrap = self.subs_check(arg_ty, sigma)
    #                 res_e = self.poly(body)(extend_env(name, sigma, env), Check(res_ty))
    #                 def _core():
    #                     fresh_var = self.make_name("d")
    #                     arg_co = self.with_wrapper(arg_wrap, lambda: self.core.var(name, sigma))()
    #                     body = self.core.subst(name, self.core.var(fresh_var, arg_ty), res_e())
    #                     return self.core.lam(name, sigma,
    #                         self.core.let(fresh_var, arg_ty, arg_co, body))
    #                 return _core
    #             case _:
    #                 raise Exception("impossible")
    #     return _go

    # @override
    # def app(self, fun: TyCkRes, arg: TyCkRes) -> TyCkRes:
    #     def _go(env: Env, exp: Expect) -> Defer[OUT]:
    #         # First infer the function type
    #         fun_ty, fun_core = run_infer(env, fun)
    #         # Decompose to arg and result types
    #         (arg_ty, res_ty) = self.unify_fun(fun_ty)
    #         # Check argument against expected arg type
    #         arg_core = self.poly(arg)(env, Check(arg_ty))
    #         # inst res_ty
    #         res_wrap = self.inst(res_ty)(env, exp)
    #         return self.with_wrapper(res_wrap, lambda: self.core.app(fun_core(), arg_core()))
    #     return _go

    # def annot(self, expr: Expr, sigma: Ty, exp: Expect) -> TyCkRes:
    #     # Check expression against annotated type
    #     e = self.poly_check_expr(expr, sigma)
    #     wrap = self.inst(sigma, exp)
    #     return self.wrapped_out(wrap, e)

    # @override
    # def let(self, name: str, expr: TyCkRes, body: TyCkRes) -> TyCkRes:
    #     def _go(env: Env, exp: Expect) -> Defer[OUT]:
    #         # Infer polymorphic type for expr
    #         sigma, e_expr = run_infer(env, self.poly(expr))
    #         # Extend environment and continue with body
    #         env_ = extend_env(name, sigma, env)
    #         e_body = body(env_, exp)
    #         return lambda: self.core.let(name, sigma, e_expr(), e_body())
    #     return _go

    def let(self, bindings: list[tuple[Name, AnnotName, Expr]], body: Expr, exp: Expect) -> TyCkRes:

        pass

    # ---
    # poly (GEN1, GEN2)

    def poly_check_expr(self, check: Callable[[Ty], TyCkRes], ty: Ty) -> TyCkRes:
        """
        Check expr against a poly type.

        Skolemise and type check with the rho type.
        Check for skolem escape afterwards.
        """
        # Skolemise and check
        with self.push_level():
            # sk_wrap: rho ~~> sigma
            sks, rho, sk_wrap = self.skolemise(ty)
            e = check(rho)
        # Check skolem var escape
        return self.wrapped_out(sk_wrap, e)

    def poly_infer_expr(self, expr: Expr, exp: Infer) -> TyCkRes:
        """
        By quantify over unbound meta vars.
        """
        ty, e = run_infer(lambda inf: self.expr(expr, inf))
        forall_tvs = [m for m in get_meta_vars([ty]) if m.level == self.tc_level + 1]
        binders, [sigma_ty] = self.quantify(forall_tvs, [ty])
        exp.set(sigma_ty)
        return self.wrapped_out(mk_wp_ty_lams(binders, WP_HOLE), e)

    # ---
    # inst (INST1, INST2)

    def inst(self, ty: Ty, exp: Expect) -> Wrapper:
        """
        The inst judgment - instantiate a polymorphic type.
        """
        match exp:
            case Infer(ref):
                # instantiate by inserts type applications
                instantiated, wrap = self.instantiate(ty)
                ref.set(instantiated)
                return wrap
            case Check(ty2):
                # subsumption check and produce casts
                # reordred type args by eta expansion, TyLam & TyApp
                return self.subs_check_rho(ty, ty2)
            case _:
                raise Exception("impossible")

    def quantify(self, tvs: list[MetaTv], tys: list[Ty]) -> tuple[list[TyVar], list[Ty]]:
        """
        Quantify a type over a list of meta type variables.
        """
        if not tvs:
            return [], tys

        used_names = set(itertools.chain(*[varnames(binders_of_ty(ty)) for ty in tys]))
        binders: list[TyVar] = list(itertools.islice(
            (BoundTv(self.name_gen.new_name(n, None)) for n in allnames() if n not in used_names),
            len(tvs)
        ))

        # bind meta to bound vars
        for tv, n in zip(tvs, binders):
            tv.ref.set(n)

        return binders, [TyForall(binders, zonk_type(ty)) for ty in tys]

    # ---
    # helpers

    @override
    def lookup_gbl(self, name: Name) -> TyThing:
        if (th := self.gbl_type_env.get(name)) is not None:
            return th
        raise Exception(f"{name} not found")

    def fill_infer_or_check(self, exp: Infer, ty: Ty):
        match exp:
            case Infer(ref):
                if (t := ref.get()) is not None:
                    unify(t, ty)
                else:
                    ref.set(ty)

    def out(self, fn: Callable[[], CoreTm]) -> TyCkRes:
        """
        Just to expose TyCkRes as plain type to internals and also ensure types.
        """
        return fn

    def wrapped_out(self, w: Wrapper, fn: Callable[[], CoreTm]) -> TyCkRes:
        def _go():
            return self.wrapper_runner.run_wrapper(zonk_wrapper(w), fn())
        return _go


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


def split_app(fun: Expr, arg: Expr) -> tuple[Expr, list[Expr]]:
    """
    traverse along the func (left) side of app chain to split into
    fun and args
    """
    args = [arg]
    while isinstance(fun, ast.App):
        args.append(fun.arg)
        fun = fun.func
    return fun, list(reversed(args))
