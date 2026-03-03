"""Surface language AST for System F.

Surface syntax uses name-based binding (not de Bruijn indices) and allows
omitting type annotations where they can be inferred.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from systemf.utils.location import Location


# =============================================================================
# Surface Node Base Class
# =============================================================================


@dataclass(frozen=True, kw_only=True)
class SurfaceNode:
    """Base class for all surface AST nodes."""

    location: Optional[Location] = field(default=None)


# =============================================================================
# Surface Types
# =============================================================================


class SurfaceType(SurfaceNode):
    """Base class for surface types."""

    pass


@dataclass(frozen=True, kw_only=True)
class SurfaceTypeVar(SurfaceType):
    """Type variable: a."""

    name: str = ""

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, kw_only=True)
class SurfaceTypeArrow(SurfaceType):
    """Function type: arg -> ret with optional parameter docstring.

    Example:
        String -- ^ Input text -> String

    Representation:
        SurfaceTypeArrow(
            arg=SurfaceTypeConstructor(name="String"),
            ret=SurfaceTypeConstructor(name="String"),
            param_doc="Input text",
            location=loc
        )
    """

    arg: Optional[SurfaceType] = None
    ret: Optional[SurfaceType] = None
    param_doc: Optional[str] = None  # Populated when parser sees -- ^ after type

    def __str__(self) -> str:
        match self.arg:
            case SurfaceTypeArrow():
                arg_str = f"({self.arg})"
            case _:
                arg_str = str(self.arg)
        doc_suffix = f" -- ^ {self.param_doc}" if self.param_doc else ""
        return f"{arg_str}{doc_suffix} -> {self.ret}"


@dataclass(frozen=True, kw_only=True)
class SurfaceTypeForall(SurfaceType):
    """Polymorphic type: forall a. body."""

    var: str = ""
    body: Optional[SurfaceType] = None

    def __str__(self) -> str:
        return f"forall {self.var}. {self.body}"


@dataclass(frozen=True, kw_only=True)
class SurfaceTypeConstructor(SurfaceType):
    """Data type constructor: T t1 ... tn."""

    name: str = ""
    args: list[SurfaceType] = field(default_factory=list)

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


@dataclass(frozen=True, kw_only=True)
class SurfaceTypeTuple(SurfaceType):
    """Tuple type: (t1, t2, ..., tn) - desugars to nested Pairs.

    Sugar for: Pair t1 (Pair t2 (... tn))
    """

    elements: list[SurfaceType] = field(default_factory=list)

    def __str__(self) -> str:
        elems_str = ", ".join(str(e) for e in self.elements)
        return f"({elems_str})"


SurfaceTypeRepr = Union[
    SurfaceTypeVar, SurfaceTypeArrow, SurfaceTypeForall, SurfaceTypeConstructor, SurfaceTypeTuple
]


# =============================================================================
# Surface Terms
# =============================================================================


class SurfaceTerm(SurfaceNode):
    """Base class for surface terms."""

    pass


@dataclass(frozen=True, kw_only=True)
class SurfaceVar(SurfaceTerm):
    """Variable reference by name: x."""

    name: str = ""

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, kw_only=True)
class SurfaceAbs(SurfaceTerm):
    r"""Lambda abstraction: \x -> body or \x:T -> body.

    Supports multiple parameters: \x y z -> body (desugared to nested lambdas)
    """

    # Multi-param support: list of (name, type) pairs
    # For single param, use params=[(name, type)]
    params: list[tuple[str, Optional[SurfaceType]]] = field(default_factory=list)
    body: Optional[SurfaceTerm] = None

    # Backwards compatibility properties
    @property
    def var(self) -> str:
        """First parameter name (backwards compatibility)."""
        return self.params[0][0] if self.params else ""

    @property
    def var_type(self) -> Optional[SurfaceType]:
        """First parameter type (backwards compatibility)."""
        return self.params[0][1] if self.params else None

    def __init__(
        self,
        params: list[tuple[str, Optional[SurfaceType]]] | None = None,
        body: SurfaceTerm | None = None,
        location: Location | None = None,
        # Backwards compatibility kwargs
        var: str | None = None,
        var_type: SurfaceType | None = None,
    ):
        """Initialize with backwards compatibility for old API.

        Old API: SurfaceAbs(var="x", var_type=Int, body=..., location=...)
        New API: SurfaceAbs(params=[("x", Int)], body=..., location=...)
        """
        # Handle old API: if var is provided, build params from it
        if var is not None:
            params = [(var, var_type)]
        elif params is None:
            params = []

        # Use object.__setattr__ since dataclass is frozen
        object.__setattr__(self, "params", params)
        object.__setattr__(self, "body", body)
        object.__setattr__(self, "location", location)

    def __str__(self) -> str:
        if not self.params:
            return f"\\ -> {self.body}"
        params_str = " ".join(f"{name}:{ty}" if ty else name for name, ty in self.params)
        return f"\\{params_str} -> {self.body}"


@dataclass(frozen=True, kw_only=True)
class ScopedVar(SurfaceTerm):
    """Variable reference by de Bruijn index (after scope checking).

    Replaces SurfaceVar during scope checking. Index 0 refers to the
    nearest binder, index 1 to the next outer binder, etc.

    Attributes:
        index: De Bruijn index (0 = nearest binder)
        debug_name: Original name for error messages and debugging
        location: Source location
    """

    index: int = 0
    debug_name: str = ""

    def __str__(self) -> str:
        return f"#{self.index}({self.debug_name})"


@dataclass(frozen=True, kw_only=True)
class ScopedAbs(SurfaceTerm):
    """Lambda with parameter name preserved (after scope checking).

    Replaces SurfaceAbs during scope checking. The body contains ScopedVar
    references instead of SurfaceVar.

    Attributes:
        var_name: Original parameter name (for error messages)
        var_type: Optional type annotation
        body: The function body (contains ScopedVar references)
        location: Source location
    """

    var_name: str = ""
    var_type: Optional[SurfaceType] = None
    body: Optional[SurfaceTerm] = None

    def __str__(self) -> str:
        if self.var_type:
            return f"\\{self.var_name}:{self.var_type} -> {self.body}"
        return f"\\{self.var_name} -> {self.body}"


@dataclass(frozen=True, kw_only=True)
class SurfaceApp(SurfaceTerm):
    """Function application: f arg."""

    func: Optional[SurfaceTerm] = None
    arg: Optional[SurfaceTerm] = None

    def __str__(self) -> str:
        return f"({self.func} {self.arg})"


@dataclass(frozen=True, kw_only=True)
class SurfaceTypeAbs(SurfaceTerm):
    """Type abstraction: /\a. body (written as /\a. or Λa.).

    Supports multiple type variables: /\a b c. body (desugared to nested type abstractions)
    """

    # Multi-var support: list of type variable names
    # For single var, use vars=["a"]
    vars: list[str] = field(default_factory=list)
    body: Optional[SurfaceTerm] = None

    # Backwards compatibility property
    @property
    def var(self) -> str:
        """First type variable name (backwards compatibility)."""
        return self.vars[0] if self.vars else ""

    def __init__(
        self,
        vars: list[str] | None = None,
        body: SurfaceTerm | None = None,
        location: Location | None = None,
        # Backwards compatibility kwargs
        var: str | None = None,
    ):
        """Initialize with backwards compatibility for old API.

        Old API: SurfaceTypeAbs(var="a", body=..., location=...)
        New API: SurfaceTypeAbs(vars=["a"], body=..., location=...)
        """
        # Handle old API: if var is provided, build vars from it
        if var is not None:
            vars = [var]
        elif vars is None:
            vars = []

        # Use object.__setattr__ since dataclass is frozen
        object.__setattr__(self, "vars", vars)
        object.__setattr__(self, "body", body)
        object.__setattr__(self, "location", location)

    def __str__(self) -> str:
        if not self.vars:
            return f"/\\. {self.body}"
        vars_str = " ".join(self.vars)
        return f"/\\{vars_str}. {self.body}"


@dataclass(frozen=True, kw_only=True)
class SurfaceTypeApp(SurfaceTerm):
    """Type application: func @type or func [type]."""

    func: Optional[SurfaceTerm] = None
    type_arg: Optional[SurfaceType] = None

    def __str__(self) -> str:
        return f"({self.func} @{self.type_arg})"


@dataclass(frozen=True, kw_only=True)
class SurfaceLet(SurfaceTerm):
    """Local let binding within an expression.

    Syntax:
        let x : Int = 42 in x + 1
        let
          x = 1
          y = 2
        in x + y

    Note: type annotation is optional for locals since they can be inferred.
    """

    bindings: list[tuple[str, Optional[SurfaceType], SurfaceTerm]] = field(
        default_factory=list
    )  # (var_name, var_type, value)
    body: Optional[SurfaceTerm] = None

    def __str__(self) -> str:
        if len(self.bindings) == 1:
            var_name, var_type, value = self.bindings[0]
            type_part = f" : {var_type}" if var_type else ""
            return f"let {var_name}{type_part} = {value} in {self.body}"
        else:
            bindings_str = "\n".join(
                f"  {name}{f' : {t}' if t else ''} = {val}" for name, t, val in self.bindings
            )
            return f"let\n{bindings_str}\nin {self.body}"


@dataclass(frozen=True, kw_only=True)
class SurfaceAnn(SurfaceTerm):
    """Type annotation: term : type."""

    term: Optional[SurfaceTerm] = None
    type: Optional[SurfaceType] = None

    def __str__(self) -> str:
        return f"({self.term} : {self.type})"


@dataclass(frozen=True, kw_only=True)
class SurfaceIf(SurfaceTerm):
    """Conditional expression: if cond then t else f.

    Syntactic sugar for: case cond of True -> t | False -> f
    """

    cond: Optional[SurfaceTerm] = None
    then_branch: Optional[SurfaceTerm] = None
    else_branch: Optional[SurfaceTerm] = None

    def __str__(self) -> str:
        return f"if {self.cond} then {self.then_branch} else {self.else_branch}"


@dataclass(frozen=True, kw_only=True)
class SurfaceConstructor(SurfaceTerm):
    """Data constructor application: Con args."""

    name: str = ""
    args: list[SurfaceTerm] = field(default_factory=list)

    def __str__(self) -> str:
        if not self.args:
            return self.name
        args_str = " ".join(str(arg) for arg in self.args)
        return f"({self.name} {args_str})"


@dataclass(frozen=True, kw_only=True)
class SurfaceLit(SurfaceTerm):
    """Primitive literal: Int, String, Float, etc.

    Unified representation for all primitive literals.
    The prim_type field indicates the primitive type ("Int", "String", etc.).

    Attributes:
        prim_type: The primitive type name (e.g., "Int", "String")
        value: The literal value (int, str, float, etc.)
    """

    prim_type: str = ""
    value: object = None

    def __str__(self) -> str:
        if self.prim_type == "String":
            return f'"{self.value}"'
        return str(self.value)


@dataclass(frozen=True, kw_only=True)
class GlobalVar(SurfaceTerm):
    """Global variable reference by name (after scope checking).

    Replaces SurfaceVar for global variables during scope checking.
    Unlike ScopedVar which uses de Bruijn indices for local variables,
    GlobalVar keeps the name and is resolved from TypeContext.globals.

    Attributes:
        name: Global variable name
    """

    name: str = ""

    def __str__(self) -> str:
        return f"@{self.name}"


@dataclass(frozen=True, kw_only=True)
class SurfaceOp(SurfaceTerm):
    """Infix operator expression: left op right.

    This is a surface syntax construct that gets desugared to a primitive
    operation application. Operators include +, -, *, /, ==, <, >, <=, >=.
    """

    left: Optional[SurfaceTerm] = None
    op: str = ""  # The operator symbol: '+', '-', '*', '/', '==', '<', '>', '<=', '>='
    right: Optional[SurfaceTerm] = None

    def __str__(self) -> str:
        return f"({self.left} {self.op} {self.right})"


@dataclass(frozen=True, kw_only=True)
class SurfaceTuple(SurfaceTerm):
    """Tuple expression: (e1, e2, ..., en) - desugars to nested Pairs.

    Sugar for: Pair e1 (Pair e2 (... en))
    """

    elements: list[SurfaceTerm] = field(default_factory=list)

    def __str__(self) -> str:
        elems_str = ", ".join(str(e) for e in self.elements)
        return f"({elems_str})"


@dataclass(frozen=True, kw_only=True)
class SurfacePattern(SurfaceNode):
    """Pattern in a case branch: Con vars."""

    constructor: str = ""
    vars: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.vars:
            return f"{self.constructor} {' '.join(self.vars)}"
        return self.constructor


@dataclass(frozen=True, kw_only=True)
class SurfacePatternTuple(SurfaceNode):
    """Tuple pattern: (p1, p2, ..., pn) - desugars to nested Pairs.

    Sugar for: Pair p1 (Pair p2 (... pn))
    """

    elements: list[SurfacePattern] = field(default_factory=list)

    def __str__(self) -> str:
        elems_str = ", ".join(str(e) for e in self.elements)
        return f"({elems_str})"


@dataclass(frozen=True, kw_only=True)
class SurfaceBranch(SurfaceNode):
    """Case branch: pattern -> body."""

    pattern: Optional[SurfacePattern] = None
    body: Optional[SurfaceTerm] = None

    def __str__(self) -> str:
        return f"{self.pattern} -> {self.body}"


@dataclass(frozen=True, kw_only=True)
class SurfaceCase(SurfaceTerm):
    """Pattern matching: case scrutinee of branches."""

    scrutinee: Optional[SurfaceTerm] = None
    branches: list[SurfaceBranch] = field(default_factory=list)

    def __str__(self) -> str:
        branches_str = " | ".join(str(branch) for branch in self.branches)
        return f"case {self.scrutinee} of {{ {branches_str} }}"


@dataclass(frozen=True, kw_only=True)
class SurfaceToolCall(SurfaceTerm):
    """Tool invocation: @tool_name arg1 arg2 ...

    Tool calls allow SystemF code to invoke external operations.
    The tool name is resolved at runtime from the tool registry.
    """

    tool_name: str = ""
    args: list[SurfaceTerm] = field(default_factory=list)

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
    SurfaceLit,
    GlobalVar,
    SurfaceOp,
]


# =============================================================================
# Surface Pragmas
# =============================================================================


@dataclass(frozen=True, kw_only=True)
class SurfacePragma(SurfaceNode):
    """Pragma annotation: {-# LLM raw_content #-}.

    Simplified storage - just keeps the raw string after the directive.
    Key=value parsing happens in later passes if needed.
    """

    directive: str = ""  # e.g., "LLM"
    raw_content: str = (
        ""  # Raw string content after directive (e.g., "model=gpt-4 temperature=0.7")
    )

    def __str__(self) -> str:
        return "{-# " + self.directive + " " + self.raw_content + " #-}"


# =============================================================================
# Surface Declarations
# =============================================================================


class SurfaceDeclaration(SurfaceNode):
    """Base class for surface declarations."""

    pass


@dataclass(frozen=True, kw_only=True)
class SurfaceConstructorInfo(SurfaceNode):
    """Data constructor with optional docstring."""

    name: str = ""
    args: list[SurfaceType] = field(default_factory=list)
    docstring: str | None = None


@dataclass(frozen=True, kw_only=True)
class SurfaceDataDeclaration(SurfaceDeclaration):
    """Data type declaration: data Name params = Con1 args1 | Con2 args2 | ..."""

    name: str = ""
    params: list[str] = field(default_factory=list)
    constructors: list[SurfaceConstructorInfo] = field(default_factory=list)
    docstring: str | None = None
    pragma: dict[str, str] | None = None

    def __str__(self) -> str:
        params_str = " ".join(self.params) if self.params else ""
        constrs_str = " | ".join(
            f"{c.name} {' '.join(str(t) for t in c.args)}" for c in self.constructors
        )
        return f"data {self.name} {params_str} = {constrs_str}"


@dataclass(frozen=True, kw_only=True)
class SurfaceTermDeclaration(SurfaceDeclaration):
    """Named term declaration at module level.

    Syntax:
        -- | Function description
        func : Type -- ^ param -> Type
        func = \\x -> body

    Or with pragma:
        {-# LLM model=gpt-4 #-}
        -- | Translate text
        prim_op func : Type -- ^ param -> Type
    """

    name: str = ""
    type_annotation: SurfaceType | None = None  # REQUIRED - changed from Optional
    body: Optional[SurfaceTerm] = None
    docstring: str | None = None  # -- | style, attaches to this declaration
    pragma: dict[str, str] | None = None  # {"LLM": "model=gpt-4 temp=0.7"}

    def __str__(self) -> str:
        return f"{self.name} : {self.type_annotation} = {self.body}"


@dataclass(frozen=True, kw_only=True)
class SurfacePrimTypeDecl(SurfaceDeclaration):
    """Primitive type declaration: prim_type Name.

    Declares a primitive type in the prelude. This registers the type
    name in the primitive_types registry for use by the type checker.

    Example: prim_type Int
    """

    name: str = ""
    docstring: str | None = None
    pragma: dict[str, str] | None = None

    def __str__(self) -> str:
        return f"prim_type {self.name}"


@dataclass(frozen=True, kw_only=True)
class SurfacePrimOpDecl(SurfaceDeclaration):
    """Primitive operation declaration: prim_op name : type.

    Declares a primitive operation with its type signature.
    The name is registered as $prim.name in global_types.

    Example: prim_op int_plus : Int -> Int -> Int

    With pragma for LLM functions:
        {-# LLM model=gpt-4 #-}
        prim_op translate : String -> String
    """

    name: str = ""
    type_annotation: Optional[SurfaceType] = None
    docstring: str | None = None
    pragma: dict[str, str] | None = None  # {"LLM": "model=gpt-4 temp=0.7"}

    def __str__(self) -> str:
        return f"prim_op {self.name} : {self.type_annotation}"


SurfaceDeclarationRepr = Union[
    SurfaceDataDeclaration, SurfaceTermDeclaration, SurfacePrimTypeDecl, SurfacePrimOpDecl
]


# Note: equals_ignore_location has been moved to systemf.utils.ast_utils
# It is re-exported here for backward compatibility.
