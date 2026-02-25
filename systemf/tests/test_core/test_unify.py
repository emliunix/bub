"""Tests for unification algorithm."""

import pytest

from systemf.core.types import TypeVar, TypeArrow, TypeForall, TypeConstructor
from systemf.core.unify import Substitution, unify, occurs_in
from systemf.core.errors import UnificationError, OccursCheckError


class TestOccursIn:
    """Tests for occurs check."""

    def test_var_in_var_same(self):
        """Test variable occurs in itself."""
        assert occurs_in("a", TypeVar("a")) is True

    def test_var_in_var_different(self):
        """Test variable does not occur in different variable."""
        assert occurs_in("a", TypeVar("b")) is False

    def test_var_in_arrow(self):
        """Test variable occurs in arrow type."""
        t = TypeArrow(TypeVar("a"), TypeVar("b"))
        assert occurs_in("a", t) is True
        assert occurs_in("b", t) is True
        assert occurs_in("c", t) is False

    def test_var_in_forall_bound(self):
        """Test variable does not occur if bound by forall."""
        t = TypeForall("a", TypeVar("a"))
        assert occurs_in("a", t) is False

    def test_var_in_forall_free(self):
        """Test variable occurs if free in forall body."""
        t = TypeForall("a", TypeVar("b"))
        assert occurs_in("b", t) is True

    def test_var_in_constructor(self):
        """Test variable occurs in constructor arguments."""
        t = TypeConstructor("List", [TypeVar("a")])
        assert occurs_in("a", t) is True
        assert occurs_in("b", t) is False


class TestSubstitution:
    """Tests for Substitution class."""

    def test_empty(self):
        """Test empty substitution."""
        s = Substitution.empty()
        t = TypeVar("a")
        assert s.apply(t) == t

    def test_singleton(self):
        """Test singleton substitution."""
        s = Substitution.singleton("a", TypeVar("b"))
        assert s.apply(TypeVar("a")) == TypeVar("b")
        assert s.apply(TypeVar("c")) == TypeVar("c")

    def test_apply_arrow(self):
        """Test applying substitution to arrow type."""
        s = Substitution.singleton("a", TypeVar("x"))
        t = TypeArrow(TypeVar("a"), TypeVar("b"))
        result = s.apply(t)
        expected = TypeArrow(TypeVar("x"), TypeVar("b"))
        assert result == expected

    def test_apply_forall(self):
        """Test applying substitution to forall type."""
        s = Substitution.singleton("b", TypeVar("x"))
        body = TypeArrow(TypeVar("a"), TypeVar("b"))
        t = TypeForall("a", body)
        result = s.apply(t)
        expected_body = TypeArrow(TypeVar("a"), TypeVar("x"))
        expected = TypeForall("a", expected_body)
        assert result == expected

    def test_apply_forall_avoids_capture(self):
        """Test substitution avoids capturing bound variables."""
        s = Substitution.singleton("a", TypeVar("x"))
        t = TypeForall("a", TypeVar("a"))
        result = s.apply(t)
        # Bound variable 'a' should not be substituted
        assert result == t

    def test_apply_constructor(self):
        """Test applying substitution to constructor."""
        s = Substitution.singleton("a", TypeVar("x"))
        t = TypeConstructor("List", [TypeVar("a")])
        result = s.apply(t)
        expected = TypeConstructor("List", [TypeVar("x")])
        assert result == expected

    def test_compose_identity(self):
        """Test composition with empty substitution."""
        s = Substitution.singleton("a", TypeVar("b"))
        empty = Substitution.empty()
        assert s.compose(empty) == s
        assert empty.compose(s) == s

    def test_compose_order(self):
        """Test composition order: self ∘ other."""
        # other substitutes a -> b
        other = Substitution.singleton("a", TypeVar("b"))
        # self substitutes b -> c
        self_sub = Substitution.singleton("b", TypeVar("c"))
        # Compose: apply other first, then self
        composed = self_sub.compose(other)
        # a should become c (a -> b -> c)
        assert composed.apply(TypeVar("a")) == TypeVar("c")

    def test_compose_complex(self):
        """Test complex composition."""
        s1 = Substitution.singleton("a", TypeVar("b"))
        s2 = Substitution.singleton("b", TypeVar("c"))
        composed = s2.compose(s1)
        # After s1 then s2: a -> b -> c
        assert composed.apply(TypeVar("a")) == TypeVar("c")


class TestUnifyVariables:
    """Tests for variable unification."""

    def test_same_variable(self):
        """Test unifying same variable."""
        t = TypeVar("a")
        result = unify(t, t)
        assert result == Substitution.empty()

    def test_var_with_type(self):
        """Test unifying variable with concrete type."""
        t1 = TypeVar("a")
        t2 = TypeConstructor("Int", [])
        result = unify(t1, t2)
        assert result == Substitution.singleton("a", t2)

    def test_type_with_var(self):
        """Test unifying concrete type with variable."""
        t1 = TypeConstructor("Int", [])
        t2 = TypeVar("a")
        result = unify(t1, t2)
        assert result == Substitution.singleton("a", t1)


