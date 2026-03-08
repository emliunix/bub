"""Signature collection pass for System F surface language.

This module implements Phase 2, step 1 of the elaboration pipeline:
collecting all type signatures from declarations before type elaboration.

The signature collection pass:
1. Collects type signatures from term declarations and primitive operations
2. Converts surface types to core types
3. Separates term declarations from data/primitive declarations
4. Returns the collected signatures for use during type elaboration
"""

from systemf.core.types import Type, TypeArrow, TypeConstructor, TypeForall, TypeVar
from systemf.surface.result import Err, Ok, Result
from systemf.surface.types import (
    SurfaceDeclaration,
    SurfacePrimOpDecl,
    SurfaceTermDeclaration,
    SurfaceType,
    SurfaceTypeArrow,
    SurfaceTypeConstructor,
    SurfaceTypeForall,
    SurfaceTypeVar,
)

from systemf.surface.inference.context import TypeContext
from systemf.surface.inference.errors import TypeError


def _surface_to_core_type(ty: SurfaceType, ctx: TypeContext) -> Type:
    """Convert a surface type to a core type.

    Handles type variables, arrows, foralls, and constructors.
    Type variables in the surface type are looked up in the context.

    Args:
        ty: Surface type to convert
        ctx: Current type context

    Returns:
        Core type representation

    Raises:
        TypeError: If the surface type contains unbound type variables
            or has invalid structure.
    """
    match ty:
        case SurfaceTypeVar(location=loc, name=name):
            # Check if it's a type variable (lowercase or underscore) vs constructor (uppercase)
            if name[0].islower() or name == "_":
                # It's a type variable
                if ctx.is_bound_type(name):
                    # Convert to de Bruijn index representation
                    return TypeVar(name)
                else:
                    # Unbound type variable - not allowed in signatures
                    raise TypeError(
                        f"Unbound type variable '{name}' in type signature",
                        location=loc,
                    )
            else:
                # It's a type constructor (Int, Bool, etc.)
                return TypeConstructor(name, [])

        case SurfaceTypeArrow(location=_, arg=arg, ret=ret, param_doc=param_doc):
            core_arg = _surface_to_core_type(arg, ctx)
            core_ret = _surface_to_core_type(ret, ctx)
            return TypeArrow(core_arg, core_ret, param_doc)

        case SurfaceTypeForall(location=_, var=var, body=body):
            # Extend context with bound variable
            new_ctx = ctx.extend_type(var)
            core_body = _surface_to_core_type(body, new_ctx)
            return TypeForall(var, core_body)

        case SurfaceTypeConstructor(location=_, name=name, args=args):
            core_args = [_surface_to_core_type(arg, ctx) for arg in args]
            return TypeConstructor(name, core_args)

        case _:
            raise TypeError(f"Unknown surface type: {ty}")


def signature_collect_pass(
    decls: list[SurfaceDeclaration],
    constructors: dict[str, Type] | None = None,
) -> Result[
    tuple[dict[str, Type], list[SurfaceTermDeclaration], list[tuple[int, SurfaceDeclaration]]],
    TypeError,
]:
    """Collect type signatures from surface declarations.

    Phase 2, step 1: Collects all type signatures from declarations before
    type elaboration. This ensures that all global types are known when
    elaborating term bodies.

    Args:
        decls: List of surface declarations to process
        constructors: Optional dictionary of constructor types to add to global types

    Returns:
        Result containing:
        - global_types: Dictionary mapping names to their core type signatures
        - term_decls: List of term declarations to be elaborated
        - other_decls: List of other declarations (data, prim) with their indices

    Example:
        >>> from systemf.surface.types import SurfaceTermDeclaration, SurfaceTypeConstructor
        >>> from systemf.utils.location import Location
        >>>
        >>> # Create a simple declaration: x : Int
        >>> loc = Location("test", 1, 1)
        >>> int_type = SurfaceTypeConstructor(name="Int", args=[], location=loc)
        >>> decl = SurfaceTermDeclaration(
        ...     name="x",
        ...     type_annotation=int_type,
        ...     body=None,
        ...     location=loc
        ... )
        >>>
        >>> result = signature_collect_pass([decl])
        >>> if result.is_ok():
        ...     global_types, term_decls, other_decls = result.unwrap()
        ...     print(f"Global types: {global_types}")
        ...     print(f"Term decls: {len(term_decls)}")
    """
    global_types: dict[str, Type] = {}
    term_decls: list[SurfaceTermDeclaration] = []
    other_decls: list[tuple[int, SurfaceDeclaration]] = []

    try:
        for i, decl in enumerate(decls):
            match decl:
                case SurfaceTermDeclaration():
                    if decl.type_annotation is None:
                        return Err(
                            TypeError(
                                f"Term declaration '{decl.name}' missing type annotation",
                                location=decl.location,
                            )
                        )
                    core_type = _surface_to_core_type(decl.type_annotation, TypeContext())
                    global_types[decl.name] = core_type
                    term_decls.append(decl)

                case SurfacePrimOpDecl():
                    if decl.type_annotation is None:
                        return Err(
                            TypeError(
                                f"Primitive operation '{decl.name}' missing type annotation",
                                location=decl.location,
                            )
                        )
                    core_type = _surface_to_core_type(decl.type_annotation, TypeContext())
                    global_types[decl.name] = core_type
                    other_decls.append((i, decl))

                case _:
                    other_decls.append((i, decl))

        # Add constructors if provided
        if constructors:
            for name, ty in constructors.items():
                global_types[name] = ty

        return Ok((global_types, term_decls, other_decls))

    except TypeError as e:
        return Err(e)
