"""Tests for typing contexts."""

import pytest

from systemf.core.context import Context
from systemf.core.types import TypeVar, TypeArrow, TypeConstructor


class TestContextCreation:
    """Tests for context creation."""

    def test_empty_context(self):
        """Test creating empty context."""
        ctx = Context.empty()
        assert len(ctx) == 0
        assert ctx.type_vars == set()

    def test_context_with_vars(self):
        """Test creating context with variables."""
        ctx = Context([TypeVar("a"), TypeVar("b")], {"x"})
        assert len(ctx) == 2
        assert ctx.type_vars == {"x"}


class TestContextLookup:
    """Tests for context lookup."""

    def test_lookup_first(self):
        """Test looking up most recent variable (index 0)."""
        ctx = Context([TypeVar("a")], set())
        assert ctx.lookup_type(0) == TypeVar("a")

    def test_lookup_second(self):
        """Test looking up second variable (index 1)."""
        ctx = Context([TypeVar("a"), TypeVar("b")], set())
        # Index 0 is most recent: a
        assert ctx.lookup_type(0) == TypeVar("a")
        # Index 1 is next: b
        assert ctx.lookup_type(1) == TypeVar("b")

    def test_lookup_out_of_bounds(self):
        """Test lookup with out of bounds index."""
        ctx = Context.empty()
        with pytest.raises(IndexError):
            ctx.lookup_type(0)

    def test_lookup_negative_index(self):
        """Test lookup with negative index."""
        ctx = Context([TypeVar("a")], set())
        with pytest.raises(IndexError):
            ctx.lookup_type(-1)


class TestContextExtension:
    """Tests for context extension."""

    def test_extend_term(self):
        """Test extending context with term variable."""
        ctx = Context.empty()
        extended = ctx.extend_term(TypeVar("a"))
        assert len(extended) == 1
        assert extended.lookup_type(0) == TypeVar("a")
        # Original unchanged
        assert len(ctx) == 0

    def test_extend_term_ordering(self):
        """Test that extension shifts existing variables."""
        ctx = Context([TypeVar("a")], set())
        extended = ctx.extend_term(TypeVar("b"))
        # b is now at index 0, a at index 1
        assert extended.lookup_type(0) == TypeVar("b")
        assert extended.lookup_type(1) == TypeVar("a")

    def test_extend_type(self):
        """Test extending context with type variable."""
        ctx = Context.empty()
        extended = ctx.extend_type("a")
        assert "a" in extended.type_vars
        assert extended.term_vars == []

    def test_extend_type_preserves_terms(self):
        """Test that extending type preserves term variables."""
        ctx = Context([TypeVar("a")], set())
        extended = ctx.extend_type("x")
        assert len(extended) == 1
        assert "x" in extended.type_vars


class TestContextDeBruijn:
    """Tests demonstrating de Bruijn index behavior."""

    def test_nested_binding(self):
        """Test de Bruijn indices in nested bindings.

        Simulating: λx:a.λy:b.x
        - After binding x (type a): ctx = [a]
        - After binding y (type b): ctx = [b, a]
        - x has index 1 (was shifted by y)
        """
        ctx = Context.empty()
        ctx = ctx.extend_term(TypeVar("a"))  # bind x
        ctx = ctx.extend_term(TypeVar("b"))  # bind y
        # Now lookup:
        # index 0 = y (type b)
        # index 1 = x (type a)
        assert ctx.lookup_type(0) == TypeVar("b")
        assert ctx.lookup_type(1) == TypeVar("a")

    def test_function_type_context(self):
        """Test context with function types."""
        int_type = TypeConstructor("Int", [])
        fun_type = TypeArrow(int_type, int_type)
        ctx = Context.empty()
        ctx = ctx.extend_term(int_type)  # first arg
        ctx = ctx.extend_term(fun_type)  # second arg
        assert ctx.lookup_type(0) == fun_type
        assert ctx.lookup_type(1) == int_type


class TestContextStr:
    """Tests for string representation."""

    def test_empty_str(self):
        """Test string of empty context."""
        ctx = Context.empty()
        s = str(ctx)
        assert "terms=[]" in s
        assert "types=[]" in s

    def test_str_with_terms(self):
        """Test string with term variables."""
        ctx = Context([TypeVar("a"), TypeVar("b")], set())
        s = str(ctx)
        assert "x0:a" in s
        assert "x1:b" in s

    def test_str_with_types(self):
        """Test string with type variables."""
        ctx = Context([], {"a", "b"})
        s = str(ctx)
        assert "a" in s
        assert "b" in s
