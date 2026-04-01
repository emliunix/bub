"""Surface language: parser and elaborator for System F.

This module provides the surface language AST, parser, and the new multi-pass
elaboration pipeline for System F.
"""

# AST Types
from systemf.surface.types import (
    SurfaceAbs,
    SurfaceApp,
    SurfaceBranch,
    SurfaceCase,
    SurfaceConstructor,
    SurfaceConstructorInfo,
    SurfaceDataDeclaration,
    SurfaceDeclaration,
    SurfaceLet,
    SurfacePattern,
    SurfacePatternBase,
    SurfacePatternCons,
    SurfacePatternTuple,
    SurfaceTerm,
    SurfaceTermDeclaration,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceTypeArrow,
    SurfaceTypeConstructor,
    SurfaceTypeForall,
    SurfaceTypeVar,
    SurfaceVar,
    SurfaceAnn,
    SurfaceVarPattern,
)

# Lexer
from systemf.surface.parser import Lexer, lex, Token

# Pipeline
from systemf.surface.pipeline import (
    ElaborationPipeline,
    PipelineResult,
    elaborate_module,
)
from systemf.core.errors import ElaborationError

# Desugaring passes
from systemf.surface.desugar import (
    if_to_case_pass,
    operator_to_prim_pass,
    multi_arg_lambda_pass,
    multi_var_type_abs_pass,
    implicit_type_abs_pass,
    cons_pattern_pass,
    desugar_term,
    desugar_declaration,
)

# Scope checking passes
from systemf.surface.scoped import (
    scope_check_pass,
    ScopeContext,
    ScopeError,
    UndefinedVariableError,
    UndefinedTypeVariableError,
    DuplicateBindingError,
    ScopeDepthError,
    GlobalVariableError,
)

# Type inference passes
from systemf.surface.inference import (
    BidiInference,
    signature_collect_pass,
    data_decl_elab_pass,
    prepare_contexts_pass,
    elab_bodies_pass,
    build_decls_pass,
    TypeContext,
    TypeError,
    TypeMismatchError,
    InfiniteTypeError,
    UnificationError,
    KindError,
    UndefinedTypeError,
    TMeta,
    Substitution,
    unify,
    occurs_check,
    resolve_type,
    is_meta_variable,
    is_unresolved_meta,
)

# LLM pragma pass
from systemf.surface.llm import (
    llm_pragma_pass,
    LLMMetadata,
    LLMError,
)

__all__ = [
    # AST Types
    "SurfaceTerm",
    "SurfaceVar",
    "SurfaceAbs",
    "SurfaceApp",
    "SurfaceTypeAbs",
    "SurfaceTypeApp",
    "SurfaceLet",
    "SurfaceAnn",
    "SurfaceConstructor",
    "SurfaceCase",
    "SurfaceBranch",
    "SurfacePattern",
    "SurfacePatternBase",
    "SurfacePatternTuple",
    "SurfacePatternCons",
    "SurfaceVarPattern",
    "SurfaceDeclaration",
    "SurfaceDataDeclaration",
    "SurfaceTermDeclaration",
    "SurfaceConstructorInfo",
    "SurfaceTypeVar",
    "SurfaceTypeArrow",
    "SurfaceTypeForall",
    "SurfaceTypeConstructor",
    # Lexer
    "Lexer",
    "Token",
    "lex",
    # Pipeline
    "ElaborationPipeline",
    "PipelineResult",
    "elaborate_module",
    "ElaborationError",
    # Desugaring passes
    "if_to_case_pass",
    "operator_to_prim_pass",
    "multi_arg_lambda_pass",
    "multi_var_type_abs_pass",
    "implicit_type_abs_pass",
    "cons_pattern_pass",
    "desugar_term",
    "desugar_declaration",
    # Scope checking passes
    "scope_check_pass",
    "ScopeContext",
    "ScopeError",
    "UndefinedVariableError",
    "UndefinedTypeVariableError",
    "DuplicateBindingError",
    "ScopeDepthError",
    "GlobalVariableError",
    # Type inference passes
    "BidiInference",
    "signature_collect_pass",
    "data_decl_elab_pass",
    "prepare_contexts_pass",
    "elab_bodies_pass",
    "build_decls_pass",
    "TypeContext",
    "TypeError",
    "TypeMismatchError",
    "InfiniteTypeError",
    "UnificationError",
    "KindError",
    "UndefinedTypeError",
    "TMeta",
    "Substitution",
    "unify",
    "occurs_check",
    "resolve_type",
    "is_meta_variable",
    "is_unresolved_meta",
    # LLM pragma pass
    "llm_pragma_pass",
    "LLMMetadata",
    "LLMError",
]
