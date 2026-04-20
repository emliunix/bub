
import functools

from collections.abc import Generator
from dataclasses import dataclass
from typing import Callable, TypeVar, cast, override

from systemf.utils import run_capture_return

from .types import Name, NameGenerator, REPLContext
from .types.ast import Ann, AnnotName, App, Binding, Case, CaseBranch, Expr, Lam, Let, LitExpr, Pat, ConPat, Var, VarPat, LitPat, WildcardPat
from .types.core import C, CoreTm
from .types.tything import AnId, TyThing, TypeEnv
from .types.wrapper import WP_HOLE, Wrapper, WrapperRunner, mk_wp_ty_lams, wp_compose, zonk_wrapper
from .types.ty import Id, Lit, LitInt, MetaTv, Ty, TyConApp, TyForall, TyFun, TyVar, get_meta_vars, subst_ty, zonk_type
from .types.xpat import XPat, XPatCo, XPatLit, XPatCon, XPatVar, XPatWild

from .matchc import MRInfallible, MatchC, MatchResult, mr_run
from .reader_env import ReaderEnv
from .tc_ctx import Expect, Infer, Check, TyCkRes, Unifier



T = TypeVar("T")
R = TypeVar("R")


type Checker[I, O, R] = Callable[[I, Callable[[], R]], tuple[O, R]]


type CB[R] = Callable[[], R]


@dataclass
class InstFunArg:
    ty: Ty


@dataclass
class InstFunWrap:
    wrap: Wrapper


type InstFun = InstFunArg | InstFunWrap


