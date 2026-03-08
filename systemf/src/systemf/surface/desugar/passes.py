"""Composite desugaring passes module.

This module imports individual pass functions and provides composite
functions that chain multiple passes together.
"""

from __future__ import annotations

from systemf.surface.desugar.if_to_case_pass import if_to_case_pass
from systemf.surface.desugar.operator_pass import operator_to_prim_pass
from systemf.surface.desugar.multi_arg_lambda_pass import multi_arg_lambda_pass
from systemf.surface.desugar.multi_var_type_abs_pass import multi_var_type_abs_pass
from systemf.surface.desugar.implicit_type_abs_pass import implicit_type_abs_pass

from systemf.surface.types import SurfaceTerm, SurfaceTermDeclaration
from systemf.surface.result import Result, Ok


# Re-export individual passes
__all__ = [
    "if_to_case_pass",
    "operator_to_prim_pass",
    "multi_arg_lambda_pass",
    "multi_var_type_abs_pass",
    "implicit_type_abs_pass",
    "desugar_term",
    "desugar_declaration",
]


class DesugarError(Exception):
    """Error during desugaring transformation."""

    def __init__(self, message: str, location=None):
        super().__init__(message)
        self.message = message
        self.location = location

    def __str__(self) -> str:
        if self.location:
            return f"DesugarError at {self.location}: {self.message}"
        return f"DesugarError: {self.message}"


def desugar_term(term: SurfaceTerm) -> Result[SurfaceTerm, DesugarError]:
    """Apply all term-level desugaring passes.

    Passes are applied in order:
    1. Multi-var type abstractions -> nested single-var
    2. Multi-arg lambdas -> nested single-arg
    3. If-then-else -> case
    4. Operators -> primitive applications

    Args:
        term: The surface term to desugar.

    Returns:
        Result containing either the fully desugared term or an error.
    """
    # Apply passes in order, short-circuiting on error
    result = multi_var_type_abs_pass(term)
    if result.is_err():
        return result
    term = result.unwrap()

    result = multi_arg_lambda_pass(term)
    if result.is_err():
        return result
    term = result.unwrap()

    result = if_to_case_pass(term)
    if result.is_err():
        return result
    term = result.unwrap()

    result = operator_to_prim_pass(term)
    if result.is_err():
        return result
    term = result.unwrap()

    return Ok(term)


def desugar_declaration(
    decl: SurfaceTermDeclaration,
) -> Result[SurfaceTermDeclaration, DesugarError]:
    """Apply all desugaring passes to a declaration.

    Passes are applied in order:
    1. Insert implicit type abstractions (for rank-1 polymorphism)
    2. Desugar the body (if-then-else, operators, etc.)

    Args:
        decl: The term declaration to desugar.

    Returns:
        Result containing either the desugared declaration or an error.
    """
    # Pass 1: Insert implicit type abstractions
    result = implicit_type_abs_pass(decl)
    if result.is_err():
        return result
    decl = result.unwrap()

    # Pass 2: Desugar the body (if it exists)
    if decl.body is not None:
        body_result = desugar_term(decl.body)
        if body_result.is_err():
            return body_result

        decl = SurfaceTermDeclaration(
            name=decl.name,
            type_annotation=decl.type_annotation,
            body=body_result.unwrap(),
            location=decl.location,
            docstring=decl.docstring,
            pragma=decl.pragma,
        )

    return Ok(decl)
