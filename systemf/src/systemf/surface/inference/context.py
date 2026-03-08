"""Type context for type checking during elaboration.

The TypeContext maintains the type checking environment during Phase 2
(type elaboration). It tracks:
- Term variable types (indexed by de Bruijn index)
- Type variable kinds (for polymorphic types)
- Type constructor signatures (with versioning for shadowing)
- Global type signatures
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from systemf.core.types import Type, TypeArrow, TypeForall, TypeConstructor
from systemf.core.coercion import CoercionAxiom


@dataclass(frozen=True)
class TypeContext:
    """Tracks type bindings and constraints during type elaboration.

    The TypeContext maintains the typing environment similar to ScopeContext
    but for type checking. It uses de Bruijn indices for term variables and
    tracks type variable kinds.

    Supports shadowed type definitions through versioning. When a type is
    redefined, the new definition gets a unique version number, preventing
    accidental unification between old and new definitions.

    Attributes:
        term_types: Types of bound term variables, index 0 = most recent
        type_vars: Bound type variable names with their kinds (or None for *)
        constructors: Type constructor signatures (name -> type scheme)
        globals: Global name -> type signature mapping
        metas: Meta type variables (for unification)
        type_versions: Maps type name -> current version number

    Example:
        >>> ctx = TypeContext()
        >>> ctx = ctx.extend_term(TypeConstructor("Int", []))
        >>> ctx = ctx.extend_term(TypeArrow(TypeConstructor("Int", []), TypeConstructor("Int", [])))
        >>> ctx.lookup_term_type(0)  # Most recent
        TypeArrow(Int -> Int)
        >>> ctx.lookup_term_type(1)  # Second most recent
        Int
    """

    term_types: list[Type] = field(default_factory=list)
    type_vars: list[tuple[str, Optional[Type]]] = field(default_factory=list)
    constructors: dict[str, Type] = field(default_factory=dict)
    globals: dict[str, Type] = field(default_factory=dict)
    metas: list[Type] = field(default_factory=list)
    coercion_axioms: dict[str, CoercionAxiom] = field(default_factory=dict)
    type_versions: dict[str, int] = field(default_factory=dict)

    def lookup_term_type(self, index: int) -> Type:
        """Get the type of a term variable by de Bruijn index.

        Args:
            index: The de Bruijn index (0 = most recent binder)

        Returns:
            The type of the variable at the given index

        Raises:
            IndexError: If the index is out of bounds

        Example:
            >>> ctx = TypeContext(term_types=[TypeConstructor("Int", []), TypeConstructor("Bool", [])])
            >>> ctx.lookup_term_type(0)
            Int
            >>> ctx.lookup_term_type(1)
            Bool
        """
        if index < 0 or index >= len(self.term_types):
            raise IndexError(
                f"Variable index {index} out of bounds in context with {len(self.term_types)} variables"
            )
        return self.term_types[index]

    def lookup_type_var(self, name: str) -> Optional[Type]:
        """Get the kind of a type variable by name.

        Args:
            name: The type variable name to look up

        Returns:
            The kind of the type variable, or None if not found

        Example:
            >>> ctx = TypeContext(type_vars=[("a", None), ("b", None)])
            >>> ctx.lookup_type_var("a")
            None  # Represents kind *
            >>> ctx.lookup_type_var("c")  # Returns None (not found)
        """
        for var_name, kind in self.type_vars:
            if var_name == name:
                return kind
        return None

    def lookup_type_var_index(self, name: str) -> int:
        """Get the de Bruijn index for a type variable name.

        Args:
            name: The type variable name to look up

        Returns:
            The de Bruijn index (0 = most recent binder)

        Raises:
            NameError: If the type variable is not bound

        Example:
            >>> ctx = TypeContext(type_vars=[("b", None), ("a", None)])
            >>> ctx.lookup_type_var_index("b")
            0
            >>> ctx.lookup_type_var_index("a")
            1
        """
        for i, (var_name, _) in enumerate(self.type_vars):
            if var_name == name:
                return i
        raise NameError(f"Undefined type variable '{name}'")

    def lookup_constructor(self, name: str) -> Type:
        """Get the type signature for a type constructor.

        Args:
            name: The constructor name to look up

        Returns:
            The type scheme (polymorphic type) for the constructor

        Raises:
            NameError: If the constructor is not defined

        Example:
            >>> ctx = TypeContext(constructors={"Just": TypeForall("a", TypeArrow(TypeVar("a"), TypeConstructor("Maybe", [TypeVar("a")])))})
            >>> ctx.lookup_constructor("Just")
            forall a. a -> Maybe a
        """
        if name not in self.constructors:
            raise NameError(f"Undefined constructor '{name}'")
        return self.constructors[name]

    def lookup_global(self, name: str) -> Type:
        """Get the type of a global name.

        Args:
            name: The global name to look up

        Returns:
            The type signature of the global

        Raises:
            NameError: If the global is not defined

        Example:
            >>> ctx = TypeContext(globals={"id": TypeForall("a", TypeArrow(TypeVar("a"), TypeVar("a")))})
            >>> ctx.lookup_global("id")
            forall a. a -> a
        """
        if name not in self.globals:
            raise NameError(f"Undefined global '{name}'")
        return self.globals[name]

    def extend_term(self, ty: Type) -> TypeContext:
        """Create a new context with an additional term variable binding.

        The new binding becomes index 0, and all existing bindings are
        shifted by 1.

        Args:
            ty: The type of the new variable

        Returns:
            A new TypeContext with the additional binding

        Example:
            >>> ctx = TypeContext(term_types=[TypeConstructor("Int", [])])
            >>> new_ctx = ctx.extend_term(TypeConstructor("Bool", []))
            >>> new_ctx.lookup_term_type(0)
            Bool
            >>> new_ctx.lookup_term_type(1)
            Int
            >>> ctx.lookup_term_type(0)  # Original unchanged
            Int
        """
        return TypeContext(
            term_types=[ty] + self.term_types,
            type_vars=self.type_vars,
            constructors=self.constructors,
            globals=self.globals,
            metas=self.metas,
            coercion_axioms=self.coercion_axioms,
            type_versions=self.type_versions,
        )

    def extend_type(self, name: str, kind: Optional[Type] = None) -> TypeContext:
        """Create a new context with an additional type variable binding.

        The new binding becomes index 0, and all existing bindings are
        shifted by 1.

        Args:
            name: The type variable name to bind
            kind: The kind of the type variable (None represents *)

        Returns:
            A new TypeContext with the additional binding

        Example:
            >>> ctx = TypeContext(type_vars=[("a", None)])
            >>> new_ctx = ctx.extend_type("b")
            >>> new_ctx.lookup_type_var_index("b")
            0
            >>> new_ctx.lookup_type_var_index("a")
            1
        """
        return TypeContext(
            term_types=self.term_types,
            type_vars=[(name, kind)] + self.type_vars,
            constructors=self.constructors,
            globals=self.globals,
            metas=self.metas,
            coercion_axioms=self.coercion_axioms,
            type_versions=self.type_versions,
        )

    def add_constructor(self, name: str, ty: Type) -> TypeContext:
        """Create a new context with an additional type constructor.

        Args:
            name: The constructor name
            ty: The type scheme for the constructor

        Returns:
            A new TypeContext with the constructor added
        """
        new_constructors = dict(self.constructors)
        new_constructors[name] = ty
        return TypeContext(
            term_types=self.term_types,
            type_vars=self.type_vars,
            constructors=new_constructors,
            globals=self.globals,
            metas=self.metas,
            coercion_axioms=self.coercion_axioms,
            type_versions=self.type_versions,
        )

    def add_global(self, name: str, ty: Type) -> TypeContext:
        """Create a new context with an additional global binding.

        Args:
            name: The global name
            ty: The type signature of the global

        Returns:
            A new TypeContext with the global added
        """
        new_globals = dict(self.globals)
        new_globals[name] = ty
        return TypeContext(
            term_types=self.term_types,
            type_vars=self.type_vars,
            constructors=self.constructors,
            globals=new_globals,
            metas=self.metas,
            coercion_axioms=self.coercion_axioms,
            type_versions=self.type_versions,
        )

    def add_meta(self, meta: Type) -> TypeContext:
        """Create a new context with an additional meta type variable.

        Meta type variables are used during unification for type inference.

        Args:
            meta: The meta type variable to add

        Returns:
            A new TypeContext with the meta added
        """
        return TypeContext(
            term_types=self.term_types,
            type_vars=self.type_vars,
            constructors=self.constructors,
            globals=self.globals,
            metas=self.metas + [meta],
            coercion_axioms=self.coercion_axioms,
            type_versions=self.type_versions,
        )

    def lookup_coercion_axiom(self, name: str) -> CoercionAxiom:
        """Get a coercion axiom by name.

        Args:
            name: The coercion axiom name (e.g., "ax_Nat")

        Returns:
            The coercion axiom

        Raises:
            NameError: If the coercion axiom is not found

        Example:
            >>> ctx = TypeContext(coercion_axioms={"ax_Nat": CoercionAxiom("ax_Nat", Nat, Repr(Nat))})
            >>> ctx.lookup_coercion_axiom("ax_Nat")
            CoercionAxiom(name='ax_Nat', ...)
        """
        if name not in self.coercion_axioms:
            raise NameError(f"Undefined coercion axiom '{name}'")
        return self.coercion_axioms[name]

    def add_coercion_axiom(self, axiom: CoercionAxiom) -> TypeContext:
        """Create a new context with an additional coercion axiom.

        Args:
            axiom: The coercion axiom to add

        Returns:
            A new TypeContext with the axiom added

        Example:
            >>> ctx = TypeContext()
            >>> axiom = CoercionAxiom("ax_Nat", Nat, Repr(Nat))
            >>> new_ctx = ctx.add_coercion_axiom(axiom)
            >>> new_ctx.lookup_coercion_axiom("ax_Nat")
            CoercionAxiom(name='ax_Nat', ...)
        """
        new_axioms = dict(self.coercion_axioms)
        new_axioms[axiom.name] = axiom
        return TypeContext(
            term_types=self.term_types,
            type_vars=self.type_vars,
            constructors=self.constructors,
            globals=self.globals,
            metas=self.metas,
            coercion_axioms=new_axioms,
            type_versions=self.type_versions,
        )

    def is_coercion_axiom(self, name: str) -> bool:
        """Check if a name is a known coercion axiom.

        Args:
            name: The name to check

        Returns:
            True if the name is a coercion axiom

        Example:
            >>> ctx = TypeContext(coercion_axioms={"ax_Nat": ...})
            >>> ctx.is_coercion_axiom("ax_Nat")
            True
            >>> ctx.is_coercion_axiom("ax_Bool")
            False
        """
        return name in self.coercion_axioms

    def get_coercion_axioms(self) -> dict[str, CoercionAxiom]:
        """Get all coercion axioms in the context.

        Returns:
            Dictionary mapping axiom names to coercion axioms
        """
        return dict(self.coercion_axioms)

    def is_bound_term(self, index: int) -> bool:
        """Check if a term variable index is valid.

        Args:
            index: The de Bruijn index to check

        Returns:
            True if the index is within bounds
        """
        return 0 <= index < len(self.term_types)

    def is_bound_type(self, name: str) -> bool:
        """Check if a type variable name is bound.

        Args:
            name: The type variable name to check

        Returns:
            True if the name is bound
        """
        return any(var_name == name for var_name, _ in self.type_vars)

    def is_constructor(self, name: str) -> bool:
        """Check if a name is a type constructor.

        Args:
            name: The name to check

        Returns:
            True if the name is a defined constructor
        """
        return name in self.constructors

    def is_global(self, name: str) -> bool:
        """Check if a name is a known global.

        Args:
            name: The name to check

        Returns:
            True if the name is a global
        """
        return name in self.globals

    def get_term_count(self) -> int:
        """Return the number of bound term variables.

        Returns:
            The count of term variables in context
        """
        return len(self.term_types)

    def get_type_count(self) -> int:
        """Return the number of bound type variables.

        Returns:
            The count of type variables in context
        """
        return len(self.type_vars)

    # -------------------------------------------------------------------------
    # Type versioning methods (for shadowed type definitions)
    # -------------------------------------------------------------------------

    def get_type_version(self, name: str) -> int:
        """Get the current version number for a type.

        Returns 0 if the type has never been defined.

        Args:
            name: Type name

        Returns:
            Current version number (0 = never defined)

        Example:
            >>> ctx = TypeContext()
            >>> ctx.get_type_version("T")
            0
            >>> ctx = ctx.increment_type_version("T")
            >>> ctx.get_type_version("T")
            1
        """
        return self.type_versions.get(name, 0)

    def increment_type_version(self, name: str) -> "TypeContext":
        """Increment the version number for a type.

        Called when a type is redefined to create a new version.

        Args:
            name: Type name

        Returns:
            New TypeContext with incremented version

        Example:
            >>> ctx = TypeContext()
            >>> ctx = ctx.increment_type_version("T")  # First definition
            >>> ctx.get_type_version("T")
            1
            >>> ctx = ctx.increment_type_version("T")  # Redefinition
            >>> ctx.get_type_version("T")
            2
        """
        new_versions = dict(self.type_versions)
        new_versions[name] = new_versions.get(name, 0) + 1
        return TypeContext(
            term_types=self.term_types,
            type_vars=self.type_vars,
            constructors=self.constructors,
            globals=self.globals,
            metas=self.metas,
            coercion_axioms=self.coercion_axioms,
            type_versions=new_versions,
        )

    def set_type_version(self, name: str, version: int) -> "TypeContext":
        """Set a specific version number for a type.

        Args:
            name: Type name
            version: Version number to set

        Returns:
            New TypeContext with set version
        """
        new_versions = dict(self.type_versions)
        new_versions[name] = version
        return TypeContext(
            term_types=self.term_types,
            type_vars=self.type_vars,
            constructors=self.constructors,
            globals=self.globals,
            metas=self.metas,
            coercion_axioms=self.coercion_axioms,
            type_versions=new_versions,
        )

    def is_current_type_version(self, type_con: TypeConstructor) -> bool:
        """Check if a TypeConstructor uses the current version.

        Args:
            type_con: Type constructor to check

        Returns:
            True if this is the current version of the type

        Example:
            >>> ctx = TypeContext()
            >>> ctx = ctx.increment_type_version("T")
            >>> t1 = TypeConstructor("T", [], version=1)
            >>> ctx.is_current_type_version(t1)
            True
            >>> ctx = ctx.increment_type_version("T")
            >>> ctx.is_current_type_version(t1)
            False
        """
        current = self.get_type_version(type_con.name)
        return type_con.version == current

    def check_type_version_mismatch(
        self, expected: TypeConstructor, actual: TypeConstructor
    ) -> Optional[tuple[str, int, int]]:
        """Check if two type constructors have a version mismatch.

        Returns information about the mismatch if both types have the same
        name but different versions.

        Args:
            expected: Expected type
            actual: Actual type

        Returns:
            Tuple of (type_name, expected_version, actual_version) if mismatch,
            None otherwise

        Example:
            >>> ctx = TypeContext()
            >>> ctx = ctx.increment_type_version("T")  # v1
            >>> ctx = ctx.increment_type_version("T")  # v2
            >>> t1 = TypeConstructor("T", [], version=1)
            >>> t2 = TypeConstructor("T", [], version=2)
            >>> ctx.check_type_version_mismatch(t1, t2)
            ('T', 1, 2)
        """
        if expected.name != actual.name:
            return None
        if expected.version == actual.version:
            return None
        return (expected.name, expected.version, actual.version)

    def __repr__(self) -> str:
        """Return a string representation for debugging."""
        return (
            f"TypeContext("
            f"term_types={self.term_types}, "
            f"type_vars={self.type_vars}, "
            f"constructors={set(self.constructors.keys())}, "
            f"globals={set(self.globals.keys())}, "
            f"metas={len(self.metas)}, "
            f"coercion_axioms={set(self.coercion_axioms.keys())}, "
            f"type_versions={self.type_versions}"
            f")"
        )
