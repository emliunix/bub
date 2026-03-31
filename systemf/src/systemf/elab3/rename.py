from collections.abc import Iterable

from systemf.elab3.types import Name
from systemf.utils.cons import Cons, lookup
from .reader_env import QualName, RdrName, ReaderEnv, UnqualName
from .tything import ACon, TyThing
from .ast import RnDataDecl, RnTermDecl

from systemf.surface.types import SurfaceDataDeclaration, SurfaceDeclarationRepr, SurfaceTermDeclaration
from systemf.utils.uniq import Uniq

type RnEnv = Cons[tuple[str, Name]]


def rename(
        uniq: Uniq, reader_env: ReaderEnv,
        data_decls: list[SurfaceDataDeclaration],
        term_decls: list[SurfaceTermDeclaration]
) -> tuple[list[RnDataDecl], list[RnTermDecl]]:
    renamer = Rename(uniq, reader_env)
    return (
        renamer.rename_data_decls(data_decls),
        renamer.rename_term_decls(term_decls)
    )


class Rename:
    uniq: Uniq
    reader_env: ReaderEnv
    names: dict[int, Name]

    """
    Assign unique to names lexically.
    """
    def __init__(self, uniq: Uniq, reader_env: ReaderEnv):
        self.uniq = uniq
        self.reader_env = reader_env
        self.names = {}

    def rename_data_decls(self, decls: list[SurfaceDataDeclaration]) -> list[RnDataDecl]:
        """
        1. Assign unique to tycon names and data con names.
        2. Backfill tycon with data cons.
        """
        tycons = [
            self.rename_tycon(decl)
            for decl in decls
        ]
        self.add_tycon_names(tycons)
        ty_and_data_cons = [
            (tycon, self.rename_datacons(decl))
            for (tycon, decl) in zip(tycons, decls)
        ]

        for (tycon, data_cons) in ty_and_data_cons:
            patch_datacons(tycon, data_cons)

        self.add_datacon_names([
            dcon
            for (tycon, data_cons) in ty_and_data_cons
            for dcon in data_cons
        ])


    def rename_term_decls(self, decls: list[SurfaceTermDeclaration]) -> list[RnTermDecl]:
        self.add_term_decl_names(decls)
        return [
            self.rename_term_decl(decl)
            for decl in decls
        ]

    def add_names(self, names: Iterable[Name]):
        self.names.update({
            name.unique: name
            for name in names
        })

    def add_tycon_names(self, tycons: Iterable[RnDataDecl]):
        self.add_names([
            t.name
            for t in tycons
        ])

    def add_datacon_names(self, datacons: Iterable[ACon]):
        self.add_names([
            d.name
            for d in datacons
        ])


def lookup_name(rn_env: RnEnv, gbl_env: ReaderEnv, name: RdrName) -> Name:
    match name:
        case UnqualName(name_) if (n := lookup(rn_env, name_)) is not None:
            return n
        case _:
            return lookup_gbl_name(gbl_env, name)


def lookup_gbl_name(gbl_env: ReaderEnv, name: RdrName) -> Name:
    match gbl_env.lookup(name):
        case []:
            raise Exception(f"unresolved name: {name}")
        case [n]:
            return n.name
        case xs:
            raise Exception(f"ambiguous name: {name} (candidates: {xs})")
