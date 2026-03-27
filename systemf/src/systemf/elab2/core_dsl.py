from collections.abc import Generator
from typing import Callable, TypeVar

from systemf.utils.uniq import Uniq
from systemf.elab2.core import *

class CoreDSL:
    """
    HOAS dsl to build core terms
    """
    def __init__(self):
        self.ty_cons = []
        self.data_cons = []
        self.uniq = Uniq()

    def add_data_decl(self,
                      ty_cons: list[tuple[
                          str,
                          list[str],
                          Callable[..., # ty_cons
                                   Callable[..., list[DataCon]]]]] # ty_vars
                      ):
                      
        ty_con_ids = [
            self.uniq_id(name)
            for (name, _, _) in ty_cons
        ]
        
        for (ty_con_id, (_, ty_var_names, mk_dcons)) in zip(ty_con_ids, ty_cons):
            ty_vars = [
                TyVar(self.uniq_id(n))
                for n in ty_var_names
            ]
            dcons = mk_dcons(ty_con_ids)(*ty_vars)
            self.ty_cons.append(TyData(ty_con_id, ty_vars, dcons))
            self.data_cons.extend(dcons)
    
    def uniq_id(self, name: str) -> Id:
        return Id(name, self.uniq.make_uniq())
    
    def gen_var(self):
        u = self.uniq.make_uniq()
        return Id(f"$v{u}", u)
    
    T = TypeVar("T")

    def vars(self, names: list[tuple[str, Ty]],) -> list[Var]:
        return [Var(self.uniq_id(name), ty) for (name, ty) in names]
    
    def bracket_vars(self,
                     names: list[tuple[str, Ty]],
                     cont: Callable[..., T]) -> T:
        """
        With bracket_vars we leverage host language variables for housekeeping
        of vars and vars shadowing
        """
        return cont(*self.vars(names))

    def var(self, var: Var) -> CoreVar:
        return CoreVar(var)

    def lit_num(self, n: int) -> LitNum:
        return LitNum(n)

    def lit_str(self, s: str) -> LitStr:
        return LitStr(s)

    def cases(self,
              e: CoreTm,
              branches: list[tuple[
                  DataCon,
                  list[tuple[str, Ty]],
                  Callable[..., CoreTm]]],
              default: CoreTm
              ) -> CoreCase:
        def _build_branch(data_con, vars, body):
            vars_ = self.vars(vars)
            return CaseBranch(data_con, vars_, body(*vars_))
        return CoreCase(
            e,
            [_build_branch(*branch) for branch in branches],
            default)

    def lam(self, name, ty, body):
        (v, ) = self.vars([(name, ty)])
        return CoreLam(v, body(v))

    def let(self, bind, body):
        return CoreLet(bind, body)

    def nonrec_bind(self, name, ty, expr):
        (v, ) = self.vars([(name, ty)])
        return NonRecBind(v, expr)

    def rec_binds(self, binds: list[tuple[str, Ty, Callable[..., CoreTm]]]) -> RecBinds:
        vars = self.vars([
            (name, ty)
            for name, ty, _ in binds
        ])
        rec_binds = [
            expr(*vars)
            for _, _, expr in binds
        ]
        return RecBinds(rec_binds)

# Example
# C.bracket_vars(["x"], lambda x: C.lam(x, TyInt(), C.var(x))))
# C.bracket_vars(["x", "y"], lambda x: C.lam(x, TyInt(), C.lam(y, TyInt(), C.var(y))))
