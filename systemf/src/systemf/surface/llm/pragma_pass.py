"""LLM pragma pass for System F surface language.

Pure surface AST → surface AST transformation. Processes LLM pragma
annotations on prim_op declarations, marking them for synthesizer-backed
resolution at runtime.

Pipeline position: post-parse, pre-rename.

Input:  list[SurfaceDeclaration]
Output: same declarations + pragma metadata extracted from prim_op decls
"""

from __future__ import annotations

from dataclasses import dataclass

from systemf.surface.types import (
    SurfaceDeclaration,
    SurfacePrimOpDecl,
)


@dataclass(frozen=True)
class PragmaMeta:
    function_name: str
    pragma_config: dict[str, str]
    docstring: str | None


def pragma_pass(
    decls: list[SurfaceDeclaration],
) -> tuple[list[SurfaceDeclaration], list[PragmaMeta]]:
    """Extract pragma metadata from prim_op declarations.

    For SurfacePrimOpDecl with a non-None, non-empty pragma dict,
    extracts PragmaMeta for downstream synthesizer wiring.

    The declarations pass through unchanged — the metadata is used
    by the rename/typecheck pipeline to register the primop as
    synthesizer-backed.

    Returns (declarations, pragma_metadata_list).
    """
    metas: list[PragmaMeta] = []

    for decl in decls:
        match decl:
            case SurfacePrimOpDecl(
                name=name, pragma=pragma, docstring=docstring
            ) if pragma:
                metas.append(PragmaMeta(
                    function_name=name,
                    pragma_config=pragma,
                    docstring=docstring,
                ))
            case _:
                pass

    return decls, metas


def parse_pragma_config(config: str) -> dict[str, str]:
    result: dict[str, str] = {}

    if not config:
        return result

    parts = config.split()
    for part in parts:
        if "=" in part:
            key, value = part.split("=", 1)
            result[key.strip()] = value.strip()
        else:
            result[part.strip()] = "true"

    return result
