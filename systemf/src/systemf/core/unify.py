"""Unification algorithm for System F types."""

from dataclasses import dataclass

from systemf.core.types import Type, TypeArrow, TypeConstructor, TypeForall, TypeVar
from systemf.core.errors import OccursCheckError, UnificationError


@dataclass(frozen=True)
class Substitution:
    """Immutable substitution mapping type variables to types."""

    mapping: dict[str, Type]

    @staticmethod
    def empty() -> "Substitution":
        """Create an empty substitution."""
        return Substitution({})

    @staticmethod
    def singleton(var: str, t: Type) -> "Substitution":
        """Create a substitution with a single mapping."""
        return Substitution({var: t})

    def apply(self, t: Type) -> Type:
        """Apply this substitution to a type."""
        if isinstance(t, TypeVar):
            if t.name in self.mapping:
                return self.mapping[t.name]
            return t
        elif isinstance(t, TypeArrow):
            return TypeArrow(self.apply(t.arg), self.apply(t.ret))
        elif isinstance(t, TypeForall):
            # Don't substitute bound variables
            filtered_mapping = {k: v for k, v in self.mapping.items() if k != t.var}
            if not filtered_mapping:
                return t
            return TypeForall(t.var, Substitution(filtered_mapping).apply(t.body))
        elif isinstance(t, TypeConstructor):
            return TypeConstructor(t.name, [self.apply(arg) for arg in t.args])
        else:
            raise TypeError(f"Unknown type: {t}")

    def compose(self, other: "Substitution") -> "Substitution":
        """Compose substitutions: self ∘ other (apply other first, then self).

        Returns a new substitution equivalent to λt. self.apply(other.apply(t))
        """
        # Apply self to all values in other
        new_mapping = {var: self.apply(ty) for var, ty in other.mapping.items()}
        # Add mappings from self that aren't in other
        for var, ty in self.mapping.items():
            if var not in new_mapping:
                new_mapping[var] = ty
        return Substitution(new_mapping)

    def __str__(self) -> str:
        items = ", ".join(f"{k} -> {v}" for k, v in self.mapping.items())
        return f"{{{items}}}"


def occurs_in(var: str, t: Type) -> bool:
    """Check if a type variable occurs in a type.

    Args:
        var: Name of the type variable
        t: Type to check

    Returns:
        True if var occurs in t
    """
    if isinstance(t, TypeVar):
        return t.name == var
    elif isinstance(t, TypeArrow):
        return occurs_in(var, t.arg) or occurs_in(var, t.ret)
    elif isinstance(t, TypeForall):
        # Bound variable doesn't count as occurring
        if t.var == var:
            return False
        return occurs_in(var, t.body)
    elif isinstance(t, TypeConstructor):
        return any(occurs_in(var, arg) for arg in t.args)
    else:
        raise TypeError(f"Unknown type: {t}")


def unify(t1: Type, t2: Type) -> Substitution:
    """Compute the most general unifier of two types.

    Implements Robinson's unification algorithm with occurs check.

    Args:
        t1: First type
        t2: Second type

    Returns:
        A substitution θ such that θ(t1) = θ(t2)

    Raises:
        UnificationError: If types cannot be unified
        OccursCheckError: If occurs check fails (infinite type)
    """
    # Both are the same variable
    if isinstance(t1, TypeVar) and isinstance(t2, TypeVar) and t1.name == t2.name:
        return Substitution.empty()

    # t1 is a variable
    if isinstance(t1, TypeVar):
        if occurs_in(t1.name, t2):
            raise OccursCheckError(t1.name, t2)
        return Substitution.singleton(t1.name, t2)

    # t2 is a variable
    if isinstance(t2, TypeVar):
        if occurs_in(t2.name, t1):
            raise OccursCheckError(t2.name, t1)
        return Substitution.singleton(t2.name, t1)

    # Both are arrow types
    if isinstance(t1, TypeArrow) and isinstance(t2, TypeArrow):
        s1 = unify(t1.arg, t2.arg)
        s2 = unify(s1.apply(t1.ret), s1.apply(t2.ret))
        return s2.compose(s1)

    # Both are forall types (first-order unification only)
    if isinstance(t1, TypeForall) and isinstance(t2, TypeForall):
        # For first-order unification, we unify bodies directly
        # This is a simplification - full higher-order unification is complex
        return unify(t1.body, t2.body)

    # Both are type constructors
    if isinstance(t1, TypeConstructor) and isinstance(t2, TypeConstructor):
        if t1.name != t2.name:
            raise UnificationError(t1, t2)
        if len(t1.args) != len(t2.args):
            raise UnificationError(t1, t2)

        subst = Substitution.empty()
        current_t1 = t1
        current_t2 = t2

        for i in range(len(t1.args)):
            s = unify(subst.apply(current_t1.args[i]), subst.apply(current_t2.args[i]))
            subst = s.compose(subst)

        return subst

    # Types are different constructors
    raise UnificationError(t1, t2)
