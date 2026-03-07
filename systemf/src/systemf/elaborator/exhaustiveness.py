"""Pattern exhaustiveness and redundancy checking for System F case expressions.

This module implements pattern exhaustiveness checking to ensure that case
expressions cover all possible values of the scrutinee type. It also detects
redundant patterns (patterns that can never match because previous patterns
are more general).

Key concepts:
- Exhaustiveness: All constructors of a type must be covered
- Redundancy: A pattern is redundant if it's covered by previous patterns
- Pattern matrix: A data structure for efficient pattern analysis

Example:
    case x of
        Zero -> ...
        Succ n -> ...

    This is exhaustive for Nat (covers both constructors).

    case x of
        Zero -> ...
        _ -> ...
        Succ n -> ...

    The 'Succ n' branch is redundant (covered by '_').
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from systemf.core.types import Type, TypeConstructor
from systemf.core.ast import Branch, Pattern


@dataclass
class ExhaustivenessError(Exception):
    """Error raised when patterns are not exhaustive."""

    missing_patterns: list[str]
    message: str = ""

    def __str__(self) -> str:
        if not self.message:
            return f"Non-exhaustive patterns, missing: {', '.join(self.missing_patterns)}"
        return self.message


@dataclass
class RedundancyError(Exception):
    """Error raised when patterns are redundant."""

    redundant_patterns: list[int]  # Indices of redundant patterns
    message: str = ""

    def __str__(self) -> str:
        if not self.message:
            indices_str = ", ".join(str(i) for i in self.redundant_patterns)
            return f"Redundant patterns at indices: {indices_str}"
        return self.message


@dataclass
class PatternMatrix:
    """Matrix representation of patterns for exhaustiveness analysis.

    Each row represents a pattern with columns for each position.
    A wildcard '_' matches any constructor.

    Attributes:
        rows: List of pattern rows, where each row is a list of pattern elements
        constructors: Set of available constructors for each column
    """

    rows: list[list[str | None]] = field(default_factory=list)
    """Rows of the matrix. None represents wildcard '_'."""

    def add_row(self, patterns: list[str | None]) -> None:
        """Add a pattern row to the matrix."""
        self.rows.append(patterns)

    def is_exhaustive(self, all_constructors: set[str]) -> tuple[bool, set[str]]:
        """Check if the matrix covers all constructors.

        Args:
            all_constructors: Set of all possible constructors for the type

        Returns:
            Tuple of (is_exhaustive, missing_constructors)
        """
        if not self.rows:
            return (False, all_constructors)

        # Collect all constructors that appear in the first column
        covered: set[str] = set()
        for row in self.rows:
            if row and row[0] is not None:
                covered.add(row[0])
            elif row and row[0] is None:
                # Wildcard covers all constructors
                return (True, set())

        missing = all_constructors - covered
        return (len(missing) == 0, missing)

    def find_redundant(self) -> list[int]:
        """Find indices of redundant pattern rows.

        A pattern is redundant if all constructors it covers are already
        covered by previous patterns.

        Returns:
            List of indices of redundant patterns
        """
        redundant: list[int] = []
        covered_so_far: set[str] = set()
        full_coverage: bool = False

        for i, row in enumerate(self.rows):
            if not row:
                continue

            first_col = row[0]
            if first_col is None:
                # Wildcard - if we already have full coverage, this is redundant
                if full_coverage:
                    redundant.append(i)
                # Wildcard covers everything
                full_coverage = True
            else:
                # Specific constructor
                if full_coverage or first_col in covered_so_far:
                    # Already covered
                    redundant.append(i)
                else:
                    covered_so_far.add(first_col)

        return redundant


@dataclass
class TypeConstructors:
    """Registry of type constructors for exhaustiveness checking."""

    # Maps type name to set of constructor names
    _types: dict[str, set[str]] = field(default_factory=dict)

    def register_type(self, type_name: str, constructors: list[str]) -> None:
        """Register a type with its constructors."""
        self._types[type_name] = set(constructors)

    def get_constructors(self, type_name: str) -> set[str]:
        """Get all constructors for a type.

        Args:
            type_name: Name of the type

        Returns:
            Set of constructor names

        Raises:
            KeyError: If type is not registered
        """
        if type_name not in self._types:
            raise KeyError(f"Type '{type_name}' not registered for exhaustiveness checking")
        return self._types[type_name]

    def is_registered(self, type_name: str) -> bool:
        """Check if a type is registered."""
        return type_name in self._types


# Global registry of type constructors
_type_registry = TypeConstructors()


def register_type(type_name: str, constructors: list[str]) -> None:
    """Register a type with its constructors.

    Args:
        type_name: Name of the type (e.g., "Nat", "Bool")
        constructors: List of constructor names

    Example:
        >>> register_type("Nat", ["Zero", "Succ"])
        >>> register_type("Bool", ["True", "False"])
    """
    _type_registry.register_type(type_name, constructors)


def check_exhaustiveness(
    branches: list[Branch],
    scrut_type: Type,
) -> tuple[bool, list[str]]:
    """Check if patterns are exhaustive for the given scrutinee type.

    Args:
        branches: List of case branches with patterns
        scrut_type: Type of the scrutinee

    Returns:
        Tuple of (is_exhaustive, list_of_missing_patterns)

    Example:
        >>> branches = [
        ...     Branch(Pattern("Zero", []), ...),
        ...     Branch(Pattern("Succ", ["n"]), ...),
        ... ]
        >>> is_exhaustive, missing = check_exhaustiveness(branches, TypeConstructor("Nat", []))
        >>> is_exhaustive
        True
    """
    # Extract constructor names from patterns
    matrix = PatternMatrix()
    for branch in branches:
        constructor = branch.pattern.constructor
        # None represents wildcard
        pattern_elem = None if constructor == "_" else constructor
        matrix.add_row([pattern_elem])

    # Get constructors for the type
    match scrut_type:
        case TypeConstructor(name=type_name):
            if not _type_registry.is_registered(type_name):
                # Unknown type - assume exhaustive (can't check)
                return (True, [])
            all_constructors = _type_registry.get_constructors(type_name)
        case _:
            # Non-constructor type - assume exhaustive
            return (True, [])

    # Check exhaustiveness
    is_exhaustive, missing = matrix.is_exhaustive(all_constructors)
    missing_list = sorted(missing) if missing else []
    return (is_exhaustive, missing_list)


def check_redundancy(branches: list[Branch]) -> list[int]:
    """Check for redundant patterns in case branches.

    A pattern is redundant if it's completely covered by previous patterns.

    Args:
        branches: List of case branches

    Returns:
        List of indices of redundant branches

    Example:
        >>> branches = [
        ...     Branch(Pattern("Zero", []), ...),
        ...     Branch(Pattern("_", []), ...),  # Wildcard
        ...     Branch(Pattern("Succ", ["n"]), ...),  # Redundant!
        ... ]
        >>> check_redundancy(branches)
        [2]
    """
    matrix = PatternMatrix()
    for branch in branches:
        constructor = branch.pattern.constructor
        pattern_elem = None if constructor == "_" else constructor
        matrix.add_row([pattern_elem])

    return matrix.find_redundant()


def check_patterns(
    branches: list[Branch],
    scrut_type: Type,
    raise_on_error: bool = True,
) -> tuple[bool, list[str], list[int]]:
    """Comprehensive pattern checking: exhaustiveness and redundancy.

    Args:
        branches: List of case branches
        scrut_type: Type of the scrutinee
        raise_on_error: If True, raise exceptions on errors

    Returns:
        Tuple of (is_exhaustive, missing_patterns, redundant_indices)

    Raises:
        ExhaustivenessError: If patterns are not exhaustive and raise_on_error is True
        RedundancyError: If patterns are redundant and raise_on_error is True

    Example:
        >>> register_type("Nat", ["Zero", "Succ"])
        >>> branches = [Branch(Pattern("Zero", []), ...)]
        >>> check_patterns(branches, TypeConstructor("Nat", []))
        Traceback (most recent call last):
            ...
        ExhaustivenessError: Non-exhaustive patterns, missing: Succ
    """
    # Check exhaustiveness
    is_exhaustive, missing = check_exhaustiveness(branches, scrut_type)

    # Check redundancy
    redundant = check_redundancy(branches)

    if raise_on_error:
        if not is_exhaustive:
            raise ExhaustivenessError(missing_patterns=missing)
        if redundant:
            raise RedundancyError(redundant_patterns=redundant)

    return (is_exhaustive, missing, redundant)


def get_missing_patterns(
    branches: list[Branch],
    scrut_type: Type,
) -> list[str]:
    """Get a list of missing patterns for non-exhaustive case expressions.

    Args:
        branches: List of case branches
        scrut_type: Type of the scrutinee

    Returns:
        List of missing constructor names

    Example:
        >>> register_type("Nat", ["Zero", "Succ"])
        >>> branches = [Branch(Pattern("Zero", []), ...)]
        >>> get_missing_patterns(branches, TypeConstructor("Nat", []))
        ['Succ']
    """
    _, missing = check_exhaustiveness(branches, scrut_type)
    return missing


# Register common types
register_type("Bool", ["True", "False"])
register_type("Nat", ["Zero", "Succ"])
register_type("List", ["Nil", "Cons"])
register_type("Maybe", ["Nothing", "Just"])
register_type("Either", ["Left", "Right"])
register_type("Pair", ["Pair"])
register_type("Unit", ["Unit"])
register_type("Ordering", ["LT", "EQ", "GT"])
