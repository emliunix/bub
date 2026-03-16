"""
adapt surface ast to our syntax DSL
"""

import functools
from systemf.elab2.types import SyntaxDSL, REPR, Ty
from systemf.surface.types import SurfaceAbs, SurfaceLit, SurfaceNode, SurfaceType

def run_ast(dsl: SyntaxDSL[REPR], ast: SurfaceNode) -> REPR:
    run = functools.partial(run_ast, dsl)
    match ast:
        case SurfaceAbs(name=name, body=body, location=location):
            assert body, "missing body"
            return dsl.lam(name, run(body))
        case SurfaceLit(value=value, location=location):
            return dsl.lit(value)
        case SurfaceNode(fun=fun, arg=arg, location=location):
            return dsl.app(run(fun), run(arg))
        case _:
            return dsl.var(ast.name)

def type_of(sty: SurfaceType) -> Ty:
    ...
