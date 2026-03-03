"""Tests for type operations."""

import pytest

from systemf.core.types import TypeVar, TypeArrow, TypeForall, TypeConstructor


class TestTypeVar:
    """Tests for TypeVar."""

    def test_str(self):
        """Test string representation."""
        t = TypeVar("a")
        assert str(t) == "a"

    def test_free_vars(self):
        """Test free_vars returns the variable name."""
        t = TypeVar("a")
        assert t.free_vars() == {"a"}

    def test_substitute_matching(self):
        """Test substitution with matching variable."""
        t = TypeVar("a")
        subst = {"a": TypeVar("b")}
        result = t.substitute(subst)
        assert result == TypeVar("b")

    def test_substitute_non_matching(self):
        """Test substitution with non-matching variable."""
        t = TypeVar("a")
        subst = {"b": TypeVar("c")}
        result = t.substitute(subst)
        assert result == TypeVar("a")


class TestTypeArrow:
    """Tests for TypeArrow (function types)."""

    def test_str(self):
        """Test string representation."""
        t = TypeArrow(TypeVar("a"), TypeVar("b"))
        assert str(t) == "a -> b"

    def test_free_vars(self):
        """Test free_vars returns union of free variables."""
        t = TypeArrow(TypeVar("a"), TypeVar("b"))
        assert t.free_vars() == {"a", "b"}

    def test_substitute(self):
        """Test substitution propagates to components."""
        t = TypeArrow(TypeVar("a"), TypeVar("b"))
        subst = {"a": TypeVar("x"), "b": TypeVar("y")}
        result = t.substitute(subst)
        expected = TypeArrow(TypeVar("x"), TypeVar("y"))
        assert result == expected


class TestTypeForall:
    """Tests for TypeForall (polymorphic types)."""

    def test_str(self):
        """Test string representation."""
        body = TypeArrow(TypeVar("a"), TypeVar("a"))
        t = TypeForall("a", body)
        assert str(t) == "∀a.a -> a"

    def test_free_vars_excludes_bound(self):
        """Test free_vars excludes bound variable."""
        body = TypeArrow(TypeVar("a"), TypeVar("b"))
        t = TypeForall("a", body)
        assert t.free_vars() == {"b"}

    def test_substitute_avoids_capture(self):
        """Test substitution avoids capturing bound variable."""
        body = TypeArrow(TypeVar("a"), TypeVar("b"))
        t = TypeForall("a", body)
        subst = {"a": TypeVar("x")}  # Should be ignored
        result = t.substitute(subst)
        assert result == t

    def test_substitute_applies_to_body(self):
        """Test substitution applies to body."""
        body = TypeArrow(TypeVar("a"), TypeVar("b"))
        t = TypeForall("a", body)
        subst = {"b": TypeVar("c")}
        result = t.substitute(subst)
        expected_body = TypeArrow(TypeVar("a"), TypeVar("c"))
        expected = TypeForall("a", expected_body)
        assert result == expected


class TestTypeConstructor:
    """Tests for TypeConstructor (data types)."""

    def test_str(self):
        """Test string representation."""
        t = TypeConstructor("List", [TypeVar("a")])
        assert str(t) == "List a"

    def test_free_vars(self):
        """Test free_vars returns union of free variables in args."""
        t = TypeConstructor("Pair", [TypeVar("a"), TypeVar("b")])
        assert t.free_vars() == {"a", "b"}

    def test_substitute(self):
        """Test substitution applies to all arguments."""
        t = TypeConstructor("Pair", [TypeVar("a"), TypeVar("b")])
        subst = {"a": TypeVar("x")}
        result = t.substitute(subst)
        expected = TypeConstructor("Pair", [TypeVar("x"), TypeVar("b")])
        assert result == expected


class TestTypeEquality:
    """Tests for type equality (via frozen dataclasses)."""

    def test_typevar_equality(self):
        """Test TypeVar equality (representative for all dataclass-based types)."""
        assert TypeVar("a") == TypeVar("a")
        assert TypeVar("a") != TypeVar("b")


class TestExampleTypes:
    """Tests for example types from specification."""

    def test_identity_type(self):
        """Test identity type: ∀a. a -> a."""
        id_type = TypeForall("a", TypeArrow(TypeVar("a"), TypeVar("a")))
        assert str(id_type) == "∀a.a -> a"
        assert id_type.free_vars() == set()

    def test_list_int(self):
        """Test List Int."""
        list_int = TypeConstructor("List", [TypeConstructor("Int", [])])
        assert str(list_int) == "List Int"
        assert list_int.free_vars() == set()

    def test_maybe_a(self):
        """Test Maybe a."""
        maybe_a = TypeForall("a", TypeConstructor("Maybe", [TypeVar("a")]))
        assert str(maybe_a) == "∀a.Maybe a"
        assert maybe_a.free_vars() == set()
