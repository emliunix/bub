"""Core language: AST, types, and type checker."""

from systemf.core.ast import (
    Abs,
    App,
    Branch,
    Case,
    Constructor,
    DataDeclaration,
    Declaration,
    Let,
    Pattern,
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
    "Abs",
    "App",
    "TAbs",
    "TApp",
    "Constructor",
    "Case",
    "Branch",
    "Pattern",
    "Let",
    "Declaration",
    "DataDeclaration",
    "TermDeclaration",
    # Types
    "Type",
    "TypeVar",
    "TypeArrow",
    "TypeForall",
    "TypeConstructor",
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
