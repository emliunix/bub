"""Unification logic for System F surface language type inference.

This module implements Robinson-style unification with occurs check and
substitution management for the surface language type elaboration phase.

Key components:
- Substitution: Maps meta type variables to their resolved types
- unify(): Unifies two types, returning an updated substitution
- occurs_check(): Detects infinite types during unification
- Meta type variables: Fresh type variables created during inference
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from systemf.core.types import (
    Type,
    TypeVar,
    TypeArrow,
    TypeForall,
    TypeConstructor,
    PrimitiveType,
    TypeSkolem,
)
from systemf.surface.inference.errors import (
    UnificationError,
    InfiniteTypeError,
    TypeMismatchError,
)
from systemf.utils.location import Location


# Module-level counter for generating unique meta variable ids
_meta_id_counter = 0


# =============================================================================
# Meta Type Variables
# =============================================================================


@dataclass(frozen=True)
class TMeta(Type):
    """Meta type variable for unification.

    Meta variables are fresh type variables created during type inference.
    They are placeholders that get unified with concrete types. Each meta
    variable has a unique id and an optional name for debugging.

    Attributes:
        id: Unique identifier for this meta variable
        name: Optional name for debugging (e.g., "_a", "_b")

    Example:
        >>> meta1 = TMeta.fresh("a")
        >>> meta2 = TMeta.fresh("b")
        >>> meta1.id != meta2.id
        True
    """

    id: int
    name: Optional[str] = None

    @classmethod
    def fresh(cls, name: Optional[str] = None) -> TMeta:
        """Create a fresh meta type variable with a unique id.

        Args:
            name: Optional name prefix for debugging

        Returns:
            A new TMeta with a unique id
        """
        global _meta_id_counter
        current_id = _meta_id_counter
        _meta_id_counter += 1
        return cls(current_id, name)

    def __str__(self) -> str:
        if self.name:
            return f"_{self.name}"
        return f"_{self.id}"

    def free_vars(self) -> set[str]:
        """Return empty set - meta vars don't contribute to free vars."""
        return set()

    def substitute(self, subst: dict[str, Type]) -> Type:
        """Meta variables are not affected by normal substitution."""
        return self


# =============================================================================
# Substitution
# =============================================================================


@dataclass(frozen=True)
class Substitution:
    """Immutable substitution mapping meta type variables to types.

    A substitution maps TMeta variables (by their id) to their resolved types.
    The substitution is applied recursively to resolve chains of meta variables.

    Attributes:
        mapping: Dictionary from meta var id to resolved type

    Example:
        >>> subst = Substitution.empty()
        >>> meta = TMeta.fresh("a")
        >>> subst = subst.extend(meta, PrimitiveType("Int"))
        >>> subst.apply_to_type(meta)
        PrimitiveType("Int")
    """

    mapping: dict[int, Type] = field(default_factory=dict)

    @staticmethod
    def empty() -> Substitution:
        """Create an empty substitution."""
        return Substitution({})

    @staticmethod
    def singleton(meta: TMeta, ty: Type) -> Substitution:
        """Create a substitution with a single mapping."""
        return Substitution({meta.id: ty})

    def lookup(self, meta: TMeta) -> Optional[Type]:
        """Look up a meta variable in the substitution.

        Args:
            meta: The meta variable to look up

        Returns:
            The resolved type if found, None otherwise
        """
        return self.mapping.get(meta.id)

    def extend(self, meta: TMeta, ty: Type) -> Substitution:
        """Create a new substitution with an additional mapping.

        Args:
            meta: The meta variable to map
            ty: The type to map it to

        Returns:
            A new Substitution with the additional binding
        """
        new_mapping = dict(self.mapping)
        new_mapping[meta.id] = ty
        return Substitution(new_mapping)

    def apply_to_type(self, ty: Type) -> Type:
        """Apply this substitution to a type, resolving all meta variables.

        This recursively resolves meta variables, following chains of
        substitutions until a concrete type is found.

        Args:
            ty: The type to apply the substitution to

        Returns:
            The type with all meta variables resolved
        """
        match ty:
            case TMeta(id=meta_id):
                # Look up the meta variable
                if meta_id in self.mapping:
                    resolved = self.mapping[meta_id]
                    # Recursively apply to handle chains
                    return self.apply_to_type(resolved)
                return ty

            case TypeVar(_) | TypeSkolem(_):
                # Regular type variables and skolems are not substituted
                return ty

            case TypeArrow(arg, ret, param_doc):
                return TypeArrow(self.apply_to_type(arg), self.apply_to_type(ret), param_doc)

            case TypeForall(var, body):
                # Apply substitution to body, avoiding capture
                return TypeForall(var, self.apply_to_type(body))

            case TypeConstructor(name, args):
                return TypeConstructor(name, [self.apply_to_type(arg) for arg in args])

            case PrimitiveType(_):
                return ty

            case _:
                raise TypeError(f"Unknown type: {ty}")

    def compose(self, other: Substitution) -> Substitution:
        """Compose substitutions: self ∘ other (apply other first, then self).

        Returns a new substitution equivalent to:
        λt. self.apply_to_type(other.apply_to_type(t))

        Args:
            other: The substitution to apply first

        Returns:
            The composed substitution
        """
        # Apply self to all values in other
        new_mapping = {var_id: self.apply_to_type(ty) for var_id, ty in other.mapping.items()}
        # Add mappings from self that aren't in other
        for var_id, ty in self.mapping.items():
            if var_id not in new_mapping:
                new_mapping[var_id] = ty
        return Substitution(new_mapping)

    def __str__(self) -> str:
        items = ", ".join(f"{TMeta(k)} -> {v}" for k, v in self.mapping.items())
        return f"{{{items}}}"


