"""Desugaring passes for surface language.

Converts syntactic sugar to simpler core constructs.
"""

from __future__ import annotations

from systemf.surface.types import (
    SurfaceAbs,
    SurfaceApp,
    SurfaceBranch,
    SurfaceCase,
    SurfaceConstructor,
    SurfaceIf,
    SurfaceLet,
    SurfaceOp,
    SurfacePattern,
    SurfacePrimOpDecl,
    SurfaceTerm,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceVar,
    SurfaceAnn,
)
from systemf.utils.location import Location


# Operator to primitive operation name mapping
# Maps surface operators to primitive names (without $prim. prefix)
# The prefix is added by the evaluator when looking up implementations
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


class Desugarer:
    """Desugars surface syntax to simpler forms.

    Performs transformations like:
    - if-then-else -> case expressions
    - let bindings -> lambda applications
    - Operator expressions -> primitive operation applications
    """

    def desugar(self, term: SurfaceTerm) -> SurfaceTerm:
        """Apply all desugaring passes to a term.

        Args:
            term: Surface term with potential syntactic sugar

        Returns:
            Desugared surface term
        """
        # Recursively desugar subterms first
        term = self._desugar_children(term)

        # Apply desugaring transformations
        term = self._desugar_if_then_else(term)
        term = self._desugar_multi_arg_lambda(term)
        term = self._desugar_letrec(term)
        term = self._desugar_operators(term)

        return term

    def _desugar_children(self, term: SurfaceTerm) -> SurfaceTerm:
        """Recursively desugar children of a term."""
        match term:
            case SurfaceAbs(var=var, var_type=var_type, body=body, location=loc):
                assert body is not None
                return SurfaceAbs(var=var, var_type=var_type, body=self.desugar(body), location=loc)

            case SurfaceApp(func=func, arg=arg, location=loc):
                assert func is not None and arg is not None
                return SurfaceApp(func=self.desugar(func), arg=self.desugar(arg), location=loc)

            case SurfaceTypeAbs(var=var, body=body, location=loc):
                assert body is not None
                return SurfaceTypeAbs(var=var, body=self.desugar(body), location=loc)

            case SurfaceTypeApp(func=func, type_arg=type_arg, location=loc):
                assert func is not None
                return SurfaceTypeApp(func=self.desugar(func), type_arg=type_arg, location=loc)

            case SurfaceLet(bindings=bindings, body=body, location=loc):
                assert body is not None
                # bindings is list of (name, var_type, value)
                new_bindings = [
                    (name, var_type, self.desugar(value)) for name, var_type, value in bindings
                ]
                return SurfaceLet(bindings=new_bindings, body=self.desugar(body), location=loc)

            case SurfaceAnn(term=inner, type=type_ann, location=loc):
                assert inner is not None
                return SurfaceAnn(term=self.desugar(inner), type=type_ann, location=loc)

            case SurfaceConstructor(name=name, args=args, location=loc):
                return SurfaceConstructor(
                    name=name, args=[self.desugar(arg) for arg in args], location=loc
                )

            case SurfaceCase(scrutinee=scrutinee, branches=branches, location=loc):
                assert scrutinee is not None
                new_branches = []
                for branch in branches:
                    assert branch.body is not None
                    new_branches.append(
                        SurfaceBranch(
                            pattern=branch.pattern,
                            body=self.desugar(branch.body),
                            location=branch.location,
                        )
                    )
                return SurfaceCase(
                    scrutinee=self.desugar(scrutinee),
                    branches=new_branches,
                    location=loc,
                )

            case SurfaceOp(left=left, op=op, right=right, location=loc):
                assert left is not None and right is not None
                return SurfaceOp(
                    left=self.desugar(left), op=op, right=self.desugar(right), location=loc
                )

            case _:
                return term

    def _desugar_if_then_else(self, term: SurfaceTerm) -> SurfaceTerm:
        """Convert if-then-else to case expression.

        Transforms:
            if c then t else f
        To:
            case c of { True -> t | False -> f }
        """
        match term:
            case SurfaceIf(
                cond=cond, then_branch=then_branch, else_branch=else_branch, location=loc
            ):
                return SurfaceCase(
                    scrutinee=cond,
                    branches=[
                        SurfaceBranch(
                            pattern=SurfacePattern(constructor="True", vars=[], location=loc),
                            body=then_branch,
                            location=loc,
                        ),
                        SurfaceBranch(
                            pattern=SurfacePattern(constructor="False", vars=[], location=loc),
                            body=else_branch,
                            location=loc,
                        ),
                    ],
                    location=loc,
                )
        return term

    def _desugar_multi_arg_lambda(self, term: SurfaceTerm) -> SurfaceTerm:
        """Convert multi-argument lambda to nested single-argument lambdas.

        Example:
            \\x y -> body
        Becomes:
            \\x -> \\y -> body
        """
        # This is handled by the parser now, but could be added here
        # if we support multi-arg syntax like \\x y -> ...
        return term

    def _desugar_letrec(self, term: SurfaceTerm) -> SurfaceTerm:
        r"""Convert recursive let to fixpoint.

        Note: System F doesn't have recursion by default.
        This is a placeholder for when we add fixpoint constructs.

        Transforms:
            letrec f = \x -> ... f ... in body
        To:
            let f = fix (\f -> \x -> ... f ...) in body
        """
        # Placeholder - System F doesn't have recursion by default
        return term

    def _desugar_operators(self, term: SurfaceTerm) -> SurfaceTerm:
        """Convert operator expressions to primitive operation applications.

        Transforms:
            left + right  ->  ($prim.int.plus left) right
            left - right  ->  ($prim.int.minus left) right
            left * right  ->  ($prim.int.multiply left) right
            left / right  ->  ($prim.int.divide left) right
            left == right ->  ($prim.int.eq left) right
            left < right  ->  ($prim.int.lt left) right
            left > right  ->  ($prim.int.gt left) right
            left <= right ->  ($prim.int.le left) right
            left >= right ->  ($prim.int.ge left) right
        """
        match term:
            case SurfaceOp(left=left, op=op, right=right, location=loc):
                # Get the primitive operation name
                prim_name = OPERATOR_TO_PRIM.get(op)
                if prim_name is None:
                    # Unknown operator, return as-is
                    return term

                # Create the primitive variable reference
                prim_var = SurfaceVar(name=prim_name, location=loc)

                # Build: ((prim left) right)
                # First apply: (prim left)
                first_app = SurfaceApp(func=prim_var, arg=left, location=loc)
                # Then apply: ((prim left) right)
                return SurfaceApp(func=first_app, arg=right, location=loc)

            case _:
                return term


