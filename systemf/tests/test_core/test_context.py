"""Tests for typing contexts."""

import pytest

from systemf.core.context import Context
from systemf.core.types import TypeVar


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

    def test_lookup_valid_indices(self):
        """Test looking up valid indices (0, 1)."""
        ctx = Context([TypeVar("a"), TypeVar("b")], set())
        # Index 0 is most recent: a
        assert ctx.lookup_type(0) == TypeVar("a")
        # Index 1 is next: b
        assert ctx.lookup_type(1) == TypeVar("b")

    def test_lookup_invalid_indices(self):
        """Test lookup with invalid indices (out of bounds, negative)."""
        ctx = Context([TypeVar("a")], set())
        with pytest.raises(IndexError):
            ctx.lookup_type(1)  # out of bounds
        with pytest.raises(IndexError):
            ctx.lookup_type(-1)  # negative index


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


class TestContextStr:
    """Tests for string representation."""

    def test_str_with_terms(self):
        """Test string representation with term variables."""
        ctx = Context([TypeVar("a"), TypeVar("b")], set())
        s = str(ctx)
        assert "x0:a" in s
        assert "x1:b" in s
