"""
"""
import itertools

from collections.abc import Generator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from functools import reduce
from typing import cast

from systemf.elab3.rename_expr import RenameExpr

from .builtins import BUILTIN_FALSE, BUILTIN_BIN_OPS, BUILTIN_LIST_CONS, BUILTIN_PAIR, BUILTIN_PAIR_MKPAIR, BUILTIN_TRUE

from .mod import Module
from .types import Lit, LitInt, LitString, Name, Ty, TyConApp, TyForall, TyFun, TyInt, TyString, TyVar, BoundTv
from .reader_env import ImportRdrElt, ImportSpec, LocalRdrElt, QualName, RdrElt, RdrName, ReaderEnv, UnqualName
from .tything import ACon, TyThing
from .ast import (
    Ann, AnnotName, App, Binding, Case, CaseBranch, ConPat, Expr, ImportDecl,
    Lam, Let, LitExpr, LitPat, Pat, RnDataDecl, RnTermDecl, Var, VarPat
)

from systemf.surface.types import (
    SurfaceDeclaration
)

from systemf.utils import capture_return
from systemf.utils.cons import Cons, lookup
from systemf.utils.location import Location
from systemf.utils.uniq import Uniq


@dataclass
class RenameResult:
    data_decls: list[RnDataDecl]
    term_decls: list[RnTermDecl]


type RnEnv = Cons[tuple[str, Name]]


class Rename:
    uniq: Uniq
    reader_env: ReaderEnv
    mod_name: str

    """
    Assign unique to names lexically.
    """
    def __init__(self, ctx: REPLContext, reader_env: ReaderEnv, mod_name: str):
        self.ctx = ctx
        self.uniq = ctx.uniq
        self.reader_env = reader_env
        self.mod_name = mod_name
        self.rename_expr = RenameExpr(reader_env, mod_name, ctx.uniq)

    def rename(self, ast: list[SurfaceDeclaration]) -> RenameResult:
        ast_imports, ast_datas, ast_terms = split_ast(ast)
        # imports
        imports = get_imports(ast_imports)
        modules = self.do_imports(imports)
        envs = [
            env_from_import_decl(mod, decl)
            for (mod, decl) in zip(modules, imports)]
        self.reader_env = reduce(lambda m1, m2: m1 + m2, envs, self.reader_env)

        # lhs
        lhs_data_names = self.rename_lhs_datas(ast_datas)
        lhs_term_names = self.rename_lhs_terms(ast_terms)
        self.reader_env = self.reader_env + env_from_local_names(
            itertools.chain(lhs_data_names, lhs_term_names))

        # rhs
        rn_datas = self.rename_rhs_datas(ast)
        rn_terms = self.rename_rhs_terms(ast)

        return RenameResult(rn_datas, rn_terms)
