"""LLM metadata extraction from Core AST.

This module provides functionality to extract LLM function metadata
after type checking, when types have been validated.

Extraction Timing:
    This module is designed to be called AFTER type checking completes.
    The extraction process depends on:
    1. Module.docstrings - populated during elaboration from Surface AST docstrings
    2. TypeArrow.param_doc - embedded in type annotations during elaboration
    3. Validated types from the type checker

    The two-pass architecture ensures:
    - Pass 1 (Elaboration): Extracts docstrings to Module.docstrings
    - Pass 2 (Post-Typecheck): Extracts LLMMetadata using validated types
"""

from systemf.core.ast import Declaration, TermDeclaration
from systemf.core.module import LLMMetadata, Module
from systemf.core.types import Type, TypeArrow


def extract_llm_metadata(module: Module, global_types: dict[str, Type]) -> dict[str, LLMMetadata]:
    """Extract LLM function metadata from Core declarations after type checking.

    This should be called after type checking when we have validated types.
    Docstrings are extracted from Module.docstrings (populated during elaboration),
    and parameter docstrings are extracted from TypeArrow.param_doc fields.

    Args:
        module: The compiled module containing Core declarations
        global_types: Mapping of validated types from the type checker

    Returns:
        Dictionary mapping function names to LLMMetadata
    """
    llm_functions: dict[str, LLMMetadata] = {}

    for decl in module.declarations:
        if not isinstance(decl, TermDeclaration):
            continue

        # Check if this is an LLM function (has pragma - None means no pragma)
        if decl.pragma is None:
            continue

        # Get the validated type from type checker
        validated_type = global_types.get(decl.name)
        if validated_type is None:
            continue

        # Extract argument types from validated type
        arg_types = _extract_arg_types(validated_type)

        # Build LLMMetadata
        # Get function docstring from Module.docstrings (extracted during elaboration)
        function_docstring = module.docstrings.get(decl.name)
        # Get param docstrings from TypeArrow.param_doc fields in the validated type
        arg_docstrings = _extract_arg_docstrings(validated_type)
        # Ensure correct length
        while len(arg_docstrings) < len(arg_types):
            arg_docstrings.append(None)

        metadata = LLMMetadata(
            function_name=decl.name,
            function_docstring=function_docstring,
            arg_types=arg_types,
            arg_docstrings=arg_docstrings,
            pragma_params=decl.pragma,
        )

        llm_functions[decl.name] = metadata

    return llm_functions


def _extract_arg_types(ty: Type) -> list[Type]:
    """Extract argument types from a function type.

    For a type like A -> B -> C, returns [A, B].
    """
    arg_types: list[Type] = []
    current = ty

    while isinstance(current, TypeArrow):
        arg_types.append(current.arg)
        current = current.ret

    return arg_types


def _extract_arg_docstrings(ty: Type) -> list[str | None]:
    """Extract parameter docstrings from type annotations.

    For a type like (A -- ^ doc1) -> (B -- ^ doc2) -> C,
    returns [doc1, doc2].

    Parameter docs are stored in TypeArrow.param_doc field.
    """
    arg_docs: list[str | None] = []
    current = ty

    while isinstance(current, TypeArrow):
        arg_docs.append(current.param_doc)
        current = current.ret

    return arg_docs
