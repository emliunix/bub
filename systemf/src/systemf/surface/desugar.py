"""Desugaring passes for surface language.

Converts syntactic sugar to simpler core constructs.
"""

from __future__ import annotations

from systemf.surface.ast import (
    SurfaceAbs,
    SurfaceApp,
    SurfaceBranch,
    SurfaceCase,
    SurfaceConstructor,
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
# Maps surface operators to $prim names that cannot be shadowed
# Using underscore naming to match prelude declarations (e.g., prim_op int_plus)
OPERATOR_TO_PRIM: dict[str, str] = {
    "+": "$prim.int_plus",
    "-": "$prim.int_minus",
    "*": "$prim.int_multiply",
    "/": "$prim.int_divide",
    "==": "$prim.int_eq",
    "<": "$prim.int_lt",
    ">": "$prim.int_gt",
    "<=": "$prim.int_le",
    ">=": "$prim.int_ge",
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
            case SurfaceAbs(var, var_type, body, loc):
                return SurfaceAbs(var, var_type, self.desugar(body), loc)

            case SurfaceApp(func, arg, loc):
                return SurfaceApp(self.desugar(func), self.desugar(arg), loc)

            case SurfaceTypeAbs(var, body, loc):
                return SurfaceTypeAbs(var, self.desugar(body), loc)

            case SurfaceTypeApp(func, type_arg, loc):
                return SurfaceTypeApp(self.desugar(func), type_arg, loc)

            case SurfaceLet(name, value, body, loc):
                return SurfaceLet(name, self.desugar(value), self.desugar(body), loc)

            case SurfaceAnn(inner, type_ann, loc):
                return SurfaceAnn(self.desugar(inner), type_ann, loc)

            case SurfaceConstructor(name, args, loc):
                return SurfaceConstructor(name, [self.desugar(arg) for arg in args], loc)

            case SurfaceCase(scrutinee, branches, loc):
                return SurfaceCase(
                    self.desugar(scrutinee),
                    [
                        SurfaceBranch(
                            branch.pattern,
                            self.desugar(branch.body),
                            branch.location,
                        )
                        for branch in branches
                    ],
                    loc,
                )

            case SurfaceOp(left, op, right, loc):
                return SurfaceOp(self.desugar(left), op, self.desugar(right), loc)

            case _:
                return term

    def _desugar_if_then_else(self, term: SurfaceTerm) -> SurfaceTerm:
        """Convert if-then-else to case expression.

        Transforms:
            if c then t else f
        To:
            case c of { True -> t | False -> f }
        """
        # Note: This assumes a surface syntax for if-then-else
        # For now, this is a placeholder since we don't have If construct
        # When If is added to surface AST, implement the transformation here
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
            case SurfaceOp(left, op, right, loc):
                # Get the primitive operation name
                prim_name = OPERATOR_TO_PRIM.get(op)
                if prim_name is None:
                    # Unknown operator, return as-is
                    return term

                # Create the primitive variable reference
                prim_var = SurfaceVar(prim_name, loc)

                # Build: ((prim left) right)
                # First apply: (prim left)
                first_app = SurfaceApp(prim_var, left, loc)
                # Then apply: ((prim left) right)
                return SurfaceApp(first_app, right, loc)

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
            case SurfaceLet(name, value, body, loc):
                # Recursively desugar subterms
                value = self.desugar(value)
                body = self.desugar(body)

                # Transform to: (\name -> body) value
                lam = SurfaceAbs(name, None, body, loc)
                return SurfaceApp(lam, value, loc)

            case SurfaceAbs(var, var_type, body, loc):
                return SurfaceAbs(var, var_type, self.desugar(body), loc)

            case SurfaceApp(func, arg, loc):
                return SurfaceApp(self.desugar(func), self.desugar(arg), loc)

            case SurfaceTypeAbs(var, body, loc):
                return SurfaceTypeAbs(var, self.desugar(body), loc)

            case SurfaceTypeApp(func, type_arg, loc):
                return SurfaceTypeApp(self.desugar(func), type_arg, loc)

            case SurfaceAnn(inner, type_ann, loc):
                return SurfaceAnn(self.desugar(inner), type_ann, loc)

            case SurfaceConstructor(name, args, loc):
                return SurfaceConstructor(name, [self.desugar(arg) for arg in args], loc)

            case SurfaceCase(scrutinee, branches, loc):
                return SurfaceCase(
                    self.desugar(scrutinee),
                    [
                        SurfaceBranch(
                            branch.pattern,
                            self.desugar(branch.body),
                            branch.location,
                        )
                        for branch in branches
                    ],
                    loc,
                )

            case SurfaceOp(left, op, right, loc):
                return SurfaceOp(self.desugar(left), op, self.desugar(right), loc)

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
