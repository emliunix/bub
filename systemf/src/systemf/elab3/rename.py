"""
rename all names with a unique id.
- to check all name uses are in scope
- so define and uses are linked
"""
import itertools

from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from .rename_expr import RenameExpr
from .mod import Module
from .repl import REPLContext
from .ty import Lit, LitInt, LitString, Name, Ty, TyConApp, TyForall, TyFun, TyInt, TyString, TyVar, BoundTv
from .reader_env import ImportRdrElt, ImportSpec, LocalRdrElt, QualName, RdrElt, RdrName, ReaderEnv, UnqualName
from .tything import ACon, TyThing
from .ast import (
    Ann, AnnotName, App, Binding, Case, CaseBranch, ConPat, Expr, ImportDecl,
    Lam, Let, LitExpr, LitPat, Pat, RnDataConDecl, RnDataDecl, RnTermDecl, Var, VarPat
)

from systemf.surface.types import (
    SurfaceConstructorInfo,
    SurfaceDataDeclaration,
    SurfaceDeclaration,
    SurfaceDeclarationRepr,
    SurfaceImportDeclaration,
    SurfaceTermDeclaration,
    SurfaceTypeForall,
    SurfaceTypeVar
)

from systemf.utils.location import Location
from systemf.utils.uniq import Uniq


@dataclass
class RenameResult:
    data_decls: list[RnDataDecl]
    term_decls: list[RnTermDecl]


class Rename:
    ctx: REPLContext
    reader_env: ReaderEnv
    mod_name: str
    name_gen: NameGeneratorImpl

    """
    Assign unique to names lexically.
    """
    def __init__(self, ctx: REPLContext, reader_env: ReaderEnv, mod_name: str):
        self.ctx = ctx
        self.reader_env = reader_env
        self.mod_name = mod_name
        self.name_gen = NameGeneratorImpl(mod_name, self.ctx.uniq)

    @property
    def rename_expr(self):
        """fresh new RenameExpr with local env"""
        return RenameExpr(self.reader_env, self.mod_name, self.name_gen)

    def rename(self, ast: list[SurfaceDeclaration]) -> RenameResult:
        ast_imports, ast_datas, ast_terms = split_ast(ast)
        # imports
        self.do_imports(get_imports(ast_imports))

        # lhs
        lhs_datas = self.rename_lhs_datas(ast_datas)
        lhs_terms = self.rename_lhs_terms(ast_terms)
        self.reader_env = self.reader_env + env_from_local_names(
            itertools.chain(
                [r.name for r in lhs_datas],
                itertools.chain.from_iterable(r.datacons for r in lhs_datas),
                [r.name for r in lhs_terms]))

        # rhs
        rn_datas = [self.rename_rhs_data(ld) for ld in lhs_datas]
        rn_terms = [self.rename_rhs_term(lt) for lt in lhs_terms]

        return RenameResult(rn_datas, rn_terms)

    def do_imports(self, imports: list[ImportDecl]):
        # TODO: implement import handling
        for imp in imports:
            mod = self.ctx.load(imp.module)
            env = env_from_import_decl(mod, imp)
            self.reader_env = self.reader_env + env

    def rename_lhs_datas(self, datas: list[SurfaceDataDeclaration]) -> list[RnLhsDataResult]:
        def _go(decl: SurfaceDataDeclaration) -> RnLhsDataResult:
            tycon_name = self.name_gen.new_name(decl.name, decl.location)
            datacon_names = [
                self.name_gen.new_name(con.name, con.location)
                for con in decl.constructors
            ]
            return RnLhsDataResult(tycon_name, datacon_names, decl)
        return [_go(decl) for decl in datas]

    def rename_lhs_terms(self, terms: list[SurfaceTermDeclaration]) -> list[RnLhsTermResult]:
        return [
            RnLhsTermResult(self.name_gen.new_name(decl.name, decl.location), decl)
            for decl in terms
        ]

    def rename_rhs_data(self, lhs_res: RnLhsDataResult) -> RnDataDecl:
        var_names = self.name_gen.new_names(lhs_res.decl.params, lhs_res.decl.location)
        rn_data = RnDataDecl(name=lhs_res.name, tyvars=[BoundTv(v) for v in var_names], constructors=[])

        def _go(con: SurfaceConstructorInfo, con_name: Name) -> RnDataConDecl:
            tys = [
                self.rename_expr.rename_forall_type(var_names, arg)
                for arg in con.args]
            return RnDataConDecl(con_name, rn_data, tys)

        for con, con_name in zip(lhs_res.decl.constructors, lhs_res.datacons):
            rn_data.constructors.append(_go(con, con_name))

        return rn_data

    def rename_rhs_term(self, lhs_res: RnLhsTermResult) -> RnTermDecl:
        if lhs_res.decl.type_annotation is None:
            term_ty = None
        else:
            term_ty = self.rename_expr.rename_type(lhs_res.decl.type_annotation)
        term = self.rename_expr.rename_expr(lhs_res.decl.body)
        return RnTermDecl(
            name=AnnotName(lhs_res.name, term_ty) if term_ty else lhs_res.name,
            expr=term
        )


@dataclass
class RnLhsDataResult:
    name: Name
    datacons: list[Name]
    decl: SurfaceDataDeclaration


@dataclass
class RnLhsTermResult:
    name: Name
    decl: SurfaceTermDeclaration


class NameGeneratorImpl:
    mod_name: str
    uniq: Uniq

    def __init__(self, mod_name: str, uniq: Uniq):
        self.mod_name = mod_name
        self.uniq = uniq

    def new_name(self, name: str, loc: Location | None) -> Name:
        return Name(self.mod_name, name, self.uniq.make_uniq(), loc)

    def new_names(self, names: list[str], loc: Location | None) -> list[Name]:
        check_dups(names, loc)
        return [self.new_name(name, loc) for name in names]


def split_ast(
    ast: list[SurfaceDeclaration]
) -> tuple[
    list[SurfaceImportDeclaration],
    list[SurfaceDataDeclaration],
    list[SurfaceTermDeclaration]
]:
    imports: list[SurfaceImportDeclaration]  = []
    datas: list[SurfaceDataDeclaration] = []
    terms: list[SurfaceTermDeclaration] = []
    for decl in ast:
        match decl:
            case SurfaceImportDeclaration():
                imports.append(decl)
            case SurfaceDataDeclaration():
                datas.append(decl)
            case SurfaceTermDeclaration():
                terms.append(decl)
            case _:
                raise Exception(f"unexpected declaration: {decl}")
    return imports, datas, terms

def get_imports(imports: list[SurfaceImportDeclaration]) -> list[ImportDecl]:
    return [ImportDecl(
        module=decl.module,
        qualified=decl.qualified,
        alias=decl.alias,
        import_items=decl.items,
        hiding_items=[],  # TODO: fix surface to support hiding items
    ) for decl in imports]


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
