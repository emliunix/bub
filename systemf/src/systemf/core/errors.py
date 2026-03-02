"""Error types for System F.

All errors carry source location information for accurate error reporting.
"""

from abc import ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from systemf.core.types import Type
from systemf.utils.location import Location

if TYPE_CHECKING:
    from systemf.core.ast import Term


@dataclass
class SystemFError(Exception, ABC):
    """Abstract base class for all System F errors.

    All errors carry source location information to enable accurate
    error messages that point to the exact source code location.
    Can optionally include the problematic term and diagnostic details.

    Attributes:
        message: Human-readable error description
        location: Source location where error occurred (line, column, file)
        term: Optional problematic term that caused the error
        diagnostic: Optional detailed diagnostic message with suggestions
    """

    message: str
    location: Optional[Location]
    term: Optional["Term"] = None
    diagnostic: Optional[str] = None

    def __init__(
        self,
        message: str,
        location: Optional[Location] = None,
        term: Optional["Term"] = None,
        diagnostic: Optional[str] = None,
    ):
        self.message = message
        self.location = location
        self.term = term
        self.diagnostic = diagnostic
        # Format message with location prefix if available
        if location:
            super().__init__(f"{location}: {message}")
        else:
            super().__init__(message)

    def __str__(self) -> str:
        parts = []
        if self.location:
            parts.append(str(self.location))
        parts.append(self.message)
        if self.term:
            parts.append(f"in term: {self.term}")
        if self.diagnostic:
            parts.append(f"\n  Diagnostic: {self.diagnostic}")
        return ": ".join(parts)


class TypeError(SystemFError):
    """Base class for type errors."""

    def __init__(self, message: str, location: Optional[Location] = None):
        super().__init__(message, location)


class UnificationError(TypeError):
    """Unification failure - types cannot be made equal."""

    def __init__(
        self,
        t1: Type,
        t2: Type,
        location: Optional[Location] = None,
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
        location: Optional[Location] = None,
    ):
        self.expected = expected
        self.actual = actual
        super().__init__(f"Expected type {expected}, but got {actual}", location)


class UndefinedVariable(TypeError):
    """Variable not found in typing context."""

    def __init__(
        self,
        index: int,
        location: Optional[Location] = None,
    ):
        self.index = index
        super().__init__(f"Undefined variable with de Bruijn index {index}", location)


class UndefinedConstructor(TypeError):
    """Data constructor not declared."""

    def __init__(
        self,
        name: str,
        location: Optional[Location] = None,
    ):
        self.name = name
        super().__init__(f"Undefined constructor: {name}", location)


class OccursCheckError(TypeError):
    """Occurs check failed - infinite type detected."""

    def __init__(
        self,
        var: str,
        t: Type,
        location: Optional[Location] = None,
    ):
        self.var = var
        self.t = t
        super().__init__(f"Occurs check failed: {var} occurs in {t}", location)


class ElaborationError(SystemFError):
    """Error during elaboration (surface to core translation)."""

    def __init__(self, message: str, location: Optional[Location] = None):
        super().__init__(message, location)


class ScopeError(SystemFError):
    """Error during scope checking (name resolution)."""

    def __init__(self, message: str, location: Optional[Location] = None):
        super().__init__(message, location)


class ParseError(SystemFError):
    """Error during parsing."""

    def __init__(self, message: str, location: Optional[Location] = None):
        super().__init__(message, location)
