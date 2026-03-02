"""Pipeline orchestrator for System F elaboration.

This module provides the main integration point for the three-phase elaboration
pipeline:

1. Phase 1 - Scope Checking: Surface AST → Scoped AST
2. Phase 2 - Type Elaboration: Scoped AST → typed Core AST
3. Phase 3 - LLM Pragma Pass: Transform LLM functions

The orchestrator coordinates these phases with proper error handling and
collects all compilation artifacts into a Core.Module.

Example:
    >>> from systemf.surface.pipeline import ElaborationPipeline
    >>> from systemf.surface.types import SurfaceTermDeclaration
    >>>
    >>> # Create pipeline
    >>> pipeline = ElaborationPipeline(module_name="main")
    >>>
    >>> # Elaborate declarations
    >>> declarations = [func1_decl, func2_decl]
    >>> module = pipeline.elaborate_module(declarations)
    >>>
    >>> # Check for errors
    >>> if module.errors:
    ...     print(f"Errors: {module.errors}")
    >>> else:
    ...     print(f"Success: {len(module.declarations)} declarations")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from systemf.core import ast as core
from systemf.core.module import LLMMetadata, Module
from systemf.core.types import PrimitiveType, Type
from systemf.core.errors import ElaborationError
from systemf.surface.scoped.checker import ScopeChecker
from systemf.surface.scoped.context import ScopeContext
from systemf.surface.scoped.errors import UndefinedVariableError
from systemf.surface.inference import TypeElaborator, TypeContext
from systemf.surface.inference.errors import (
    TypeError,
    TypeMismatchError,
    UnificationError,
)
from systemf.surface.llm.pragma_pass import LLMPragmaPass, LLMPragmaResult
from systemf.surface.types import SurfaceDeclaration, SurfaceTermDeclaration


@dataclass
class PipelineResult:
    """Result of running the elaboration pipeline.

    Attributes:
        module: The compiled module (may contain errors)
        success: Whether the pipeline completed without errors
        errors: List of errors encountered during elaboration
        warnings: List of warnings generated
    """

    module: Module
    success: bool
    errors: list[ElaborationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ElaborationPipeline:
    """Main pipeline orchestrator for System F elaboration.

    Coordinates the three-phase elaboration process:
    1. Scope checking - resolve names to de Bruijn indices
    2. Type elaboration - infer and check types
    3. LLM pragma pass - transform LLM functions

    The pipeline handles errors gracefully, collecting all errors
    and warnings into the resulting Module.

    Attributes:
        module_name: Name of the module being compiled
        scope_checker: Phase 1 scope checker
        type_elaborator: Phase 2 type elaborator
        llm_pass: Phase 3 LLM pragma processor

    Example:
        >>> pipeline = ElaborationPipeline(module_name="main")
        >>> decls = [func1_decl, func2_decl]
        >>> result = pipeline.run(decls)
        >>>
        >>> if result.success:
        ...     print(f"Compiled {len(result.module.declarations)} declarations")
        ... else:
        ...     for error in result.errors:
        ...         print(f"Error: {error}")
    """

    def __init__(self, module_name: str = "main"):
        """Initialize the elaboration pipeline.

        Args:
            module_name: Name for the compiled module
        """
        self.module_name = module_name
        self.scope_checker = ScopeChecker()
        self.type_elaborator = TypeElaborator()
        self.llm_pass = LLMPragmaPass()
        self._errors: list[ElaborationError] = []
        self._warnings: list[str] = []

    def run(
        self,
        declarations: list[SurfaceDeclaration],
        constructors: Optional[dict[str, Type]] = None,
    ) -> PipelineResult:
        """Run the full elaboration pipeline on a list of declarations.

        Executes all three phases:
        1. Scope checking - Surface AST → Scoped AST
        2. Type elaboration - Scoped AST → Core AST with types
        3. LLM pragma pass - Transform LLM functions

        Args:
            declarations: List of surface declarations to elaborate
            constructors: Optional data constructor types

        Returns:
            PipelineResult containing the compiled module and status
        """
        try:
            # Phase 1 & 2: Scope check and type elaborate
            core_decls, ctx, global_types = self._elaborate_declarations(declarations, constructors)

            # Phase 3: Process LLM pragmas
            final_decls, llm_functions = self._process_llm_pragmas(
                declarations, core_decls, global_types
            )

            # Collect docstrings
            docstrings = self._collect_docstrings(declarations)

            # Create the module
            module = Module(
                name=self.module_name,
                declarations=final_decls,
                constructor_types=constructors or {},
                global_types=global_types,
                primitive_types={},
                docstrings=docstrings,
                llm_functions=llm_functions,
                errors=list(self._errors),
                warnings=list(self._warnings),
            )

            return PipelineResult(
                module=module,
                success=len(self._errors) == 0,
                errors=list(self._errors),
                warnings=list(self._warnings),
            )

        except Exception as e:
            # Handle unexpected errors
            error = ElaborationError(
                message=f"Pipeline failed: {e}",
                location=None,
            )
            self._errors.append(error)

            # Return empty module with error
            module = Module(
                name=self.module_name,
                declarations=[],
                constructor_types=constructors or {},
                global_types={},
                primitive_types={},
                docstrings={},
                llm_functions={},
                errors=list(self._errors),
                warnings=list(self._warnings),
            )

            return PipelineResult(
                module=module,
                success=False,
                errors=list(self._errors),
                warnings=list(self._warnings),
            )

    def elaborate_module(
        self,
        declarations: list[SurfaceDeclaration],
        constructors: Optional[dict[str, Type]] = None,
    ) -> Module:
        """Elaborate declarations into a Core.Module.

        Convenience method that runs the pipeline and returns just the module.

        Args:
            declarations: List of surface declarations
            constructors: Optional data constructor types

        Returns:
            The compiled Module (check module.errors for issues)
        """
        result = self.run(declarations, constructors)
        return result.module

    def _elaborate_declarations(
        self,
        declarations: list[SurfaceDeclaration],
        constructors: Optional[dict[str, Type]],
    ) -> tuple[list[core.Declaration], TypeContext, dict[str, Type]]:
        """Run Phase 1 (scope checking) and Phase 2 (type elaboration).

        Uses TypeElaborator.elaborate_declarations() which internally
        calls ScopeChecker for the scope checking phase.

        Args:
            declarations: Surface declarations
            constructors: Optional constructor types

        Returns:
            Tuple of (core declarations, type context, global types)
        """
        try:
            return self.type_elaborator.elaborate_declarations(declarations, constructors)
        except (UndefinedVariableError, TypeError, UnificationError) as e:
            # Convert to ElaborationError and re-raise for outer handler
            self._errors.append(
                ElaborationError(
                    message=str(e),
                    location=getattr(e, "location", None),
                )
            )
            # Return empty results
            return [], TypeContext(), {}

    def _process_llm_pragmas(
        self,
        surface_decls: list[SurfaceDeclaration],
        core_decls: list[core.Declaration],
        global_types: dict[str, Type],
    ) -> tuple[list[core.Declaration], dict[str, LLMMetadata]]:
        """Run Phase 3: Process LLM pragmas.

        Args:
            surface_decls: Original surface declarations
            core_decls: Core declarations from Phase 2
            global_types: Global type signatures

        Returns:
            Tuple of (final declarations, LLM metadata dict)
        """
        final_decls: list[core.Declaration] = []
        llm_functions: dict[str, LLMMetadata] = {}

        # Build a map of declaration name to surface declaration
        surface_map: dict[str, SurfaceDeclaration] = {}
        for decl in surface_decls:
            if isinstance(decl, SurfaceTermDeclaration):
                surface_map[decl.name] = decl

        # Process each core declaration
        for core_decl in core_decls:
            if isinstance(core_decl, core.TermDeclaration):
                # Get corresponding surface declaration
                surface_decl = surface_map.get(core_decl.name)

                if surface_decl is not None:
                    # Process through LLM pass
                    result = self.llm_pass.process_declaration(
                        surface_decl, core_decl.type_annotation
                    )

                    final_decls.append(result.declaration)

                    if result.is_llm and result.metadata is not None:
                        llm_functions[result.metadata.function_name] = result.metadata
                else:
                    # No surface decl found, use as-is
                    final_decls.append(core_decl)
            else:
                # Non-term declarations pass through unchanged
                final_decls.append(core_decl)

        return final_decls, llm_functions

    def _collect_docstrings(
        self,
        declarations: list[SurfaceDeclaration],
    ) -> dict[str, str]:
        """Collect docstrings from surface declarations.

        Args:
            declarations: Surface declarations

        Returns:
            Dictionary mapping names to docstrings
        """
        docstrings: dict[str, str] = {}

        for decl in declarations:
            if isinstance(decl, SurfaceTermDeclaration):
                if decl.docstring:
                    docstrings[decl.name] = decl.docstring

        return docstrings

    def get_error_count(self) -> int:
        """Get the number of errors encountered.

        Returns:
            Count of errors
        """
        return len(self._errors)

    def get_warning_count(self) -> int:
        """Get the number of warnings generated.

        Returns:
            Count of warnings
        """
        return len(self._warnings)


def elaborate_module(
    declarations: list[SurfaceDeclaration],
    module_name: str = "main",
    constructors: Optional[dict[str, Type]] = None,
) -> Module:
    """Convenience function to elaborate declarations into a module.

    Args:
        declarations: List of surface declarations
        module_name: Name for the compiled module
        constructors: Optional data constructor types

    Returns:
        The compiled Module

    Example:
        >>> decls = [func1_decl, func2_decl]
        >>> module = elaborate_module(decls, module_name="main")
        >>>
        >>> if not module.errors:
        ...     print(f"Success: {len(module.declarations)} declarations")
    """
    pipeline = ElaborationPipeline(module_name=module_name)
    return pipeline.elaborate_module(declarations, constructors)
