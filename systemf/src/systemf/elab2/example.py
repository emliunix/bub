from systemf.elab2.tyck import TyCkImpl, with_infer


if __name__ == "__main__":
    L = TyCkImpl()
    expr = L.let("x", L.lit(42), L.var("x"))
    print(with_infer(expr))
