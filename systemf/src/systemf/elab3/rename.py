"""
"""
import itertools

from collections.abc import Generator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from functools import reduce
from typing import cast

from systemf.elab3.builtins import BUILTIN_FALSE, BUILTIN_PAIR, BUILTIN_PAIR_MKPAIR, BUILTIN_TRUE

from .mod import Module
from .types import LitInt, LitString, Name, Ty, TyConApp, TyForall, TyFun, TyInt, TyString, TyVar, BoundTv
from .reader_env import ImportRdrElt, ImportSpec, LocalRdrElt, QualName, RdrElt, RdrName, ReaderEnv, UnqualName
from .tything import ACon, TyThing
from .ast import Ann, AnnotName, App, Binding, Case, CaseBranch, ConPat, Expr, ImportDecl, Lam, Let, LitExpr, RnDataDecl, RnTermDecl, Var

from systemf.surface.types import (
    SurfaceAbs, SurfaceAnn, SurfaceApp, SurfaceCase, SurfaceDataDeclaration, SurfaceDeclaration, SurfaceDeclarationRepr, SurfaceIf, SurfaceLet,
    SurfaceLit, SurfaceTerm, SurfaceTermDeclaration, SurfaceTuple, SurfaceType, SurfaceTypeArrow,
    SurfaceTypeConstructor, SurfaceTypeForall, SurfaceTypeTuple, SurfaceTypeVar,
    SurfaceVar, ValBind
)

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