# =============================================================================
# Occurs Check
# =============================================================================


def occurs_check(meta: TMeta, ty: Type, subst: Substitution) -> bool:
    """Check if a meta type variable occurs in a type.

    This detects infinite types (e.g., unifying _a with _a -> Int).
    The check is performed after applying the current substitution to
    ensure we detect cycles through resolved meta variables.

    Args:
        meta: The meta variable to check for
        ty: The type to check within
        subst: Current substitution (for resolving meta vars)

    Returns:
        True if meta occurs in ty (would create infinite type)

    Example:
        >>> subst = Substitution.empty()
        >>> meta = TMeta.fresh("a")
        >>> occurs_check(meta, TypeArrow(meta, PrimitiveType("Int")), subst)
        True
        >>> occurs_check(meta, PrimitiveType("Int"), subst)
        False
    """
    # First, fully resolve the type by applying substitution
    resolved_ty = subst.apply_to_type(ty)
    return _occurs_check_recursive(meta, resolved_ty)


def _occurs_check_recursive(meta: TMeta, ty: Type) -> bool:
    """Recursive helper for occurs check.

    Args:
        meta: The meta variable to check for
        ty: The type to check within (already resolved)

    Returns:
        True if meta occurs in ty
    """
    match ty:
        case TMeta(id=other_id):
            return meta.id == other_id

        case TypeVar(_) | TypeSkolem(_):
            return False

        case TypeArrow(arg, ret, _):
            return _occurs_check_recursive(meta, arg) or _occurs_check_recursive(meta, ret)

        case TypeForall(_, body):
            return _occurs_check_recursive(meta, body)

        case TypeConstructor(_, args):
            return any(_occurs_check_recursive(meta, arg) for arg in args)

        case PrimitiveType(_):
            return False

        case _:
            raise TypeError(f"Unknown type: {ty}")


def _subst_type_var_in_type(ty: Type, var: str, replacement: Type) -> Type:
    """Substitute free occurrences of TypeVar(var) with replacement."""
    match ty:
        case TypeVar(name) if name == var:
            return replacement
        case TypeVar(_) | TMeta(_) | PrimitiveType(_) | TypeSkolem():
            return ty
        case TypeArrow(arg, ret, doc):
            return TypeArrow(
                _subst_type_var_in_type(arg, var, replacement),
                _subst_type_var_in_type(ret, var, replacement),
                doc,
            )
        case TypeForall(bv, body) if bv == var:
            return ty  # shadowed
        case TypeForall(bv, body):
            return TypeForall(bv, _subst_type_var_in_type(body, var, replacement))
        case TypeConstructor(name, args):
            return TypeConstructor(
                name,
                [_subst_type_var_in_type(a, var, replacement) for a in args],
            )
        case _:
            return ty


# =============================================================================
# Unification
# =============================================================================


