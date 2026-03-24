"""
adapt surface ast to our syntax DSL
"""

import functools
from typing import TypeVar
from systemf.elab2.types import SyntaxDSL, Ty
from systemf.surface.types import SurfaceAbs, SurfaceLit, SurfaceNode, SurfaceType

R = TypeVar("R")

def run_surface(dsl: SyntaxDSL[R], ast: SurfaceNode) -> R:
    def _go(ast: SurfaceNode):
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
    return _go(ast)

def type_of(sty: SurfaceType) -> Ty:
    ...