class RenameExpr:
    reader_env: ReaderEnv
    local_env: list[tuple[str, Name]]
    mod_name: str
    uniq: Uniq

    def __init__(self, reader_env: ReaderEnv, mod_name: str, uniq: Uniq):
        self.reader_env = reader_env
        self.mod_name = mod_name
        self.uniq = uniq
        self.local_env = []
        
    def lookup(self, name: RdrName, loc: Location | None = None) -> Name:
        match name:
            case UnqualName(name_) if (n := self.lookup_local_name(name_)) is not None:
                return n
            case _:
                return self.lookup_gbl_name(name, loc)

    def lookup_local_name(self, name: str) -> Name | None:
        for (occ, n) in reversed(self.local_env):
            if occ == name:
                return n
        return None

    def lookup_gbl_name(self, name: RdrName, loc: Location | None = None) -> Name:
        match self.reader_env.lookup(name):
            case []:
                raise Exception(f"unresolved variable: {name} at {loc}")
            case [n]:
                return n.name
            case xs:
                raise Exception(f"ambiguous name: {name} (candidates: {xs}) at {loc}")

    def new_name(self, name: str, loc: Location | None = None) -> Name:
        return Name(mod=self.mod_name, surface=name, unique=self.uniq.make_uniq(), loc=loc)

    @contextmanager
    def extend_local(self, names: list[Name]) -> Generator[None, None, None]:
        self.local_env.extend((name.surface, name) for name in names)
        yield
        for _ in range(len(names)):
            _ = self.local_env.pop()

    def rename_expr(self, ast: SurfaceTerm) -> Expr:
        match ast:
            case SurfaceVar(name=name, location=loc):
                return Var(self.lookup(UnqualName(name), loc))

            case SurfaceLit(prim_type=prim_type, value=value):
                match prim_type:
                    case "string":
                        return LitExpr(LitString(cast(str, value)))
                    case "int":
                        return LitExpr(LitInt(cast(int, value)))
                    case _:
                        raise Exception(f"unknown literal type: {prim_type}")

            case SurfaceAbs(params=params, body=body, location=loc):
                check_dups((n for (n, _) in params))
                names = [
                    self.new_name(param)
                    for (param, _) in params
                ]
                params_ = [
                    (AnnotName(name, self.rename_type(ty))) if ty else name
                    for ((_, ty), name) in zip(params, names)
                ]
                with self.extend_local(names):
                    body_ = self.rename_expr(body)
                return Lam(params_, body_)

            case SurfaceApp(func=func, arg=arg):
                return App(self.rename_expr(func), self.rename_expr(arg))

            case SurfaceLet(bindings=bindings, body=body):
                name_ty_locs = binding_names(bindings)
                names = [self.new_name(n, loc) for (n, _, loc) in name_ty_locs]
                anno_names = [
                    AnnotName(n, self.rename_type(ty)) if ty else n
                    for (n, (_, ty, _)) in zip (names, name_ty_locs)]

                with self.extend_local(names):
                    binding_rhss = [
                        self.rename_expr(b.value)
                        for b in bindings]
                    body_ = self.rename_expr(body)
                bindings_ = [
                    Binding(n, b)
                    for (n, b) in zip(anno_names, binding_rhss)]
                return Let(bindings_, body_)

            case SurfaceAnn(term=term, type=type_):
                return Ann(self.rename_expr(term), self.rename_type(type_))
            
            case SurfaceIf(cond=cond, then_branch=then_b, else_branch=else_b):
                return Case(self.rename_expr(cond), [
                    CaseBranch(ConPat(BUILTIN_TRUE, []), self.rename_expr(then_b)),
                    CaseBranch(ConPat(BUILTIN_FALSE, []), self.rename_expr(else_b)),
                ])
            
            # case SurfaceOp(left=left, op=op, right=right):
            #     # Operator: a + b
            #     pass
            
            case SurfaceTuple(elements=elements):
                return reduce(lambda acc, curr: App(App(Var(BUILTIN_PAIR_MKPAIR), curr), acc), reversed([
                    self.rename_expr(e) for e in elements
                ]))
            
            case SurfaceCase(scrutinee=scrutinee, branches=branches):
                # Case: case x of Pat -> body
                pass
            
            case _:
                raise Exception(f"unknown expr: {ast}")

    def rename_type(self, ty: SurfaceType) -> Ty:
        match ty:
            case SurfaceTypeVar(name=name, location=loc):
                return BoundTv(self.lookup(UnqualName(name)))
            case SurfaceTypeArrow(arg=arg, ret=ret, param_doc=param_doc):
                return TyFun(
                    self.rename_type(arg),
                    self.rename_type(ret),
                )
            case SurfaceTypeForall(var=var, body=body, location=loc):
                name = self.new_name(var, loc)
                with self.extend_local([name]):
                    return TyForall([BoundTv(name)], self.rename_type(body))
            case SurfaceTypeConstructor(name=name, args=args):
                match name:
                    case "Int":
                        return TyInt()
                    case "String":
                        return TyString()
                    case _:
                        pass
                tycon = self.lookup(UnqualName(name))
                args = [self.rename_type(a) for a in args]
                return TyConApp(tycon, args)
            case SurfaceTypeTuple(elements=elements):
                return reduce(lambda acc, curr: TyConApp(BUILTIN_PAIR, [curr, acc]), reversed([
                    self.rename_type(e) for e in elements
                ]))
            case _:
                raise Exception(f"unknown type: {ty}")


def env_from_import_decl(mod: Module, decl: ImportDecl) -> ReaderEnv:
    spec = ImportSpec(decl.module, decl.alias, decl.qualified)
    if decl.import_items:
        imports = set(decl.import_items)
        items = [item for item in mod.exports if item.surface in imports]
    else:
        hidings = set(decl.hiding_items or [])
        items = [item for item in mod.exports if item.surface not in hidings]
    return ReaderEnv.from_elts([
        cast(RdrElt, ImportRdrElt(item, [spec]))
        for item in items
    ])


def env_from_local_names(names: Iterable[Name]) -> ReaderEnv:
    return ReaderEnv.from_elts([
        LocalRdrElt(name=name)
        for name in names
    ])


def check_dups(names: Iterable[str], loc: Location | None = None):
    s: set[str] = set()
    for n in names:
        if n in s:
            raise Exception(f"duplicate param names: {n} at {loc}")
        s.add(n)


def binding_names(bindings: Iterable[ValBind]) -> list[tuple[str, SurfaceType | None, Location | None]]:
    return [(b.name, b.type_ann, b.location) for b in bindings]
    
