"""Tests for unification logic.

Tests the unification algorithm including:
- Meta type variable creation
- Substitution operations
- Occurs check (infinite type detection)
- Unification of various type combinations
- Error handling
"""

import pytest

from systemf.core.types import (
    TypeVar,
    TypeArrow,
    TypeForall,
    TypeConstructor,
    PrimitiveType,
)
from systemf.surface.inference.unification import (
    TMeta,
    Substitution,
    unify,
    occurs_check,
    resolve_type,
    is_meta_variable,
    is_unresolved_meta,
)
from systemf.surface.inference.errors import InfiniteTypeError, UnificationError


# =============================================================================
# TMeta Tests
# =============================================================================


class TestTMeta:
    """Test meta type variable creation."""

    def test_fresh_creates_unique_ids(self):
        """Fresh meta variables should have unique ids."""
        meta1 = TMeta.fresh("a")
        meta2 = TMeta.fresh("b")
        meta3 = TMeta.fresh()

        assert meta1.id != meta2.id
        assert meta2.id != meta3.id
        assert meta1.id != meta3.id

    def test_fresh_preserves_name(self):
        """Fresh meta variables should preserve the given name."""
        meta = TMeta.fresh("myvar")
        assert meta.name == "myvar"

    def test_fresh_without_name(self):
        """Fresh meta variables can be created without a name."""
        meta = TMeta.fresh()
        assert meta.name is None

    def test_str_with_name(self):
        """String representation includes name if available."""
        meta = TMeta.fresh("a")
        assert str(meta) == "_a"

    def test_str_without_name(self):
        """String representation uses id if no name."""
        meta = TMeta.fresh()
        assert str(meta) == f"_{meta.id}"

    def test_free_vars_empty(self):
        """Meta variables don't contribute to free vars."""
        meta = TMeta.fresh("a")
        assert meta.free_vars() == set()


# =============================================================================
# Substitution Tests
# =============================================================================


class TestSubstitution:
    """Test substitution operations."""

    def test_empty_substitution(self):
        """Empty substitution should not change types."""
        subst = Substitution.empty()
        ty = PrimitiveType("Int")
        assert subst.apply_to_type(ty) == ty

    def test_singleton_creation(self):
        """Singleton substitution with one mapping."""
        meta = TMeta.fresh("a")
        ty = PrimitiveType("Int")
        subst = Substitution.singleton(meta, ty)

        assert subst.lookup(meta) == ty

    def test_extend_substitution(self):
        """Extend substitution with new mapping."""
        meta1 = TMeta.fresh("a")
        meta2 = TMeta.fresh("b")
        subst = Substitution.empty()
        subst = subst.extend(meta1, PrimitiveType("Int"))
        subst = subst.extend(meta2, PrimitiveType("Bool"))

        assert subst.lookup(meta1) == PrimitiveType("Int")
        assert subst.lookup(meta2) == PrimitiveType("Bool")

    def test_apply_to_meta_variable(self):
        """Apply substitution resolves meta variables."""
        meta = TMeta.fresh("a")
        subst = Substitution.singleton(meta, PrimitiveType("Int"))

        result = subst.apply_to_type(meta)
        assert result == PrimitiveType("Int")

    def test_apply_to_unbound_meta(self):
        """Unbound meta variables remain unchanged."""
        meta = TMeta.fresh("a")
        subst = Substitution.empty()

        result = subst.apply_to_type(meta)
        assert result == meta

    def test_apply_chain_resolution(self):
        """Substitution resolves chains of meta variables."""
        meta1 = TMeta.fresh("a")
        meta2 = TMeta.fresh("b")

        # meta1 -> meta2, meta2 -> Int
        subst = Substitution.empty()
        subst = subst.extend(meta1, meta2)
        subst = subst.extend(meta2, PrimitiveType("Int"))

        result = subst.apply_to_type(meta1)
        assert result == PrimitiveType("Int")

    def test_apply_to_type_arrow(self):
        """Substitution applies to both parts of arrow type."""
        meta = TMeta.fresh("a")
        arrow = TypeArrow(meta, PrimitiveType("Int"))
        subst = Substitution.singleton(meta, PrimitiveType("Bool"))

        result = subst.apply_to_type(arrow)
        expected = TypeArrow(PrimitiveType("Bool"), PrimitiveType("Int"))
        assert result == expected

    def test_apply_to_type_constructor(self):
        """Substitution applies to constructor arguments."""
        meta = TMeta.fresh("a")
        constr = TypeConstructor("Maybe", [meta])
        subst = Substitution.singleton(meta, PrimitiveType("Int"))

        result = subst.apply_to_type(constr)
        expected = TypeConstructor("Maybe", [PrimitiveType("Int")])
        assert result == expected

    def test_apply_to_type_forall(self):
        """Substitution applies to forall body."""
        meta = TMeta.fresh("a")
        forall = TypeForall("x", meta)
        subst = Substitution.singleton(meta, PrimitiveType("Int"))

        result = subst.apply_to_type(forall)
        expected = TypeForall("x", PrimitiveType("Int"))
        assert result == expected

    def test_type_var_unchanged(self):
        """Regular type variables are not substituted."""
        meta = TMeta.fresh("a")
        subst = Substitution.singleton(meta, PrimitiveType("Int"))

        tvar = TypeVar("a")  # Same name as meta, but different type
        result = subst.apply_to_type(tvar)
        assert result == tvar

    def test_compose_substitutions(self):
        """Compose two substitutions."""
        meta1 = TMeta.fresh("a")
        meta2 = TMeta.fresh("b")

        subst1 = Substitution.singleton(meta1, PrimitiveType("Int"))
        subst2 = Substitution.singleton(meta2, meta1)  # meta2 -> meta1

        composed = subst1.compose(subst2)

        # meta2 should resolve to Int through meta1
        result = composed.apply_to_type(meta2)
        assert result == PrimitiveType("Int")


