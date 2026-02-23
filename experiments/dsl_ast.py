#!/usr/bin/env python3
"""
Workflow DSL - Shared AST Definitions

This module defines the canonical AST structure for the workflow DSL.
All parser implementations must produce ASTs that match these definitions.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Union, Any
from enum import Enum, auto


# =============================================================================
# Types
# =============================================================================


@dataclass(frozen=True)
class Type:
    """Type annotation in the DSL."""

    name: str

    def __eq__(self, other):
        if isinstance(other, str):
            return self.name == other
        return isinstance(other, Type) and self.name == other.name


# Primitive types
INT = Type("int")
FLOAT = Type("float")
STR = Type("str")
BOOL = Type("bool")
VOID = Type("void")


# =============================================================================
# Literals
# =============================================================================


@dataclass(frozen=True)
class IntegerLiteral:
    value: int


@dataclass(frozen=True)
class FloatLiteral:
    value: float


@dataclass(frozen=True)
class StringLiteral:
    value: str


@dataclass(frozen=True)
class BoolLiteral:
    value: bool


Literal = Union[IntegerLiteral, FloatLiteral, StringLiteral, BoolLiteral]


# =============================================================================
# Expressions
# =============================================================================


@dataclass(frozen=True)
class Identifier:
    """Variable or function reference."""

    name: str


@dataclass(frozen=True)
class LLMCall:
    """Builtin LLM call expression."""

    prompt: str
    context: Optional[Any] = None  # Expression or None


Expression = Union[Identifier, Literal, LLMCall]


# =============================================================================
# Statements
# =============================================================================


@dataclass(frozen=True)
class LetBinding:
    """Variable binding: let name :: Type = expression"""

    name: str
    type_: Type
    value: Expression


@dataclass(frozen=True)
class ReturnStmt:
    """Return statement: return expression"""

    value: Expression


@dataclass(frozen=True)
class ExprStmt:
    """Expression used as statement."""

    expr: Expression


Statement = Union[LetBinding, ReturnStmt, ExprStmt]


# =============================================================================
# Function Definition
# =============================================================================


@dataclass(frozen=True)
class TypedParam:
    """Function parameter with type annotation."""

    name: str
    type_: Type


@dataclass(frozen=True)
class FunctionDef:
    """Function definition."""

    name: str
    params: List[TypedParam]
    return_type: Optional[Type]
    doc: Optional[str]
    body: List[Statement]


# =============================================================================
# Program
# =============================================================================


@dataclass(frozen=True)
class Program:
    """Root of the AST - contains all function definitions."""

    functions: List[FunctionDef]


# =============================================================================
# AST Serialization
# =============================================================================


def ast_to_dict(node: Any) -> Any:
    """Convert AST node to dictionary for serialization/comparison."""
    if node is None:
        return None
    elif isinstance(node, (str, int, float, bool)):
        return node
    elif isinstance(node, list):
        return [ast_to_dict(item) for item in node]
    elif hasattr(node, "__dataclass_fields__"):
        result = {"_type": node.__class__.__name__}
        for field_name in node.__dataclass_fields__:
            value = getattr(node, field_name)
            result[field_name] = ast_to_dict(value)
        return result
    else:
        return str(node)


def pprint_ast(node: Any) -> str:
    """Pretty print AST as JSON-like structure."""
    import json

    return json.dumps(ast_to_dict(node), indent=2)
