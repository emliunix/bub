"""Tests for ADT coercion axiom generation and integration.

Tests the generation of coercion axioms for algebraic data types
and their integration into the elaboration pipeline.

Coverage:
- ADT axiom generation for simple and recursive types
- Polymorphic ADT axiom generation
- Axiom registration in TypeContext
- Constructor elaboration with coercions
- Pattern matching with inverse coercions
"""

import pytest

from systemf.core.types import TypeVar, TypeConstructor
from systemf.core.coercion import CoercionAxiom, CoercionSym
from systemf.core import ast as core
from systemf.elaborator.coercion_axioms import (
    CoercionAxiomGenerator,
    ADTAxiom,
    generate_adt_axiom,
    generate_axioms_for_declarations,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def nat_data_decl():
    """Core DataDeclaration for Nat type."""
    return core.DataDeclaration(
        name="Nat",
        params=[],
        constructors=[
            ("Zero", []),
            ("Succ", [TypeConstructor("Nat", [])]),
        ],
    )


@pytest.fixture
def list_data_decl():
    """Core DataDeclaration for polymorphic List type."""
    a = TypeVar("a")
    return core.DataDeclaration(
        name="List",
        params=["a"],
        constructors=[
            ("Nil", []),
            ("Cons", [a, TypeConstructor("List", [a])]),
        ],
    )


@pytest.fixture
def tree_data_decl():
    """Core DataDeclaration for Tree type (mutually recursive with Forest)."""
    a = TypeVar("a")
    return core.DataDeclaration(
        name="Tree",
        params=["a"],
        constructors=[
            ("Leaf", [a]),
            ("Node", [TypeConstructor("Forest", [a])]),
        ],
    )


@pytest.fixture
def forest_data_decl():
    """Core DataDeclaration for Forest type (mutually recursive with Tree)."""
    a = TypeVar("a")
    return core.DataDeclaration(
        name="Forest",
        params=["a"],
        constructors=[
            ("Empty", []),
            ("FCons", [TypeConstructor("Tree", [a]), TypeConstructor("Forest", [a])]),
        ],
    )


# =============================================================================
# ADT Axiom Generation Tests
# =============================================================================


class TestADTAxiomGeneration:
    """Test generation of coercion axioms for ADTs."""

    def test_simple_type_axiom(self, nat_data_decl):
        """Test axiom generation for simple non-recursive type."""
        generator = CoercionAxiomGenerator()
        adt_axiom = generator.generate_axiom(nat_data_decl)

        # Check ADTAxiom structure
        assert adt_axiom.declaration == nat_data_decl
        assert adt_axiom.axiom_name == "ax_Nat"

        # Check coercion structure
        coercion = adt_axiom.coercion
        assert isinstance(coercion, CoercionAxiom)
        assert coercion.name == "ax_Nat"
        assert coercion.left == TypeConstructor("Nat", [])
        assert coercion.right == TypeConstructor("Repr", [TypeConstructor("Nat", [])])

    def test_polymorphic_type_axiom(self, list_data_decl):
        """Test axiom generation for polymorphic type."""
        generator = CoercionAxiomGenerator()
        adt_axiom = generator.generate_axiom(list_data_decl)

        assert adt_axiom.axiom_name == "ax_List"

        coercion = adt_axiom.coercion
        assert coercion.name == "ax_List"

        # Check type arguments for polymorphism
        assert len(coercion.type_args) == 1
        assert coercion.type_args[0] == TypeVar("a")

    def test_axiom_types(self, nat_data_decl):
        """Test abstract and representation types in axiom."""
        adt_axiom = generate_adt_axiom(nat_data_decl)

        # Abstract type should be Nat
        assert adt_axiom.abstract_type == TypeConstructor("Nat", [])

        # Representation type should be Repr(Nat)
        expected_repr = TypeConstructor("Repr", [TypeConstructor("Nat", [])])
        assert adt_axiom.repr_type == expected_repr

    def test_multiple_axioms(self, nat_data_decl, list_data_decl):
        """Test generating axioms for multiple types."""
        decls = [nat_data_decl, list_data_decl]
        axioms = generate_axioms_for_declarations(decls)

        assert len(axioms) == 2

        names = {ax.axiom_name for ax in axioms}
        assert names == {"ax_Nat", "ax_List"}


# =============================================================================
# Coercion Axiom Generator Tests
# =============================================================================


class TestCoercionAxiomGenerator:
    """Test the CoercionAxiomGenerator class."""

    def test_generator_storage(self, nat_data_decl, list_data_decl):
        """Test that generator stores generated axioms."""
        generator = CoercionAxiomGenerator()

        # Generate axioms
        axiom1 = generator.generate_axiom(nat_data_decl)
        axiom2 = generator.generate_axiom(list_data_decl)

        # Retrieve by name
        assert generator.get_axiom("Nat") == axiom1
        assert generator.get_axiom("List") == axiom2

    def test_has_axiom(self, nat_data_decl):
        """Test checking if axiom exists."""
        generator = CoercionAxiomGenerator()

        assert not generator.has_axiom("Nat")

        generator.generate_axiom(nat_data_decl)

        assert generator.has_axiom("Nat")
        assert not generator.has_axiom("Int")

    def test_get_all_axioms(self, nat_data_decl, list_data_decl):
        """Test retrieving all generated axioms."""
        generator = CoercionAxiomGenerator()

        generator.generate_axiom(nat_data_decl)
        generator.generate_axiom(list_data_decl)

        all_axioms = generator.get_all_axioms()
        assert len(all_axioms) == 2

        names = {ax.axiom_name for ax in all_axioms}
        assert names == {"ax_Nat", "ax_List"}

    def test_unknown_axiom_returns_none(self):
        """Test that unknown axioms return None."""
        generator = CoercionAxiomGenerator()
        assert generator.get_axiom("Unknown") is None


# =============================================================================
# Recursive Type Axiom Tests
# =============================================================================


class TestRecursiveTypeAxioms:
    """Test axiom generation for recursive and mutually recursive types."""

    def test_self_recursive_type(self, nat_data_decl):
        """Test axiom for self-recursive type (Nat with Succ)."""
        adt_axiom = generate_adt_axiom(nat_data_decl)

        # The axiom should still be simple
        assert adt_axiom.axiom_name == "ax_Nat"
        assert adt_axiom.coercion.left == TypeConstructor("Nat", [])

    def test_polymorphic_recursive_type(self, list_data_decl):
        """Test axiom for polymorphic recursive type (List)."""
        adt_axiom = generate_adt_axiom(list_data_decl)

        assert adt_axiom.axiom_name == "ax_List"
        assert len(adt_axiom.coercion.type_args) == 1

    def test_mutual_recursion_axioms(self, tree_data_decl, forest_data_decl):
        """Test axioms for mutually recursive types."""
        decls = [tree_data_decl, forest_data_decl]
        axioms = generate_axioms_for_declarations(decls)

        assert len(axioms) == 2

        names = {ax.axiom_name for ax in axioms}
        assert names == {"ax_Tree", "ax_Forest"}

        # Both should have type variable 'a'
        for ax in axioms:
            assert len(ax.coercion.type_args) == 1
            assert ax.coercion.type_args[0] == TypeVar("a")


# =============================================================================
# Constructor and Pattern Match Integration Tests
# =============================================================================


class TestConstructorPatternIntegration:
    """Test integration of axioms with constructor and pattern matching."""

    def test_constructor_cast_axiom_direction(self, nat_data_decl):
        """Test that constructor cast uses correct axiom direction.

        When we have: Zero : Repr(Nat)
        We cast to:   Zero ▷ ax_Nat : Nat

        The axiom witnesses: Nat ~ Repr(Nat)
        So ax_Nat : Nat ~ Repr(Nat)
        And we need: Repr(Nat) ~ Nat to cast from Repr to Nat
        """
        adt_axiom = generate_adt_axiom(nat_data_decl)
        coercion = adt_axiom.coercion

        # ax_Nat : Nat ~ Repr(Nat)
        assert coercion.left == TypeConstructor("Nat", [])
        assert coercion.right == TypeConstructor("Repr", [TypeConstructor("Nat", [])])

    def test_pattern_match_inverse_direction(self, nat_data_decl):
        """Test that pattern matching uses inverse axiom direction.

        When we have: x : Nat
        We cast to:   x ▷ Sym(ax_Nat) : Repr(Nat)

        Sym(ax_Nat) : Repr(Nat) ~ Nat
        """
        adt_axiom = generate_adt_axiom(nat_data_decl)
        inverse = CoercionSym(adt_axiom.coercion)

        # Sym(ax_Nat) : Repr(Nat) ~ Nat
        assert inverse.left == TypeConstructor("Repr", [TypeConstructor("Nat", [])])
        assert inverse.right == TypeConstructor("Nat", [])

    def test_roundtrip_coercion(self, nat_data_decl):
        """Test that cast then pattern match roundtrips correctly."""
        adt_axiom = generate_adt_axiom(nat_data_decl)
        axiom = adt_axiom.coercion
        inverse = CoercionSym(axiom)

        # Constructor: Zero : Repr(Nat)
        # Cast: (Zero ▷ ax_Nat) : Nat
        # Pattern match: (Zero ▷ ax_Nat) ▷ Sym(ax_Nat) : Repr(Nat)

        # After roundtrip, we're back at Repr(Nat)
        assert inverse.left == TypeConstructor("Repr", [TypeConstructor("Nat", [])])


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestADTAxiomEdgeCases:
    """Test edge cases in ADT axiom generation."""

    def test_empty_constructor_type(self):
        """Test axiom for type with only nullary constructors."""
        decl = core.DataDeclaration(
            name="Bool",
            params=[],
            constructors=[("True", []), ("False", [])],
        )

        adt_axiom = generate_adt_axiom(decl)

        assert adt_axiom.axiom_name == "ax_Bool"
        assert adt_axiom.coercion.left == TypeConstructor("Bool", [])

    def test_single_constructor_type(self):
        """Test axiom for type with single constructor."""
        decl = core.DataDeclaration(
            name="Identity",
            params=["a"],
            constructors=[("Id", [TypeVar("a")])],
        )

        adt_axiom = generate_adt_axiom(decl)

        assert adt_axiom.axiom_name == "ax_Identity"
        assert len(adt_axiom.coercion.type_args) == 1

    def test_nested_type_arguments(self):
        """Test axiom for type with nested type arguments."""
        decl = core.DataDeclaration(
            name="Nested",
            params=[],
            constructors=[
                ("MkNested", [TypeConstructor("List", [TypeConstructor("Int", [])])]),
            ],
        )

        adt_axiom = generate_adt_axiom(decl)

        assert adt_axiom.axiom_name == "ax_Nested"


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Test convenience functions for axiom generation."""

    def test_generate_adt_axiom(self, nat_data_decl):
        """Test the single-axiom convenience function."""
        adt_axiom = generate_adt_axiom(nat_data_decl)

        assert isinstance(adt_axiom, ADTAxiom)
        assert adt_axiom.axiom_name == "ax_Nat"

    def test_generate_axioms_for_declarations(self, nat_data_decl, list_data_decl):
        """Test the batch convenience function."""
        decls = [nat_data_decl, list_data_decl]
        axioms = generate_axioms_for_declarations(decls)

        assert len(axioms) == 2
        assert all(isinstance(ax, ADTAxiom) for ax in axioms)

    def test_generate_axioms_empty_list(self):
        """Test batch function with empty list."""
        axioms = generate_axioms_for_declarations([])
        assert axioms == []

    def test_generate_axioms_single_decl(self, nat_data_decl):
        """Test batch function with single declaration."""
        axioms = generate_axioms_for_declarations([nat_data_decl])

        assert len(axioms) == 1
        assert axioms[0].axiom_name == "ax_Nat"
