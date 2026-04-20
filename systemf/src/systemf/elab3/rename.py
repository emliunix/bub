"""
rename all names with a unique id.
- to check all name uses are in scope
- so define and uses are linked
"""
import itertools

from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from systemf.elab3.name_gen import NAME_CACHE, NameGeneratorImpl, check_dups

from .rename_expr import RenameExpr
from .reader_env import ImportRdrElt, ImportSpec, LocalRdrElt, QualName, RdrElt, RdrName, ReaderEnv, UnqualName
from .types import NameGenerator, REPLContext, Module
from .types.ty import Name, BoundTv
from .types.ast import (
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


@dataclass
class RenameResult:
    data_decls: list[RnDataDecl]
    term_decls: list[RnTermDecl]


class Rename:
    ctx: REPLContext
    reader_env: ReaderEnv
    mod_name: str
    name_gen: NameGenerator

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
        lhs_names = itertools.chain(
                [r.name for r in lhs_datas],
                itertools.chain.from_iterable(r.datacons for r in lhs_datas),
                [r.name for r in lhs_terms])
        self.reader_env = self.reader_env + env_from_local_names(lhs_names)

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
            tycon_name = self.new_lhs_name(decl.name, decl.location)
            datacon_names = [
                self.new_lhs_name(con.name, con.location)
                for con in decl.constructors
            ]
            return RnLhsDataResult(tycon_name, datacon_names, decl)
        return [_go(decl) for decl in datas]

    def rename_lhs_terms(self, terms: list[SurfaceTermDeclaration]) -> list[RnLhsTermResult]:
        return [
            RnLhsTermResult(self.new_lhs_name(decl.name, decl.location), decl)
            for decl in terms
        ]

    def rename_rhs_data(self, lhs_res: RnLhsDataResult) -> RnDataDecl:
        var_names = self.new_lhs_names(lhs_res.decl.params, lhs_res.decl.location)
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
    
    def new_lhs_name(self, name: str, loc: Location | None) -> Name:
        """
        Combined NAME_CACHE and NameGenerator
        
        when name is builtin, we return from the cache
        otherwise we generate a new name and put it in the cache so later occ_name lookup finds it.
        """
        if (n := NAME_CACHE.get(self.mod_name, name)) is not None:
            return n
        n = self.name_gen.new_name(name, loc)
        NAME_CACHE.put(n)
        return n

    def new_lhs_names(self, names: list[str], loc: Location | None) -> list[Name]:
        check_dups(names, loc)
        return [self.new_lhs_name(name, loc) for name in names]


@dataclass
class RnLhsDataResult:
    name: Name
    datacons: list[Name]
    decl: SurfaceDataDeclaration


@dataclass
class RnLhsTermResult:
    name: Name
    decl: SurfaceTermDeclaration


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
