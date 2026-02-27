"""Surface language: parser and elaborator for System F."""

from systemf.surface.ast import (
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
from systemf.surface.elaborator import (
    Elaborator,
    UndefinedTypeVariable,
    UndefinedVariable,
    elaborate,
    elaborate_term,
)
from systemf.surface.lexer import Lexer, lex
from systemf.surface.types import Token
from systemf.surface.parser import (
    ParseError,
    Parser,
    parse_program,
    parse_term,
)

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
    # Parser
    "Parser",
    "ParseError",
    "parse_term",
    "parse_program",
    # Elaborator
    "Elaborator",
    "ElaborationError",
    "UndefinedVariable",
    "UndefinedTypeVariable",
    "elaborate",
    "elaborate_term",
    # Desugarer
    "Desugarer",
    "LetToLambdaDesugarer",
    "desugar",
    "desugar_lets",
]
