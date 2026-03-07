"""Core language AST for System F."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from systemf.core.types import Type, TypeVar
from systemf.core.coercion import Coercion, CoercionRefl
from systemf.utils.location import Location


@dataclass(frozen=True)
class Term:
    """Base class for terms with source location information."""

    source_loc: Optional[Location] = None
    """Source location where this term originated. Used for error reporting."""


@dataclass(frozen=True)
class Var(Term):
    """Variable reference using de Bruijn index with original name for debugging.

    Index 0 refers to the nearest binder, 1 to the next, etc.
    The debug_name preserves the original variable name for error messages and display.
    Example: λx.λy.x  =>  Abs("x", _, Abs("y", _, Var(None, 1, "x"), None), None)
    """

    index: int = 0
    debug_name: str = ""  # Original name for error reporting and display
    # source_loc inherited from Term

    def __str__(self) -> str:
        if self.debug_name:
            return self.debug_name
        return f"x{self.index}"


@dataclass(frozen=True)
class Global(Term):
    """Global variable reference by name.

    Used in REPL for references to previously defined terms.
    Resolved to actual values by the evaluator.
    """

    name: str = ""
    # source_loc inherited from Term

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Abs(Term):
    """Lambda abstraction: λ(x:σ).t with original parameter name.

    var_type is the type annotation for the bound variable.
    var_name preserves the original parameter name for error reporting.
    """

    var_name: str = ""  # Original parameter name
    var_type: Type = field(default_factory=lambda: TypeVar("_"))
    body: Term = field(default_factory=lambda: Var())
    # source_loc inherited from Term

    def __str__(self) -> str:
        name = self.var_name if self.var_name else "_"
        return f"λ({name}:{self.var_type}).{self.body}"


@dataclass(frozen=True)
class App(Term):
    """Function application: f arg."""

    func: Term = field(default_factory=lambda: Var())
    arg: Term = field(default_factory=lambda: Var())
    # source_loc inherited from Term

    def __str__(self) -> str:
        return f"({self.func} {self.arg})"


@dataclass(frozen=True)
class TAbs(Term):
    """Type abstraction: Λα.t"""

    var: str = ""
    body: Term = field(default_factory=lambda: Var())
    # source_loc inherited from Term

    def __str__(self) -> str:
        return f"Λ{self.var}.{self.body}"


@dataclass(frozen=True)
class TApp(Term):
    """Type application: t[τ]."""

    func: Term = field(default_factory=lambda: Var())
    type_arg: Type = field(default_factory=lambda: TypeVar("_"))
    # source_loc inherited from Term

    def __str__(self) -> str:
        return f"({self.func}[{self.type_arg}])"


@dataclass(frozen=True)
class Pattern:
    """Pattern in a case branch: Constructor name + bound variables."""

    constructor: str = ""
    vars: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.vars:
            return f"{self.constructor} {' '.join(self.vars)}"
        return self.constructor


@dataclass(frozen=True)
class Branch:
    """Case branch: pattern -> body."""

    pattern: Pattern = field(default_factory=Pattern)
    body: Term = field(default_factory=lambda: Var())

    def __str__(self) -> str:
        return f"{self.pattern} -> {self.body}"


@dataclass(frozen=True)
class Constructor(Term):
    """Data constructor application: C t₁...tₙ."""

    name: str = ""
    args: list[Term] = field(default_factory=list)
    # source_loc inherited from Term

    def __str__(self) -> str:
        if not self.args:
            return self.name
        args_str = " ".join(str(arg) for arg in self.args)
        return f"({self.name} {args_str})"


@dataclass(frozen=True)
class Case(Term):
    """Pattern matching: case scrutinee of branches."""

    scrutinee: Term = field(default_factory=lambda: Var())
    branches: list[Branch] = field(default_factory=list)
    # source_loc inherited from Term

    def __str__(self) -> str:
        branches_str = " | ".join(str(branch) for branch in self.branches)
        return f"case {self.scrutinee} of {branches_str}"


@dataclass(frozen=True)
class Let(Term):
    """Let binding: let name = value in body.

    Note: 'name' is for debugging only (de Bruijn index 0 in body).
    """

    name: str = ""
    value: Term = field(default_factory=lambda: Var())
    body: Term = field(default_factory=lambda: Var())
    # source_loc inherited from Term

    def __str__(self) -> str:
        return f"let {self.name} = {self.value} in {self.body}"


@dataclass(frozen=True)
class Lit(Term):
    """Primitive literal: Int, String, Float, etc.

    Unified representation for all primitive literals.
    The prim_type field indicates the primitive type.

    Attributes:
        prim_type: The primitive type name ("Int", "String", "Float", etc.)
        value: The literal value
    """

    prim_type: str = ""
    value: object = None

    def __str__(self) -> str:
        if self.prim_type == "String":
            return f'"{self.value}"'
        return str(self.value)


@dataclass(frozen=True)
class PrimOp(Term):
    """Primitive operation: $prim.xxx

    Elaborator converts $prim.xxx names to PrimOp.
    The name is stored without the $prim. prefix.
    Arguments are handled via App wrapping (consistent with functions).

    Example: $prim.int_plus becomes PrimOp("int_plus")
    Usage: App(App(PrimOp("int_plus"), IntLit(1)), IntLit(2))
    """

    name: str = ""
    # source_loc inherited from Term

    def __str__(self) -> str:
        return f"$prim.{self.name}"


@dataclass(frozen=True)
class ToolCall(Term):
    """Tool invocation for FFI operations.

    Represents a call to an external tool (like LLM APIs, file operations).
    The tool is resolved by name at runtime from the tool registry.
    """

    tool_name: str = ""
    args: list[Term] = field(default_factory=list)
    # source_loc inherited from Term

    def __str__(self) -> str:
        if not self.args:
            return f"@{self.tool_name}"
        args_str = " ".join(str(arg) for arg in self.args)
        return f"(@{self.tool_name} {args_str})"


@dataclass(frozen=True)
class Cast(Term):
    """Type cast using coercion: expr ▷ γ

    System FC extends System F with explicit type casts using coercions.
    A cast (expr ▷ γ) converts expr from type τ₁ to type τ₂ where γ : τ₁ ~ τ₂.

    The coercion γ is a proof that the two types are equal, witnessed by
    the coercion system. Casts are zero-cost (erased at runtime).

    Example:
        x : Int, ax : Int ~ Nat ⊢ (x ▷ ax) : Nat
    """

    expr: Term = field(default_factory=lambda: Var())
    coercion: Coercion = field(default_factory=lambda: CoercionRefl(TypeVar("_")))
    # source_loc inherited from Term

    def __str__(self) -> str:
        return f"({self.expr} ▷ {self.coercion})"


@dataclass(frozen=True)
class Axiom(Term):
    """Axiom term for introducing coercion proofs: axiom[name] @ [τ₁, ..., τₙ]

    Axiom terms introduce named coercion axioms with type arguments.
    They are used during elaboration to convert between abstract and
    representation types for ADTs.

    The name identifies the axiom (e.g., "ax_Nat"), and args provide
    type arguments for polymorphic axioms.

    Example:
        axiom[ax_Nat] @ [] : Nat ~ Repr(Nat)
        axiom[ax_List] @ [Int] : List Int ~ Repr(List Int)
    """

    name: str = ""
    args: list[Type] = field(default_factory=list)
    # source_loc inherited from Term

    def __str__(self) -> str:
        if not self.args:
            return f"axiom[{self.name}]"
        args_str = ", ".join(str(arg) for arg in self.args)
        return f"axiom[{self.name}] @ [{args_str}]"


@dataclass(frozen=True)
class DataDeclaration:
    """data T a = K₁ τ₁ | ... | Kₙ τₙ"""

    name: str = ""  # Type constructor name
    params: list[str] = field(default_factory=list)  # Type parameters
    constructors: list[tuple[str, list[Type]]] = field(default_factory=list)  # (name, arg_types)


@dataclass(frozen=True)
class TermDeclaration:
    """x : τ = e

    Core term declaration after elaboration. The Core AST is clean and
    focused on semantics.

    LLM functions are identified by pragma field containing configuration
    parameters (e.g., "model=gpt-4 temperature=0.7"). The body is replaced
    with a PrimOp("llm.{name}") during elaboration.

    Docstrings and param_docstrings are stored here for LLM metadata extraction.
    """

    name: str = ""
    type_annotation: Optional[Type] = None
    body: Term = field(default_factory=lambda: Var())
    pragma: Optional[str] = None
    docstring: Optional[str] = None
    param_docstrings: Optional[list[str]] = None


Declaration = DataDeclaration | TermDeclaration


# Export the term union for type checking
TermRepr = Union[
    Var, Abs, App, TAbs, TApp, Constructor, Case, Let, ToolCall, Lit, PrimOp, Cast, Axiom
]
