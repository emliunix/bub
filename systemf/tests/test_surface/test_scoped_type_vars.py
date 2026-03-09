"""Tests for ScopedTypeVariables helper functions.

Tests for:
- collect_forall_vars: Extracting forall-bound type variables from types
- extend_with_forall_vars: Extending TypeContext with forall-bound variables
"""

import pytest

from systemf.core.types import (
    Type,
    TypeVar,
    TypeArrow,
    TypeForall,
    TypeConstructor,
)
from systemf.surface.inference.context import (
    TypeContext,
    collect_forall_vars,
    extend_with_forall_vars,
)


# =============================================================================
# Tests for collect_forall_vars
# =============================================================================


class TestCollectForallVars:
    """Test cases for collect_forall_vars function."""

    def test_single_forall(self):
        """forall a. a -> a should return ['a']."""
        # forall a. a -> a
        ty = TypeForall("a", TypeArrow(TypeVar("a"), TypeVar("a")))

        result = collect_forall_vars(ty)

        assert result == ["a"]

    def test_nested_foralls(self):
        """forall a. forall b. a -> b should return ['a', 'b']."""
        # forall a. forall b. a -> b
        ty = TypeForall("a", TypeForall("b", TypeArrow(TypeVar("a"), TypeVar("b"))))

        result = collect_forall_vars(ty)

        assert result == ["a", "b"]

    def test_triple_nested_foralls(self):
        """forall a. forall b. forall c. a -> b -> c should return ['a', 'b', 'c']."""
        # forall a. forall b. forall c. a -> b -> c
        ty = TypeForall(
            "a",
            TypeForall(
                "b", TypeForall("c", TypeArrow(TypeVar("a"), TypeArrow(TypeVar("b"), TypeVar("c"))))
            ),
        )

        result = collect_forall_vars(ty)

        assert result == ["a", "b", "c"]

    def test_non_forall_type_arrow(self):
        """Int -> Int should return []."""
        # Int -> Int
        ty = TypeArrow(TypeConstructor("Int", []), TypeConstructor("Int", []))

        result = collect_forall_vars(ty)

        assert result == []

    def test_non_forall_type_constructor(self):
        """Int should return []."""
        # Int
        ty = TypeConstructor("Int", [])

        result = collect_forall_vars(ty)

        assert result == []

    def test_non_forall_type_var(self):
        """TypeVar 'a' should return []."""
        # a
        ty = TypeVar("a")

        result = collect_forall_vars(ty)

        assert result == []

    def test_forall_with_constructor_args(self):
        """forall a. List a should return ['a']."""
        # forall a. List a
        ty = TypeForall("a", TypeConstructor("List", [TypeVar("a")]))

        result = collect_forall_vars(ty)

        assert result == ["a"]

    def test_forall_with_nested_arrow(self):
        """forall a. (a -> a) -> a should return ['a']."""
        # forall a. (a -> a) -> a
        inner_arrow = TypeArrow(TypeVar("a"), TypeVar("a"))
        ty = TypeForall("a", TypeArrow(inner_arrow, TypeVar("a")))

        result = collect_forall_vars(ty)

        assert result == ["a"]


# =============================================================================
# Tests for extend_with_forall_vars
# =============================================================================


