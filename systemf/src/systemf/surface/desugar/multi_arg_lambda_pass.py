"""Multi-argument lambda desugaring pass.

Phase 0 desugar pass. Transforms multi-parameter lambdas to nested single-parameter lambdas.
"""

from __future__ import annotations

from systemf.surface.result import Ok, Result
from systemf.surface.types import (
    SurfaceAbs,
    SurfaceTerm,
)


class DesugarError(Exception):
    """Error during desugaring."""

    pass


def _desugar_children(term: SurfaceTerm, desugar_fn) -> SurfaceTerm:
    """Recursively apply a desugar function to all children of a term.

    This is a generic helper used by all desugaring passes.
    """
    from systemf.surface.types import (
        SurfaceAbs,
        SurfaceApp,
        SurfaceAnn,
        SurfaceCase,
        SurfaceConstructor,
        SurfaceLet,
        SurfaceOp,
        SurfaceTypeAbs,
        SurfaceTypeApp,
    )

    match term:
        case SurfaceAbs(params=params, body=body, location=loc):
            if body is None:
                return term
            return SurfaceAbs(params=params, body=desugar_fn(body), location=loc)

        case SurfaceApp(func=func, arg=arg, location=loc):
            assert func is not None and arg is not None
            return SurfaceApp(func=desugar_fn(func), arg=desugar_fn(arg), location=loc)

        case SurfaceTypeAbs(vars=vars, body=body, location=loc):
            if body is None:
                return term
            return SurfaceTypeAbs(vars=vars, body=desugar_fn(body), location=loc)

        case SurfaceTypeApp(func=func, type_arg=type_arg, location=loc):
            assert func is not None
            return SurfaceTypeApp(func=desugar_fn(func), type_arg=type_arg, location=loc)

        case SurfaceLet(bindings=bindings, body=body, location=loc):
            assert body is not None
            new_bindings = [
                (name, var_type, desugar_fn(value)) for name, var_type, value in bindings
            ]
            return SurfaceLet(bindings=new_bindings, body=desugar_fn(body), location=loc)

        case SurfaceAnn(term=inner, type=type_ann, location=loc):
            assert inner is not None
            return SurfaceAnn(term=desugar_fn(inner), type=type_ann, location=loc)

        case SurfaceConstructor(name=name, args=args, location=loc):
            return SurfaceConstructor(
                name=name, args=[desugar_fn(arg) for arg in args], location=loc
            )

        case SurfaceCase(scrutinee=scrutinee, branches=branches, location=loc):
            from systemf.surface.types import SurfaceBranch

            assert scrutinee is not None
            new_branches = []
            for branch in branches:
                assert branch.body is not None
                new_branches.append(
                    SurfaceBranch(
                        pattern=branch.pattern,
                        body=desugar_fn(branch.body),
                        location=branch.location,
                    )
                )
            return SurfaceCase(scrutinee=desugar_fn(scrutinee), branches=new_branches, location=loc)

        case SurfaceOp(left=left, op=op, right=right, location=loc):
            assert left is not None and right is not None
            return SurfaceOp(left=desugar_fn(left), op=op, right=desugar_fn(right), location=loc)

        case _:
            return term


def multi_arg_lambda_pass(term: SurfaceTerm) -> Result[SurfaceTerm, DesugarError]:
    """Convert multi-parameter lambda to nested single-parameter lambdas.

    Transforms:
        \\x y z -> body
    To:
        \\x -> \\y -> \\z -> body

    This pass handles the SurfaceAbs.params list and converts it to
    nested SurfaceAbs nodes with single params.
    """

    def transform(t: SurfaceTerm) -> SurfaceTerm:
        # First, recursively desugar children
        t = _desugar_children(t, transform)

        # Then transform this node if it's a multi-arg lambda
        match t:
            case SurfaceAbs(params=params, body=body, location=loc):
                if len(params) <= 1 or body is None:
                    return t  # Single param, no params, or no body - no desugaring needed

                # Build nested lambdas from right to left
                # \x y z -> body becomes nested single-arg lambdas
                result: SurfaceTerm = body
                for var_name, var_type in reversed(params):
                    result = SurfaceAbs(
                        params=[(var_name, var_type)],
                        body=result,
                        location=loc,
                    )
                return result

        return t

    return Ok(transform(term))
