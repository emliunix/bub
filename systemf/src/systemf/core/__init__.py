"""Core language: AST, types, and type checker."""

from systemf.core.ast import (
    Abs,
    App,
    Branch,
    Case,
    Constructor,
    DataDeclaration,
    Declaration,
    Global,
    IntLit,
    Let,
    Pattern,
    PrimOp,
    TAbs,
    TApp,
    Term,
    TermDeclaration,
    Var,
)
from systemf.core.checker import TypeChecker
from systemf.core.context import Context
from systemf.core.errors import (
    OccursCheckError,
    TypeError,
    TypeMismatch,
    UndefinedConstructor,
    UndefinedVariable,
    UnificationError,
)
from systemf.core.types import (
    PrimitiveType,
    Type,
    TypeArrow,
    TypeConstructor,
    TypeForall,
    TypeVar,
)
from systemf.core.unify import Substitution, unify

__all__ = [
    # AST
    "Term",
    "Var",
    "Global",
    "Abs",
    "App",
    "TAbs",
    "TApp",
    "Constructor",
    "Case",
    "Branch",
    "Pattern",
    "Let",
    "IntLit",
    "PrimOp",
    "Declaration",
    "DataDeclaration",
    "TermDeclaration",
    # Types
    "Type",
    "TypeVar",
    "TypeArrow",
    "TypeForall",
    "TypeConstructor",
    "PrimitiveType",
    # Context
    "Context",
    # Unification
    "Substitution",
    "unify",
    # Errors
    "TypeError",
    "TypeMismatch",
    "UndefinedVariable",
    "UndefinedConstructor",
    "UnificationError",
    "OccursCheckError",
    # Type Checker
    "TypeChecker",
]
