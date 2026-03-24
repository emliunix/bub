from collections.abc import Generator
from contextlib import contextmanager
from typing import Callable, TypeVar
from systemf.utils.uniq import Uniq
from systemf.elab2.core import *

class CoreDSL:
    def __init__(self):
        self.uniq = Uniq()
    
    def uniq_id(self, name: str) -> Id:
        return Id(name, self.uniq.make_uniq())
    
    def new_var(self):
        u = self.uniq.make_uniq()
        return Id(f"$v{u}", u)
    
    env: dict[Id, Ty] = dict()
    
    @contextmanager
    def with_vars(self, names: list[str]) -> Generator[list[Id], None, None]:
        yield [self.uniq_id(name) for name in names]
    
    T = TypeVar("T")
    
    def bracket_vars(self, names: list[str], cont: Callable[..., T]) -> T:
        """
        With bracket_vars we leverage host language variables for housekeeping
        of vars and vars shadowing
        """
        def _go():
            with self.with_vars(names) as ids:
                return cont(*ids)
        return _go()
    
    def cases(self,
              e: CoreTm,
              branches: list[tuple[DataCon, list[Id], CoreTm]],
              default: CoreTm
              ) -> CoreCase:
        def _build_branch(data_con, vars, body):
            return CaseBranch(data_con, vars, body)
        return CoreCase(
            e,
            [_build_branch(*branch) for branch in branches],
            default)

    def lam(self, name, type, body):
        self.env[name] = type
        return CoreLam(name, type, body)

    def var(self, name):
        return self.env[name]

    def lit_num(self, n: int) -> LitNum:
        return LitNum(n)

    def lit_str(self, s: str) -> LitStr:
        return LitStr(s)

# Example
# C.bracket_vars(["x"], lambda x: C.lam(x, TyInt(), C.var(x))))
# C.bracket_vars(["x", "y"], lambda x: C.lam(x, TyInt(), C.lam(y, TyInt(), C.var(y))))