class TestUnifyArrows:
    """Tests for arrow type unification."""

    def test_simple_arrow(self):
        """Test unifying simple arrows."""
        t1 = TypeArrow(TypeVar("a"), TypeVar("b"))
        t2 = TypeArrow(TypeVar("x"), TypeVar("y"))
        result = unify(t1, t2)
        # Result should unify a with x and b with y
        assert result.apply(t1) == result.apply(t2)

    def test_arrow_with_concrete(self):
        """Test unifying arrow with concrete types."""
        t1 = TypeArrow(TypeVar("a"), TypeVar("a"))
        int_type = TypeConstructor("Int", [])
        t2 = TypeArrow(int_type, int_type)
        result = unify(t1, t2)
        assert result.apply(TypeVar("a")) == int_type

    def test_arrow_mismatch(self):
        """Test unifying arrows with different structure."""
        t1 = TypeArrow(TypeVar("a"), TypeVar("b"))
        t2 = TypeConstructor("Int", [])
        with pytest.raises(UnificationError):
            unify(t1, t2)


class TestUnifyForall:
    """Tests for forall type unification (first-order only)."""

    def test_same_forall(self):
        """Test unifying identical forall types."""
        body = TypeArrow(TypeVar("a"), TypeVar("a"))
        t1 = TypeForall("a", body)
        t2 = TypeForall("a", body)
        result = unify(t1, t2)
        assert result == Substitution.empty()

    def test_forall_different_var(self):
        """Test unifying forall with different bound variables."""
        t1 = TypeForall("a", TypeVar("a"))
        t2 = TypeForall("b", TypeVar("b"))
        result = unify(t1, t2)
        # First-order: unifies bodies a and b (both are free in body context)
        # Note: Full alpha-equivalence checking is Phase 2
        assert result.apply(TypeVar("a")) == TypeVar("b")


class TestUnifyConstructors:
    """Tests for constructor unification."""

    def test_same_nullary(self):
        """Test unifying same nullary constructor."""
        t1 = TypeConstructor("Int", [])
        t2 = TypeConstructor("Int", [])
        result = unify(t1, t2)
        assert result == Substitution.empty()

    def test_different_constructors(self):
        """Test unifying different constructors."""
        t1 = TypeConstructor("Int", [])
        t2 = TypeConstructor("Bool", [])
        with pytest.raises(UnificationError):
            unify(t1, t2)

    def test_same_constructor_with_args(self):
        """Test unifying constructors with unifiable args."""
        t1 = TypeConstructor("List", [TypeVar("a")])
        t2 = TypeConstructor("List", [TypeConstructor("Int", [])])
        result = unify(t1, t2)
        assert result.apply(TypeVar("a")) == TypeConstructor("Int", [])

    def test_different_arity(self):
        """Test unifying constructors with different arities."""
        t1 = TypeConstructor("Pair", [TypeVar("a"), TypeVar("b")])
        t2 = TypeConstructor("Pair", [TypeVar("a")])
        with pytest.raises(UnificationError):
            unify(t1, t2)


class TestOccursCheck:
    """Tests for occurs check failures."""

    def test_simple_occurs(self):
        """Test simple occurs check failure."""
        t1 = TypeVar("a")
        t2 = TypeArrow(TypeVar("a"), TypeConstructor("Int", []))
        with pytest.raises(OccursCheckError):
            unify(t1, t2)

    def test_nested_occurs(self):
        """Test nested occurs check failure."""
        t1 = TypeVar("a")
        t2 = TypeConstructor("List", [TypeVar("a")])
        with pytest.raises(OccursCheckError):
            unify(t1, t2)

    def test_occurs_in_return(self):
        """Test occurs in return type."""
        t1 = TypeVar("a")
        t2 = TypeArrow(TypeConstructor("Int", []), TypeVar("a"))
        with pytest.raises(OccursCheckError):
            unify(t1, t2)


class TestUnifyComposition:
    """Tests demonstrating substitution composition in unification."""

    def test_transitive_unification(self):
        """Test that unification properly composes substitutions."""
        # Unify: (a -> b) with (Int -> c)
        t1 = TypeArrow(TypeVar("a"), TypeVar("b"))
        t2 = TypeArrow(TypeConstructor("Int", []), TypeVar("c"))
        result = unify(t1, t2)
        # Should substitute a -> Int and b -> c
        assert result.apply(TypeVar("a")) == TypeConstructor("Int", [])
        assert result.apply(TypeVar("b")) == TypeVar("c")

    def test_chain_unification(self):
        """Test chaining unifications."""
        # First unify: a with b -> c
        s1 = unify(TypeVar("a"), TypeArrow(TypeVar("b"), TypeVar("c")))
        # Then unify: a with Int -> d
        applied = s1.apply(TypeVar("a"))
        s2 = unify(applied, TypeArrow(TypeConstructor("Int", []), TypeVar("d")))
        # Compose
        final = s2.compose(s1)
        # Check result
        assert final.apply(TypeVar("b")) == TypeConstructor("Int", [])
        assert final.apply(TypeVar("c")) == TypeVar("d")
