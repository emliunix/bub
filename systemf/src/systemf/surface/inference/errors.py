"""Type error types for System F surface language.

This module defines the exception hierarchy for type checking errors,
including unification failures, type mismatches, and occurs check errors
with source location tracking.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Union

from systemf.core.errors import SystemFError
from systemf.core.types import Type as CoreType
from systemf.utils.location import Location

if TYPE_CHECKING:
    from systemf.surface.types import SurfaceTerm, SurfaceType


@dataclass
class TypeError(SystemFError):
    """Error during type inference and checking.

    Base class for all type-related errors in the surface language.
    These errors occur during the type checking phase of elaboration
    when types cannot be unified or types don't match expectations.

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
        # Store surface term separately since base class expects core Term
        self.surface_term = term


class TypeMismatchError(TypeError):
    """Expected type does not match actual type.

    Raised when a term has a type that doesn't match the expected type
    in a given context. For example, using a function where a number
    is expected.

    Attributes:
        expected: The expected type
        actual: The actual type found
        location: Source location of the type mismatch
        context: Optional description of the context where mismatch occurred
    """

    expected: Union["SurfaceType", CoreType]
    actual: Union["SurfaceType", CoreType]
    context: Optional[str]

    def __init__(
        self,
        expected: Union["SurfaceType", CoreType],
        actual: Union["SurfaceType", CoreType],
        location: Optional[Location] = None,
        term: Optional["SurfaceTerm"] = None,
        context: Optional[str] = None,
    ):
        self.expected = expected
        self.actual = actual
        self.context = context

        message = f"Type mismatch: expected '{expected}', but got '{actual}'"
        diagnostic = None
        if context:
            diagnostic = f"In context: {context}"

        super().__init__(message, location, term, diagnostic)


class InfiniteTypeError(TypeError):
    """Occurs check failed - infinite type detected.

    Raised during unification when a type variable would need to be
    unified with a type that contains itself, which would create an
    infinite type. For example, unifying 'a' with 'a -> b'.

    Attributes:
        type_var: The type variable name
        contains_type: The type that contains the variable
        location: Source location of the unification attempt
    """

    type_var: str
    contains_type: Union["SurfaceType", CoreType]

    def __init__(
        self,
        type_var: str,
        contains_type: Union["SurfaceType", CoreType],
        location: Optional[Location] = None,
        term: Optional["SurfaceTerm"] = None,
    ):
        self.type_var = type_var
        self.contains_type = contains_type

        message = f"Infinite type detected: '{type_var}' occurs in '{contains_type}'"
        diagnostic = (
            f"Cannot construct the infinite type '{type_var} = {contains_type}'. "
            f"Check for recursive definitions that lack proper type annotations."
        )

        super().__init__(message, location, term, diagnostic)


class UnificationError(TypeError):
    """Unification failure - types cannot be made equal.

    Raised when two types cannot be unified because they have
    incompatible structures. For example, trying to unify a function
    type with a base type.

    Attributes:
        type1: First type in unification attempt
        type2: Second type in unification attempt
        location: Source location of the unification failure
    """

    type1: Union["SurfaceType", CoreType]
    type2: Union["SurfaceType", CoreType]

    def __init__(
        self,
        type1: Union["SurfaceType", CoreType],
        type2: Union["SurfaceType", CoreType],
        location: Optional[Location] = None,
        term: Optional["SurfaceTerm"] = None,
    ):
        self.type1 = type1
        self.type2 = type2

        message = f"Cannot unify '{type1}' with '{type2}'"
        diagnostic = (
            f"These types have incompatible structures and cannot be made equal. "
            f"Type 1: {type1}, Type 2: {type2}"
        )

        super().__init__(message, location, term, diagnostic)


class KindError(TypeError):
    """Type constructor mismatch - kind error.

    Raised when a type constructor is applied to the wrong number or
    kind of arguments. For example, applying a type that expects a
    type argument to a term, or applying too many/few arguments.

    Attributes:
        type_constructor: The type constructor name
        expected_args: Expected number of arguments
        actual_args: Actual number of arguments provided
        location: Source location of the kind mismatch
    """

    type_constructor: str
    expected_args: int
    actual_args: int

    def __init__(
        self,
        type_constructor: str,
        expected_args: int,
        actual_args: int,
        location: Optional[Location] = None,
        term: Optional["SurfaceTerm"] = None,
    ):
        self.type_constructor = type_constructor
        self.expected_args = expected_args
        self.actual_args = actual_args

        message = (
            f"Kind error in '{type_constructor}': "
            f"expected {expected_args} argument(s), but got {actual_args}"
        )

        if actual_args < expected_args:
            diagnostic = (
                f"Type constructor '{type_constructor}' expects {expected_args} "
                f"type argument(s), but only {actual_args} were provided. "
                f"Add the missing type arguments."
            )
        elif actual_args > expected_args:
            diagnostic = (
                f"Type constructor '{type_constructor}' expects {expected_args} "
                f"type argument(s), but {actual_args} were provided. "
                f"Remove the extra type arguments."
            )
        else:
            diagnostic = (
                f"Type constructor '{type_constructor}' has incorrect kind. "
                f"Check that the type arguments have the correct kind."
            )

        super().__init__(message, location, term, diagnostic)


class UndefinedTypeError(TypeError):
    """Undefined type constructor referenced.

    Raised when a type constructor name is used but not defined in
    the current context. This is similar to undefined variables but
    specifically for types.

    Attributes:
        name: The undefined type constructor name
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

        message = f"Undefined type: '{name}'"
        diagnostic = None
        if self.available:
            suggestions = ", ".join(f"'{n}'" for n in self.available[:5])
            diagnostic = f"Did you mean one of: {suggestions}?"
        else:
            diagnostic = (
                f"Type constructor '{name}' is not defined. Check imports and type definitions."
            )

        super().__init__(message, location, None, diagnostic)
        # Store type separately since base expects SurfaceTerm
        self.type_term = type_term
