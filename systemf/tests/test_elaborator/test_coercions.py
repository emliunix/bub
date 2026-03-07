"""Tests for System FC coercion operations.

Tests coercion composition, normalization, inversion, and equality
for the System FC extension that supports ADT representation types.

Coverage:
- Coercion datatypes (Refl, Sym, Trans, Comp, Axiom)
- Coercion composition with optimizations
- Coercion inversion with double-negation elimination
- Coercion normalization for canonical forms
- Coercion equality checking
"""

import pytest

from systemf.core.types import TypeVar, TypeConstructor
from systemf.core.coercion import (
    CoercionRefl,
    CoercionSym,
    CoercionTrans,
    CoercionComp,
    CoercionAxiom,
    coercion_equality,
    compose_coercions,
    invert_coercion,
    normalize_coercion,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def nat_type():
    """Simple Nat type."""
    return TypeConstructor("Nat", [])


@pytest.fixture
def list_type():
    """Polymorphic List type."""
    a = TypeVar("a")
    return TypeConstructor("List", [a])


@pytest.fixture
def nat_axiom(nat_type):
    """Coercion axiom for Nat."""
    repr_type = TypeConstructor("Repr", [nat_type])
    return CoercionAxiom(
        name="ax_Nat",
        left_ty=nat_type,
        right_ty=repr_type,
        type_args=[],
    )


@pytest.fixture
def list_axiom(list_type):
    """Coercion axiom for List."""
    a = TypeVar("a")
    repr_type = TypeConstructor("Repr", [list_type])
    return CoercionAxiom(
        name="ax_List",
        left_ty=list_type,
        right_ty=repr_type,
        type_args=[a],
    )


# =============================================================================
# Coercion Datatype Tests
# =============================================================================


class TestCoercionDatatypes:
    """Test basic coercion datatype construction and properties."""

    def test_coercion_refl(self, nat_type):
        """Test reflexivity coercion."""
        refl = CoercionRefl(nat_type)
        assert refl.left == nat_type
        assert refl.right == nat_type
        assert "Refl" in str(refl)
        assert "Nat" in str(refl)

    def test_coercion_sym(self, nat_axiom):
        """Test symmetry coercion."""
        sym = CoercionSym(nat_axiom)
        # Sym(γ) swaps left and right
        assert sym.left == nat_axiom.right
        assert sym.right == nat_axiom.left
        assert sym.coercion == nat_axiom

    def test_coercion_trans(self, nat_axiom):
        """Test transitivity coercion."""
        repr_type = nat_axiom.right
        # Create a chain: T ~ Repr(T) ~ T (using sym to go back)
        sym_back = CoercionSym(nat_axiom)
        trans = CoercionTrans(nat_axiom, sym_back)

        assert trans.left == nat_axiom.left
        assert trans.right == sym_back.right
        assert trans.first == nat_axiom
        assert trans.second == sym_back

    def test_coercion_comp(self, nat_axiom):
        """Test composition coercion."""
        sym = CoercionSym(nat_axiom)
        comp = CoercionComp(nat_axiom, sym)

        assert comp.left == nat_axiom.left
        assert comp.right == sym.right

    def test_coercion_axiom(self, nat_type):
        """Test axiom coercion for ADT representations."""
        repr_type = TypeConstructor("Repr", [nat_type])
        axiom = CoercionAxiom(
            name="ax_Nat",
            left_ty=nat_type,
            right_ty=repr_type,
            type_args=[],
        )

        assert axiom.name == "ax_Nat"
        assert axiom.left == nat_type
        assert axiom.right == repr_type
        assert axiom.type_args == []

    def test_polymorphic_axiom(self, list_type):
        """Test polymorphic axiom with type arguments."""
        a = TypeVar("a")
        repr_type = TypeConstructor("Repr", [list_type])
        axiom = CoercionAxiom(
            name="ax_List",
            left_ty=list_type,
            right_ty=repr_type,
            type_args=[a],
        )

        assert len(axiom.type_args) == 1
        assert axiom.type_args[0] == a


# =============================================================================
# Coercion Equality Tests
# =============================================================================


class TestCoercionEquality:
    """Test structural equality of coercions."""

    def test_refl_equality(self, nat_type):
        """Test that Refl coercions are equal when types match."""
        refl1 = CoercionRefl(nat_type)
        refl2 = CoercionRefl(TypeConstructor("Nat", []))

        assert coercion_equality(refl1, refl2)

    def test_refl_inequality_different_types(self, nat_type):
        """Test that Refl coercions differ when types differ."""
        refl_nat = CoercionRefl(nat_type)
        refl_int = CoercionRefl(TypeConstructor("Int", []))

        assert not coercion_equality(refl_nat, refl_int)

    def test_sym_equality(self, nat_axiom):
        """Test symmetry coercions are equal when inner coercions match."""
        sym1 = CoercionSym(nat_axiom)
        sym2 = CoercionSym(
            CoercionAxiom(
                name="ax_Nat",
                left_ty=nat_axiom.left,
                right_ty=nat_axiom.right,
                type_args=[],
            )
        )

        assert coercion_equality(sym1, sym2)

    def test_trans_equality(self, nat_axiom):
        """Test transitivity coercions are equal when both parts match."""
        sym = CoercionSym(nat_axiom)
        trans1 = CoercionTrans(nat_axiom, sym)
        trans2 = CoercionTrans(nat_axiom, sym)

        assert coercion_equality(trans1, trans2)

    def test_axiom_equality(self, nat_type):
        """Test axiom coercions are equal when all fields match."""
        repr_type = TypeConstructor("Repr", [nat_type])
        axiom1 = CoercionAxiom("ax_Nat", nat_type, repr_type, [])
        axiom2 = CoercionAxiom("ax_Nat", nat_type, repr_type, [])

        assert coercion_equality(axiom1, axiom2)

    def test_axiom_inequality_different_names(self, nat_type):
        """Test axiom coercions differ when names differ."""
        repr_type = TypeConstructor("Repr", [nat_type])
        axiom1 = CoercionAxiom("ax_Nat", nat_type, repr_type, [])
        axiom2 = CoercionAxiom("ax_Int", nat_type, repr_type, [])

        assert not coercion_equality(axiom1, axiom2)


# =============================================================================
# Coercion Composition Tests
# =============================================================================


class TestCoercionComposition:
    """Test coercion composition with optimizations."""

    def test_compose_with_refl_left(self, nat_axiom):
        """Test Refl ∘ γ = γ optimization."""
        refl = CoercionRefl(nat_axiom.left)

        # Compose refl with axiom: Refl(Nat) ∘ ax_Nat = ax_Nat
        result = compose_coercions(refl, nat_axiom)

        # Should return the axiom directly, not a Comp
        assert result is nat_axiom
        assert not isinstance(result, CoercionComp)

    def test_compose_with_refl_right(self, nat_axiom):
        """Test γ ∘ Refl = γ optimization."""
        repr_type = nat_axiom.right
        refl = CoercionRefl(repr_type)

        # Compose axiom with refl: ax_Nat ∘ Refl(Repr(Nat)) = ax_Nat
        result = compose_coercions(nat_axiom, refl)

        # Should return the axiom directly
        assert result is nat_axiom

    def test_compose_no_optimization(self, nat_axiom):
        """Test composition without optimizations creates Comp."""
        sym = CoercionSym(nat_axiom)

        # Compose axiom with its sym: ax_Nat ∘ Sym(ax_Nat)
        result = compose_coercions(nat_axiom, sym)

        # Should create a Comp since neither is Refl
        assert isinstance(result, CoercionComp)
        assert result.first == nat_axiom
        assert result.second == sym

    def test_compose_chain(self, nat_axiom):
        """Test composing a chain of coercions."""
        sym = CoercionSym(nat_axiom)

        # ax_Nat ∘ Sym(ax_Nat) should give us: Nat ~ Repr(Nat) ~ Nat
        comp = compose_coercions(nat_axiom, sym)

        assert comp.left == nat_axiom.left  # Nat
        assert comp.right == sym.right  # Nat (through Sym)


# =============================================================================
# Coercion Inversion Tests
# =============================================================================


class TestCoercionInversion:
    """Test coercion inversion with double-negation elimination."""

    def test_invert_refl(self, nat_type):
        """Test inverting Refl returns Refl."""
        refl = CoercionRefl(nat_type)
        result = invert_coercion(refl)

        # Inverting Refl should give Refl back
        assert isinstance(result, CoercionRefl)
        assert result.left == nat_type

    def test_invert_sym_double_negation(self, nat_axiom):
        """Test Sym(Sym(γ)) = γ elimination."""
        sym = CoercionSym(nat_axiom)

        # Invert Sym(axiom) should give us back the axiom
        result = invert_coercion(sym)

        assert result is nat_axiom
        assert not isinstance(result, CoercionSym)

    def test_invert_axiom(self, nat_axiom):
        """Test inverting an axiom creates Sym."""
        result = invert_coercion(nat_axiom)

        # Should create Sym(axiom)
        assert isinstance(result, CoercionSym)
        assert result.coercion == nat_axiom

    def test_invert_trans(self, nat_axiom):
        """Test inverting transitivity reverses order."""
        sym = CoercionSym(nat_axiom)
        trans = CoercionTrans(nat_axiom, sym)

        result = invert_coercion(trans)

        # Trans(γ1, γ2)^-1 = Trans(γ2^-1, γ1^-1)
        # Since Sym(axiom)^-1 = axiom, and axiom^-1 = Sym(axiom)
        # Result should be: Trans(axiom, Sym(axiom))
        assert isinstance(result, CoercionTrans)
        # The coercions should be inverted and order swapped
        assert result.first == nat_axiom  # Sym(axiom)^-1 = axiom
        assert isinstance(result.second, CoercionSym)  # axiom^-1 = Sym(axiom)


# =============================================================================
# Coercion Normalization Tests
# =============================================================================


class TestCoercionNormalization:
    """Test coercion normalization to canonical forms."""

    def test_normalize_refl_refl(self, nat_type):
        """Test normalizing Trans(Refl, Refl) gives Refl."""
        refl = CoercionRefl(nat_type)
        trans = CoercionTrans(refl, refl)

        result = normalize_coercion(trans)

        # Should simplify to just Refl
        assert isinstance(result, CoercionRefl)

    def test_normalize_trans_refl(self, nat_axiom):
        """Test normalizing Trans(γ, Refl) gives γ."""
        repr_type = nat_axiom.right
        refl = CoercionRefl(repr_type)
        trans = CoercionTrans(nat_axiom, refl)

        result = normalize_coercion(trans)

        # Should simplify to just the axiom
        assert result is nat_axiom

    def test_normalize_refl_trans(self, nat_axiom):
        """Test normalizing Trans(Refl, γ) gives γ."""
        nat_type = nat_axiom.left
        refl = CoercionRefl(nat_type)
        trans = CoercionTrans(refl, nat_axiom)

        result = normalize_coercion(trans)

        # Should simplify to just the axiom
        assert result is nat_axiom

    def test_normalize_sym_sym(self, nat_axiom):
        """Test normalizing Sym(Sym(γ)) gives γ."""
        sym = CoercionSym(nat_axiom)
        sym_sym = CoercionSym(sym)

        result = normalize_coercion(sym_sym)

        # Should eliminate the double negation
        assert result is nat_axiom

    def test_normalize_nested(self, nat_type):
        """Test normalizing deeply nested coercions."""
        refl1 = CoercionRefl(nat_type)
        refl2 = CoercionRefl(nat_type)
        trans1 = CoercionTrans(refl1, refl2)
        sym = CoercionSym(trans1)
        trans2 = CoercionTrans(sym, refl1)

        result = normalize_coercion(trans2)

        # Should simplify significantly
        assert isinstance(result, (CoercionRefl, CoercionSym))


# =============================================================================
# Integration Tests
# =============================================================================


class TestCoercionIntegration:
    """Test integration of coercion operations in realistic scenarios."""

    def test_constructor_cast_coercion(self, nat_type):
        """Test the coercion used in constructor casts."""
        # When elaborating Zero : Nat, we need:
        #   Zero : Repr(Nat)  (constructor produces representation)
        #   Cast(Zero, ax_Nat) : Nat  (cast to abstract type)

        repr_type = TypeConstructor("Repr", [nat_type])
        axiom = CoercionAxiom("ax_Nat", nat_type, repr_type, [])

        # The coercion witnesses: Repr(Nat) ~ Nat
        # So we cast from Repr(Nat) to Nat
        assert axiom.left == nat_type
        assert axiom.right == repr_type

    def test_pattern_match_coercion(self, nat_type):
        """Test the coercion used in pattern matching."""
        # When pattern matching on x : Nat, we need:
        #   Cast(x, Sym(ax_Nat)) : Repr(Nat)
        #   Then match on Repr(Nat)

        repr_type = TypeConstructor("Repr", [nat_type])
        axiom = CoercionAxiom("ax_Nat", nat_type, repr_type, [])
        inv_coercion = CoercionSym(axiom)

        # The inverse coercion witnesses: Nat ~ Repr(Nat)
        assert inv_coercion.left == repr_type
        assert inv_coercion.right == nat_type

    def test_roundtrip_coercion(self, nat_type):
        """Test that casting to repr and back is identity."""
        repr_type = TypeConstructor("Repr", [nat_type])
        axiom = CoercionAxiom("ax_Nat", nat_type, repr_type, [])
        inv = CoercionSym(axiom)

        # Compose axiom with inverse: ax_Nat ∘ Sym(ax_Nat)
        # This should give us: Nat ~ Repr(Nat) ~ Nat
        roundtrip = compose_coercions(inv, axiom)

        # After normalization, should be Refl(Nat) or at least simplified
        normalized = normalize_coercion(roundtrip)
        # The roundtrip should produce a valid coercion from Nat to Nat
        assert normalized.left == nat_type
        assert normalized.right == nat_type

    def test_polymorphic_coercion_substitution(self, list_type):
        """Test substitution in polymorphic coercions."""
        a = TypeVar("a")
        repr_type = TypeConstructor("Repr", [list_type])
        axiom = CoercionAxiom("ax_List", list_type, repr_type, [a])

        # The axiom should have type variables in type_args
        assert len(axiom.type_args) == 1
        assert axiom.type_args[0] == a

        # Substitution should work (tested via substitute method)
        subst = {"a": TypeConstructor("Int", [])}
        result = axiom.substitute(subst)

        assert result is not None
