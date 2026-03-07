"""Coercion axiom generation for ADT representations.

This module generates coercion axioms that witness the equality between
abstract ADT types and their concrete representations. In System FC:

- Abstract types (Nat, List a, etc.) are used in source code
- Representation types (Repr(Nat), Repr(List a), etc.) are used internally
- Coercion axioms bridge them: ax_Nat : Nat ~ Repr(Nat)

The representation of an ADT is a sum of products - each constructor
becomes a variant, and each argument becomes a field in that variant.

Example:
    data Nat = Zero | Succ Nat

    Representation:
    Repr(Nat) = Either () (Repr(Nat))  -- Zero: unit, Succ: recursive Nat

    Axiom:
    ax_Nat : Nat ~ Repr(Nat)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from systemf.core.types import Type, TypeConstructor, TypeVar
from systemf.core.coercion import CoercionAxiom
from systemf.core.ast import DataDeclaration


@dataclass(frozen=True)
class ADTAxiom:
    """A coercion axiom for an ADT.

    Associates an ADT declaration with its representation type coercion.

    Attributes:
        declaration: The original ADT declaration
        axiom_name: Name of the coercion axiom (e.g., "ax_Nat")
        abstract_type: The abstract ADT type (e.g., Nat)
        repr_type: The representation type (e.g., Repr(Nat))
        coercion: The coercion axiom witnessing abstract ~ repr
    """

    declaration: DataDeclaration
    axiom_name: str
    abstract_type: Type
    repr_type: Type
    coercion: CoercionAxiom


class CoercionAxiomGenerator:
    """Generates coercion axioms for ADT declarations.

        For each data declaration, creates a coercion axiom that witnesses
    the equality between the abstract type and its representation.

        Example:
            decl = DataDeclaration("Nat", [], [("Zero", []), ("Succ", [Nat])])
            generator = CoercionAxiomGenerator()
            axiom = generator.generate_axiom(decl)

            # axiom.coercion : Nat ~ Repr(Nat)
            # axiom.axiom_name = "ax_Nat"
    """

    def __init__(self) -> None:
        """Initialize the generator."""
        self._axioms: dict[str, ADTAxiom] = {}

    def generate_axiom(self, decl: DataDeclaration) -> ADTAxiom:
        """Generate a coercion axiom for a data declaration.

        Creates an axiom of the form:
            ax_{name} : T α₁...αₙ ~ Repr(T α₁...αₙ)

        Args:
            decl: The data declaration to generate an axiom for

        Returns:
            ADTAxiom containing the declaration, types, and coercion

        Raises:
            ValueError: If the declaration has invalid structure
        """
        # Build the abstract type: T α₁...αₙ
        abstract_type = self._build_abstract_type(decl)

        # Build the representation type: Repr(T α₁...αₙ)
        repr_type = self._build_repr_type(decl, abstract_type)

        # Create the axiom name
        axiom_name = f"ax_{decl.name}"

        # Build type arguments (the parameters)
        type_args = self._build_type_args(decl)

        # Create the coercion axiom
        coercion = CoercionAxiom(
            name=axiom_name, left_ty=abstract_type, right_ty=repr_type, type_args=type_args
        )

        # Create and store the ADT axiom
        adt_axiom = ADTAxiom(
            declaration=decl,
            axiom_name=axiom_name,
            abstract_type=abstract_type,
            repr_type=repr_type,
            coercion=coercion,
        )

        self._axioms[decl.name] = adt_axiom
        return adt_axiom

    def _build_abstract_type(self, decl: DataDeclaration) -> Type:
        """Build the abstract type T α₁...αₙ from a declaration.

        Args:
            decl: The data declaration

        Returns:
            TypeConstructor for the abstract type
        """
        if not decl.params:
            # Simple type with no parameters: Nat
            return TypeConstructor(name=decl.name, args=[])

        # Parameterized type: List α
        type_args = [TypeVar(name=param) for param in decl.params]
        return TypeConstructor(name=decl.name, args=type_args)

    def _build_repr_type(self, decl: DataDeclaration, abstract_type: Type) -> Type:
        """Build the representation type Repr(T α₁...αₙ).

        The representation wraps the abstract type in a Repr constructor.

        Args:
            decl: The data declaration
            abstract_type: The already-built abstract type

        Returns:
            TypeConstructor for Repr(abstract_type)
        """
        return TypeConstructor(name="Repr", args=[abstract_type])

    def _build_type_args(self, decl: DataDeclaration) -> list[Type]:
        """Build the list of type arguments for polymorphic axioms.

        For a declaration with parameters, returns the type variables.
        For a monomorphic declaration, returns an empty list.

        Args:
            decl: The data declaration

        Returns:
            List of TypeVars for the parameters
        """
        return [TypeVar(name=param) for param in decl.params]

    def get_axiom(self, type_name: str) -> Optional[ADTAxiom]:
        """Retrieve a previously generated axiom by type name.

        Args:
            type_name: Name of the ADT (e.g., "Nat")

        Returns:
            The ADTAxiom if found, None otherwise
        """
        return self._axioms.get(type_name)

    def get_all_axioms(self) -> list[ADTAxiom]:
        """Get all generated axioms.

        Returns:
            List of all ADTAxioms generated so far
        """
        return list(self._axioms.values())

    def has_axiom(self, type_name: str) -> bool:
        """Check if an axiom has been generated for a type.

        Args:
            type_name: Name of the ADT

        Returns:
            True if an axiom exists, False otherwise
        """
        return type_name in self._axioms


def generate_adt_axiom(decl: DataDeclaration) -> ADTAxiom:
    """Convenience function to generate a single ADT axiom.

    Args:
        decl: The data declaration

    Returns:
        ADTAxiom for the declaration

    Example:
        decl = DataDeclaration(
            name="Nat",
            params=[],
            constructors=[("Zero", []), ("Succ", [TypeConstructor("Nat", [])])]
        )
        axiom = generate_adt_axiom(decl)

        # axiom.axiom_name = "ax_Nat"
        # axiom.coercion : Nat ~ Repr(Nat)
    """
    generator = CoercionAxiomGenerator()
    return generator.generate_axiom(decl)


def generate_axioms_for_declarations(decls: list[DataDeclaration]) -> list[ADTAxiom]:
    """Generate coercion axioms for multiple data declarations.

    Args:
        decls: List of data declarations

    Returns:
        List of ADTAxioms, one for each declaration

    Example:
        nat_decl = DataDeclaration("Nat", [], [...])
        list_decl = DataDeclaration("List", ["a"], [...])

        axioms = generate_axioms_for_declarations([nat_decl, list_decl])
        # axioms[0].coercion : Nat ~ Repr(Nat)
        # axioms[1].coercion : List α ~ Repr(List α)
    """
    generator = CoercionAxiomGenerator()
    return [generator.generate_axiom(decl) for decl in decls]
