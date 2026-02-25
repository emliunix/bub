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

    def test_str_simple(self):
        """Test string representation of simple arrow."""
        t = TypeArrow(TypeVar("a"), TypeVar("b"))
        assert str(t) == "a -> b"

    def test_str_nested(self):
        """Test string representation of nested arrow."""
        inner = TypeArrow(TypeVar("a"), TypeVar("b"))
        t = TypeArrow(inner, TypeVar("c"))
        assert str(t) == "(a -> b) -> c"

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

    def test_str_nullary(self):
        """Test string representation of nullary constructor."""
        t = TypeConstructor("Int", [])
        assert str(t) == "Int"

    def test_str_unary(self):
        """Test string representation of unary constructor."""
        t = TypeConstructor("List", [TypeVar("a")])
        assert str(t) == "List a"

    def test_str_binary(self):
        """Test string representation of binary constructor."""
        t = TypeConstructor("Pair", [TypeVar("a"), TypeVar("b")])
        assert str(t) == "Pair a b"

    def test_str_with_arrow(self):
        """Test string representation with arrow argument."""
        arg = TypeArrow(TypeVar("a"), TypeVar("b"))
        t = TypeConstructor("Fun", [arg])
        assert str(t) == "Fun (a -> b)"

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
        """Test TypeVar equality."""
        assert TypeVar("a") == TypeVar("a")
        assert TypeVar("a") != TypeVar("b")

    def test_arrow_equality(self):
        """Test TypeArrow equality."""
        t1 = TypeArrow(TypeVar("a"), TypeVar("b"))
        t2 = TypeArrow(TypeVar("a"), TypeVar("b"))
        t3 = TypeArrow(TypeVar("b"), TypeVar("a"))
        assert t1 == t2
        assert t1 != t3

    def test_forall_equality(self):
        """Test TypeForall equality."""
        body = TypeArrow(TypeVar("a"), TypeVar("a"))
        t1 = TypeForall("a", body)
        t2 = TypeForall("a", body)
        t3 = TypeForall("b", body)
        assert t1 == t2
        assert t1 != t3

    def test_constructor_equality(self):
        """Test TypeConstructor equality."""
        t1 = TypeConstructor("List", [TypeVar("a")])
        t2 = TypeConstructor("List", [TypeVar("a")])
        t3 = TypeConstructor("List", [TypeVar("b")])
        assert t1 == t2
        assert t1 != t3


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
