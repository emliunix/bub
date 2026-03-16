from typing import Final

from systemf.elab2.types import SyntaxDSL, CoreTm, C
from systemf.elab2.tyck import TyCk


class TransImpl(SyntaxDSL[CoreTm]):
    tyck: Final[SyntaxDSL[TyCk]]

    def __init__(self, tyck: SyntaxDSL[TyCk]):
        self.tyck = tyck

    def lit(self, value: Value, ty: Ty) -> CoreTm:
        return CoreLit(value, ty)
    def var(self, name: str, ty: Ty) -> CoreTm:
        return CoreVar(name, ty)
    def tyapp(self, fun: CoreTm, tyargs: list[Ty]) -> CoreTm:
        return CoreTyApp(fun, tyargs)
    def tylam(self, names: list[str], body: CoreTm) -> CoreTm:
        return CoreTyLam(names, body)
    def lam(self, names: list[str], tys: list[Ty], body: CoreTm) -> CoreTm:
        return CoreLam(names, tys, body)
    def app(self, fun: CoreTm, args: list[CoreTm]) -> CoreTm:
        return CoreApp(fun, args)
    def let(self, name: str, expr: CoreTm, expr_ty: Ty, body: CoreTm) -> CoreTm:
        return CoreLet(name, expr, expr_ty, body)
