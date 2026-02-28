"""Module dataclass for compile-time artifacts.

This module defines the Module dataclass which serves as the container for all
compile-time information including declarations, type information, errors, and
LLM function metadata.
"""

from __future__ import annotations

from dataclasses import dataclass

from systemf.core.ast import DataDeclaration, Declaration, TermDeclaration
from systemf.core.types import PrimitiveType, Type
from systemf.core.errors import ElaborationError


@dataclass(frozen=True)
class LLMMetadata:
    """Complete metadata for an LLM function.

    Used by the evaluator to:
    1. Craft prompts (using docs and types)
    2. Call LLM APIs (using pragma_params)
    3. Parse responses (using return type)
    4. Handle errors (fallback to identity)

    All types are validated by type checker before extraction.

    Attributes:
        function_name: The name of the function in the module
        function_docstring: Optional docstring (-- | style) describing the function
        arg_types: Ordered list of parameter types (validated)
        arg_docstrings: Ordered list of parameter docstrings from -- ^ (parallel to arg_types)
        pragma_params: Raw pragma parameters as string (e.g., "model=gpt-4 temperature=0.7")
    """

    function_name: str
    function_docstring: str | None
    arg_types: list[Type]
    arg_docstrings: list[str | None]
    pragma_params: str | None


@dataclass(frozen=True)
class Module:
    """Container for all compile-time artifacts of a System F module.

    A Module represents a complete unit of compilation, containing all
    type-checked declarations, type information, docstrings, errors, and
    warnings generated during elaboration.

    Attributes:
        name: Module name (e.g., "prelude", "main")
        declarations: Core AST declarations (data and term declarations)
        constructor_types: Data constructor signatures (constructor_name -> Type)
        global_types: Top-level term signatures (term_name -> Type)
        primitive_types: Primitive type definitions (type_name -> PrimitiveType)
        docstrings: Name to docstring mapping for declarations
        llm_functions: LLM function metadata for @llm decorated functions
        errors: Elaboration errors encountered during type checking
        warnings: Warnings generated during compilation
    """

    name: str
    declarations: list[Declaration]
    constructor_types: dict[str, Type]
    global_types: dict[str, Type]
    primitive_types: dict[str, PrimitiveType]
    docstrings: dict[str, str]
    llm_functions: dict[str, LLMMetadata]
    errors: list[ElaborationError]
    warnings: list[str]
