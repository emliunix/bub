"""Surface language: parser and elaborator for System F.

This module provides the surface language AST, parser, and the new multi-pass
elaboration pipeline for System F.
"""

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
)
from systemf.surface.desugar import (
    Desugarer,
    LetToLambdaDesugarer,
    desugar,
    desugar_lets,
)
from systemf.core.errors import ElaborationError
from systemf.surface.pipeline import (
    ElaborationPipeline,
    PipelineResult,
    elaborate_module,
)
from systemf.surface.parser import Lexer, lex, Token

__all__ = [
    # AST
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
    "SurfaceDeclaration",
    "SurfaceDataDeclaration",
    "SurfaceTermDeclaration",
    "SurfaceConstructorInfo",
    # Types
    "SurfaceTypeVar",
    "SurfaceTypeArrow",
    "SurfaceTypeForall",
    "SurfaceTypeConstructor",
    # Lexer
    "Lexer",
    "Token",
    "lex",
    # Pipeline (new multi-pass elaborator)
    "ElaborationPipeline",
    "PipelineResult",
    "elaborate_module",
    "ElaborationError",
    # Desugarer
    "Desugarer",
    "LetToLambdaDesugarer",
    "desugar",
    "desugar_lets",
]
