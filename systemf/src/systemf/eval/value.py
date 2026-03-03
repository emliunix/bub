"""Value representations for System F interpreter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from systemf.core.ast import Term


@dataclass(frozen=True)
class VClosure:
    """Lambda closure: λx.e with captured environment."""

    env: "Environment"  # Captured environment
    body: Term  # Function body (de Bruijn index refers to env)

    def __str__(self) -> str:
        return "<function>"


@dataclass(frozen=True)
class VTypeClosure:
    """Type abstraction closure: Λα.e with captured environment."""

    env: "Environment"
    body: Term

    def __str__(self) -> str:
        return "<type-function>"


@dataclass(frozen=True)
class VConstructor:
    """Data constructor value: K v₁ ... vₙ."""

    name: str
    args: list["Value"]

    def __str__(self) -> str:
        if not self.args:
            return self.name
        args_str = " ".join(str(arg) for arg in self.args)
        return f"({self.name} {args_str})"


@dataclass(frozen=True)
class VNeutral:
    """Neutral term (stuck computation) - for error reporting."""

    term: Term

    def __str__(self) -> str:
        return f"<neutral: {self.term}>"


@dataclass(frozen=True)
class VPrim:
    """Unified primitive value representation.

    All primitive values (Int, String, etc.) are represented uniformly
    with a type tag and underlying Python value. This simplifies primitive
    operations and ensures consistency.

    Attributes:
        prim_type: The primitive type name (e.g., "Int", "String")
        value: The underlying Python value
    """

    prim_type: str
    value: object

    def __str__(self) -> str:
        if self.prim_type == "String":
            return f'"{self.value}"'
        return str(self.value)

    def __eq__(self, other: object) -> bool:
        """Compare primitive values."""
        if not isinstance(other, VPrim):
            return NotImplemented
        return self.prim_type == other.prim_type and self.value == other.value


@dataclass(frozen=True)
class VInt:
    """Runtime integer value (deprecated, use VPrim).

    Represents a primitive integer at runtime.
    Created by evaluating IntLit terms.

    Note: This is kept for backward compatibility. New code should use
    VPrim("Int", value) instead.
    """

    value: int

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class VString:
    """Runtime string value (deprecated, use VPrim).

    Represents a primitive string at runtime.
    Created by evaluating StringLit terms.

    Note: This is kept for backward compatibility. New code should use
    VPrim("String", value) instead.
    """

    value: str

    def __str__(self) -> str:
        return f'"{self.value}"'


@dataclass(frozen=True)
class VToolResult:
    """Tool execution result: represents the result of a tool call.

    Contains the tool name, result data, and success/failure status.
    """

    tool_name: str
    result: Any  # Tool-specific result data
    success: bool = True

    def __str__(self) -> str:
        if self.success:
            return f"<tool:{self.tool_name}={self.result}>"
        return f"<tool:{self.tool_name}!{self.result}>"


@dataclass(frozen=True)
class VPrimOp:
    """Primitive operation closure.

    Wraps a primitive operation implementation that expects VInt arguments.
    """

    name: str
    impl: Callable  # Callable[[Value, Value], Value]

    def __str__(self) -> str:
        return f"<primop:{self.name}>"


@dataclass(frozen=True)
class VPrimOpPartial:
    """Partially applied primitive operation.

    Stores the first argument while waiting for the second.
    """

    name: str
    impl: Callable  # Callable[[Value, Value], Value]
    first_arg: "Value"

    def __str__(self) -> str:
        return f"<primop:{self.name} {self.first_arg}>"


# Sum type for all values
Value = (
    VClosure
    | VTypeClosure
    | VConstructor
    | VNeutral
    | VInt  # Deprecated: use VPrim instead
    | VString  # Deprecated: use VPrim instead
    | VPrim
    | VToolResult
    | VPrimOp
    | VPrimOpPartial
)


@dataclass(frozen=True)
class Environment:
    """Evaluation environment mapping de Bruijn indices to values.

    Index 0 is the most recently bound variable.
    """

    values: list[Value]

    @staticmethod
    def empty() -> "Environment":
        """Create an empty environment."""
        return Environment([])

    def extend(self, value: Value) -> "Environment":
        """Add value at index 0, shifting existing values."""
        return Environment([value] + self.values)

    def lookup(self, index: int) -> Value:
        """Lookup value by de Bruijn index."""
        if index >= len(self.values):
            raise RuntimeError(f"Unbound variable at index {index}")
        return self.values[index]

    def __len__(self) -> int:
        return len(self.values)

    def __str__(self) -> str:
        return f"Environment({len(self.values)} bindings)"