class TypeChecker(Unifier):
    ctx: REPLContext
    name_gen: NameGenerator
    wrapper_runner: WrapperRunner
    matchc: MatchC
    reader_env: ReaderEnv
    gbl_type_env: TypeEnv

    def __init__(self,
                 ctx: REPLContext, 
                 mod_name: str,
                 name_gen: NameGenerator,
                 reader_env: ReaderEnv,
                 gbl_type_env: TypeEnv,
                 ):
        super().__init__(mod_name, ctx.uniq)
        self.ctx = ctx
        self.name_gen = name_gen
        self.wrapper_runner = WrapperRunner(name_gen)
        self.matchc = MatchC(self, name_gen)
        self.reader_env = reader_env
        self.gbl_type_env = gbl_type_env

    @override
    def lookup_gbl(self, name: Name) -> TyThing:
        if (r := self.gbl_type_env.get(name)) is not None:
            return r
        if (r := self.ctx.load(name.mod).items.get(name)) is not None:
            return r
        raise Exception(f"global item not found {name}")

    # ---
    # expression

    def expr(self, expr: Expr, exp: Expect) -> TyCkRes:
        match expr:
            case Var(var):
                return self.var(var, exp)
            case LitExpr(lit):
                return self.lit(lit, exp)
            case Ann(name, ty):
                return self.annot(name, ty, exp)
            case Lam(args, body):
                return self.lam(args, body, exp)
            case Let(bs, body):
                return self.let(bs, body, exp)
            case Case(scr, brs):
                return self.case_expr(scr, brs, exp)
            case App() | LitExpr() | Var():
                return self.app(expr, exp)
            case _: raise Exception("unreachable")

    def var(self, name: Name, exp: Expect) -> TyCkRes:
        match self.lookup(name):
            case AnId(id=Id(ty=ty) as id):
                rho, w = self.instantiate(ty)
                self.exp_set_ty(rho, exp)
                return self.with_wrapper(w, lambda: C.var(id))
            case thing: raise Exception(f"expected AnId for {name}, got: {thing}")

    def lit(self, lit: Lit, exp: Expect) -> TyCkRes:
        self.exp_set_ty(lit.ty, exp)
        return lambda: C.lit(lit)

    def app(self, expr: Expr, exp: Expect) -> TyCkRes:
        """
        Function application.

        if args is empty, this is just a plain value. That's how GHC works, dispatch var to tcApp,
        but our expr doesn't dispatch var to app, cause it will be an infinite loop, simply wrong.
        """
        fun, args = self.split_app(expr)
        fun_ty, fun_c = self.run_infer(lambda inf: self.expr(fun, inf))
        arg_insts, res_ty = self.inst_fun(fun_ty, len(args))

        args_stack = list(reversed(args))
        res = fun_c
        def _mk_app_c(fun: TyCkRes, arg: TyCkRes) -> TyCkRes:
            return lambda: C.app(fun(), arg())
        # applies all insts
        for inst in arg_insts:
            match inst:
                case InstFunArg(arg_ty):
                    arg_c = self.poly_check_expr(args_stack.pop(), arg_ty)
                    res = _mk_app_c(res, arg_c)
                case InstFunWrap(wrap):
                    res = self.with_wrapper(wrap, res)
                case _: raise Exception("unreachable")
        if args_stack:
            raise Exception("arity mismatch in app")
        # now res should be the app of function with all args, of sigma type
        res_w = self.inst(res_ty, exp)
        return self.with_wrapper(res_w, res)

    def let(self, bindings: list[Binding], body: Expr, exp: Expect) -> TyCkRes:
        def _body(bindings_tc: list[tuple[Id, TyCkRes]]) -> TyCkRes:
            # the ids already in scope
            body_c = self.expr(body, exp)
            def _core():
                def _go(body: CoreTm, bind: tuple[Id, TyCkRes]) -> CoreTm:
                    id, bind_c = bind
                    return C.let(id, bind_c(), body)
                return functools.reduce(_go, reversed(bindings_tc), body_c())
            return _core
        return self.bindings(bindings, _body)

    def lam(self, args: list[Name | AnnotName], body: Expr, exp: Expect) -> TyCkRes:
        def _go(arg_exps: list[Expect], res_exp: Expect) -> tuple[list[XPat], TyCkRes]:
            def _body() -> TyCkRes:
                return self.expr(body, res_exp)
            def _go_pat(t: tuple[Name | AnnotName, Expect], cb: CB[TyCkRes]) -> tuple[XPat, TyCkRes]:
                arg, exp = t
                return self.pat(VarPat(arg), exp, cb)
            return multiple(list(zip(args, arg_exps)), _go_pat, _body)
        
        w, arg_tys, res_ty, (arg_pats, body_c) = self.match_funtys(len(args), exp, _go)

        def _name(name: Name | AnnotName) -> Name:
            match name:
                case Name() as n: return n
                case AnnotName(n, _): return n

        arg_ids = [self.name_gen.new_id(f"_{_name(arg).surface}", arg_ty) for arg, arg_ty in zip(args, arg_tys)]
        
        def _core() -> CoreTm:
            mr = self.matchc.matchc(arg_ids, res_ty, [(arg_pats, MRInfallible(body_c()))])
            body = mr_run(mr, C.lit(LitInt(0)))  # FIX: dummy error handler
            return functools.reduce(lambda body, id: C.lam(id, body), arg_ids, body)

        return self.with_wrapper(w, _core)

    def annot(self, expr: Expr, ty: Ty, exp: Expect) -> TyCkRes:
        w = self.inst(ty, exp)
        return self.with_wrapper(w, self.poly_check_expr(expr, ty))

    def case_expr(self, scrutinee: Expr, branches: list[CaseBranch], exp: Expect) -> TyCkRes:
        scr_ty, scr_c = self.run_infer(lambda inf: self.expr(scrutinee, inf))
        def _rhs(rhs: Expr) -> TyCkRes:
            return self.expr(rhs, exp)
        def _branch(br: CaseBranch) -> tuple[XPat, TyCkRes]:
            pat, rhs = br.pattern, br.body
            return self.pat(pat, Check(scr_ty), lambda: _rhs(rhs))
        
        brs = [_branch(br) for br in branches]
        scr_id = self.name_gen.new_id(lambda i: f"_scrut_{i}", scr_ty)
        
        def _core() -> CoreTm:
            eqns = [([p], cast(MatchResult, MRInfallible(rhs()))) for p, rhs in brs]
            mr = self.matchc.matchc([scr_id], scr_ty, eqns)
            return C.let(scr_id, scr_c(), mr_run(mr, C.lit(LitInt(0))))  # FIX: dummy error handler

        return _core

    # ---
    # patterns

    def pat(self, pat: Pat, exp: Expect, cb: CB[R]) -> tuple[XPat, R]:
        match pat:
            case VarPat(Name() as var):
                return self.pat_var(var, exp, cb)
            case VarPat(AnnotName(name, sig)):
                # TODO: extend syntax to support general sig pattern
                return self.pat_sig(VarPat(name), sig, exp, cb)
            case ConPat(con, pats):
                return self.pat_con(con, pats, exp, cb)
            case LitPat(lit):
                return self.pat_lit(lit, exp, cb)
            case WildcardPat():
                # TODO: force a type, meta if not type inferred
                _ = self.exp_to_ty(exp)
                return XPatWild(), cb()
            case _: raise Exception("unreachable")

    def pat_var(self, var: Name, exp: Expect, cb: CB[R]) -> tuple[XPat, R]:
        ty = self.exp_to_ty(exp)
        id = Id(var, ty)
        with self.extend_env([(var, AnId(var, id))]):
            # this is why we pass CB[R] for the whole family of pat methods
            return XPatVar(id), cb()
    
    def pat_sig(self, pat: Pat, sig: Ty, exp: Expect, cb: CB[R]) -> tuple[XPat, R]:
        w = self.subs_check_pat(exp, sig)
        pat_, res = self.pat(pat, Check(sig), cb)
        return XPatCo(w, sig, pat_), res

    def pat_con(self, con: Name, pats: list[Pat], exp: Expect, cb: CB[R]) -> tuple[XPat, R]:
        def _con_arg(t: tuple[Pat, Expect], cb: CB[R]) -> tuple[XPat, R]:
            pat, exp = t
            return self.pat(pat, exp, cb)
        
        w, tyconapp, arg_tys = self.match_datacon(con, exp)
        arg_exps: list[Expect] = [cast(Expect, Check(ty)) for ty in arg_tys]
        xpats, res = multiple(list(zip(pats, arg_exps)), _con_arg, cb)
        return self.mk_co_pat(w, tyconapp, XPatCon(con, xpats, arg_tys)), res

    def pat_lit(self, lit: Lit, exp: Expect, cb: CB[R]) -> tuple[XPat, R]:
        self.unify(lit.ty, self.exp_to_ty(exp))
        return XPatLit(lit), cb()

    def match_tyconapp(self, tycon_name: Name, ty: Ty) -> tuple[list[TyVar], list[Ty]]:
        tycon = self.lookup_tycon(tycon_name)
        tyvars = cast(list[TyVar], tycon.tyvars)
        ty = zonk_type(ty)
        match ty:
            case TyConApp(name2, args) if name2 == tycon_name:
                return tyvars, args
            case _:
                tys = [cast(Ty, self.make_meta()) for _ in range(len(tyvars))]
                self.unify(ty, TyConApp(tycon_name, tys))
                return tyvars, tys

    def match_datacon(self, con_name: Name, exp: Expect) -> tuple[Wrapper, Ty, list[Ty]]:
        con = self.lookup_datacon(con_name)
        ty = self.exp_to_ty(exp)
        rho, w_inst = self.instantiate(ty)
        tyvars, tyargs = self.match_tyconapp(con.parent, rho)
        return w_inst, rho, [subst_ty(tyvars, tyargs, arg_ty) for arg_ty in con.field_types]

    def subs_check_pat(self, res: Expect, ty: Ty) -> Wrapper:
        match res:
            # TODO: check this, meta expects mono, what about Expect
            case Infer():
                self.fill_infer(res, ty)
                return WP_HOLE
            case Check(res_ty):
                return self.subs_check(res_ty, ty)
            case _: raise Exception("unreachable")

    def mk_co_pat(self, co: Wrapper, ty: Ty, pat: XPat) -> XPat:
        if co == WP_HOLE:
            return pat
        else:
            return XPatCo(co, ty, pat)
        
    # ---
    # bindings

    def bindings(self, bindings: list[Binding], cb: Callable[[list[tuple[Id, TyCkRes]]], R]) -> R:
        def _bind1(bind: Binding) -> tuple[Id, TyCkRes]:
            match bind:
                case Binding(AnnotName(name, ty), expr):
                    return Id(name, ty), self.poly_check_expr(expr, ty)
                case Binding(Name() as name, expr):
                    # TODO: check the invariant Expect can hold poly type or not.
                    ty, res = self.run_infer(lambda inf: self.poly_infer_expr(expr, inf))
                    return Id(name, ty), res
                case _: raise Exception("unreachable")
        bind_res = [_bind1(bind) for bind in bindings]
        # TODO: scc into groups and properly handle recursive bindings.
        with self.extend_env([(id.name, AnId(id.name, id)) for id, _ in bind_res]):
            return cb(bind_res)

    # ---
    # helpers

    def split_app(self, expr: Expr) -> tuple[Expr, list[Expr]]:
        """Split a chain of applications into the function and the list of arguments."""
        def _go(expr: Expr) -> Generator[Expr, None, Expr]:
            match expr:
                case App(fun, arg):
                    res = yield from _go(fun)
                    yield arg
                    return res
                case _: return expr
        args, fun = run_capture_return(_go(expr))
        return fun, args

    def match_funtys(self, arity: int, exp: Expect, cb: Callable[[list[Expect], Expect], R]) -> tuple[Wrapper, list[Ty], Ty, R]:
        def _check1(ty: Ty) -> tuple[Wrapper, Ty, Ty]:
            match ty:
                case TyForall():
                    _, rho, w = self.skolemise_shallow(ty)
                    w2, ty_arg, ty_res = _check1(rho)
                    return wp_compose(w, w2), ty_arg, ty_res
                case TyFun(ty_arg, ty_res):
                    return WP_HOLE, ty_arg, ty_res
                case _:
                    raise Exception(f"Expected a function type, got {ty}")
                
        def _exp_ty(exp: Expect) -> Ty:
            match exp:
                case Infer(ref=ref) if (ty := ref.get()) is not None:
                    return ty
                case Check(ty):
                    return ty
                case _: raise Exception("typechecking failed")

        match exp:
            case Infer():
                mv_args = [cast(Expect, self.make_infer()) for _ in range(arity)]
                mv_res = self.make_infer()
                return WP_HOLE, list(map(_exp_ty, mv_args)), _exp_ty(mv_res), cb(mv_args, mv_res)
            case Check(ty):
                ws: list[Wrapper] = []
                arg_tys: list[Ty] = []
                res_ty: Ty = ty
                # NOTE: do we need to push more levels, say 1 per check1
                # GHC creates nested levels, investigate why
                # COMMENT: let's treat it like deep skolemisation. nested levels are only needed
                # when you have expressions in between, which causes unification
                # or for a simplified theoritical model
                with self.push_level():
                    for _ in range(arity):
                        w, arg_ty, res_ty = _check1(res_ty)
                        ws.append(w)
                        arg_tys.append(arg_ty)
                    return (
                        functools.reduce(lambda acc, c: wp_compose(c, acc), reversed(ws), WP_HOLE),
                        arg_tys,
                        res_ty,
                        cb(list(map(Check, arg_tys)), Check(res_ty))
                    )
            case _: raise Exception("unreachable")

    def inst_fun(self, ty: Ty, arity: int) -> tuple[list[InstFun], Ty]:
        def _inst(ty: Ty, arity: int) -> Generator[InstFun, None, Ty]:
            match ty:
                case _ if arity == 0:
                    return ty
                case TyForall():
                    # kind of like inst infer rule inlined
                    ty2, w = self.instantiate(ty)
                    yield InstFunWrap(w)
                    res_ty = yield from _inst(ty2, arity)
                    return res_ty
                case TyFun(ty_arg, res_ty):
                    yield InstFunArg(ty_arg)
                    res_ty2 = yield from _inst(res_ty, arity - 1)
                    return res_ty2
                case _:
                    raise Exception(f"Expected a function type, got {ty}")
        
        insts, ty = run_capture_return(_inst(zonk_type(ty), arity))
        return insts, ty
    
    # poly (GEN1, GEN2)

    def poly_check_expr(self, expr: Expr, sigma: Ty) -> TyCkRes:
        """
        Check expr against a poly type.

        Skolemise and type check with the rho type.
        Check for skolem escape afterwards.
        """
        # Skolemise and check
        with self.push_level():
            # sk_wrap: rho ~~> sigma
            _, rho, sk_wrap = self.skolemise(sigma)
            return self.with_wrapper(sk_wrap, self.expr(expr, Check(rho)))

    def poly_infer_expr(self, expr: Expr, exp: Infer) -> TyCkRes:
        """
        By quantify over unbound meta vars.
        """
        with self.push_level():
            ty, expr_c = self.run_infer(lambda inf: self.expr(expr, inf))
        forall_tvs = [m for m in get_meta_vars([ty]) if m.level == self.tc_level + 1]
        binders, [sigma_ty] = self.quantify(forall_tvs, [ty])
        self.fill_infer(exp, sigma_ty)
        return self.with_wrapper(mk_wp_ty_lams(binders, WP_HOLE), expr_c)

    # inst (INST1, INST2)

    def inst(self, ty: Ty, exp: Expect) -> Wrapper:
        """
        The inst judgment - instantiate a polymorphic type.
        """
        match exp:
            case Infer(ref):
                # instantiate by inserts type applications
                instantiated, wrap = self.instantiate(ty)
                self.fill_infer(exp, instantiated)
                return wrap
            case Check(ty2):
                # subsumption check and produce casts
                # reordred type args by eta expansion, TyLam & TyApp
                return self.subs_check_rho(ty, ty2)
            case _: raise Exception("impossible")

    def quantify(self, tvs: list[MetaTv], tys: list[Ty]) -> tuple[list[TyVar], list[Ty]]:
        """
        Quantify a type over a list of meta type variables.

        :param tvs: unbound meta type variables to quantify over
        """
        if not tvs:
            return [], tys
        
        sks = [cast(TyVar, self.make_skolem(lambda i: f"a{i}")) for _ in tvs]
        for tv, sk in zip(tvs, sks):
            tv.ref.set(sk)
        return sks, [TyForall(sks, zonk_type(ty)) for ty in tys]

    def exp_set_ty(self, ty: Ty, exp: Expect):
        match exp:
            case Infer():
                self.fill_infer(exp, ty)
            case Check(ty2):
                self.unify(ty, ty2)
            case _: raise Exception("unreachable")

    def run_infer(self, run: Callable[[Infer], R]) -> tuple[Ty, R]:
        infer = self.make_infer()
        res = run(infer)
        if (ty := infer.ref.get()) is None:
            raise Exception("expected inferred type, got None")
        return ty, res

    def with_wrapper(self, w: Wrapper, run: TyCkRes) -> TyCkRes:
        def _run():
            tm = run()
            zw = zonk_wrapper(w)
            return self.wrapper_runner.run_wrapper(zw, tm)
        return _run


A = TypeVar("A")


def multiple(xs: list[T], fun: Callable[[T, CB[R]], tuple[A,R]], cb: CB[R]) -> tuple[list[A], R]:
    ts: list[A] = []
    def _mk_go(x: T, cb: CB[R]) -> CB[R]:
        def _go():
            t, r = fun(x, cb)
            # the first fun call, the last ts.append
            ts.append(t)
            return r
        return _go
    res = functools.reduce(lambda f, x: _mk_go(x, f), reversed(xs), cb)()
    return list(reversed(ts)), res