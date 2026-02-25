"""Error types for System F type checker."""

from dataclasses import dataclass

from systemf.core.types import Type
from systemf.utils.location import Location


class TypeError(Exception):
    """Base class for type errors."""

    location: Location | None

    def __init__(self, message: str, location: Location | None = None):
        super().__init__(message)
        self.location = location


class UnificationError(TypeError):
    """Unification failure - types cannot be made equal."""

    def __init__(
        self,
        t1: Type,
        t2: Type,
        location: Location | None = None,
    ):
        self.t1 = t1
        self.t2 = t2
        super().__init__(f"Cannot unify {t1} with {t2}", location)


class TypeMismatch(TypeError):
    """Expected type does not match actual type."""

    def __init__(
        self,
        expected: Type,
        actual: Type,
        location: Location | None = None,
    ):
        self.expected = expected
        self.actual = actual
        super().__init__(f"Expected type {expected}, but got {actual}", location)


class UndefinedVariable(TypeError):
    """Variable not found in typing context."""

    def __init__(
        self,
        index: int,
        location: Location | None = None,
    ):
        self.index = index
        super().__init__(f"Undefined variable with de Bruijn index {index}", location)


class UndefinedConstructor(TypeError):
    """Data constructor not declared."""

    def __init__(
        self,
        name: str,
        location: Location | None = None,
    ):
        self.name = name
        super().__init__(f"Undefined constructor: {name}", location)


class OccursCheckError(TypeError):
    """Occurs check failed - infinite type detected."""

    def __init__(
        self,
        var: str,
        t: Type,
        location: Location | None = None,
    ):
        self.var = var
        self.t = t
        super().__init__(f"Occurs check failed: {var} occurs in {t}", location)
