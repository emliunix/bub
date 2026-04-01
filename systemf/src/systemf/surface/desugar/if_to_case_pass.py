"""If-to-case desugaring pass for surface language.

Phase 0 desugar pass that transforms SurfaceIf to SurfaceCase with True/False branches.
"""

from __future__ import annotations

from systemf.surface.result import Result, Ok, Err
from systemf.surface.types import (
    SurfaceLet,
    SurfaceTerm,
    SurfaceIf,
    SurfaceCase,
    SurfaceBranch,
    SurfacePattern,
    SurfaceVarPattern,
    ValBind,
)


class DesugarError(Exception):
    """Error that occurs during desugaring."""

    def __init__(self, message: str, location=None) -> None:
        super().__init__(message)
        self.message = message
        self.location = location

    def __str__(self) -> str:
        if self.location:
            return f"DesugarError at {self.location}: {self.message}"
        return f"DesugarError: {self.message}"


def if_to_case_pass(term: SurfaceTerm) -> Result[SurfaceTerm, DesugarError]:
    """Convert if-then-else expressions to case expressions.

    Transforms:
        if cond then t else f
    To:
        case cond of { True -> t | False -> f }

    This is a bottom-up pass - desugars children first, then the node itself.

    Args:
        term: The surface term to desugar.

    Returns:
        Result containing either the desugared term or a DesugarError.
    """
    try:
        desugared_term = _desugar_children(term)

        match desugared_term:
            case SurfaceIf(
                cond=cond, then_branch=then_branch, else_branch=else_branch, location=loc
            ):
                if cond is None or then_branch is None or else_branch is None:
                    return Err(DesugarError("If expression has missing components", loc))

                result = SurfaceCase(
                    scrutinee=cond,
                    branches=[
                        SurfaceBranch(
                            pattern=SurfacePattern(patterns=[SurfaceVarPattern(name="True", location=loc)], location=loc),
                            body=then_branch,
                            location=loc,
                        ),
                        SurfaceBranch(
                            pattern=SurfacePattern(patterns=[SurfaceVarPattern(name="False", location=loc)], location=loc),
                            body=else_branch,
                            location=loc,
                        ),
                    ],
                    location=loc,
                )
                return Ok(result)

        return Ok(desugared_term)

    except Exception as e:
        return Err(DesugarError(f"Unexpected error during desugaring: {e}"))


def _desugar_children(term: SurfaceTerm) -> SurfaceTerm:
    """Recursively apply if_to_case_pass to all children of a term.

    This is a helper function used to implement bottom-up desugaring.
    """
    from systemf.surface.types import (
        SurfaceAbs,
        SurfaceApp,
        SurfaceTypeAbs,
        SurfaceTypeApp,
        SurfaceLet,
        SurfaceAnn,
        SurfaceConstructor,
        SurfaceCase,
        SurfaceOp,
    )

    match term:
        case SurfaceAbs(params=params, body=body, location=loc):
            if body is None:
                return term
            result = if_to_case_pass(body)
            if result.is_err():
                return term
            return SurfaceAbs(params=params, body=result.unwrap(), location=loc)

        case SurfaceApp(func=func, arg=arg, location=loc):
            if func is None or arg is None:
                return term
            func_result = if_to_case_pass(func)
            arg_result = if_to_case_pass(arg)
            if func_result.is_err() or arg_result.is_err():
                return term
            return SurfaceApp(func=func_result.unwrap(), arg=arg_result.unwrap(), location=loc)

        case SurfaceTypeAbs(var=var, body=body, location=loc):
            if body is None:
                return term
            result = if_to_case_pass(body)
            if result.is_err():
                return term
            return SurfaceTypeAbs(var=var, body=result.unwrap(), location=loc)

        case SurfaceTypeApp(func=func, type_arg=type_arg, location=loc):
            if func is None:
                return term
            result = if_to_case_pass(func)
            if result.is_err():
                return term
            return SurfaceTypeApp(func=result.unwrap(), type_arg=type_arg, location=loc)

        case SurfaceLet(bindings=bindings, body=body, location=loc):
            if body is None:
                return term
            body_result = if_to_case_pass(body)
            if body_result.is_err():
                return term

            new_bindings = []
            for b in bindings:
                value_result = if_to_case_pass(b.value)
                if value_result.is_err():
                    return term
                new_bindings.append(ValBind(
                    name=b.name,
                    type_ann=b.type_ann,
                    value=value_result.unwrap(),
                    location=b.location
                ))

            return SurfaceLet(bindings=new_bindings, body=body_result.unwrap(), location=loc)

        case SurfaceAnn(term=inner, type=type_ann, location=loc):
            if inner is None:
                return term
            result = if_to_case_pass(inner)
            if result.is_err():
                return term
            return SurfaceAnn(term=result.unwrap(), type=type_ann, location=loc)

        case SurfaceConstructor(name=name, args=args, location=loc):
            new_args = []
            for arg in args:
                result = if_to_case_pass(arg)
                if result.is_err():
                    return term
                new_args.append(result.unwrap())
            return SurfaceConstructor(name=name, args=new_args, location=loc)

        case SurfaceCase(scrutinee=scrutinee, branches=branches, location=loc):
            if scrutinee is None:
                return term

            scrut_result = if_to_case_pass(scrutinee)
            if scrut_result.is_err():
                return term

            new_branches = []
            for branch in branches:
                if branch.body is None:
                    new_branches.append(branch)
                else:
                    body_result = if_to_case_pass(branch.body)
                    if body_result.is_err():
                        return term
                    new_branches.append(
                        SurfaceBranch(
                            pattern=branch.pattern,
                            body=body_result.unwrap(),
                            location=branch.location,
                        )
                    )

            return SurfaceCase(scrutinee=scrut_result.unwrap(), branches=new_branches, location=loc)

        case SurfaceOp(left=left, op=op, right=right, location=loc):
            if left is None or right is None:
                return term
            left_result = if_to_case_pass(left)
            right_result = if_to_case_pass(right)
            if left_result.is_err() or right_result.is_err():
                return term
            return SurfaceOp(
                left=left_result.unwrap(), op=op, right=right_result.unwrap(), location=loc
            )

        case _:
            return term
