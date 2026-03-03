"""Desugaring passes for surface language.

Each pass is an independent transformation that can be composed.
This module provides a collection of standalone desugaring functions.
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
    SurfaceTermDeclaration,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceTypeArrow,
    SurfaceTypeForall,
    SurfaceVar,
    SurfaceAnn,
)
from systemf.utils.location import Location


# =============================================================================
# Pass 1: If-Then-Else to Case
# =============================================================================


def desugar_if_then_else(term: SurfaceTerm) -> SurfaceTerm:
    r"""Convert if-then-else to case expression.

    Transforms:
        if c then t else f
    To:
        case c of { True -> t | False -> f }

    This is a bottom-up pass - desugars children first, then the node itself.
    """
    # First, recursively desugar children
    term = _desugar_children(term, desugar_if_then_else)

    # Then transform this node if it's an If
    match term:
        case SurfaceIf(cond=cond, then_branch=then_branch, else_branch=else_branch, location=loc):
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


# =============================================================================
# Pass 2: Operators to Primitive Applications
# =============================================================================

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


def desugar_operators(term: SurfaceTerm) -> SurfaceTerm:
    """Convert operator expressions to primitive operation applications.

    Transforms:
        left + right  ->  ($prim.int_plus left) right
        left - right  ->  ($prim.int_minus left) right
        etc.
    """
    # First, recursively desugar children
    term = _desugar_children(term, desugar_operators)

    # Then transform this node if it's an operator
    match term:
        case SurfaceOp(left=left, op=op, right=right, location=loc):
            prim_name = OPERATOR_TO_PRIM.get(op)
            if prim_name is None:
                return term  # Unknown operator, leave as-is

            # Create the primitive variable reference
            prim_var = SurfaceVar(name=prim_name, location=loc)

            # Build: ((prim left) right)
            first_app = SurfaceApp(func=prim_var, arg=left, location=loc)
            return SurfaceApp(func=first_app, arg=right, location=loc)

    return term


# =============================================================================
# Pass 3: Implicit Type Abstractions for Rank-1 Polymorphism
# =============================================================================


def desugar_implicit_type_abstractions(decl: SurfaceTermDeclaration) -> SurfaceTermDeclaration:
    """Insert implicit type abstractions for rank-1 polymorphism.

    Inserts Λa. for each ∀a. at the top level, unless the body already
    starts with a type abstraction.

    Examples:
        id : ∀a. a → a = λx → x
        -- Becomes: Λa. λx → x

        const : ∀a. ∀b. a → b → a = λx y → x
        -- Becomes: Λa. Λb. λx y → x
    """
    type_ann = decl.type_annotation
    body = decl.body

    # Collect rank-1 (top-level) forall-bound type variables
    type_vars: list[str] = []
    current_type = type_ann

    while isinstance(current_type, SurfaceTypeForall):
        type_vars.append(current_type.var)
        current_type = current_type.body

    # If no type variables at rank-1, return as-is
    if not type_vars:
        return decl

    # Simple check: if body already starts with SurfaceTypeAbs, don't insert
    if isinstance(body, SurfaceTypeAbs):
        return decl

    # Wrap body with type abstractions
    new_body = body
    for var in reversed(type_vars):
        new_body = SurfaceTypeAbs(
            var=var,
            body=new_body,
            location=decl.location,
        )

    return SurfaceTermDeclaration(
        name=decl.name,
        type_annotation=decl.type_annotation,
        body=new_body,
        location=decl.location,
        docstring=decl.docstring,
        pragma=decl.pragma,
    )


# =============================================================================
# Pass 4: Multi-Arg Lambda to Nested Single-Arg Lambdas
# =============================================================================


def desugar_multi_arg_lambda(term: SurfaceTerm) -> SurfaceTerm:
    r"""Convert multi-parameter lambda to nested single-parameter lambdas.

    Transforms:
        \x y z -> body
    To:
        \x -> \y -> \z -> body

    This pass handles the SurfaceAbs.params list and converts it to
    nested SurfaceAbs nodes with single params.
    """
    # First, recursively desugar children
    term = _desugar_children(term, desugar_multi_arg_lambda)

    # Then transform this node if it's a multi-arg lambda
    match term:
        case SurfaceAbs(params=params, body=body, location=loc):
            if len(params) <= 1 or body is None:
                return term  # Single param, no params, or no body - no desugaring needed

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

    return term


# =============================================================================
# Pass 5: Let to Lambda Application (Optional)
# =============================================================================


def desugar_let_to_application(term: SurfaceTerm) -> SurfaceTerm:
    r"""Convert let bindings to lambda applications.

    Transforms:
        let x = e1 in e2
    To:
        (\x -> e2) e1

    Note: This is optional as System F supports let directly.
    """
    # First, recursively desugar children
    term = _desugar_children(term, desugar_let_to_application)

    match term:
        case SurfaceLet(bindings=bindings, body=body, location=loc):
            if len(bindings) != 1:
                return term  # Multi-binding let - keep as-is for now

            name, var_type, value = bindings[0]

            # Transform to: (\name -> body) value
            lam = SurfaceAbs(params=[(name, var_type)], body=body, location=loc)
            return SurfaceApp(func=lam, arg=value, location=loc)

    return term


# =============================================================================
# Pass 4b: Multi-Var Type Abstraction to Nested Single-Var
# =============================================================================


def desugar_multi_var_type_abs(term: SurfaceTerm) -> SurfaceTerm:
    r"""Convert multi-variable type abstraction to nested single-variable abstractions.

    Transforms:
        /\a b c. body
    To:
        /\a. /\b. /\c. body

    This pass handles the SurfaceTypeAbs.vars list and converts it to
    nested SurfaceTypeAbs nodes with single vars.
    """
    # First, recursively desugar children
    term = _desugar_children(term, desugar_multi_var_type_abs)

    # Then transform this node if it's a multi-var type abstraction
    match term:
        case SurfaceTypeAbs(vars=vars, body=body, location=loc):
            if len(vars) <= 1 or body is None:
                return term  # Single var, no vars, or no body - no desugaring needed

            # Build nested type abstractions from right to left
            # /\a b c. body becomes nested single-var type abstractions
            result: SurfaceTerm = body
            for var_name in reversed(vars):
                result = SurfaceTypeAbs(
                    vars=[var_name],
                    body=result,
                    location=loc,
                )
            return result

    return term


# =============================================================================
# Utility: Child Desugaring Helper
# =============================================================================


def _desugar_children(term: SurfaceTerm, desugar_fn) -> SurfaceTerm:
    """Recursively apply a desugar function to all children of a term.

    This is a generic helper used by all desugaring passes.
    """
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


# =============================================================================
# Composite Pass (for convenience)
# =============================================================================


def desugar_term(term: SurfaceTerm) -> SurfaceTerm:
    """Apply all term-level desugaring passes.

    Passes are applied in order:
    1. Multi-var type abstractions -> nested single-var
    2. Multi-arg lambdas -> nested single-arg
    3. If-then-else -> case
    4. Operators -> primitive applications
    """
    term = desugar_multi_var_type_abs(term)
    term = desugar_multi_arg_lambda(term)
    term = desugar_if_then_else(term)
    term = desugar_operators(term)
    return term


def desugar_declaration(decl: SurfaceTermDeclaration) -> SurfaceTermDeclaration:
    """Apply all desugaring passes to a declaration.

    Passes are applied in order:
    1. Insert implicit type abstractions (for rank-1 polymorphism)
    2. Desugar the body (if-then-else, operators)
    """
    # Pass 1: Insert implicit type abstractions
    decl = desugar_implicit_type_abstractions(decl)

    # Pass 2: Desugar the body (if it exists)
    new_body = decl.body
    if new_body is not None:
        new_body = desugar_term(new_body)

    return SurfaceTermDeclaration(
        name=decl.name,
        type_annotation=decl.type_annotation,
        body=new_body,
        location=decl.location,
        docstring=decl.docstring,
        pragma=decl.pragma,
    )


# =============================================================================
# Legacy API (for backwards compatibility)
# =============================================================================


class Desugarer:
    """Legacy desugarer - wraps the new functional API."""

    def desugar(self, term: SurfaceTerm) -> SurfaceTerm:
        """Apply all desugaring passes."""
        return desugar_term(term)


# Legacy convenience function
def desugar(term: SurfaceTerm) -> SurfaceTerm:
    """Apply all desugaring passes to a term."""
    return desugar_term(term)


# Legacy alias
insert_implicit_type_abstractions = desugar_implicit_type_abstractions