def unify(
    t1: Type, t2: Type, subst: Substitution, location: Optional[Location] = None
) -> Substitution:
    """Unify two types, returning an updated substitution.

    Implements Robinson-style unification algorithm with occurs check.
    The substitution is threaded through recursively, with each successful
    unification potentially extending it.

    Args:
        t1: First type to unify
        t2: Second type to unify
        subst: Current substitution
        location: Optional source location for error reporting

    Returns:
        An updated substitution that makes t1 and t2 equal

    Raises:
        InfiniteTypeError: If occurs check fails (infinite type detected)
        UnificationError: If types cannot be unified

    Example:
        >>> subst = Substitution.empty()
        >>> meta = TMeta.fresh("a")
        >>> subst = unify(meta, PrimitiveType("Int"), subst)
        >>> subst.apply_to_type(meta)
        PrimitiveType("Int")
    """
    # Apply current substitution to both types
    t1 = subst.apply_to_type(t1)
    t2 = subst.apply_to_type(t2)

    match t1, t2:
        # Same meta variable
        case TMeta(id=id1), TMeta(id=id2) if id1 == id2:
            return subst

        # Skolem vs skolem: must be identical (name + unique)
        case TypeSkolem(name1, u1), TypeSkolem(name2, u2):
            if name1 == name2 and u1 == u2:
                return subst
            raise UnificationError(t1, t2, location, None)

        # Skolem vs anything else (including Meta): rigid, cannot unify
        # These must come BEFORE meta variable cases to prevent meta from
        # unifying with a rigid skolem
        case TypeSkolem(), _:
            raise UnificationError(t1, t2, location, None)

        case _, TypeSkolem():
            raise UnificationError(t1, t2, location, None)

        # t1 is a meta variable
        case TMeta() as meta, _:
            if occurs_check(meta, t2, subst):
                raise InfiniteTypeError(str(meta), t2, location, None)
            return subst.extend(meta, t2)

        # t2 is a meta variable
        case _, TMeta() as meta:
            if occurs_check(meta, t1, subst):
                raise InfiniteTypeError(str(meta), t1, location, None)
            return subst.extend(meta, t1)

        # Both are type variables
        case TypeVar(name1), TypeVar(name2) if name1 == name2:
            return subst

        # Type variable vs other (cannot unify)
        case TypeVar(_), _:
            raise UnificationError(t1, t2, location, None)

        case _, TypeVar(_):
            raise UnificationError(t1, t2, location, None)

        # Both are function types
        case TypeArrow(arg1, ret1, _), TypeArrow(arg2, ret2, _):
            subst = unify(arg1, arg2, subst, location)
            # Apply substitution before unifying return types
            ret1 = subst.apply_to_type(ret1)
            ret2 = subst.apply_to_type(ret2)
            return unify(ret1, ret2, subst, location)

        # Both are forall types (first-order unification)
        case TypeForall(var1, body1), TypeForall(var2, body2):
            if var1 == var2:
                return unify(body1, body2, subst, location)
            else:
                # Alpha-rename: replace var2 with var1 in body2
                renamed_body2 = _subst_type_var_in_type(body2, var2, TypeVar(var1))
                return unify(body1, renamed_body2, subst, location)

        # Both are type constructors
        case TypeConstructor(name1, args1), TypeConstructor(name2, args2):
            if name1 != name2:
                raise UnificationError(t1, t2, location, None)
            if len(args1) != len(args2):
                raise UnificationError(t1, t2, location, None)

            # Unify arguments pairwise, threading the substitution
            current_subst = subst
            for arg1, arg2 in zip(args1, args2):
                arg1 = current_subst.apply_to_type(arg1)
                arg2 = current_subst.apply_to_type(arg2)
                current_subst = unify(arg1, arg2, current_subst, location)

            return current_subst

        # Both are primitive types
        case PrimitiveType(name1), PrimitiveType(name2):
            if name1 != name2:
                raise UnificationError(t1, t2, location, None)
            return subst

        # Different type constructors - cannot unify
        case _:
            raise UnificationError(t1, t2, location, None)


# Utility Functions
# =============================================================================


def resolve_type(ty: Type, subst: Substitution) -> Type:
    """Fully resolve a type by applying substitution and expanding meta vars.

    Args:
        ty: The type to resolve
        subst: The substitution to apply

    Returns:
        The fully resolved type with no meta variables
    """
    resolved = subst.apply_to_type(ty)

    # Keep applying until no more changes (handles chains)
    while True:
        new_resolved = subst.apply_to_type(resolved)
        if new_resolved == resolved:
            break
        resolved = new_resolved

    return resolved


def is_meta_variable(ty: Type) -> bool:
    """Check if a type is a meta variable.

    Args:
        ty: The type to check

    Returns:
        True if ty is a TMeta
    """
    return isinstance(ty, TMeta)


def is_unresolved_meta(ty: Type, subst: Substitution) -> bool:
    """Check if a type is an unresolved meta variable.

    Args:
        ty: The type to check
        subst: The current substitution

    Returns:
        True if ty is a TMeta not mapped in subst
    """
    match ty:
        case TMeta() as meta:
            return subst.lookup(meta) is None
        case _:
            return False
