"""Scope error types for System F surface language.

This module defines the exception hierarchy for scope checking errors,
including undefined variables and type variables with source location tracking.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from systemf.core.errors import SystemFError
from systemf.utils.location import Location

if TYPE_CHECKING:
    from systemf.surface.types import SurfaceTerm, SurfaceType


@dataclass
class ScopeError(SystemFError):
    """Error during scope checking (name resolution).

    Base class for all scope-related errors in the surface language.
    These errors occur when names cannot be resolved during the scope
    checking phase of elaboration.

    Attributes:
        message: Human-readable error description
        location: Source location where error occurred
        term: Optional problematic term that caused the error
        diagnostic: Optional detailed diagnostic message with suggestions
    """

    def __init__(
        self,
        message: str,
        location: Optional[Location] = None,
        term: Optional["SurfaceTerm"] = None,
        diagnostic: Optional[str] = None,
    ):
        super().__init__(message, location, None, diagnostic)
        self.term = term


class UndefinedVariableError(ScopeError):
    """Undefined term variable referenced in scope.

    Raised when a variable name is used but not bound in the current scope
    and is not a known global.

    Attributes:
        name: The undefined variable name
        location: Source location of the reference
        available: List of similar names that might have been intended
    """

    name: str
    available: list[str]

    def __init__(
        self,
        name: str,
        location: Optional[Location] = None,
        available: Optional[list[str]] = None,
        term: Optional["SurfaceTerm"] = None,
    ):
        self.name = name
        self.available = available or []

        message = f"Undefined variable: '{name}'"
        diagnostic = None
        if self.available:
            suggestions = ", ".join(f"'{n}'" for n in self.available[:5])
            diagnostic = f"Did you mean one of: {suggestions}?"

        super().__init__(message, location, term, diagnostic)


class UndefinedTypeVariableError(ScopeError):
    """Undefined type variable referenced in scope.

    Raised when a type variable name is used but not bound in the current
    type scope.

    Attributes:
        name: The undefined type variable name
        location: Source location of the reference
        available: List of similar type names that might have been intended
    """

    name: str
    available: list[str]

    def __init__(
        self,
        name: str,
        location: Optional[Location] = None,
        available: Optional[list[str]] = None,
        type_term: Optional["SurfaceType"] = None,
    ):
        self.name = name
        self.available = available or []

        message = f"Undefined type variable: '{name}'"
        diagnostic = None
        if self.available:
            suggestions = ", ".join(f"'{n}'" for n in self.available[:5])
            diagnostic = f"Did you mean one of: {suggestions}?"

        super().__init__(message, location, None, diagnostic)
        # Store type separately since base expects SurfaceTerm
        self.type_term = type_term


class DuplicateBindingError(ScopeError):
    """Duplicate variable binding in the same scope.

    Raised when a variable is bound multiple times in the same scope,
    which would create ambiguity.

    Attributes:
        name: The duplicate variable name
        location: Source location of the duplicate binding
        original_location: Optional location of the first binding
    """

    name: str
    original_location: Optional[Location]

    def __init__(
        self,
        name: str,
        location: Optional[Location] = None,
        original_location: Optional[Location] = None,
        term: Optional["SurfaceTerm"] = None,
    ):
        self.name = name
        self.original_location = original_location

        message = f"Duplicate binding: '{name}' is already bound"
        diagnostic = None
        if original_location:
            diagnostic = f"Previously bound at {original_location}"

        super().__init__(message, location, term, diagnostic)


class ScopeDepthError(ScopeError):
    """Invalid scope depth or index access.

    Raised when an internal scope operation results in an invalid
    de Bruijn index or scope depth.

    Attributes:
        depth: The invalid depth or index value
        max_depth: The maximum allowed depth
    """

    depth: int
    max_depth: int

    def __init__(
        self,
        depth: int,
        max_depth: int,
        location: Optional[Location] = None,
        term: Optional["SurfaceTerm"] = None,
    ):
        self.depth = depth
        self.max_depth = max_depth

        message = f"Invalid scope depth: {depth} (max: {max_depth})"
        diagnostic = "Internal error: scope index out of bounds"

        super().__init__(message, location, term, diagnostic)


class GlobalVariableError(ScopeError):
    """Invalid use of a global variable.

    Raised when a global variable is used in a context where it's
    not permitted or properly initialized.

    Attributes:
        name: The global variable name
        reason: Explanation of why the global use is invalid
    """

    name: str
    reason: str

    def __init__(
        self,
        name: str,
        reason: str,
        location: Optional[Location] = None,
        term: Optional["SurfaceTerm"] = None,
    ):
        self.name = name
        self.reason = reason

        message = f"Invalid use of global '{name}': {reason}"

        super().__init__(message, location, term, None)