class LetToLambdaDesugarer:
    r"""Desugar let bindings to lambda applications.

    Transforms:
        let x = e1 in e2
    To:
        (\x -> e2) e1
    """

    def desugar(self, term: SurfaceTerm) -> SurfaceTerm:
        """Desugar all let bindings to lambda applications."""
        match term:
            case SurfaceLet(bindings=bindings, body=body, location=loc):
                assert body is not None
                # For now, handle single binding
                # bindings is list of (name, var_type, value)
                if len(bindings) != 1:
                    # Multi-binding let - for now just desugar children
                    new_bindings = [
                        (name, var_type, self.desugar(value)) for name, var_type, value in bindings
                    ]
                    return SurfaceLet(bindings=new_bindings, body=self.desugar(body), location=loc)

                name, var_type, value = bindings[0]
                # Recursively desugar subterms
                value = self.desugar(value)
                body = self.desugar(body)

                # Transform to: (\name -> body) value
                lam = SurfaceAbs(var=name, var_type=var_type, body=body, location=loc)
                return SurfaceApp(func=lam, arg=value, location=loc)

            case SurfaceAbs(var=var, var_type=var_type, body=body, location=loc):
                assert body is not None
                return SurfaceAbs(var=var, var_type=var_type, body=self.desugar(body), location=loc)

            case SurfaceApp(func=func, arg=arg, location=loc):
                assert func is not None and arg is not None
                return SurfaceApp(func=self.desugar(func), arg=self.desugar(arg), location=loc)

            case SurfaceTypeAbs(var=var, body=body, location=loc):
                assert body is not None
                return SurfaceTypeAbs(var=var, body=self.desugar(body), location=loc)

            case SurfaceTypeApp(func=func, type_arg=type_arg, location=loc):
                assert func is not None
                return SurfaceTypeApp(func=self.desugar(func), type_arg=type_arg, location=loc)

            case SurfaceAnn(term=inner, type=type_ann, location=loc):
                assert inner is not None
                return SurfaceAnn(term=self.desugar(inner), type=type_ann, location=loc)

            case SurfaceConstructor(name=name, args=args, location=loc):
                return SurfaceConstructor(
                    name=name, args=[self.desugar(arg) for arg in args], location=loc
                )

            case SurfaceCase(scrutinee=scrutinee, branches=branches, location=loc):
                assert scrutinee is not None
                new_branches = []
                for branch in branches:
                    assert branch.body is not None
                    new_branches.append(
                        SurfaceBranch(
                            pattern=branch.pattern,
                            body=self.desugar(branch.body),
                            location=branch.location,
                        )
                    )
                return SurfaceCase(
                    scrutinee=self.desugar(scrutinee),
                    branches=new_branches,
                    location=loc,
                )

            case SurfaceOp(left=left, op=op, right=right, location=loc):
                assert left is not None and right is not None
                return SurfaceOp(
                    left=self.desugar(left), op=op, right=self.desugar(right), location=loc
                )

            case _:
                return term


# =============================================================================
# Convenience Functions
# =============================================================================


def desugar(term: SurfaceTerm) -> SurfaceTerm:
    """Apply all desugaring passes to a term.

    Args:
        term: Surface term to desugar

    Returns:
        Desugared surface term
    """
    return Desugarer().desugar(term)


def desugar_lets(term: SurfaceTerm) -> SurfaceTerm:
    """Desugar let bindings to lambda applications.

    Args:
        term: Surface term

    Returns:
        Term with all let bindings converted to applications
    """
    return LetToLambdaDesugarer().desugar(term)
