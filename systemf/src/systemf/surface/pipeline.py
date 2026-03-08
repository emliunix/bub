"""Pipeline orchestrator for System F elaboration.

This module provides the main integration point for the 15-pass elaboration
pipeline organized into 4 phases:

Phase 0: Desugar (5 passes)
    1. if_to_case_pass - Transform if-then-else to case expressions
    2. operator_to_prim_pass - Transform operators to primitive applications
    3. multi_arg_lambda_pass - Convert multi-arg lambdas to nested single-arg
    4. multi_var_type_abs_pass - Convert multi-var type abs to nested single-var
    5. implicit_type_abs_pass - Insert implicit type abstractions for rank-1 poly

Phase 1: Scope (1 pass)
    6. scope_check_pass - Transform names to de Bruijn indices

Phase 2: Type (6 components)
    7. signature_collect_pass - Collect type signatures from declarations
    8. data_decl_elab_pass - Elaborate data type declarations
    9. prepare_contexts_pass - Prepare type contexts for body elaboration
    10. elab_bodies_pass - Elaborate term bodies using bidirectional inference
    11. build_decls_pass - Build core term declarations from elaborated bodies
    12. BidiInference - Utility class used by elab_bodies_pass

Phase 3: LLM (1 pass)
    13. llm_pragma_pass - Transform LLM functions and extract metadata

The orchestrator coordinates these passes with proper error handling using
Result types and match/case for explicit error propagation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from systemf.core import ast as core
from systemf.core.module import LLMMetadata, Module
from systemf.core.types import Type
from systemf.surface.desugar.if_to_case_pass import if_to_case_pass, DesugarError as IfDesugarError
from systemf.surface.desugar.operator_pass import (
    operator_to_prim_pass,
    DesugarError as OpDesugarError,
)
from systemf.surface.desugar.multi_arg_lambda_pass import (
    multi_arg_lambda_pass,
    DesugarError as LambdaDesugarError,
)
from systemf.surface.desugar.multi_var_type_abs_pass import (
    multi_var_type_abs_pass,
    DesugarError as TypeAbsDesugarError,
)
from systemf.surface.desugar.implicit_type_abs_pass import (
    implicit_type_abs_pass,
    DesugarError as ImplicitDesugarError,
)
from systemf.surface.scoped.scope_pass import scope_check_pass
from systemf.surface.scoped.context import ScopeContext
from systemf.surface.scoped.errors import ScopeError
from systemf.surface.inference.signature_collect_pass import signature_collect_pass
from systemf.surface.inference.data_decl_elab_pass import data_decl_elab_pass
from systemf.surface.inference.prepare_contexts_pass import prepare_contexts_pass
from systemf.surface.inference.elab_bodies_pass import elab_bodies_pass
from systemf.surface.inference.build_decls_pass import build_decls_pass
from systemf.surface.inference.bidi_inference import BidiInference
from systemf.surface.inference.context import TypeContext
from systemf.surface.inference.errors import TypeError
from systemf.surface.llm.pragma_pass import llm_pragma_pass, LLMError
from systemf.surface.result import Result, Ok, Err
from systemf.surface.types import (
    SurfaceDeclaration,
    SurfaceTermDeclaration,
    SurfaceDataDeclaration,
    SurfacePrimOpDecl,
)


@dataclass(frozen=True)
class PipelineError:
    """Error that occurs during pipeline execution.

    Wraps errors from individual passes with phase context.
    """

    phase: str
    message: str
    original_error: Exception | None = None

    def __str__(self) -> str:
        if self.original_error:
            return f"[{self.phase}] {self.message}: {self.original_error}"
        return f"[{self.phase}] {self.message}"


class ElaborationPipeline:
    """Main pipeline orchestrator for System F elaboration.

    Coordinates all 15 passes across 4 phases:
    - Phase 0: Desugar (5 passes)
    - Phase 1: Scope (1 pass)
    - Phase 2: Type (6 components)
    - Phase 3: LLM (1 pass)

    Each phase feeds into the next, with explicit error handling via
    Result types and match/case for error propagation.

    Attributes:
        module_name: Name of the module being compiled

    Example:
        >>> pipeline = ElaborationPipeline(module_name="main")
        >>> result = pipeline.run(declarations, scope_ctx, type_ctx)
        >>> match result:
        ...     case Ok(module):
        ...         print(f"Success: {len(module.declarations)} declarations")
        ...     case Err(error):
        ...         print(f"Error: {error}")
    """

    def __init__(self, module_name: str = "main"):
        self.module_name = module_name

    def run(
        self,
        declarations: list[SurfaceDeclaration],
        scope_ctx: ScopeContext,
        type_ctx: TypeContext,
        constructors: dict[str, Type] | None = None,
    ) -> Result[Module, PipelineError]:
        """Run the full 15-pass elaboration pipeline.

        Executes all phases in dependency order with explicit error handling:
        1. Phase 0: Desugar - Transform surface syntax to core forms
        2. Phase 1: Scope - Resolve names to de Bruijn indices
        3. Phase 2: Type - Infer and check types, elaborate to Core AST
        4. Phase 3: LLM - Process LLM pragma annotations

        Args:
            declarations: List of surface declarations to elaborate
            scope_ctx: Initial scope context for name resolution
            type_ctx: Initial type context for type checking
            constructors: Optional data constructor types from previous modules

        Returns:
            Result containing either the compiled Module or a PipelineError
        """
        # =====================================================================
        # Phase 0: Desugar (5 passes)
        # =====================================================================
        # Transform high-level surface syntax into simpler core forms:
        # - if-then-else → case expressions
        # - operators → primitive applications
        # - multi-arg lambdas → nested single-arg lambdas
        # - multi-var type abstractions → nested single-var
        # - Insert implicit type abstractions for rank-1 polymorphism

        desugared_decls_result = self._run_phase0_desugar(declarations)
        match desugared_decls_result:
            case Err(error):
                return Err(error)
            case Ok(desugared_decls):
                pass

        # =====================================================================
        # Phase 1: Scope
        # =====================================================================
        # Transform name-based variable references to de Bruijn indices.
        # This enables the type checker to work with index-based references
        # and supports mutual recursion by making all globals available.

        scoped_decls_result = self._run_phase1_scope(desugared_decls, scope_ctx)
        match scoped_decls_result:
            case Err(error):
                return Err(error)
            case Ok(scoped_decls):
                pass

        # =====================================================================
        # Phase 2: Type (6 steps)
        # =====================================================================
        # Elaborate scoped declarations to typed Core AST through 6 coordinated
        # steps that progressively build up type information and Core terms.

        type_result = self._run_phase2_type(scoped_decls, type_ctx, constructors)
        match type_result:
            case Err(error):
                return Err(error)
            case Ok((core_decls, final_ctx, all_constructors, global_types)):
                pass

        # =====================================================================
        # Phase 3: LLM
        # =====================================================================
        # Process LLM pragma annotations on function declarations.
        # Transforms LLM function bodies to PrimOp references and extracts
        # metadata (model config, docstrings, types) for runtime execution.

        llm_result = self._run_phase3_llm(core_decls, scoped_decls)
        match llm_result:
            case Err(error):
                return Err(error)
            case Ok((final_decls, llm_functions)):
                pass

        # =====================================================================
        # Build and return Module
        # =====================================================================
        # Collect all compilation artifacts into a Module structure containing:
        # - declarations: Core AST declarations (data and term)
        # - constructor_types: Data constructor signatures
        # - global_types: Top-level term signatures
        # - llm_functions: LLM metadata for runtime
        # - docstrings: Documentation from surface declarations

        docstrings = self._collect_docstrings(declarations)

        module = Module(
            name=self.module_name,
            declarations=final_decls,
            constructor_types=all_constructors,
            global_types=global_types,
            primitive_types={},
            docstrings=docstrings,
            llm_functions=llm_functions,
            errors=[],
            warnings=[],
        )

        return Ok(module)

    def _run_phase0_desugar(
        self, declarations: list[SurfaceDeclaration]
    ) -> Result[list[SurfaceDeclaration], PipelineError]:
        """Phase 0: Run all 5 desugaring passes on declarations.

        Passes run in order:
        1. if_to_case_pass - if-then-else → case
        2. operator_to_prim_pass - operators → primitives
        3. multi_arg_lambda_pass - multi-arg → nested single-arg
        4. multi_var_type_abs_pass - multi-var → nested single-var
        5. implicit_type_abs_pass - insert implicit Λ for rank-1 poly

        Each pass operates on term bodies within declarations.
        """
        desugared_decls: list[SurfaceDeclaration] = []

        for decl in declarations:
            match decl:
                case SurfaceTermDeclaration(body=body) if body is not None:
                    # Pass 1: if-then-else → case expressions
                    result = if_to_case_pass(body)
                    match result:
                        case Err(error):
                            return Err(
                                PipelineError(
                                    phase="Phase 0: Desugar",
                                    message=f"if_to_case_pass failed for '{decl.name}'",
                                    original_error=error,
                                )
                            )
                        case Ok(term):
                            body = term

                    # Pass 2: operators → primitive applications
                    result = operator_to_prim_pass(body)
                    match result:
                        case Err(error):
                            return Err(
                                PipelineError(
                                    phase="Phase 0: Desugar",
                                    message=f"operator_to_prim_pass failed for '{decl.name}'",
                                    original_error=error,
                                )
                            )
                        case Ok(term):
                            body = term

                    # Pass 3: multi-arg lambdas → nested single-arg
                    result = multi_arg_lambda_pass(body)
                    match result:
                        case Err(error):
                            return Err(
                                PipelineError(
                                    phase="Phase 0: Desugar",
                                    message=f"multi_arg_lambda_pass failed for '{decl.name}'",
                                    original_error=error,
                                )
                            )
                        case Ok(term):
                            body = term

                    # Pass 4: multi-var type abstractions → nested single-var
                    result = multi_var_type_abs_pass(body)
                    match result:
                        case Err(error):
                            return Err(
                                PipelineError(
                                    phase="Phase 0: Desugar",
                                    message=f"multi_var_type_abs_pass failed for '{decl.name}'",
                                    original_error=error,
                                )
                            )
                        case Ok(term):
                            body = term

                    # Build updated declaration with desugared body
                    desugared_decl = SurfaceTermDeclaration(
                        name=decl.name,
                        type_annotation=decl.type_annotation,
                        body=body,
                        location=decl.location,
                        docstring=decl.docstring,
                        pragma=decl.pragma,
                    )

                    # Pass 5: insert implicit type abstractions
                    result = implicit_type_abs_pass(desugared_decl)
                    match result:
                        case Err(error):
                            return Err(
                                PipelineError(
                                    phase="Phase 0: Desugar",
                                    message=f"implicit_type_abs_pass failed for '{decl.name}'",
                                    original_error=error,
                                )
                            )
                        case Ok(final_decl):
                            desugared_decls.append(final_decl)

                case _:
                    # Data declarations and primitives don't need desugaring
                    desugared_decls.append(decl)

        return Ok(desugared_decls)

    def _run_phase1_scope(
        self,
        declarations: list[SurfaceDeclaration],
        scope_ctx: ScopeContext,
    ) -> Result[list[SurfaceDeclaration], PipelineError]:
        """Phase 1: Scope checking - transform names to de Bruijn indices.

        Uses scope_check_pass to:
        1. Collect all global names from term declarations
        2. Add globals to context (enables mutual recursion)
        3. Transform each declaration's body to use de Bruijn indices
        """
        result = scope_check_pass(declarations, scope_ctx)
        match result:
            case Err(error):
                return Err(
                    PipelineError(
                        phase="Phase 1: Scope",
                        message="Scope checking failed",
                        original_error=error,
                    )
                )
            case Ok(scoped_decls):
                return Ok(scoped_decls)

    def _run_phase2_type(
        self,
        declarations: list[SurfaceDeclaration],
        type_ctx: TypeContext,
        constructors: dict[str, Type] | None,
    ) -> Result[
        tuple[
            list[core.Declaration],
            TypeContext,
            dict[str, Type],
            dict[str, Type],
        ],
        PipelineError,
    ]:
        """Phase 2: Type elaboration (6 steps).

        Step 1: signature_collect_pass
            - Collect type signatures from term and primitive declarations
            - Convert surface types to core types
            - Return: (global_types, term_decls, other_decls)

        Step 2: data_decl_elab_pass
            - Elaborate SurfaceDataDeclaration to core.DataDeclaration
            - Build constructor types (e.g., Just: forall a. a -> Maybe a)
            - Return: (data_decls, constructor_types)

        Step 3: prepare_contexts_pass
            - Add collected signatures to TypeContext.globals
            - Add constructor types to TypeContext.constructors
            - Return: prepared TypeContext ready for body elaboration

        Step 4: elab_bodies_pass
            - Elaborate each term body using BidiInference
            - Uses checking mode when signature available, inference otherwise
            - Return: list of (name, core_body, inferred_type) tuples

        Step 5: build_decls_pass
            - Build core.TermDeclaration from elaborated bodies
            - Preserve docstrings and pragmas from surface declarations
            - Return: list of core.TermDeclaration

        Step 6: Combine results
            - Merge data declarations and term declarations
            - Return final core declarations and type information
        """
        # Step 1: Collect type signatures
        sig_result = signature_collect_pass(declarations, constructors)
        match sig_result:
            case Err(error):
                return Err(
                    PipelineError(
                        phase="Phase 2: Type",
                        message="Signature collection failed",
                        original_error=error,
                    )
                )
            case Ok((global_types, term_decls, other_decls)):
                pass

        # Step 2: Elaborate data declarations
        # Filter for data declarations from other_decls
        data_decls_input = [
            (i, decl) for i, decl in other_decls if isinstance(decl, SurfaceDataDeclaration)
        ]

        data_result = data_decl_elab_pass(data_decls_input, type_ctx)
        match data_result:
            case Err(error):
                return Err(
                    PipelineError(
                        phase="Phase 2: Type",
                        message="Data declaration elaboration failed",
                        original_error=error,
                    )
                )
            case Ok((data_decls, data_constructor_types)):
                pass

        # Merge constructor types: input + newly defined
        all_constructors = (constructors or {}) | data_constructor_types

        # Step 3: Prepare type contexts
        ctx_result = prepare_contexts_pass(global_types, all_constructors, type_ctx)
        match ctx_result:
            case Err(error):
                return Err(
                    PipelineError(
                        phase="Phase 2: Type",
                        message="Context preparation failed",
                        original_error=error,
                    )
                )
            case Ok(prepared_ctx):
                pass

        # Step 4: Elaborate term bodies
        bodies_result = elab_bodies_pass(term_decls, prepared_ctx, global_types)
        match bodies_result:
            case Err(error):
                return Err(
                    PipelineError(
                        phase="Phase 2: Type",
                        message="Body elaboration failed",
                        original_error=error,
                    )
                )
            case Ok(elaborated_bodies):
                pass

        # Step 5: Build core term declarations
        # Build pragma map from surface declarations
        pragma_map: dict[str, str | None] = {}
        for decl in term_decls:
            if decl.pragma:
                pragma_map[decl.name] = decl.pragma.get("LLM")
            else:
                pragma_map[decl.name] = None

        build_result = build_decls_pass(elaborated_bodies, term_decls, pragma_map)
        match build_result:
            case Err(error):
                return Err(
                    PipelineError(
                        phase="Phase 2: Type",
                        message="Building declarations failed",
                        original_error=error,
                    )
                )
            case Ok(term_core_decls):
                pass

        # Step 6: Combine all core declarations
        # Data declarations first, then term declarations
        all_core_decls: list[core.Declaration] = list(data_decls) + list(term_core_decls)

        return Ok((all_core_decls, prepared_ctx, all_constructors, global_types))

    def _run_phase3_llm(
        self,
        core_decls: list[core.Declaration],
        surface_decls: list[SurfaceDeclaration],
    ) -> Result[tuple[list[core.Declaration], dict[str, LLMMetadata]], PipelineError]:
        """Phase 3: LLM pragma processing.

        Transforms LLM function declarations:
        - Identifies declarations with LLM pragma
        - Replaces body with PrimOp("llm.{name}")
        - Extracts LLMMetadata for runtime
        """
        result = llm_pragma_pass(core_decls)
        match result:
            case Err(error):
                return Err(
                    PipelineError(
                        phase="Phase 3: LLM",
                        message="LLM pragma processing failed",
                        original_error=error,
                    )
                )
            case Ok((final_decls, llm_functions)):
                return Ok((final_decls, llm_functions))

    def _collect_docstrings(
        self,
        declarations: list[SurfaceDeclaration],
    ) -> dict[str, str]:
        """Collect docstrings from surface declarations.

        Args:
            declarations: Surface declarations

        Returns:
            Dictionary mapping declaration names to docstrings
        """
        docstrings: dict[str, str] = {}

        for decl in declarations:
            match decl:
                case SurfaceTermDeclaration(name=name, docstring=doc) if doc:
                    docstrings[name] = doc
                case SurfaceDataDeclaration(name=name, docstring=doc) if doc:
                    docstrings[name] = doc
                case SurfacePrimOpDecl(name=name, docstring=doc) if doc:
                    docstrings[name] = doc

        return docstrings


def run_pipeline(
    declarations: list[SurfaceDeclaration],
    module_name: str = "main",
    scope_ctx: ScopeContext | None = None,
    type_ctx: TypeContext | None = None,
    constructors: dict[str, Type] | None = None,
) -> Result[Module, PipelineError]:
    """Convenience function to run the full elaboration pipeline.

    Args:
        declarations: List of surface declarations to elaborate
        module_name: Name for the compiled module
        scope_ctx: Optional initial scope context (creates empty if None)
        type_ctx: Optional initial type context (creates empty if None)
        constructors: Optional data constructor types

    Returns:
        Result containing either the compiled Module or a PipelineError

    Example:
        >>> decls = [func_decl, data_decl]
        >>> result = run_pipeline(decls, module_name="main")
        >>> match result:
        ...     case Ok(module):
        ...         print(f"Compiled {len(module.declarations)} declarations")
        ...     case Err(error):
        ...         print(f"Failed: {error}")
    """
    pipeline = ElaborationPipeline(module_name=module_name)

    if scope_ctx is None:
        scope_ctx = ScopeContext()

    if type_ctx is None:
        type_ctx = TypeContext()

    return pipeline.run(declarations, scope_ctx, type_ctx, constructors)


@dataclass(frozen=True)
class PipelineResult:
    """Result of running the elaboration pipeline.

    Attributes:
        module: The compiled module (may contain errors in module.errors)
        success: Whether the pipeline completed without errors
        errors: List of errors encountered during elaboration
    """

    module: Module
    success: bool
    errors: list[PipelineError]


def elaborate_module(
    declarations: list[SurfaceDeclaration],
    module_name: str = "main",
    constructors: dict[str, Type] | None = None,
) -> PipelineResult:
    """Convenience function to elaborate declarations into a module.

    This is a simplified interface that returns a PipelineResult directly
    instead of a Result type. Check result.success to see if elaboration
    succeeded, and result.module.errors for any elaboration errors.

    Args:
        declarations: List of surface declarations to elaborate
        module_name: Name for the compiled module
        constructors: Optional data constructor types from previous modules

    Returns:
        PipelineResult containing the compiled module and status

    Example:
        >>> decls = [func_decl, data_decl]
        >>> result = elaborate_module(decls, module_name="main")
        >>>
        >>> if result.success:
        ...     print(f"Compiled {len(result.module.declarations)} declarations")
        ... else:
        ...     for error in result.errors:
        ...         print(f"Error: {error}")
    """
    pipeline = ElaborationPipeline(module_name=module_name)
    scope_ctx = ScopeContext()
    type_ctx = TypeContext()

    run_result = pipeline.run(declarations, scope_ctx, type_ctx, constructors)

    match run_result:
        case Ok(module):
            return PipelineResult(
                module=module,
                success=len(module.errors) == 0,
                errors=[],
            )
        case Err(error):
            # Create an empty module with the error
            empty_module = Module(
                name=module_name,
                declarations=[],
                constructor_types=constructors or {},
                global_types={},
                primitive_types={},
                docstrings={},
                llm_functions={},
                errors=[],
                warnings=[],
            )
            return PipelineResult(
                module=empty_module,
                success=False,
                errors=[error],
            )
