"""LLM pragma pass for System F surface language.

This module implements Phase 3 of the elaboration pipeline: processing LLM pragma
annotations on function declarations. The pass extracts LLM configuration from
pragmas, transforms the function body to a PrimOp, and prepares metadata for
LLM-based function execution.

Example:
    Input:
        {-# LLM model=gpt-4 temperature=0.7 #-}
        -- | Translate text to French
        translate : String -> String
        translate = \\text -> @llm text

    Output:
        - TermDeclaration with:
          - body = PrimOp("llm.translate")
          - pragma = "model=gpt-4 temperature=0.7"
          - docstring = "Translate text to French"
        - LLMMetadata extracted for runtime
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from systemf.core import ast as core
from systemf.core.module import LLMMetadata
from systemf.core.types import Type, TypeArrow
from systemf.surface.types import (
    SurfaceDeclaration,
    SurfaceTermDeclaration,
    SurfacePrimOpDecl,
    SurfaceAbs,
)
from systemf.utils.location import Location


@dataclass(frozen=True)
class LLMPragmaResult:
    """Result of processing a declaration with LLM pragma.

    Attributes:
        declaration: The transformed Core declaration
        metadata: Optional LLM metadata if this was an LLM function
        is_llm: Whether this declaration had an LLM pragma
    """

    declaration: core.Declaration
    metadata: Optional[LLMMetadata]
    is_llm: bool


class LLMPragmaPass:
    """Pass to process LLM pragma annotations on declarations.

    This pass scans declarations for LLM pragmas and:
    1. Extracts LLM configuration (model, temperature, max_tokens, etc.)
    2. Replaces the function body with a PrimOp referencing the LLM
    3. Builds LLMMetadata for runtime execution
    4. Preserves docstrings and parameter information

    The pass handles two types of LLM declarations:
    - SurfaceTermDeclaration: Regular function with LLM pragma
    - SurfacePrimOpDecl: Primitive operation with LLM pragma

    Example:
        >>> from systemf.surface.types import SurfaceTermDeclaration, SurfaceTypeConstructor
        >>> from systemf.utils.location import Location
        >>>
        >>> # Create pass
        >>> llm_pass = LLMPragmaPass()
        >>>
        >>> # Process declaration with LLM pragma
        >>> decl = SurfaceTermDeclaration(
        ...     name="translate",
        ...     type_annotation=SurfaceTypeConstructor(name="String", args=[], location=loc),
        ...     body=SurfaceAbs("text", None, SurfaceVar(0, "text", loc), loc),
        ...     location=loc,
        ...     docstring="Translate to French",
        ...     pragma={"LLM": "model=gpt-4"}
        ... )
        >>> result = llm_pass.process_declaration(decl, core_type)
    """

    def __init__(self):
        """Initialize the LLM pragma pass."""
        self._processed_count = 0

    def process_declaration(
        self,
        decl: SurfaceDeclaration,
        core_type: Optional[Type] = None,
    ) -> LLMPragmaResult:
        """Process a single surface declaration for LLM pragmas.

        Args:
            decl: The surface declaration to process
            core_type: Optional core type for the declaration (if already elaborated)

        Returns:
            LLMPragmaResult containing the transformed declaration and metadata
        """
        match decl:
            case SurfaceTermDeclaration():
                return self._process_term_declaration(decl, core_type)
            case SurfacePrimOpDecl():
                return self._process_prim_op_declaration(decl, core_type)
            case _:
                # Other declaration types don't have LLM pragmas - pass through unchanged
                return LLMPragmaResult(
                    declaration=decl,
                    metadata=None,
                    is_llm=False,
                )

    def _process_term_declaration(
        self,
        decl: SurfaceTermDeclaration,
        core_type: Optional[Type],
    ) -> LLMPragmaResult:
        """Process a term declaration with potential LLM pragma.

        Args:
            decl: The surface term declaration
            core_type: The elaborated core type

        Returns:
            LLMPragmaResult with transformed declaration and metadata
        """
        # Check if this has an LLM pragma
        pragma_config = self._extract_pragma_config(decl.pragma)

        if pragma_config is None:
            # Not an LLM function - skip and let main elaborator handle it
            # Return the original surface declaration unchanged
            return LLMPragmaResult(
                declaration=decl,  # Pass through unchanged
                metadata=None,
                is_llm=False,
            )

        # This is an LLM function - extract metadata and transform
        self._processed_count += 1

        # Extract parameter docstrings from lambda if present
        param_docstrings: list[str] = []
        if isinstance(decl.body, SurfaceAbs) and decl.body.param_docstrings:
            param_docstrings = [str(ds) if ds else "" for ds in decl.body.param_docstrings]

        # Build LLM metadata
        metadata = self._build_llm_metadata(
            name=decl.name,
            docstring=decl.docstring,
            pragma_config=pragma_config,
            core_type=core_type,
            param_docstrings=param_docstrings if param_docstrings else None,
        )

        # Create Core declaration with PrimOp body
        core_decl = core.TermDeclaration(
            name=decl.name,
            type_annotation=core_type,
            body=core.PrimOp(decl.location, f"llm.{decl.name}"),
            pragma=pragma_config,
            docstring=decl.docstring,
            param_docstrings=param_docstrings if param_docstrings else None,
        )

        return LLMPragmaResult(
            declaration=core_decl,
            metadata=metadata,
            is_llm=True,
        )

    def _process_prim_op_declaration(
        self,
        decl: SurfacePrimOpDecl,
        core_type: Optional[Type],
    ) -> LLMPragmaResult:
        """Process a primitive operation declaration with potential LLM pragma.

        Args:
            decl: The surface primitive operation declaration
            core_type: The elaborated core type

        Returns:
            LLMPragmaResult with transformed declaration and metadata
        """
        # Check if this has an LLM pragma
        pragma_config = self._extract_pragma_config(decl.pragma)

        if pragma_config is None:
            # Not an LLM primitive - return regular declaration
            return LLMPragmaResult(
                declaration=self._convert_prim_op_to_core(decl, core_type),
                metadata=None,
                is_llm=False,
            )

        # This is an LLM primitive - extract metadata and transform
        self._processed_count += 1

        # Build LLM metadata
        metadata = self._build_llm_metadata(
            name=decl.name,
            docstring=decl.docstring,
            pragma_config=pragma_config,
            core_type=core_type,
            param_docstrings=None,
        )

        # Create Core declaration with PrimOp body
        core_decl = core.TermDeclaration(
            name=decl.name,
            type_annotation=core_type,
            body=core.PrimOp(decl.location, f"llm.{decl.name}"),
            pragma=pragma_config,
            docstring=decl.docstring,
            param_docstrings=None,
        )

        return LLMPragmaResult(
            declaration=core_decl,
            metadata=metadata,
            is_llm=True,
        )

    def _extract_pragma_config(self, pragma: dict[str, str] | None) -> Optional[str]:
        """Extract LLM configuration from pragma dict.

        Args:
            pragma: The pragma dict from surface declaration

        Returns:
            LLM configuration string if present, None otherwise
        """
        if pragma is None:
            return None

        if "LLM" not in pragma:
            return None

        config = pragma["LLM"].strip()
        return config if config else None

    def _build_llm_metadata(
        self,
        name: str,
        docstring: Optional[str],
        pragma_config: str,
        core_type: Optional[Type],
        param_docstrings: Optional[list[str]],
    ) -> LLMMetadata:
        """Build LLMMetadata from declaration information.

        Args:
            name: Function name
            docstring: Function docstring
            pragma_config: Raw pragma configuration string
            core_type: The core type (for extracting arg types)
            param_docstrings: Parameter docstrings

        Returns:
            LLMMetadata for runtime execution
        """
        # Extract argument types from core type
        arg_types: list[Type] = []
        arg_docs: list[str | None] = []

        if core_type is not None:
            arg_types = self._extract_arg_types(core_type)
            arg_docs = self._extract_arg_docstrings(core_type)

        # Ensure param_docstrings aligns with arg_types
        if param_docstrings is not None:
            # Use provided param docstrings, filling gaps
            while len(arg_docs) < len(param_docstrings):
                arg_docs.append(None)
            for i, doc in enumerate(param_docstrings):
                if i < len(arg_docs) and doc:
                    arg_docs[i] = doc

        # Trim to match arg_types length
        arg_docs = arg_docs[: len(arg_types)]

        return LLMMetadata(
            function_name=name,
            function_docstring=docstring,
            arg_types=arg_types,
            arg_docstrings=arg_docs,
            pragma_params=pragma_config,
        )

    def _extract_arg_types(self, ty: Type) -> list[Type]:
        """Extract argument types from a function type.

        For a type like A -> B -> C, returns [A, B].

        Args:
            ty: The function type

        Returns:
            List of argument types
        """
        arg_types: list[Type] = []
        current = ty

        while isinstance(current, TypeArrow):
            arg_types.append(current.arg)
            current = current.ret

        return arg_types

    def _extract_arg_docstrings(self, ty: Type) -> list[str | None]:
        """Extract parameter docstrings from type annotations.

        For a type like (A -- ^ doc1) -> (B -- ^ doc2) -> C,
        returns [doc1, doc2].

        Args:
            ty: The function type with parameter docs

        Returns:
            List of parameter docstrings (may contain None)
        """
        arg_docs: list[str | None] = []
        current = ty

        while isinstance(current, TypeArrow):
            arg_docs.append(current.param_doc)
            current = current.ret

        return arg_docs

    def _convert_non_llm_declaration(
        self,
        decl: SurfaceDeclaration,
        core_type: Optional[Type] = None,
    ) -> core.Declaration:
        """Convert a non-LLM surface declaration to Core.

        This is a placeholder that would normally be handled by the main
        elaborator. For the LLM pass, we just return a basic structure.

        Args:
            decl: The surface declaration
            core_type: Optional core type

        Returns:
            Basic Core declaration
        """
        # For non-LLM declarations, we create a placeholder
        # The actual elaboration happens elsewhere
        match decl:
            case SurfaceTermDeclaration():
                return core.TermDeclaration(
                    name=decl.name,
                    type_annotation=core_type,
                    body=core.PrimOp(decl.location, f"${decl.name}"),
                    pragma=None,
                    docstring=decl.docstring,
                    param_docstrings=None,
                )
            case _:
                # Return a minimal placeholder for other types
                return core.DataDeclaration(
                    name="placeholder",
                    params=[],
                    constructors=[],
                )

    def _convert_prim_op_to_core(
        self,
        decl: SurfacePrimOpDecl,
        core_type: Optional[Type],
    ) -> core.Declaration:
        """Convert a primitive operation to Core declaration.

        Args:
            decl: The surface primitive operation declaration
            core_type: The elaborated core type

        Returns:
            Core TermDeclaration
        """
        return core.TermDeclaration(
            name=decl.name,
            type_annotation=core_type,
            body=core.PrimOp(decl.location, f"{decl.name}"),
            pragma=None,
            docstring=decl.docstring,
            param_docstrings=None,
        )

    def get_processed_count(self) -> int:
        """Return the number of LLM declarations processed.

        Returns:
            Count of LLM functions processed by this pass
        """
        return self._processed_count


def process_llm_pragmas(
    decls: list[SurfaceDeclaration],
    type_map: dict[str, Type],
) -> tuple[list[core.Declaration], dict[str, LLMMetadata]]:
    """Process LLM pragmas on a list of declarations.

    Convenience function that processes multiple declarations and collects
    all LLM metadata.

    Args:
        decls: List of surface declarations to process
        type_map: Mapping from declaration names to their core types

    Returns:
        Tuple of (core declarations, llm metadata dict)

    Example:
        >>> decls = [func1_decl, func2_decl, llm_func_decl]
        >>> types = {"func1": type1, "func2": type2, "llm_func": llm_type}
        >>> core_decls, llm_meta = process_llm_pragmas(decls, types)
    """
    llm_pass = LLMPragmaPass()
    core_decls: list[core.Declaration] = []
    llm_metadata: dict[str, LLMMetadata] = {}

    for decl in decls:
        # Get the type for this declaration if available
        core_type = None
        if isinstance(decl, (SurfaceTermDeclaration, SurfacePrimOpDecl)):
            core_type = type_map.get(decl.name)

        # Process the declaration
        result = llm_pass.process_declaration(decl, core_type)

        core_decls.append(result.declaration)

        if result.is_llm and result.metadata is not None:
            llm_metadata[result.metadata.function_name] = result.metadata

    return core_decls, llm_metadata


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
    # More complex parsing (quoted values, etc.) can be added later
    parts = config.split()

    for part in parts:
        if "=" in part:
            key, value = part.split("=", 1)
            result[key.strip()] = value.strip()
        else:
            # Handle flags without values (e.g., "stream")
            result[part.strip()] = "true"

    return result
