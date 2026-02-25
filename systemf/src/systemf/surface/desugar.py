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
    SurfacePattern,
    SurfaceTerm,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceVar,
    SurfaceAnn,
)
from systemf.utils.location import Location


class Desugarer:
    """Desugars surface syntax to simpler forms.

    Performs transformations like:
    - if-then-else -> case expressions
    - let bindings -> lambda applications
    - Operator sections
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
