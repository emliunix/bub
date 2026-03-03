"""Scope context for tracking name-to-index mapping during scope checking.

The ScopeContext maintains the binding environment for both term variables
and type variables, mapping names to de Bruijn indices (0 = most recent binder).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScopeContext:
    """Tracks name → de Bruijn index mapping for scope checking.

    De Bruijn indices are used to represent variable references in a way that
    is insensitive to alpha-renaming. Index 0 refers to the most recent binder,
    index 1 to the second most recent, etc.

    Attributes:
        term_names: List of bound term variable names, index 0 = most recent
        type_names: List of bound type variable names, index 0 = most recent
        globals: Set of global names that are always in scope

    Example:
        >>> ctx = ScopeContext()
        >>> ctx = ctx.extend_term("x")
        >>> ctx = ctx.extend_term("y")
        >>> ctx.lookup_term("y")  # Most recent
        0
        >>> ctx.lookup_term("x")  # Second most recent
        1
    """

    term_names: list[str] = field(default_factory=list)
    type_names: list[str] = field(default_factory=list)
    globals: set[str] = field(default_factory=set)

    def lookup_term(self, name: str) -> int | None:
        """Get the de Bruijn index for a term variable name.

        Args:
            name: The variable name to look up

        Returns:
            The de Bruijn index (0 = most recent binder), or None if not found

        Example:
            >>> ctx = ScopeContext(term_names=["y", "x"])
            >>> ctx.lookup_term("y")
            0
            >>> ctx.lookup_term("x")
            1
            >>> ctx.lookup_term("z")
            None
        """
        for i, n in enumerate(self.term_names):
            if n == name:
                return i
        return None

    def lookup_type(self, name: str) -> int:
        """Get the de Bruijn index for a type variable name.

        Args:
            name: The type variable name to look up

        Returns:
            The de Bruijn index (0 = most recent binder)

        Raises:
            NameError: If the type name is not bound in the current scope

        Example:
            >>> ctx = ScopeContext(type_names=["b", "a"])
            >>> ctx.lookup_type("b")
            0
            >>> ctx.lookup_type("a")
            1
        """
        for i, n in enumerate(self.type_names):
            if n == name:
                return i
        raise NameError(f"Undefined type variable '{name}'")

    def extend_term(self, name: str) -> ScopeContext:
        """Create a new context with an additional term variable binding.

        The new binding becomes index 0, and all existing bindings are
        shifted by 1.

        Args:
            name: The variable name to bind

        Returns:
            A new ScopeContext with the additional binding

        Example:
            >>> ctx = ScopeContext(term_names=["x"])
            >>> new_ctx = ctx.extend_term("y")
            >>> new_ctx.lookup_term("y")
            0
            >>> new_ctx.lookup_term("x")
            1
            >>> ctx.lookup_term("x")  # Original unchanged
            0
        """
        return ScopeContext(
            term_names=[name] + self.term_names,
            type_names=self.type_names,
            globals=self.globals,
        )

    def extend_type(self, name: str) -> ScopeContext:
        """Create a new context with an additional type variable binding.

        The new binding becomes index 0, and all existing bindings are
        shifted by 1.

        Args:
            name: The type variable name to bind

        Returns:
            A new ScopeContext with the additional binding

        Example:
            >>> ctx = ScopeContext(type_names=["a"])
            >>> new_ctx = ctx.extend_type("b")
            >>> new_ctx.lookup_type("b")
            0
            >>> new_ctx.lookup_type("a")
            1
        """
        return ScopeContext(
            term_names=self.term_names,
            type_names=[name] + self.type_names,
            globals=self.globals,
        )

    def add_global(self, name: str) -> ScopeContext:
        """Create a new context with an additional global name.

        Args:
            name: The global name to add

        Returns:
            A new ScopeContext with the additional global
        """
        new_globals = self.globals | {name}
        return ScopeContext(
            term_names=self.term_names,
            type_names=self.type_names,
            globals=new_globals,
        )

    def is_bound_term(self, name: str) -> bool:
        """Check if a term name is bound in the current scope.

        Args:
            name: The variable name to check

        Returns:
            True if the name is bound, False otherwise
        """
        return name in self.term_names

    def is_bound_type(self, name: str) -> bool:
        """Check if a type name is bound in the current scope.

        Args:
            name: The type variable name to check

        Returns:
            True if the name is bound, False otherwise
        """
        return name in self.type_names

    def is_global(self, name: str) -> bool:
        """Check if a name is a known global.

        Args:
            name: The name to check

        Returns:
            True if the name is a global, False otherwise
        """
        return name in self.globals

    def __repr__(self) -> str:
        """Return a string representation for debugging."""
        return (
            f"ScopeContext("
            f"terms={self.term_names}, "
            f"types={self.type_names}, "
            f"globals={self.globals}"
            f")"
        )
