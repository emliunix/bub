"""Type registry for managing shadowed type definitions.

This module provides TypeRegistry, which tracks type definitions with versioning
to support REPL-style type redefinition where shadowed types don't unify with
new definitions.

Example:
    >>> from systemf.core.types import TypeConstructor
    >>> from systemf.core.module import TypeDefinition
    >>> registry = TypeRegistry()

    >>> # First definition of T
    >>> v1 = registry.define_type("T", TypeDefinition("T", [], [...]))
    >>> t1 = TypeConstructor("T", [], version=v1)

    >>> # Redefine T
    >>> v2 = registry.define_type("T", TypeDefinition("T", [], [...]))
    >>> t2 = TypeConstructor("T", [], version=v2)

    >>> # They don't unify
    >>> t1 == t2
    False
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from systemf.core.types import TypeConstructor


@dataclass
class TypeDefinitionInfo:
    """Information about a type definition.

    Attributes:
        name: Type name
        version: Version number (0, 1, 2, ...)
        location: Source location where defined
        params: Type parameters
        constructors: Data constructors
    """

    name: str
    version: int
    location: Optional[object] = None  # Location object
    params: list[str] = field(default_factory=list)
    constructors: list[tuple[str, list]] = field(default_factory=list)

    def __str__(self) -> str:
        if self.version == 0:
            return f"{self.name}"
        return f"{self.name}#v{self.version}"


@dataclass
class TypeRegistry:
    """Registry for tracking type definitions with versioning.

    The registry maintains a history of type definitions, assigning each
    definition a unique version number. This allows shadowed types to be
    distinguished from new definitions at the type level.

    Key features:
    - Version tracking: Each redefinition increments the version
    - Current lookup: Get the latest version of a type
    - History access: Look up any previous version
    - Term tracking: Track which terms use which type versions

    Example:
        >>> registry = TypeRegistry()

        >>> # Define T for the first time
        >㸾 v1 = registry.define_type("T", TypeDefinitionInfo("T", 0))
        >>> registry.get_current_version("T")
        1

        >>> # Redefine T
        >>> v2 = registry.define_type("T", TypeDefinitionInfo("T", 0))
        >>> registry.get_current_version("T")
        2

        >>> # Check if types are compatible
        >>> registry.are_types_compatible(
        ...     TypeConstructor("T", [], version=1),
        ...     TypeConstructor("T", [], version=2)
        ... )
        False
    """

    # Current version number for each type name (starts at 0, first def is 1)
    _current_versions: dict[str, int] = field(default_factory=dict)

    # All definitions indexed by (name, version)
    _definitions: dict[tuple[str, int], TypeDefinitionInfo] = field(default_factory=dict)

    # Map term names -> (type_name, version) they use
    _term_type_versions: dict[str, list[tuple[str, int]]] = field(default_factory=dict)

    def define_type(self, name: str, info: TypeDefinitionInfo) -> int:
        """Define a new version of a type.

        Assigns the next version number and stores the definition.

        Args:
            name: Type name
            info: Type definition info

        Returns:
            The version number assigned (1, 2, 3, ...)
        """
        version = self._current_versions.get(name, 0) + 1
        self._current_versions[name] = version

        # Update info with assigned version
        info.version = version
        info.name = name

        self._definitions[(name, version)] = info
        return version

    def get_current_version(self, name: str) -> Optional[int]:
        """Get the current (latest) version of a type.

        Args:
            name: Type name

        Returns:
            Current version number, or None if type not defined
        """
        return self._current_versions.get(name)

    def get_definition(self, name: str, version: int) -> Optional[TypeDefinitionInfo]:
        """Get a specific version of a type definition.

        Args:
            name: Type name
            version: Version number

        Returns:
            Type definition info, or None if not found
        """
        return self._definitions.get((name, version))

    def get_current_definition(self, name: str) -> Optional[TypeDefinitionInfo]:
        """Get the current definition of a type.

        Args:
            name: Type name

        Returns:
            Current type definition, or None if not defined
        """
        version = self.get_current_version(name)
        if version is None:
            return None
        return self._definitions.get((name, version))

    def is_current_version(self, type_con: TypeConstructor) -> bool:
        """Check if a TypeConstructor uses the current version.

        Args:
            type_con: Type constructor to check

        Returns:
            True if this is the current version of the type
        """
        current = self.get_current_version(type_con.name)
        if current is None:
            return False
        return type_con.version == current

    def are_types_compatible(self, type1: TypeConstructor, type2: TypeConstructor) -> bool:
        """Check if two type constructors are compatible (same version).

        Args:
            type1: First type
            type2: Second type

        Returns:
            True if types have same name and version
        """
        return type1.name == type2.name and type1.version == type2.version

    def get_version_info(self, type_con: TypeConstructor) -> Optional[TypeDefinitionInfo]:
        """Get definition info for a type constructor.

        Args:
            type_con: Type constructor

        Returns:
            Definition info, or None if not found
        """
        return self._definitions.get((type_con.name, type_con.version))

    def record_term_type_usage(self, term_name: str, type_con: TypeConstructor) -> None:
        """Record that a term uses a specific type version.

        Args:
            term_name: Name of the term
            type_con: Type constructor used
        """
        if term_name not in self._term_type_versions:
            self._term_type_versions[term_name] = []
        self._term_type_versions[term_name].append((type_con.name, type_con.version))

    def get_term_type_versions(self, term_name: str) -> list[tuple[str, int]]:
        """Get all type versions used by a term.

        Args:
            term_name: Name of the term

        Returns:
            List of (type_name, version) tuples
        """
        return self._term_type_versions.get(term_name, [])

    def check_term_uses_current_types(self, term_name: str) -> list[tuple[str, int, int]]:
        """Check if a term uses outdated type versions.

        Args:
            term_name: Name of the term

        Returns:
            List of (type_name, used_version, current_version) for outdated types
        """
        outdated = []
        for type_name, used_version in self._term_type_versions.get(term_name, []):
            current = self.get_current_version(type_name)
            if current is not None and used_version != current:
                outdated.append((type_name, used_version, current))
        return outdated

    def get_all_versions(self, name: str) -> list[TypeDefinitionInfo]:
        """Get all versions of a type definition.

        Args:
            name: Type name

        Returns:
            List of all versions (sorted by version number)
        """
        versions = []
        version = 1
        while (name, version) in self._definitions:
            versions.append(self._definitions[(name, version)])
            version += 1
        return versions

    def is_defined(self, name: str) -> bool:
        """Check if a type has been defined.

        Args:
            name: Type name

        Returns:
            True if type has any definition
        """
        return name in self._current_versions

    def list_defined_types(self) -> list[str]:
        """Get list of all defined type names.

        Returns:
            List of type names
        """
        return list(self._current_versions.keys())


# Global type registry instance
_global_registry: Optional[TypeRegistry] = None


def get_global_registry() -> TypeRegistry:
    """Get the global type registry instance.

    Returns:
        Global TypeRegistry
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = TypeRegistry()
    return _global_registry


def reset_global_registry() -> None:
    """Reset the global type registry (useful for testing)."""
    global _global_registry
    _global_registry = TypeRegistry()
