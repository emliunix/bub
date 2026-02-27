"""Surface language AST for System F.

Surface syntax uses name-based binding (not de Bruijn indices) and allows
omitting type annotations where they can be inferred.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from systemf.utils.location import Location


# =============================================================================
# Surface Types
# =============================================================================


class SurfaceType:
    """Base class for surface types."""

    pass


@dataclass(frozen=True)
class SurfaceTypeVar(SurfaceType):
    """Type variable: a."""

    name: str
    location: Location

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class SurfaceTypeArrow(SurfaceType):
    """Function type: arg -> ret."""

    arg: SurfaceType
    ret: SurfaceType
    location: Location

    def __str__(self) -> str:
        match self.arg:
            case SurfaceTypeArrow():
                arg_str = f"({self.arg})"
            case _:
                arg_str = str(self.arg)
        return f"{arg_str} -> {self.ret}"


@dataclass(frozen=True)
class SurfaceTypeForall(SurfaceType):
    """Polymorphic type: forall a. body."""

    var: str
    body: SurfaceType
    location: Location

    def __str__(self) -> str:
        return f"forall {self.var}. {self.body}"


@dataclass(frozen=True)
class SurfaceTypeConstructor(SurfaceType):
    """Data type constructor: T t1 ... tn."""

    name: str
    args: list[SurfaceType]
    location: Location

    def __str__(self) -> str:
        if not self.args:
            return self.name
        args_strs = []
        for arg in self.args:
            match arg:
                case SurfaceTypeArrow() | SurfaceTypeForall():
                    args_strs.append(f"({arg})")
                case _:
                    args_strs.append(str(arg))
        args_str = " ".join(args_strs)
        return f"{self.name} {args_str}"


SurfaceTypeRepr = Union[SurfaceTypeVar, SurfaceTypeArrow, SurfaceTypeForall, SurfaceTypeConstructor]


# =============================================================================
# Surface Terms
# =============================================================================


class SurfaceTerm:
    """Base class for surface terms."""

    pass


@dataclass(frozen=True)
class SurfaceVar(SurfaceTerm):
    """Variable reference by name: x."""

    name: str
    location: Location

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class SurfaceAbs(SurfaceTerm):
    """Lambda abstraction: \\x -> body or \\x:T -> body.

    Supports Haddock-style parameter docstrings: \\x -- ^ docstring -> body
    """

    var: str
    var_type: Optional[SurfaceType]
    body: SurfaceTerm
    location: Location
    param_docstrings: list[str | None] = field(
        default_factory=list
    )  # Docstrings for each parameter

    def __str__(self) -> str:
        if self.var_type:
            return f"\\{self.var}:{self.var_type} -> {self.body}"
        return f"\\{self.var} -> {self.body}"


@dataclass(frozen=True)
class SurfaceApp(SurfaceTerm):
    """Function application: f arg."""

    func: SurfaceTerm
    arg: SurfaceTerm
    location: Location

    def __str__(self) -> str:
        return f"({self.func} {self.arg})"


@dataclass(frozen=True)
class SurfaceTypeAbs(SurfaceTerm):
    """Type abstraction: /\\a. body (written as /\\a. or Λa.)."""

    var: str
    body: SurfaceTerm
    location: Location

    def __str__(self) -> str:
        return f"/\\{self.var}. {self.body}"


@dataclass(frozen=True)
class SurfaceTypeApp(SurfaceTerm):
    """Type application: func @type or func [type]."""

    func: SurfaceTerm
    type_arg: SurfaceType
    location: Location

    def __str__(self) -> str:
        return f"({self.func} @{self.type_arg})"


@dataclass(frozen=True)
class SurfaceLet(SurfaceTerm):
    """Let binding: let name = value in body."""

    name: str
    value: SurfaceTerm
    body: SurfaceTerm
    location: Location

    def __str__(self) -> str:
        return f"let {self.name} = {self.value} in {self.body}"


@dataclass(frozen=True)
class SurfaceAnn(SurfaceTerm):
    """Type annotation: term : type."""

    term: SurfaceTerm
    type: SurfaceType
    location: Location

    def __str__(self) -> str:
        return f"({self.term} : {self.type})"


@dataclass(frozen=True)
class SurfaceConstructor(SurfaceTerm):
    """Data constructor application: Con args."""

    name: str
    args: list[SurfaceTerm]
    location: Location

    def __str__(self) -> str:
        if not self.args:
            return self.name
        args_str = " ".join(str(arg) for arg in self.args)
        return f"({self.name} {args_str})"


@dataclass(frozen=True)
class SurfaceIntLit(SurfaceTerm):
    """Integer literal: 42, -7, etc."""

    value: int
    location: Location

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class SurfaceStringLit(SurfaceTerm):
    """String literal: "hello", "world", etc."""

    value: str
    location: Location

    def __str__(self) -> str:
        return f'"{self.value}"'


@dataclass(frozen=True)
class SurfaceOp(SurfaceTerm):
    """Infix operator expression: left op right.

    This is a surface syntax construct that gets desugared to a primitive
    operation application. Operators include +, -, *, /, ==, <, >, <=, >=.
    """

    left: SurfaceTerm
    op: str  # The operator symbol: '+', '-', '*', '/', '==', '<', '>', '<=', '>='
    right: SurfaceTerm
    location: Location

    def __str__(self) -> str:
        return f"({self.left} {self.op} {self.right})"


@dataclass(frozen=True)
class SurfacePattern:
    """Pattern in a case branch: Con vars."""

    constructor: str
    vars: list[str]
    location: Location

    def __str__(self) -> str:
        if self.vars:
            return f"{self.constructor} {' '.join(self.vars)}"
        return self.constructor


@dataclass(frozen=True)
class SurfaceBranch:
    """Case branch: pattern -> body."""

    pattern: SurfacePattern
    body: SurfaceTerm
    location: Location

    def __str__(self) -> str:
        return f"{self.pattern} -> {self.body}"


@dataclass(frozen=True)
class SurfaceCase(SurfaceTerm):
    """Pattern matching: case scrutinee of branches."""

    scrutinee: SurfaceTerm
    branches: list[SurfaceBranch]
    location: Location

    def __str__(self) -> str:
        branches_str = " | ".join(str(branch) for branch in self.branches)
        return f"case {self.scrutinee} of {{ {branches_str} }}"


@dataclass(frozen=True)
class SurfaceToolCall(SurfaceTerm):
    """Tool invocation: @tool_name arg1 arg2 ...

    Tool calls allow SystemF code to invoke external operations.
    The tool name is resolved at runtime from the tool registry.
    """

    tool_name: str
    args: list[SurfaceTerm]
    location: Location

    def __str__(self) -> str:
        if not self.args:
            return f"@{self.tool_name}"
        args_str = " ".join(str(arg) for arg in self.args)
        return f"(@{self.tool_name} {args_str})"


SurfaceTermRepr = Union[
    SurfaceVar,
    SurfaceAbs,
    SurfaceApp,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceLet,
    SurfaceAnn,
    SurfaceConstructor,
    SurfaceCase,
    SurfaceToolCall,
    SurfaceIntLit,
    SurfaceStringLit,
    SurfaceOp,
]


# =============================================================================
# Surface Pragmas
# =============================================================================


@dataclass(frozen=True)
class SurfacePragma:
    """Pragma annotation: {-# LLM raw_content #-}.

    Simplified storage - just keeps the raw string after the directive.
    Key=value parsing happens in later passes if needed.
    """

    directive: str  # e.g., "LLM"
    raw_content: str  # Raw string content after directive (e.g., "model=gpt-4 temperature=0.7")
    location: Location

    def __str__(self) -> str:
        return "{-# " + self.directive + " " + self.raw_content + " #-}"


# =============================================================================
# Surface Declarations
# =============================================================================


class SurfaceDeclaration:
    """Base class for surface declarations."""

    pass


@dataclass(frozen=True)
class SurfaceConstructorInfo:
    """Data constructor with optional docstring."""

    name: str
    args: list[SurfaceType]
    docstring: str | None = None
    location: Location = None  # type: ignore[assignment]


@dataclass(frozen=True)
class SurfaceDataDeclaration(SurfaceDeclaration):
    """Data type declaration: data Name params = Con1 args1 | Con2 args2 | ..."""

    name: str
    params: list[str]
    constructors: list[SurfaceConstructorInfo]
    location: Location
    docstring: str | None = None

    def __str__(self) -> str:
        params_str = " ".join(self.params) if self.params else ""
        constrs_str = " | ".join(
            f"{c.name} {' '.join(str(t) for t in c.args)}" for c in self.constructors
        )
        return f"data {self.name} {params_str} = {constrs_str}"


@dataclass(frozen=True)
class SurfaceTermDeclaration(SurfaceDeclaration):
    """Term declaration: name : type = body or name = body."""

    name: str
    type_annotation: Optional[SurfaceType]
    body: SurfaceTerm
    location: Location
    docstring: str | None = None
    pragma: dict[str, str] | None = None  # e.g., {"LLM": "model=gpt-4 temperature=0.7"}

    def __str__(self) -> str:
        if self.type_annotation:
            return f"{self.name} : {self.type_annotation} = {self.body}"
        return f"{self.name} = {self.body}"


@dataclass(frozen=True)
class SurfacePrimTypeDecl(SurfaceDeclaration):
    """Primitive type declaration: prim_type Name.

    Declares a primitive type in the prelude. This registers the type
    name in the primitive_types registry for use by the type checker.

    Example: prim_type Int
    """

    name: str
    location: Location
    docstring: str | None = None

    def __str__(self) -> str:
        return f"prim_type {self.name}"


@dataclass(frozen=True)
class SurfacePrimOpDecl(SurfaceDeclaration):
    """Primitive operation declaration: prim_op name : type.

    Declares a primitive operation with its type signature.
    The name is registered as $prim.name in global_types.

    Example: prim_op int_plus : Int -> Int -> Int
    """

    name: str
    type_annotation: SurfaceType
    location: Location
    docstring: str | None = None

    def __str__(self) -> str:
        return f"prim_op {self.name} : {self.type_annotation}"


SurfaceDeclarationRepr = Union[
    SurfaceDataDeclaration, SurfaceTermDeclaration, SurfacePrimTypeDecl, SurfacePrimOpDecl
]
