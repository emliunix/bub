"""Type representations for System F."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


class Type:
    """Base class for types."""

    def free_vars(self) -> set[str]:
        """Return set of free type variable names."""
        raise NotImplementedError

    def substitute(self, subst: dict[str, Type]) -> Type:
        """Apply substitution to this type."""
        raise NotImplementedError


@dataclass(frozen=True)
class TypeVar(Type):
    """Type variable with a name (for debugging)."""

    name: str

    def __str__(self) -> str:
        return self.name

    def free_vars(self) -> set[str]:
        return {self.name}

    def substitute(self, subst: dict[str, Type]) -> Type:
        if self.name in subst:
            return subst[self.name]
        return self


@dataclass(frozen=True)
class TypeArrow(Type):
    """Function type: σ → τ with optional parameter docstring.

    Parameter docs are embedded in type annotations using -- ^ syntax:
        String -- ^ Input text -> String

    The param_doc field captures documentation for the argument type (σ).
    """

    arg: Type
    ret: Type
    param_doc: Optional[str] = None  # Populated when elaborator sees -- ^ after type

    def __str__(self) -> str:
        match self.arg:
            case TypeArrow():
                arg_str = f"({self.arg})"
            case _:
                arg_str = str(self.arg)
        doc_suffix = f" -- ^ {self.param_doc}" if self.param_doc else ""
        return f"{arg_str}{doc_suffix} -> {self.ret}"

    def free_vars(self) -> set[str]:
        return self.arg.free_vars() | self.ret.free_vars()

    def substitute(self, subst: dict[str, Type]) -> Type:
        return TypeArrow(self.arg.substitute(subst), self.ret.substitute(subst), self.param_doc)


@dataclass(frozen=True)
class TypeForall(Type):
    """Polymorphic type: ∀α.σ."""

    var: str
    body: Type

    def __str__(self) -> str:
        return f"∀{self.var}.{self.body}"

    def free_vars(self) -> set[str]:
        return self.body.free_vars() - {self.var}

    def substitute(self, subst: dict[str, Type]) -> Type:
        # Avoid capture: don't substitute the bound variable
        subst_without_var = {k: v for k, v in subst.items() if k != self.var}
        if not subst_without_var:
            return self
        return TypeForall(self.var, self.body.substitute(subst_without_var))


@dataclass(frozen=True)
class TypeConstructor(Type):
    """Data type constructor: T τ₁...τₙ."""

    name: str
    args: list[Type]

    def __str__(self) -> str:
        if not self.args:
            return self.name
        args_strs = []
        for arg in self.args:
            match arg:
                case TypeArrow() | TypeForall():
                    args_strs.append(f"({arg})")
                case _:
                    args_strs.append(str(arg))
        args_str = " ".join(args_strs)
        return f"{self.name} {args_str}"

    def free_vars(self) -> set[str]:
        result: set[str] = set()
        for arg in self.args:
            result |= arg.free_vars()
        return result

    def substitute(self, subst: dict[str, Type]) -> Type:
        return TypeConstructor(self.name, [arg.substitute(subst) for arg in self.args])


@dataclass(frozen=True)
class PrimitiveType(Type):
    """Primitive type from prelude: Int, Float, String, etc.

    Primitive types are declared in the prelude using `prim_type` and
    registered in the type checker. They have no structure - they're
    just named types that the evaluator knows how to work with.
    """

    name: str

    def __str__(self) -> str:
        return self.name

    def free_vars(self) -> set[str]:
        return set()

    def substitute(self, subst: dict[str, Type]) -> Type:
        return self


# Export the type union for type checking
TypeRepr = Union[TypeVar, TypeArrow, TypeForall, TypeConstructor, PrimitiveType]
