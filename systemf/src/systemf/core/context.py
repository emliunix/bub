"""Typing contexts for System F."""

from dataclasses import dataclass

from systemf.core.types import Type


@dataclass
class Context:
    """Typing context Γ with term and type variables.

    - term_vars: Types of bound term variables (index 0 = most recent)
    - type_vars: Bound type variables (by name)
    """

    term_vars: list[Type]
    type_vars: set[str]

    def __init__(self, term_vars: list[Type] | None = None, type_vars: set[str] | None = None):
        self.term_vars = term_vars if term_vars is not None else []
        self.type_vars = type_vars if type_vars is not None else set()

    @staticmethod
    def empty() -> "Context":
        """Create an empty context."""
        return Context([], set())

    def lookup_type(self, index: int) -> Type:
        """Look up the type of a variable by de Bruijn index.

        Index 0 is the most recently bound variable.

        Args:
            index: de Bruijn index (0 = nearest binder)

        Returns:
            The type of the variable

        Raises:
            IndexError: If index is out of bounds
        """
        if index < 0 or index >= len(self.term_vars):
            raise IndexError(
                f"Variable index {index} out of bounds in context with {len(self.term_vars)} variables"
            )
        return self.term_vars[index]

    def extend_term(self, ty: Type) -> "Context":
        """Extend context with a new term variable binding.

        The new variable becomes index 0, shifting existing variables up by 1.

        Args:
            ty: Type of the new variable

        Returns:
            A new context with the binding added
        """
        return Context([ty] + self.term_vars, self.type_vars)

    def extend_type(self, var: str) -> "Context":
        """Extend context with a new type variable binding.

        Args:
            var: Name of the type variable

        Returns:
            A new context with the type variable added
        """
        new_type_vars = set(self.type_vars)
        new_type_vars.add(var)
        return Context(list(self.term_vars), new_type_vars)

    def __len__(self) -> int:
        """Return the number of term variables in context."""
        return len(self.term_vars)

    def __str__(self) -> str:
        terms = ", ".join(f"x{i}:{t}" for i, t in enumerate(self.term_vars))
        types = ", ".join(sorted(self.type_vars))
        return f"Context(terms=[{terms}], types=[{types}])"
