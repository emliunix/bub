"""Elaborate bodies pass for System F surface language.

This module implements Phase 2, step 3b of the elaboration pipeline:
elaborating term declaration bodies using bidirectional type inference.

The elab_bodies_pass:
1. Takes scoped term declarations
2. For each declaration, elaborates the body using BidiInference
3. Returns elaborated bodies with their types
"""

from __future__ import annotations

from systemf.core import ast as core
from systemf.core.types import Type
from systemf.surface.inference.bidi_inference import BidiInference
from systemf.surface.inference.context import TypeContext
from systemf.surface.inference.errors import TypeError
from systemf.surface.result import Err, Ok, Result
from systemf.surface.types import SurfaceTermDeclaration


def elab_bodies_pass(
    term_decls: list[SurfaceTermDeclaration],
    type_ctx: TypeContext,
    signatures: dict[str, Type],
) -> Result[list[tuple[str, core.Term, Type]], TypeError]:
    """Elaborate term declaration bodies using bidirectional type inference.

    Phase 2, step 3b: For each term declaration, elaborates the body using
    bidirectional type inference. If a signature is provided for the declaration,
    it uses checking mode; otherwise uses inference mode.

    Args:
        term_decls: List of scoped term declarations to elaborate
        type_ctx: The type context for type checking
        signatures: Dictionary mapping declaration names to their expected types

    Returns:
        Result containing a list of tuples (name, core_body, type) where:
            - name: The declaration name
            - core_body: The elaborated core term
            - type: The inferred type of the body
        Returns Err(TypeError) if elaboration fails.

    Example:
        >>> from systemf.surface.types import SurfaceTermDeclaration, SurfaceLit
        >>> from systemf.core.types import TypeConstructor
        >>> from systemf.utils.location import Location
        >>>
        >>> loc = Location("test", 1, 1)
        >>> decl = SurfaceTermDeclaration(
        ...     name="x",
        ...     body=SurfaceLit(prim_type="Int", value=42, location=loc),
        ...     location=loc
        ... )
        >>> ctx = TypeContext()
        >>> sigs = {"x": TypeConstructor("Int", [])}
        >>> result = elab_bodies_pass([decl], ctx, sigs)
        >>> if result.is_ok():
        ...     elaborated = result.unwrap()
        ...     print(f"Elaborated: {elaborated[0][0]} : {elaborated[0][2]}")
    """
    bidi = BidiInference()
    elaborated: list[tuple[str, core.Term, Type]] = []

    try:
        for decl in term_decls:
            if decl.body is None:
                return Err(
                    TypeError(
                        f"Term declaration '{decl.name}' has no body",
                        location=decl.location,
                    )
                )

            expected_type = signatures.get(decl.name)

            if expected_type is not None:
                # Check mode: we have expected type
                core_body = bidi.check(decl.body, expected_type, type_ctx)
                inferred_type = expected_type
            else:
                # Infer mode: no expected type
                core_body, inferred_type = bidi.infer(decl.body, type_ctx)

            # Apply substitution and get final type
            inferred_type = bidi._apply_subst(inferred_type)

            # Unify if needed (ensure expected matches inferred)
            if expected_type is not None:
                expected_applied = bidi._apply_subst(expected_type)
                inferred_applied = bidi._apply_subst(inferred_type)
                if expected_applied != inferred_applied:
                    try:
                        bidi._unify(expected_applied, inferred_applied, decl.location)
                    except TypeError as e:
                        return Err(e)
                inferred_type = expected_applied

            elaborated.append((decl.name, core_body, inferred_type))

        return Ok(elaborated)

    except TypeError as e:
        return Err(e)
