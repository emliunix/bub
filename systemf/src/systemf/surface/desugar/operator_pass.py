"""Phase 0 desugar pass: Transform operators to primitive applications.

This pass converts infix operator expressions to primitive operation applications.
For example: `1 + 2` becomes `((int_plus 1) 2)`.
"""

from __future__ import annotations

from systemf.surface.result import Err, Ok, Result
from systemf.surface.types import (
    SurfaceAbs,
    SurfaceAnn,
    SurfaceApp,
    SurfaceCase,
    SurfaceConstructor,
    SurfaceLet,
    SurfaceOp,
    SurfaceTerm,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceVar,
)


# Operator to primitive operation name mapping
OPERATOR_TO_PRIM: dict[str, str] = {
    "+": "int_plus",
    "-": "int_minus",
    "*": "int_multiply",
    "/": "int_divide",
    "==": "int_eq",
    "<": "int_lt",
    ">": "int_gt",
    "<=": "int_le",
    ">=": "int_ge",
}


class DesugarError:
    """Error type for desugaring passes.

    This pass doesn't typically fail, but the error type is provided
    for type safety and future extensibility.
    """

    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return f"DesugarError: {self.message}"


def operator_to_prim_pass(term: SurfaceTerm) -> Result[SurfaceTerm, DesugarError]:
    """Convert operator expressions to primitive operation applications.

    This is a bottom-up pass - desugars children first, then the node itself.

    Transforms:
        left + right  ->  ((int_plus left) right)
        left - right  ->  ((int_minus left) right)
        etc.

    Unknown operators are left unchanged.

    Args:
        term: The surface term to desugar.

    Returns:
        Result containing either the desugared term or an error.
    """
    # First, recursively desugar children
    term = _desugar_children(term)

    # Then transform this node if it's an operator
    match term:
        case SurfaceOp(left=left, op=op, right=right, location=loc):
            prim_name = OPERATOR_TO_PRIM.get(op)
            if prim_name is None:
                # Unknown operator, leave as-is
                return Ok(term)

            # Create the primitive variable reference
            prim_var = SurfaceVar(name=prim_name, location=loc)

            # Build: ((prim left) right)
            first_app = SurfaceApp(func=prim_var, arg=left, location=loc)
            result = SurfaceApp(func=first_app, arg=right, location=loc)
            return Ok(result)

    return Ok(term)


def _desugar_children(term: SurfaceTerm) -> SurfaceTerm:
    """Recursively apply operator desugaring to all children of a term.

    This is a helper that recursively processes all child terms.
    """
    match term:
        case SurfaceAbs(params=params, body=body, location=loc):
            if body is None:
                return term
            result_body = operator_to_prim_pass(body).unwrap()
            return SurfaceAbs(params=params, body=result_body, location=loc)

        case SurfaceApp(func=func, arg=arg, location=loc):
            result_func = operator_to_prim_pass(func).unwrap()
            result_arg = operator_to_prim_pass(arg).unwrap()
            return SurfaceApp(func=result_func, arg=result_arg, location=loc)

        case SurfaceTypeAbs(vars=vars, body=body, location=loc):
            if body is None:
                return term
            result_body = operator_to_prim_pass(body).unwrap()
            return SurfaceTypeAbs(vars=vars, body=result_body, location=loc)

        case SurfaceTypeApp(func=func, type_arg=type_arg, location=loc):
            result_func = operator_to_prim_pass(func).unwrap()
            return SurfaceTypeApp(func=result_func, type_arg=type_arg, location=loc)

        case SurfaceLet(bindings=bindings, body=body, location=loc):
            new_bindings = [
                (name, var_type, operator_to_prim_pass(value).unwrap())
                for name, var_type, value in bindings
            ]
            result_body = operator_to_prim_pass(body).unwrap()
            return SurfaceLet(bindings=new_bindings, body=result_body, location=loc)

        case SurfaceAnn(term=inner, type=type_ann, location=loc):
            result_inner = operator_to_prim_pass(inner).unwrap()
            return SurfaceAnn(term=result_inner, type=type_ann, location=loc)

        case SurfaceConstructor(name=name, args=args, location=loc):
            new_args = [operator_to_prim_pass(arg).unwrap() for arg in args]
            return SurfaceConstructor(name=name, args=new_args, location=loc)

        case SurfaceCase(scrutinee=scrutinee, branches=branches, location=loc):
            from systemf.surface.types import SurfaceBranch

            result_scrutinee = operator_to_prim_pass(scrutinee).unwrap()
            new_branches = []
            for branch in branches:
                result_body = operator_to_prim_pass(branch.body).unwrap()
                new_branches.append(
                    SurfaceBranch(
                        pattern=branch.pattern,
                        body=result_body,
                        location=branch.location,
                    )
                )
            return SurfaceCase(scrutinee=result_scrutinee, branches=new_branches, location=loc)

        case SurfaceOp(left=left, op=op, right=right, location=loc):
            result_left = operator_to_prim_pass(left).unwrap()
            result_right = operator_to_prim_pass(right).unwrap()
            return SurfaceOp(left=result_left, op=op, right=result_right, location=loc)

        case _:
            return term