# =============================================================================
# Occurs Check Tests
# =============================================================================


class TestOccursCheck:
    """Test occurs check for infinite type detection."""

    def test_occurs_in_same_meta(self):
        """Meta occurs in itself."""
        meta = TMeta.fresh("a")
        subst = Substitution.empty()
        assert occurs_check(meta, meta, subst) is True

    def test_occurs_not_in_different_meta(self):
        """Meta doesn't occur in different meta."""
        meta1 = TMeta.fresh("a")
        meta2 = TMeta.fresh("b")
        subst = Substitution.empty()
        assert occurs_check(meta1, meta2, subst) is False

    def test_occurs_in_arrow(self):
        """Meta occurs in arrow type."""
        meta = TMeta.fresh("a")
        arrow = TypeArrow(meta, PrimitiveType("Int"))
        subst = Substitution.empty()
        assert occurs_check(meta, arrow, subst) is True

    def test_occurs_not_in_arrow(self):
        """Meta doesn't occur in unrelated arrow."""
        meta = TMeta.fresh("a")
        arrow = TypeArrow(PrimitiveType("Bool"), PrimitiveType("Int"))
        subst = Substitution.empty()
        assert occurs_check(meta, arrow, subst) is False

    def test_occurs_in_constructor(self):
        """Meta occurs in constructor arguments."""
        meta = TMeta.fresh("a")
        constr = TypeConstructor("List", [meta])
        subst = Substitution.empty()
        assert occurs_check(meta, constr, subst) is True

    def test_occurs_in_forall(self):
        """Meta occurs in forall body."""
        meta = TMeta.fresh("a")
        forall = TypeForall("x", meta)
        subst = Substitution.empty()
        assert occurs_check(meta, forall, subst) is True

    def test_occurs_with_substitution(self):
        """Occurs check follows substitution."""
        meta1 = TMeta.fresh("a")
        meta2 = TMeta.fresh("b")

        # meta2 points to an arrow containing meta1
        subst = Substitution.singleton(meta2, TypeArrow(meta1, PrimitiveType("Int")))

        # meta1 occurs in what meta2 resolves to
        assert occurs_check(meta1, meta2, subst) is True


# =============================================================================
# Unification Tests
# =============================================================================


