"""Data declaration elaboration pass for System F.

Phase 2, step 2: Elaborates data type declarations from surface to core.
"""

from __future__ import annotations

from systemf.core import ast as core
from systemf.core.types import Type, TypeArrow, TypeConstructor, TypeForall, TypeVar
from systemf.surface.inference.context import TypeContext
from systemf.surface.result import Ok, Result
from systemf.surface.types import (
    SurfaceConstructorInfo,
    SurfaceDataDeclaration,
    SurfaceDeclaration,
    SurfaceType,
    SurfaceTypeArrow,
    SurfaceTypeConstructor,
    SurfaceTypeForall,
    SurfaceTypeVar,
)


class TypeError(Exception):
    """Type error during elaboration."""

    pass


def surface_to_core_type(ty: SurfaceType, ctx: TypeContext) -> Type:
    """Convert a surface type to a core type.

    Handles type variables, arrows, foralls, and constructors.
    Type variables in the surface type are looked up in the context
    and converted to de Bruijn indices.

    Args:
        ty: Surface type to convert
        ctx: Current type context

    Returns:
        Core type representation
    """
    match ty:
        case SurfaceTypeVar(name=name):
            # Check if it's a type variable (lowercase) vs constructor (uppercase)
            if name[0].islower() or name == "_":
                # It's a type variable
                if ctx.is_bound_type(name):
                    return TypeVar(name)
                # Free type variable - should not happen in data declarations
                raise TypeError(f"Undefined type variable '{name}'")
            else:
                # It's a type constructor (Int, Bool, etc.)
                return TypeConstructor(name, [])

        case SurfaceTypeArrow(arg=arg, ret=ret, param_doc=param_doc):
            core_arg = surface_to_core_type(arg, ctx)
            core_ret = surface_to_core_type(ret, ctx)
            return TypeArrow(core_arg, core_ret, param_doc)

        case SurfaceTypeForall(var=var, body=body):
            # Extend context with bound variable
            new_ctx = ctx.extend_type(var)
            core_body = surface_to_core_type(body, new_ctx)
            return TypeForall(var, core_body)

        case SurfaceTypeConstructor(name=name, args=args):
            core_args = [surface_to_core_type(arg, ctx) for arg in args]
            return TypeConstructor(name, core_args)

        case _:
            raise TypeError(f"Unknown surface type: {ty}")


def elaborate_data_decl(
    decl: SurfaceDataDeclaration, ctx: TypeContext
) -> tuple[core.DataDeclaration, dict[str, Type]]:
    """Elaborate a single data declaration.

    Args:
        decl: Surface data declaration
        ctx: Type context

    Returns:
        Tuple of (core data declaration, constructor types dict)
    """
    # Build result type: T a b c where a,b,c are the parameters
    result_type = TypeConstructor(decl.name, [TypeVar(p) for p in decl.params])

    # Extend context with type parameters for constructor elaboration
    type_ctx = ctx
    for param in decl.params:
        type_ctx = type_ctx.extend_type(param)

    core_constructors: list[tuple[str, list[Type]]] = []
    constructor_types: dict[str, Type] = {}

    for con_info in decl.constructors:
        # Convert constructor argument types from surface to core
        core_args = [surface_to_core_type(arg, type_ctx) for arg in con_info.args]
        core_constructors.append((con_info.name, core_args))

        # Build constructor type: args -> result_type wrapped in forall params
        # Example: data Maybe a = Just a | Nothing
        #   Just has type: forall a. a -> Maybe a
        #   Nothing has type: forall a. Maybe a
        con_type: Type = result_type
        for arg in reversed(core_args):
            con_type = TypeArrow(arg, con_type)
        for param in reversed(decl.params):
            con_type = TypeForall(param, con_type)

        constructor_types[con_info.name] = con_type

    data_decl = core.DataDeclaration(
        name=decl.name,
        params=decl.params,
        constructors=core_constructors,
    )

    return (data_decl, constructor_types)


def data_decl_elab_pass(
    decls: list[tuple[int, SurfaceDeclaration]], ctx: TypeContext
) -> Result[tuple[list[core.Declaration], dict[str, Type]], TypeError]:
    """Elaborate data type declarations to core.

    Phase 2, step 2: Processes SurfaceDataDeclaration entries and produces
    core.DataDeclaration nodes along with constructor type signatures.

    Args:
        decls: List of (order, declaration) tuples for data declarations
        ctx: Type context for looking up type variables

    Returns:
        Ok((core_decls, constructor_types)) on success
        Err(TypeError) on failure

    Example:
        Input: [(0, SurfaceDataDeclaration(name="Maybe", params=["a"],
                                          constructors=[SurfaceConstructorInfo("Just", [SurfaceTypeVar("a")]),
                                                       SurfaceConstructorInfo("Nothing", [])]))]
        Output: Ok(([DataDeclaration("Maybe", ["a"], [("Just", [TypeVar("a")]), ("Nothing", [])])],
                    {"Just": forall a. a -> Maybe a, "Nothing": forall a. Maybe a}))
    """
    core_decls: list[core.Declaration] = []
    all_constructor_types: dict[str, Type] = {}

    try:
        for _, decl in decls:
            if isinstance(decl, SurfaceDataDeclaration):
                core_decl, con_types = elaborate_data_decl(decl, ctx)
                core_decls.append(core_decl)
                all_constructor_types.update(con_types)
                # Update context with constructor types for subsequent declarations
                for name, ty in con_types.items():
                    ctx = ctx.add_constructor(name, ty)
            else:
                raise TypeError(f"Expected SurfaceDataDeclaration, got {type(decl).__name__}")

        return Ok((core_decls, all_constructor_types))
    except TypeError as e:
        from systemf.surface.result import Err

        return Err(e)
