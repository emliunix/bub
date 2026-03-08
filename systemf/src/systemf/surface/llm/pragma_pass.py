"""LLM pragma pass for System F surface language.

This module implements Phase 3 of the elaboration pipeline: processing LLM pragma
annotations on function declarations. The pass transforms LLM function bodies to
PrimOp references and extracts metadata for runtime execution.

Example:
    Input (Core declaration with pragma):
        TermDeclaration(
            name="translate",
            type_annotation=TypeArrow(...),
            body=Abs(...),  # Original lambda
            pragma="model=gpt-4 temperature=0.7",
            docstring="Translate text to French"
        )

    Output:
        TermDeclaration(
            name="translate",
            type_annotation=TypeArrow(...),
            body=PrimOp("llm.translate"),  # Replaced
            pragma="model=gpt-4 temperature=0.7",
            docstring="Translate text to French"
        )
        + LLMMetadata in the result dict
"""

from __future__ import annotations

from dataclasses import dataclass

from systemf.core import ast as core
from systemf.core.module import LLMMetadata
from systemf.core.types import Type, TypeArrow
from systemf.surface.result import Result, Ok, Err


@dataclass(frozen=True)
class LLMError:
    """Error during LLM pragma processing."""

    message: str
    function_name: str | None = None


def llm_pragma_pass(
    core_decls: list[core.Declaration],
) -> Result[tuple[list[core.Declaration], dict[str, LLMMetadata]], LLMError]:
    """Transform LLM functions to PrimOp bodies and extract metadata.

    This pass processes Core declarations that have LLM pragmas:
    1. Identifies declarations with non-None pragma field
    2. Replaces the body with PrimOp("llm.{name}")
    3. Extracts LLMMetadata for runtime
    4. Passes through non-LLM declarations unchanged

    Args:
        core_decls: List of Core declarations from elaboration

    Returns:
        Result containing:
        - final_decls: List of declarations with LLM bodies transformed
        - llm_metadata_dict: Mapping from function name to LLMMetadata

    Example:
        >>> decls = [regular_func, llm_func_with_pragma]
        >>> result = llm_pragma_pass(decls)
        >>> if result.is_ok():
        ...     final_decls, metadata = result.unwrap()
        ...     # llm_func_with_pragma now has PrimOp body
        ...     # metadata contains LLM configuration
    """
    final_decls: list[core.Declaration] = []
    llm_metadata: dict[str, LLMMetadata] = {}

    for decl in core_decls:
        match decl:
            case core.TermDeclaration(pragma=pragma) if pragma is not None:
                # This is an LLM function - transform it
                result = _transform_llm_declaration(decl)
                if isinstance(result, Err):
                    return result
                transformed_decl, metadata = result.unwrap()
                final_decls.append(transformed_decl)
                llm_metadata[metadata.function_name] = metadata
            case _:
                # Non-LLM declaration - pass through unchanged
                final_decls.append(decl)

    return Ok((final_decls, llm_metadata))


def _transform_llm_declaration(
    decl: core.TermDeclaration,
) -> Result[tuple[core.TermDeclaration, LLMMetadata], LLMError]:
    """Transform a single LLM declaration.

    Args:
        decl: TermDeclaration with pragma field set

    Returns:
        Result with transformed declaration and metadata
    """
    # Build LLM metadata from declaration
    metadata = _build_llm_metadata(decl)

    # Create transformed declaration with PrimOp body
    # PrimOp only takes name, location is inherited from Term base class
    prim_op = core.PrimOp(name=f"llm.{decl.name}")
    # Set source_loc if needed via object.__setattr__ since it's frozen
    transformed_decl = core.TermDeclaration(
        name=decl.name,
        type_annotation=decl.type_annotation,
        body=prim_op,
        pragma=decl.pragma,
        docstring=decl.docstring,
        param_docstrings=decl.param_docstrings,
    )

    return Ok((transformed_decl, metadata))


def _build_llm_metadata(decl: core.TermDeclaration) -> LLMMetadata:
    """Build LLMMetadata from a term declaration.

    Args:
        decl: The term declaration with pragma

    Returns:
        LLMMetadata for runtime execution
    """
    # Extract argument types from the type annotation
    arg_types, arg_docs = _extract_arg_info(decl.type_annotation)

    return LLMMetadata(
        function_name=decl.name,
        function_docstring=decl.docstring,
        arg_types=arg_types,
        arg_docstrings=arg_docs,
        pragma_params=decl.pragma,
    )


def _extract_arg_info(ty: Type | None) -> tuple[list[Type], list[str | None]]:
    """Extract argument types and docstrings from a function type.

    For a type like A -> B -> C, returns ([A, B], [docA, docB]).

    Args:
        ty: The function type (may be None)

    Returns:
        Tuple of (arg_types, arg_docstrings)
    """
    arg_types: list[Type] = []
    arg_docs: list[str | None] = []

    if ty is None:
        return arg_types, arg_docs

    current = ty
    while isinstance(current, TypeArrow):
        arg_types.append(current.arg)
        arg_docs.append(current.param_doc)
        current = current.ret

    return arg_types, arg_docs


def _extract_location(term: core.Term) -> core.Location:
    """Extract location from a term, or return a default location."""
    # Try to get location from common term types
    match term:
        case core.Var(location=loc):
            return loc
        case core.Abs(location=loc):
            return loc
        case core.App(location=loc):
            return loc
        case core.TAbs(location=loc):
            return loc
        case core.TApp(location=loc):
            return loc
        case core.Constructor(location=loc):
            return loc
        case core.Case(location=loc):
            return loc
        case core.Let(location=loc):
            return loc
        case core.ToolCall(location=loc):
            return loc
        case core.Lit(location=loc):
            return loc
        case core.PrimOp(location=loc):
            return loc
        case _:
            # Default location if none available
            return core.Location(line=0, column=0, file="<generated>")


def parse_pragma_config(config: str) -> dict[str, str]:
    """Parse LLM pragma configuration string into key-value pairs.

    Parses configuration strings like "model=gpt-4 temperature=0.7 max_tokens=100"
    into a dictionary.

    Args:
        config: The raw pragma configuration string

    Returns:
        Dictionary of configuration parameters

    Example:
        >>> parse_pragma_config("model=gpt-4 temperature=0.7")
        {'model': 'gpt-4', 'temperature': '0.7'}
    """
    result: dict[str, str] = {}

    if not config:
        return result

    # Simple space-separated key=value parsing
    parts = config.split()

    for part in parts:
        if "=" in part:
            key, value = part.split("=", 1)
            result[key.strip()] = value.strip()
        else:
            # Handle flags without values (e.g., "stream")
            result[part.strip()] = "true"

    return result
