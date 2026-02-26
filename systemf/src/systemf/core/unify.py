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
        match t:
            case TypeVar(name):
                if name in self.mapping:
                    return self.mapping[name]
                return t
            case TypeArrow(arg, ret):
                return TypeArrow(self.apply(arg), self.apply(ret))
            case TypeForall(var, body):
                # Don't substitute bound variables
                filtered_mapping = {k: v for k, v in self.mapping.items() if k != var}
                if not filtered_mapping:
                    return t
                return TypeForall(var, Substitution(filtered_mapping).apply(body))
            case TypeConstructor(name, args):
                return TypeConstructor(name, [self.apply(arg) for arg in args])
            case _:
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
    match t:
        case TypeVar(name):
            return name == var
        case TypeArrow(arg, ret):
            return occurs_in(var, arg) or occurs_in(var, ret)
        case TypeForall(bound_var, body):
            # Bound variable doesn't count as occurring
            if bound_var == var:
                return False
            return occurs_in(var, body)
        case TypeConstructor(_, args):
            return any(occurs_in(var, arg) for arg in args)
        case _:
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
    match t1, t2:
        # Both are the same variable
        case TypeVar(name1), TypeVar(name2) if name1 == name2:
            return Substitution.empty()

        # t1 is a variable
        case TypeVar(name), _:
            if occurs_in(name, t2):
                raise OccursCheckError(name, t2)
            return Substitution.singleton(name, t2)

        # t2 is a variable
        case _, TypeVar(name):
            if occurs_in(name, t1):
                raise OccursCheckError(name, t1)
            return Substitution.singleton(name, t1)

        # Both are arrow types
        case TypeArrow(arg1, ret1), TypeArrow(arg2, ret2):
            s1 = unify(arg1, arg2)
            s2 = unify(s1.apply(ret1), s1.apply(ret2))
            return s2.compose(s1)

        # Both are forall types (first-order unification only)
        case TypeForall(_, body1), TypeForall(_, body2):
            # For first-order unification, we unify bodies directly
            # This is a simplification - full higher-order unification is complex
            return unify(body1, body2)

        # Both are type constructors
        case TypeConstructor(name1, args1), TypeConstructor(name2, args2):
            if name1 != name2:
                raise UnificationError(t1, t2)
            if len(args1) != len(args2):
                raise UnificationError(t1, t2)

            subst = Substitution.empty()

            for i in range(len(args1)):
                s = unify(subst.apply(args1[i]), subst.apply(args2[i]))
                subst = s.compose(subst)

            return subst

        # Types are different constructors
        case _:
            raise UnificationError(t1, t2)
