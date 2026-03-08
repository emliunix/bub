"""Build declarations pass for System F surface language.

This module implements Phase 2, step 3c of the elaboration pipeline:
building core.TermDeclaration objects from elaborated term bodies.

The build declarations pass:
1. Takes elaborated bodies from ElabBodiesPass
2. Builds core.TermDeclaration for each elaborated body
3. Preserves docstrings from original surface declarations
4. Returns list of core declarations
"""

from systemf.core.ast import Term, TermDeclaration
from systemf.core.types import Type
from systemf.surface.result import Ok, Result
from systemf.surface.types import SurfaceTermDeclaration


def build_decls_pass(
    elaborated_bodies: list[tuple[str, Term, Type]],
    term_decls: list[SurfaceTermDeclaration],
    pragma_map: dict[str, str | None],
) -> Result[list[TermDeclaration], Exception]:
    """Build core term declarations from elaborated bodies.

    Phase 2, step 3c: Builds core.TermDeclaration objects from the elaborated
    term bodies produced by the elaboration phase. Preserves metadata like
    docstrings from the original surface declarations.

    Args:
        elaborated_bodies: List of (name, core_body, ty) tuples from elaboration.
            Each tuple contains the declaration name, elaborated core term,
            and inferred/core type.
        term_decls: List of original surface term declarations. Used to extract
            docstrings and other metadata that should be preserved.
        pragma_map: Dictionary mapping declaration names to their pragma
            strings (or None if no pragma). Pragmas contain metadata like
            LLM configuration.

    Returns:
        Result containing list of core.TermDeclaration objects, or an error
        if a declaration cannot be found or built.

    Example:
        >>> from systemf.core.ast import Var, Lit
        >>> from systemf.core.types import TypeConstructor
        >>> from systemf.surface.types import SurfaceTermDeclaration, SurfaceTypeConstructor
        >>>
        >>> # Create elaborated body: x = 42
        >>> core_body = Lit(prim_type="Int", value=42)
        >>> int_type = TypeConstructor(name="Int", args=[])
        >>> elaborated = [("x", core_body, int_type)]
        >>>
        >>> # Create original surface declaration with docstring
        >>> surface_type = SurfaceTypeConstructor(name="Int", args=[])
        >>> surface_decl = SurfaceTermDeclaration(
        ...     name="x",
        ...     type_annotation=surface_type,
        ...     docstring="The answer to everything"
        ... )
        >>>
        >>> # Build core declarations
        >>> result = build_decls_pass(elaborated, [surface_decl], {})
        >>> if result.is_ok():
        ...     core_decls = result.unwrap()
        ...     print(f"Built {len(core_decls)} declarations")
        ...     print(f"Docstring: {core_decls[0].docstring}")
    """
    core_decls: list[TermDeclaration] = []

    for name, core_body, ty in elaborated_bodies:
        # Find original declaration for docstring
        try:
            orig_decl = next(d for d in term_decls if d.name == name)
        except StopIteration:
            return Err(Exception(f"Could not find original declaration for '{name}'"))

        # Get pragma for this declaration (may be None)
        pragma = pragma_map.get(name)

        # Build core declaration
        core_decl = TermDeclaration(
            name=name,
            type_annotation=ty,
            body=core_body,
            pragma=pragma,
            docstring=orig_decl.docstring,
            param_docstrings=None,
        )
        core_decls.append(core_decl)

    return Ok(core_decls)
