
import functools
import itertools

from abc import ABC, abstractmethod
from contextlib import contextmanager
from collections.abc import Generator, Sequence
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar, cast, override

from systemf.utils import capture_return

from .types import ast, Name, NameGenerator, REPLContext
from .types.ast import AnnotName, Expr, Pat, ConPat, VarPat, LitPat, WildcardPat
from .types.core import C, CoreTm
from .types.tything import ACon, ATyCon, AnId, TyThing, TypeEnv
from .types.wrapper import WP_HOLE, WpCast, WpTyApp, WpTyLam, Wrapper, WrapperRunner, mk_wp_ty_lams, wp_compose, wp_fun, zonk_wrapper
from .types.ty import BoundTv, Id, Lit, MetaTv, Ref, SkolemTv, Ty, TyConApp, TyForall, TyFun, TyVar, get_free_vars, get_meta_vars, subst_ty, varnames, zonk_type

from .scc import SccGroup
from .reader_env import ReaderEnv
from .typecheck_expr import Expect, Infer, Check, TyCkRes, Unifier, TcCtx

from systemf.utils.uniq import Uniq


T = TypeVar("T")


type Checker[I, O, R] = Callable[[I, Callable[[], R]], tuple[O, R]]


@dataclass
class XPatLit:
    lit: Lit


@dataclass
class XPatCon:
    con: Name
    args: list[XPat]
    arg_tys: list[Ty]


@dataclass
class XPatVar:
    bndr: Id


@dataclass
class XPatCo:
    """
    Internal node for wrapper
    """
    co: Wrapper
    res_ty: Ty
    pat: XPat


@dataclass
class XPatWild:
    pass


type XPat = XPatCo | XPatLit | XPatCon | XPatVar | XPatWild


class TypeChecker(Unifier):
    ctx: REPLContext
    name_gen: NameGenerator
    mod_name: str
    wrapper_runner: WrapperRunner
    reader_env: ReaderEnv
    gbl_type_env: TypeEnv

    def __init__(self,
                 ctx: REPLContext, 
                 mod_name: str,
                 name_gen: NameGenerator,
                 reader_env: ReaderEnv,
                 gbl_type_env: TypeEnv,
                 ):
        super().__init__(ctx.uniq)
        self.ctx = ctx
        self.mod_name = mod_name
        self.name_gen = name_gen
        self.wrapper_runner = WrapperRunner(name_gen)
        self.reader_env = reader_env
        self.gbl_type_env = gbl_type_env

    @override
    def lookup_gbl(self, name: Name) -> TyThing:
        if (r := self.gbl_type_env.get(name)) is not None:
            return r
        if (r := self.ctx.load(name.mod).items.get(name)) is not None:
            return r
        raise Exception(f"global item not found {name}")

    def bindings(self, cb: Callable[[list[tuple[Name, TyThing, CoreTm]]], None]):
        pass

    def patterns(self, ) -> LPat[TyCkRes]:
        pass

    def pat(self, pat: Pat, exp: Expect, cb):
        match pat:
            case VarPat(Name() as var):
                with self.extend_env([(var, AnId(var, self.pat_bndr(var, exp)))]):
                    return cb()
            case VarPat(AnnotName(name, ty)):
                w = self.subs_check_pat(exp, ty)
                return self.pat(VarPat(name), Check(ty), cb)
            case ConPat(con, pats):
                pass
            case LitPat(lit):
                pass
            case WildcardPat():
                pass

    def pat_bndr(self, var: Name, exp: Expect):
        ty = self.exp_to_ty(exp)
        return Id(var, ty)
    
    def pat_sig(self, name: Name, ty: Ty, exp: Expect, ) -> tuple[Wrapper, Ty]:
        pass

    def pat_con(self, con: Name, pats: list[Pat], exp: Expect, cb):
        pass

    def match_tyconapp(self, tycon_name: Name, ty: Ty) -> tuple[list[TyVar], list[Ty]]:
        tycon = self.lookup_tycon(tycon_name)
        tyvars = cast(list[TyVar], tycon.tyvars)
        match zonk_type(ty):
            case TyConApp(name2, args) if name2 == tycon_name:
                return tyvars, args
            case _:
                tys = [cast(Ty, self.make_meta()) for _ in range(len(tyvars))]
                self.unify(ty, TyConApp(tycon_name, tys))
                return tyvars, tys

    def match_datacon(self, con_name: Name, exp: Expect) -> tuple[Wrapper, list[Ty]]:
        con = self.lookup_datacon(con_name)
        ty = self.exp_to_ty(exp)
        rho, w_inst = self.instantiate(ty)
        tyvars, tyargs = self.match_tyconapp(con.parent, rho)
        return w_inst, [subst_ty(tyvars, tyargs, arg_ty) for arg_ty in con.field_types]

    def subs_check_pat(self, res: Expect, ty: Ty) -> Wrapper:
        match res:
            # TODO: check this, meta expects mono, what about Expect
            case Infer(ref):
                ref.set(ty)
                return WP_HOLE
            case Check(res_ty):
                return self.subs_check(res_ty, ty)
            case _: raise Exception("unreachable")