class TestExtendWithForallVars:
    """Test cases for extend_with_forall_vars function."""

    def test_extend_single_forall(self):
        """Context extended with forall a. a -> a should have 'a' at index 0."""
        ctx = TypeContext()
        ty = TypeForall("a", TypeArrow(TypeVar("a"), TypeVar("a")))

        new_ctx = extend_with_forall_vars(ctx, ty)

        assert new_ctx.lookup_type_var_index("a") == 0
        assert new_ctx.get_type_count() == 1

    def test_extend_nested_foralls(self):
        """Context extended with forall a. forall b. a -> b should have correct indices."""
        ctx = TypeContext()
        ty = TypeForall("a", TypeForall("b", TypeArrow(TypeVar("a"), TypeVar("b"))))

        new_ctx = extend_with_forall_vars(ctx, ty)

        # Outermost forall becomes index 0
        assert new_ctx.lookup_type_var_index("a") == 0
        # Inner forall becomes index 1
        assert new_ctx.lookup_type_var_index("b") == 1
        assert new_ctx.get_type_count() == 2

    def test_extend_preserves_existing_context(self):
        """Extension should preserve existing type variables in context."""
        # Start with an existing type variable
        ctx = TypeContext(type_vars=[("existing", None)])
        ty = TypeForall("a", TypeArrow(TypeVar("a"), TypeVar("a")))

        new_ctx = extend_with_forall_vars(ctx, ty)

        # New variable should be at index 0 (prepended)
        assert new_ctx.lookup_type_var_index("a") == 0
        # Existing variable should be shifted to index 1
        assert new_ctx.lookup_type_var_index("existing") == 1
        assert new_ctx.get_type_count() == 2

    def test_extend_non_forall_type(self):
        """Extending with non-forall type should not modify context."""
        ctx = TypeContext()
        ty = TypeArrow(TypeConstructor("Int", []), TypeConstructor("Int", []))

        new_ctx = extend_with_forall_vars(ctx, ty)

        assert new_ctx.get_type_count() == 0
        assert new_ctx == ctx  # Should be identical (no change)

    def test_extend_empty_context(self):
        """Extending empty context with forall type should work."""
        ctx = TypeContext()
        ty = TypeForall(
            "x",
            TypeForall(
                "y", TypeForall("z", TypeArrow(TypeVar("x"), TypeArrow(TypeVar("y"), TypeVar("z"))))
            ),
        )

        new_ctx = extend_with_forall_vars(ctx, ty)

        assert new_ctx.lookup_type_var_index("x") == 0
        assert new_ctx.lookup_type_var_index("y") == 1
        assert new_ctx.lookup_type_var_index("z") == 2
        assert new_ctx.get_type_count() == 3

    def test_context_immutability(self):
        """Original context should not be modified."""
        ctx = TypeContext()
        original_count = ctx.get_type_count()
        ty = TypeForall("a", TypeArrow(TypeVar("a"), TypeVar("a")))

        _ = extend_with_forall_vars(ctx, ty)

        # Original context should be unchanged
        assert ctx.get_type_count() == original_count
        assert ctx.get_type_count() == 0


# =============================================================================
# Integration Tests
# =============================================================================


# =============================================================================
# DECL-SCOPE Tests
# =============================================================================


class TestDeclScope:
    """Test cases for DECL-SCOPE rule.

    The DECL-SCOPE rule extends the type context with forall-bound variables
    from declaration signatures before checking the body.

    Rule:
        Γ, ā ⊢ e ⇐ σ    where decl has type ∀ā.σ
        ----------------------------------------
        Γ ⊢ decl :: ∀ā.σ = e
    """

    def test_decl_scope_basic(self):
        """Test: id :: forall a. a -> a = \\x -> (x :: a) should type check."""
        # This test validates that 'a' in (x :: a) is recognized as the
        # scoped type variable from the forall quantifier
        from systemf.surface.parser import parse_program
        from systemf.surface.pipeline import elaborate_module

        code = "id :: forall a. a -> a = \\x -> (x :: a)"

        decls = parse_program(code)
        result = elaborate_module(decls)

        assert result.success, f"Expected compilation to succeed, got errors: {result.errors}"

    def test_decl_scope_nested(self):
        """Test: Nested foralls should extend context correctly."""
        from systemf.surface.parser import parse_program
        from systemf.surface.pipeline import elaborate_module

        code = "const :: forall a b. a -> b -> a = \\x y -> (x :: a)"

        decls = parse_program(code)
        result = elaborate_module(decls)

        assert result.success, f"Expected compilation to succeed, got errors: {result.errors}"


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for both functions working together."""

    def test_roundtrip_extraction_and_extension(self):
        """Extract vars, extend context, verify indices match extraction order."""
        # forall a. forall b. forall c. a -> b -> c
        ty = TypeForall(
            "a",
            TypeForall(
                "b", TypeForall("c", TypeArrow(TypeVar("a"), TypeArrow(TypeVar("b"), TypeVar("c"))))
            ),
        )

        # Extract variables
        vars = collect_forall_vars(ty)

        # Extend context
        ctx = TypeContext()
        new_ctx = extend_with_forall_vars(ctx, ty)

        # Verify indices match extraction order
        for i, var in enumerate(vars):
            assert new_ctx.lookup_type_var_index(var) == i

    def test_complex_type_multiple_foralls(self):
        """Test with a complex type containing multiple nested foralls."""
        # forall f. forall a. f a -> List (f a)
        fa = TypeConstructor("f", [TypeVar("a")])
        list_fa = TypeConstructor("List", [fa])
        inner_arrow = TypeArrow(fa, list_fa)
        forall_a = TypeForall("a", inner_arrow)
        ty = TypeForall("f", forall_a)

        vars = collect_forall_vars(ty)
        assert vars == ["f", "a"]

        ctx = extend_with_forall_vars(TypeContext(), ty)
        assert ctx.lookup_type_var_index("f") == 0
        assert ctx.lookup_type_var_index("a") == 1
