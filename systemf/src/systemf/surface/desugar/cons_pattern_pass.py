"""Cons pattern desugaring pass for surface language.

Converts cons patterns (x : xs) to constructor patterns (Cons x xs).
"""

from __future__ import annotations

from systemf.surface.result import Result, Ok
from systemf.surface.types import (
    SurfaceLet,
    SurfaceTerm,
    SurfacePattern,
    SurfacePatternBase,
    SurfacePatternCons,
    SurfacePatternTuple,
    SurfaceLitPattern,
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


def cons_pattern_pass(term: SurfaceTerm) -> Result[SurfaceTerm, DesugarError]:
    """Convert cons patterns to constructor patterns.

    Transforms:
        case xs of { x : xs -> body }
    To:
        case xs of { Cons x xs -> body }

    Also handles nested patterns:
        (a, b) : zs  ->  Cons (Pair a b) zs
        x : y : zs   ->  Cons x (Cons y zs)

    This pass should run before type checking so that all patterns are
    in the simple constructor form that the type checker expects.

    Args:
        term: The surface term to desugar.

    Returns:
        Result containing either the desugared term or a DesugarError.
    """
    try:
        desugared_term = _desugar_term(term)
        return Ok(desugared_term)
    except Exception as e:
        return Result.Err(DesugarError(f"Unexpected error during cons pattern desugaring: {e}"))


def _desugar_term(term: SurfaceTerm) -> SurfaceTerm:
    """Recursively desugar cons patterns in a term."""
    from systemf.surface.types import (
        SurfaceAbs,
        SurfaceApp,
        SurfaceTypeAbs,
        SurfaceTypeApp,
        SurfaceLet,
        SurfaceAnn,
        SurfaceConstructor,
        SurfaceCase,
        SurfaceBranch,
        SurfaceOp,
    )

    match term:
        case SurfaceAbs(params=params, body=body, location=loc):
            if body is None:
                return term
            new_body = _desugar_term(body)
            return SurfaceAbs(params=params, body=new_body, location=loc)

        case SurfaceApp(func=func, arg=arg, location=loc):
            if func is None or arg is None:
                return term
            new_func = _desugar_term(func)
            new_arg = _desugar_term(arg)
            return SurfaceApp(func=new_func, arg=new_arg, location=loc)

        case SurfaceTypeAbs(var=var, body=body, location=loc):
            if body is None:
                return term
            new_body = _desugar_term(body)
            return SurfaceTypeAbs(var=var, body=new_body, location=loc)

        case SurfaceTypeApp(func=func, type_arg=type_arg, location=loc):
            if func is None:
                return term
            new_func = _desugar_term(func)
            return SurfaceTypeApp(func=new_func, type_arg=type_arg, location=loc)

        case SurfaceLet(bindings=bindings, body=body, location=loc):
            if body is None:
                return term
            new_body = _desugar_term(body)
            new_bindings = []
            for b in bindings:
                new_value = _desugar_term(b.value)
                new_bindings.append(ValBind(
                    name=b.name,
                    type_ann=b.type_ann,
                    value=new_value,
                    location=b.location
                ))
            return SurfaceLet(bindings=new_bindings, body=new_body, location=loc)

        case SurfaceAnn(term=inner, type=type_ann, location=loc):
            if inner is None:
                return term
            new_inner = _desugar_term(inner)
            return SurfaceAnn(term=new_inner, type=type_ann, location=loc)

        case SurfaceConstructor(name=name, args=args, location=loc):
            new_args = [_desugar_term(arg) for arg in args]
            return SurfaceConstructor(name=name, args=new_args, location=loc)

        case SurfaceCase(scrutinee=scrutinee, branches=branches, location=loc):
            if scrutinee is None:
                return term
            new_scrutinee = _desugar_term(scrutinee)
            new_branches = []
            for branch in branches:
                new_pattern = _desugar_pattern(branch.pattern)
                new_body = _desugar_term(branch.body) if branch.body else branch.body
                from systemf.surface.types import SurfaceBranch

                new_branches.append(
                    SurfaceBranch(pattern=new_pattern, body=new_body, location=branch.location)
                )
            return SurfaceCase(scrutinee=new_scrutinee, branches=new_branches, location=loc)

        case SurfaceOp(left=left, op=op, right=right, location=loc):
            if left is None or right is None:
                return term
            new_left = _desugar_term(left)
            new_right = _desugar_term(right)
            return SurfaceOp(left=new_left, op=op, right=new_right, location=loc)

        case _:
            return term


def _desugar_pattern(
    pattern: SurfacePatternBase | None,
) -> SurfacePatternBase | None:
    """Recursively desugar cons patterns to constructor patterns.

    Converts:
    - SurfacePatternCons(head, tail) -> SurfacePattern(patterns=[VarPat("Cons"), head, tail])
    - SurfacePatternTuple(elements) -> SurfacePatternTuple with desugared elements
    - SurfacePattern -> desugar nested patterns
    - SurfaceLitPattern -> unchanged
    - SurfaceVarPattern -> unchanged
    """
    if pattern is None:
        return None

    match pattern:
        case SurfacePattern(patterns=patterns):
            # Recursively desugar each pattern in the flat list
            new_patterns = [_desugar_pattern(p) for p in patterns]
            return SurfacePattern(
                patterns=[v for v in new_patterns if v is not None],
                location=pattern.location,
            )

        case SurfacePatternTuple(elements=elements):
            # Desugar each element
            new_elements = [_desugar_pattern(elem) for elem in elements]
            return SurfacePatternTuple(elements=[v for v in new_elements if v is not None], location=pattern.location)

        case SurfacePatternCons(head=head, tail=tail):
            # Convert cons pattern to constructor pattern
            # x : xs -> Cons x xs (flat structure: [VarPat("Cons"), head, tail])
            # (a, b) : zs -> Cons (Pair a b) zs
            new_head = _desugar_pattern(head)
            new_tail = _desugar_pattern(tail)
            patterns: list[SurfacePatternBase] = [
                SurfaceVarPattern(name="Cons", location=pattern.location)
            ]
            if new_head is not None:
                patterns.append(new_head)
            if new_tail is not None:
                patterns.append(new_tail)
            return SurfacePattern(patterns=patterns, location=pattern.location)

        case SurfaceLitPattern():
            # Literal pattern - no change needed
            return pattern

        case SurfaceVarPattern():
            # Variable pattern - no change needed
            return pattern

        case _:
            return pattern


def _collect_pattern_vars(
    pattern: SurfacePatternBase | None,
) -> list[str]:
    """Collect variable names bound at the current pattern level."""
    if pattern is None:
        return []

    match pattern:
        case SurfacePattern(patterns=patterns):
            if len(patterns) == 1 and isinstance(patterns[0], SurfaceVarPattern):
                # Single item: variable pattern
                return [patterns[0].name]
            else:
                # Multiple items: constructor pattern, collect from args (skip constructor)
                result = []
                for pat in patterns[1:]:  # Skip constructor at patterns[0]
                    result.extend(_collect_pattern_vars(pat))
                return result

        case SurfaceVarPattern(name=name):
            return [name]

        case SurfacePatternTuple(elements=elements):
            result = []
            for elem in elements:
                result.extend(_collect_pattern_vars(elem))
            return result

        case SurfacePatternCons(head=head, tail=tail):
            result = []
            result.extend(_collect_pattern_vars(head))
            result.extend(_collect_pattern_vars(tail))
            return result

        case SurfaceLitPattern():
            return []

        case _:
            return []
