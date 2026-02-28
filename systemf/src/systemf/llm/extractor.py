"""LLM metadata extraction from Core AST.

This module provides functionality to extract LLM function metadata
after type checking, when types have been validated.
"""

from systemf.core.ast import Declaration, TermDeclaration
from systemf.core.module import LLMMetadata, Module
from systemf.core.types import Type, TypeArrow


def extract_llm_metadata(module: Module, global_types: dict[str, Type]) -> dict[str, LLMMetadata]:
    """Extract LLM function metadata from Core declarations after type checking.

    This should be called after type checking when we have validated types.

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

        # Check if this is an LLM function (has pragma)
        if not decl.pragma:
            continue

        # Get the validated type from type checker
        validated_type = global_types.get(decl.name)
        if validated_type is None:
            continue

        # Extract argument types from validated type
        arg_types = _extract_arg_types(validated_type)

        # Build LLMMetadata
        metadata = LLMMetadata(
            function_name=decl.name,
            function_docstring=decl.docstring,
            arg_names=_extract_arg_names(decl, len(arg_types)),
            arg_types=arg_types,
            arg_docstrings=decl.param_docstrings or [None] * len(arg_types),
            pragma_params=decl.pragma,
        )

        llm_functions[decl.name] = metadata

    return llm_functions


def _extract_arg_types(ty: Type) -> list[Type]:
    """Extract argument types from a function type.

    For a type like A -> B -> C, returns [A, B].
    """
    arg_types = []
    current = ty

    while isinstance(current, TypeArrow):
        arg_types.append(current.arg)
        current = current.ret

    return arg_types


def _extract_arg_names(decl: TermDeclaration, num_args: int) -> list[str]:
    """Extract argument names from declaration.

    For now, generates names like "arg0", "arg1", etc.
    In the future, could extract from lambda body if available.
    """
    # If we have param_docstrings, use their count as hint
    if decl.param_docstrings:
        count = len(decl.param_docstrings)
    else:
        count = num_args

    return [f"arg{i}" for i in range(count)]