class TestUnify:
    """Test unification of different type combinations."""

    def test_unify_same_primitive(self):
        """Unifying same primitive types succeeds."""
        subst = Substitution.empty()
        result = unify(PrimitiveType("Int"), PrimitiveType("Int"), subst)
        assert result == subst  # No change

    def test_unify_different_primitives_fails(self):
        """Unifying different primitive types fails."""
        subst = Substitution.empty()
        with pytest.raises(UnificationError):
            unify(PrimitiveType("Int"), PrimitiveType("Bool"), subst)

    def test_unify_meta_with_primitive(self):
        """Unify meta variable with primitive type."""
        meta = TMeta.fresh("a")
        subst = Substitution.empty()
        result = unify(meta, PrimitiveType("Int"), subst)

        assert result.lookup(meta) == PrimitiveType("Int")

    def test_unify_same_meta(self):
        """Unifying same meta variable is a no-op."""
        meta = TMeta.fresh("a")
        subst = Substitution.empty()
        result = unify(meta, meta, subst)
        assert result == subst

    def test_unify_different_metas(self):
        """Unify two different meta variables."""
        meta1 = TMeta.fresh("a")
        meta2 = TMeta.fresh("b")
        subst = Substitution.empty()
        result = unify(meta1, meta2, subst)

        # meta1 should map to meta2 (or vice versa)
        assert result.lookup(meta1) == meta2 or result.lookup(meta2) == meta1

    def test_unify_arrow_types(self):
        """Unify two arrow types."""
        meta1 = TMeta.fresh("a")
        meta2 = TMeta.fresh("b")

        arrow1 = TypeArrow(meta1, PrimitiveType("Int"))
        arrow2 = TypeArrow(PrimitiveType("Bool"), meta2)

        subst = unify(arrow1, arrow2, Substitution.empty())

        # After unification: meta1 = Bool, meta2 = Int
        assert subst.lookup(meta1) == PrimitiveType("Bool")
        assert subst.lookup(meta2) == PrimitiveType("Int")

    def test_unify_arrow_with_primitive_fails(self):
        """Cannot unify arrow type with primitive."""
        arrow = TypeArrow(PrimitiveType("Int"), PrimitiveType("Int"))
        prim = PrimitiveType("Int")
        subst = Substitution.empty()

        with pytest.raises(UnificationError):
            unify(arrow, prim, subst)

    def test_unify_constructors_same_name(self):
        """Unify type constructors with same name."""
        meta = TMeta.fresh("a")

        constr1 = TypeConstructor("Maybe", [meta])
        constr2 = TypeConstructor("Maybe", [PrimitiveType("Int")])

        subst = unify(constr1, constr2, Substitution.empty())
        assert subst.lookup(meta) == PrimitiveType("Int")

    def test_unify_constructors_different_names_fails(self):
        """Cannot unify constructors with different names."""
        constr1 = TypeConstructor("Maybe", [PrimitiveType("Int")])
        constr2 = TypeConstructor("List", [PrimitiveType("Int")])
        subst = Substitution.empty()

        with pytest.raises(UnificationError):
            unify(constr1, constr2, subst)

    def test_unify_constructors_different_arity_fails(self):
        """Cannot unify constructors with different arity."""
        constr1 = TypeConstructor("Pair", [PrimitiveType("Int"), PrimitiveType("Bool")])
        constr2 = TypeConstructor("Pair", [PrimitiveType("Int")])
        subst = Substitution.empty()

        with pytest.raises(UnificationError):
            unify(constr1, constr2, subst)

    def test_unify_forall_types(self):
        """Unify forall types by unifying bodies."""
        meta = TMeta.fresh("a")

        forall1 = TypeForall("x", meta)
        forall2 = TypeForall("x", PrimitiveType("Int"))

        subst = unify(forall1, forall2, Substitution.empty())
        assert subst.lookup(meta) == PrimitiveType("Int")

    def test_occurs_check_raises_infinite_type(self):
        """Unification with occurs check raises InfiniteTypeError."""
        meta = TMeta.fresh("a")
        # Trying to unify _a with _a -> Int (infinite type)
        arrow = TypeArrow(meta, PrimitiveType("Int"))
        subst = Substitution.empty()

        with pytest.raises(InfiniteTypeError) as exc_info:
            unify(meta, arrow, subst)

        assert "_a" in str(exc_info.value)
        assert "occurs" in str(exc_info.value).lower()

    def test_unify_type_var_same_name(self):
        """Unify type variables with same name."""
        tvar = TypeVar("a")
        subst = unify(tvar, tvar, Substitution.empty())
        # Should succeed with no changes

    def test_unify_type_var_with_different_fails(self):
        """Cannot unify different type variables."""
        tvar1 = TypeVar("a")
        tvar2 = TypeVar("b")
        subst = Substitution.empty()

        with pytest.raises(UnificationError):
            unify(tvar1, tvar2, subst)

    def test_unify_type_var_with_primitive_fails(self):
        """Cannot unify type variable with primitive."""
        tvar = TypeVar("a")
        prim = PrimitiveType("Int")
        subst = Substitution.empty()

        with pytest.raises(UnificationError):
            unify(tvar, prim, subst)


# =============================================================================
# Utility Function Tests
# =============================================================================


class TestUtilityFunctions:
    """Test utility functions."""

    def test_resolve_type(self):
        """Test fully resolving a type."""
        meta1 = TMeta.fresh("a")
        meta2 = TMeta.fresh("b")

        subst = Substitution.empty()
        subst = subst.extend(meta1, meta2)
        subst = subst.extend(meta2, PrimitiveType("Int"))

        result = resolve_type(meta1, subst)
        assert result == PrimitiveType("Int")

    def test_is_meta_variable_true(self):
        """is_meta_variable returns True for TMeta."""
        meta = TMeta.fresh("a")
        assert is_meta_variable(meta) is True

    def test_is_meta_variable_false(self):
        """is_meta_variable returns False for other types."""
        assert is_meta_variable(PrimitiveType("Int")) is False
        assert is_meta_variable(TypeVar("a")) is False

    def test_is_unresolved_meta_true(self):
        """is_unresolved_meta returns True for unbound meta."""
        meta = TMeta.fresh("a")
        subst = Substitution.empty()
        assert is_unresolved_meta(meta, subst) is True

    def test_is_unresolved_meta_false(self):
        """is_unresolved_meta returns False for bound meta."""
        meta = TMeta.fresh("a")
        subst = Substitution.singleton(meta, PrimitiveType("Int"))
        assert is_unresolved_meta(meta, subst) is False

    def test_is_unresolved_meta_false_for_non_meta(self):
        """is_unresolved_meta returns False for non-meta types."""
        subst = Substitution.empty()
        assert is_unresolved_meta(PrimitiveType("Int"), subst) is False
