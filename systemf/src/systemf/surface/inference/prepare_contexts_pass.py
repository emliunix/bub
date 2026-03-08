"""Prepare contexts pass for System F surface language.

This module implements Phase 2, step 3a of the elaboration pipeline:
preparing type contexts for term elaboration.

The prepare contexts pass:
1. Takes signatures from SignatureCollectPass
2. Adds them to TypeContext.globals
3. Adds constructor types to TypeContext.constructors
4. Returns ready-to-use TypeContext for body elaboration
"""

from systemf.core.types import Type
from systemf.surface.inference.context import TypeContext
from systemf.surface.inference.errors import TypeError
from systemf.surface.result import Ok, Result


def prepare_contexts_pass(
    signatures: dict[str, Type],
    constructor_types: dict[str, Type],
    base_ctx: TypeContext,
) -> Result[TypeContext, TypeError]:
    """Prepare type contexts for term elaboration.

    Phase 2, step 3a: Prepares type contexts by adding collected signatures
    and constructor types to the base context. The resulting context is
    ready for use in body elaboration.

    Args:
        signatures: Dictionary mapping names to their core type signatures
            (from SignatureCollectPass)
        constructor_types: Dictionary mapping constructor names to their types
        base_ctx: The base type context to extend

    Returns:
        Result containing the prepared TypeContext ready for elaboration,
        or a TypeError if preparation fails

    Example:
        >>> from systemf.core.types import TypeConstructor, TypeArrow
        >>> from systemf.surface.inference.context import TypeContext
        >>>
        >>> # Create base context
        >>> ctx = TypeContext()
        >>>
        >>> # Prepare signatures
        >>> signatures = {"id": TypeArrow(TypeConstructor("Int", []), TypeConstructor("Int", []))}
        >>> constructors = {"Just": TypeConstructor("Maybe", [])}
        >>>
        >>> result = prepare_contexts_pass(signatures, constructors, ctx)
        >>> if result.is_ok():
        ...     new_ctx = result.unwrap()
        ...     print(f"Globals: {new_ctx.globals}")
        ...     print(f"Constructors: {new_ctx.constructors}")
    """
    ctx = base_ctx

    # Add signatures as globals
    for name, ty in signatures.items():
        ctx = ctx.add_global(name, ty)

    # Add constructors
    for name, ty in constructor_types.items():
        ctx = ctx.add_constructor(name, ty)

    return Ok(ctx)
