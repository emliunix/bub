from systemf.elab2.tyck import TyCkImpl, with_infer
from systemf.elab2.types import LitInt


if __name__ == "__main__":
    L = TyCkImpl()
    # Using de Bruijn indices: dbi(0) refers to the most recent binding
    # let x = 42 in x
    expr = L.let("x", L.lit(LitInt(42)), L.dbi(0))
    print(with_infer(expr))
