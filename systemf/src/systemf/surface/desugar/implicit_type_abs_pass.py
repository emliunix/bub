"""Implicit type abstraction desugar pass for rank-1 polymorphism.

Phase 0 desugar pass. Inserts implicit type abstractions for rank-1 polymorphism.
"""

from systemf.surface.result import Err, Ok, Result
from systemf.surface.types import SurfaceTermDeclaration, SurfaceTypeAbs, SurfaceTypeForall


class DesugarError(Exception):
    """Error during desugaring transformation.

    Base class for all desugaring errors in the surface language.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def implicit_type_abs_pass(
    decl: SurfaceTermDeclaration,
) -> Result[SurfaceTermDeclaration, DesugarError]:
    """Insert implicit type abstractions for rank-1 polymorphism.

    Inserts Λa. for each ∀a. at the top level, unless the body already
    starts with a type abstraction.

    Examples:
        id : ∀a. a → a = λx → x
        -- Becomes: Λa. λx → x

        const : ∀a. ∀b. a → b → a = λx y → x
        -- Becomes: Λa. Λb. λx y → x

    Args:
        decl: The term declaration to transform

    Returns:
        Ok(SurfaceTermDeclaration) if successful
        Err(DesugarError) if an error occurs
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
        return Ok(decl)

    # If body already starts with SurfaceTypeAbs, don't insert
    if isinstance(body, SurfaceTypeAbs):
        return Ok(decl)

    # Wrap body with type abstractions
    new_body = body
    for var in reversed(type_vars):
        new_body = SurfaceTypeAbs(
            vars=[var],
            body=new_body,
            location=decl.location,
        )

    return Ok(
        SurfaceTermDeclaration(
            name=decl.name,
            type_annotation=decl.type_annotation,
            body=new_body,
            location=decl.location,
            docstring=decl.docstring,
            pragma=decl.pragma,
        )
    )
