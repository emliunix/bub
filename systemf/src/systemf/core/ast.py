"""Core language AST for System F."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from systemf.core.types import Type


class Term:
    """Base class for terms."""

    pass


@dataclass(frozen=True)
class Var(Term):
    """Variable reference using de Bruijn index.

    Index 0 refers to the nearest binder, 1 to the next, etc.
    Example: λx.λy.x  =>  Abs(_, Abs(_, Var(1)))
    """

    index: int

    def __str__(self) -> str:
        return f"x{self.index}"


@dataclass(frozen=True)
class Global(Term):
    """Global variable reference by name.

    Used in REPL for references to previously defined terms.
    Resolved to actual values by the evaluator.
    """

    name: str

    def __str__(self) -> str:
        return f"@{self.name}"


@dataclass(frozen=True)
class Abs(Term):
    """Lambda abstraction: λ(x:σ).t

    var_type is the type annotation for the bound variable.
    """

    var_type: Type
    body: Term

    def __str__(self) -> str:
        return f"λ(_:{self.var_type}).{self.body}"


@dataclass(frozen=True)
class App(Term):
    """Function application: f arg."""

    func: Term
    arg: Term

    def __str__(self) -> str:
        return f"({self.func} {self.arg})"


@dataclass(frozen=True)
class TAbs(Term):
    """Type abstraction: Λα.t"""

    var: str
    body: Term

    def __str__(self) -> str:
        return f"Λ{self.var}.{self.body}"


@dataclass(frozen=True)
class TApp(Term):
    """Type application: t[τ]."""

    func: Term
    type_arg: Type

    def __str__(self) -> str:
        return f"({self.func}[{self.type_arg}])"


@dataclass(frozen=True)
class Pattern:
    """Pattern in a case branch: Constructor name + bound variables."""

    constructor: str
    vars: list[str]  # Variable names for pattern binding

    def __str__(self) -> str:
        if self.vars:
            return f"{self.constructor} {' '.join(self.vars)}"
        return self.constructor


@dataclass(frozen=True)
class Branch:
    """Case branch: pattern -> body."""

    pattern: Pattern
    body: Term

    def __str__(self) -> str:
        return f"{self.pattern} -> {self.body}"


@dataclass(frozen=True)
class Constructor(Term):
    """Data constructor application: C t₁...tₙ."""

    name: str
    args: list[Term]

    def __str__(self) -> str:
        if not self.args:
            return self.name
        args_str = " ".join(str(arg) for arg in self.args)
        return f"({self.name} {args_str})"


@dataclass(frozen=True)
class Case(Term):
    """Pattern matching: case scrutinee of branches."""

    scrutinee: Term
    branches: list[Branch]

    def __str__(self) -> str:
        branches_str = " | ".join(str(branch) for branch in self.branches)
        return f"case {self.scrutinee} of {branches_str}"


@dataclass(frozen=True)
class Let(Term):
    """Let binding: let name = value in body.

    Note: 'name' is for debugging only (de Bruijn index 0 in body).
    """

    name: str
    value: Term
    body: Term

    def __str__(self) -> str:
        return f"let {self.name} = {self.value} in {self.body}"


@dataclass(frozen=True)
class IntLit(Term):
    """Integer literal: 42

    Created directly by the parser from NUMBER tokens.
    Type checker looks up the Int type from prelude-populated registry.
    """

    value: int

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class StringLit(Term):
    """String literal: "hello"

    Created directly by the parser from STRING tokens.
    Type checker looks up the String type from prelude-populated registry.
    """

    value: str

    def __str__(self) -> str:
        return f'"{self.value}"'


@dataclass(frozen=True)
class PrimOp(Term):
    """Primitive operation: $prim.xxx

    Elaborator converts $prim.xxx names to PrimOp.
    The name is stored without the $prim. prefix.
    Arguments are handled via App wrapping (consistent with functions).

    Example: $prim.int_plus becomes PrimOp("int_plus")
    Usage: App(App(PrimOp("int_plus"), IntLit(1)), IntLit(2))
    """

    name: str

    def __str__(self) -> str:
        return f"$prim.{self.name}"


@dataclass(frozen=True)
class ToolCall(Term):
    """Tool invocation for FFI operations.

    Represents a call to an external tool (like LLM APIs, file operations).
    The tool is resolved by name at runtime from the tool registry.
    """

    tool_name: str
    args: list[Term]

    def __str__(self) -> str:
        if not self.args:
            return f"@{self.tool_name}"
        args_str = " ".join(str(arg) for arg in self.args)
        return f"(@{self.tool_name} {args_str})"


@dataclass(frozen=True)
class DataDeclaration:
    """data T a = K₁ τ₁ | ... | Kₙ τₙ"""

    name: str  # Type constructor name
    params: list[str]  # Type parameters
    constructors: list[tuple[str, list[Type]]]  # (name, arg_types)


@dataclass(frozen=True)
class TermDeclaration:
    """x : τ = e

    Additional fields for LLM function support:
    - pragma: Raw pragma parameters (e.g., "model=gpt-4 temperature=0.7")
    - docstring: Function-level docstring (-- | style)
    - param_docstrings: Parameter docstrings (-- ^ style)
    """

    name: str
    type_annotation: Optional[Type]
    body: Term
    pragma: Optional[str] = None
    docstring: Optional[str] = None
    param_docstrings: Optional[list[str]] = None


Declaration = DataDeclaration | TermDeclaration


# Export the term union for type checking
TermRepr = Union[
    Var, Abs, App, TAbs, TApp, Constructor, Case, Let, ToolCall, IntLit, StringLit, PrimOp
]
