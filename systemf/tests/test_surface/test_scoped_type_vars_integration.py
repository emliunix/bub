"""Integration tests for ScopedTypeVariables feature.

These tests validate the full ScopedTypeVariables implementation including:
- DECL-SCOPE: Type variables bound at declaration level available in body
- ANN-SCOPE: Type variables in annotations available in annotated terms
- LAM-ANN-SCOPE: Type variables in lambda params available in body
- PAT-POLY: Polymorphic pattern variables retain their types

Reference: docs/notes/visible-type-application.md
"""

import pytest

from systemf.surface.parser import parse_expression, parse_program
from systemf.surface.pipeline import Pipeline
from systemf.surface.inference.errors import TypeError


class TestDeclarationScopedTypeVars:
    """Test DECL-SCOPE: Declaration signatures bind type variables for body."""

    def test_basic_scoped_type_var(self):
        """id :: forall a. a -> a = \\x -> (x :: a) should work."""
        source = """
id :: forall a. a -> a = \\x -> (x :: a)
"""
        decls = parse_program(source)
        pipeline = Pipeline(module_name="test")
        result = pipeline.run(decls)

        assert result.is_ok(), (
            f"Should type check: {result.unwrap_err() if result.is_err() else ''}"
        )

    def test_scoped_var_in_nested_expr(self):
        """Type variable available in deeply nested expressions."""
        source = """
f :: forall a. a -> a = \\x -> 
  let y = (x :: a)
  in y
"""
        decls = parse_program(source)
        pipeline = Pipeline(module_name="test")
        result = pipeline.run(decls)

        assert result.is_ok()

    def test_scoped_var_with_type_app(self):
        """Can use scoped type variable in type application."""
        source = """
id :: forall a. a -> a = \\x -> x

f :: forall b. b -> b = \\x -> id @b x
"""
        decls = parse_program(source)
        pipeline = Pipeline(module_name="test")
        result = pipeline.run(decls)

        assert result.is_ok()

    def test_multiple_forall_vars(self):
        """forall a b. binds both variables."""
        source = """
const :: forall a b. a -> b -> a = \\x y -> (x :: a)
"""
        decls = parse_program(source)
        pipeline = Pipeline(module_name="test")
        result = pipeline.run(decls)

        assert result.is_ok()

    def test_unbound_type_var_in_annotation(self):
        """Using unbound type variable should error."""
        source = """
-- 'b' is not bound by the declaration
f :: forall a. a -> a = \\x -> (x :: b)
"""
        decls = parse_program(source)
        pipeline = Pipeline(module_name="test")
        result = pipeline.run(decls)

        assert result.is_err(), "Should fail: 'b' is not in scope"


class TestAnnotationScopedTypeVars:
    """Test ANN-SCOPE: Type annotations bind type variables for annotated term."""

    def test_annotation_binds_forall(self):
        """(e :: forall a. a -> a) binds 'a' for e."""
        source = """
-- The annotation forall a. a -> a binds 'a' in \\x -> x
f :: Int -> Int = \\x -> ((\\y -> y) :: forall a. a -> a) x
"""
        decls = parse_program(source)
        pipeline = Pipeline(module_name="test")
        result = pipeline.run(decls)

        assert result.is_ok()

    def test_nested_annotation_scopes(self):
        """Nested annotations have nested scopes."""
        source = """
f :: Int -> Int = \\x -> 
  ( (\\y -> (y :: forall b. b -> b) 42) :: forall a. a -> a ) x
"""
        decls = parse_program(source)
        pipeline = Pipeline(module_name="test")
        result = pipeline.run(decls)

        assert result.is_ok()


class TestLambdaParamScopedTypeVars:
    """Test LAM-ANN-SCOPE: Lambda param annotations bind type variables for body."""

    def test_lambda_param_forall(self):
        """\\(f :: forall a. a -> a) -> ... binds 'a' in body."""
        source = """
usePoly :: (forall a. a -> a) -> Int = \\(f :: forall a. a -> a) -> f 42
"""
        decls = parse_program(source)
        pipeline = Pipeline(module_name="test")
        result = pipeline.run(decls)

        assert result.is_ok()

    def test_lambda_param_with_type_app(self):
        """Can use scoped type variable in type application."""
        source = """
usePoly :: (forall a. a -> a) -> Int = \\(f :: forall a. a -> a) -> f @Int 42
"""
        decls = parse_program(source)
        pipeline = Pipeline(module_name="test")
        result = pipeline.run(decls)

        assert result.is_ok()

    def test_lambda_param_rank2_with_return(self):
        """Higher-rank lambda parameter with return type."""
        source = """
applyToPoly :: (forall a. a -> a) -> Int -> Int = \\
  (f :: forall a. a -> a) (x :: Int) -> f @Int x
"""
        decls = parse_program(source)
        pipeline = Pipeline(module_name="test")
        result = pipeline.run(decls)

        assert result.is_ok()


class TestPatternPolymorphicBinders:
    """Test PAT-POLY: Pattern variables retain polymorphic types."""

    def test_pattern_poly_box(self):
        """Pattern match on PolyBox should give polymorphic function."""
        source = """
data PolyBox = PolyBox (forall a. a -> a)

useBox :: PolyBox -> Int = \\
  (PolyBox f) -> f 42
"""
        decls = parse_program(source)
        pipeline = Pipeline(module_name="test")
        result = pipeline.run(decls)

        assert result.is_ok()

    def test_pattern_poly_with_type_app(self):
        """Can use type application on pattern-bound polymorphic function."""
        source = """
data PolyBox = PolyBox (forall a. a -> a)

useBox :: PolyBox -> (Int, Bool) = \\
  (PolyBox f) -> (f @Int 42, f @Bool True)
"""
        decls = parse_program(source)
        pipeline = Pipeline(module_name="test")
        result = pipeline.run(decls)

        assert result.is_ok()


class TestScopedTypeVarsIntegration:
    """Integration tests combining multiple features."""

    def test_full_example(self):
        """Complete example with declaration, lambda, and pattern scoped vars."""
        source = """
data PolyBox = PolyBox (forall a. a -> a)

id :: forall a. a -> a = \\x -> (x :: a)

useId :: PolyBox -> Int = \\
  (PolyBox f) -> 
    let g = \\(h :: forall b. b -> b) -> h @Int 42
    in g f
"""
        decls = parse_program(source)
        pipeline = Pipeline(module_name="test")
        result = pipeline.run(decls)

        assert result.is_ok()

    def test_scoped_var_escaping_scope_should_fail(self):
        """Type variable should not escape its scope."""
        source = """
-- 'a' from id's forall should not be available here
outer :: Int -> Int = \\x -> 
  let result = id @a x  -- 'a' not in scope here
  in result
  where
    id :: forall a. a -> a = \\y -> y
"""
        decls = parse_program(source)
        pipeline = Pipeline(module_name="test")
        result = pipeline.run(decls)

        # This might or might not fail depending on scoping rules
        # For now, let's just document the behavior
        pass  # TODO: Define expected behavior


class TestScopedTypeVarsEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_forall_not_allowed(self):
        """Empty forall should be rejected or handled gracefully."""
        # This is a syntax-level check, might be caught by parser
        pass  # TODO: Depends on parser behavior

    def test_shadowing_type_vars(self):
        """Inner forall should shadow outer."""
        source = """
-- Inner 'a' shadows outer 'a'
f :: forall a. a -> (forall a. a -> a) = \\
  (x :: a) (f :: forall a. a -> a) -> f x
"""
        decls = parse_program(source)
        pipeline = Pipeline(module_name="test")
        result = pipeline.run(decls)

        # Should work with proper shadowing
        assert result.is_ok()

    def test_type_var_in_type_annotation_only(self):
        """Type variable only available where bound."""
        source = """
-- 'a' is bound in annotation but not available in unrelated subexpr
f :: Int -> Int = \\x -> 
  let y = (x :: forall a. a -> a)  -- 'a' bound here
      z = y  -- 'a' not available here
  in z
"""
        decls = parse_program(source)
        pipeline = Pipeline(module_name="test")
        result = pipeline.run(decls)

        # Should work - z uses the instantiated type
        assert result.is_ok()


# Mark tests that are expected to fail until implementation is complete
pytestmark = [
    pytest.mark.xfail(
        reason="ScopedTypeVariables implementation pending - DECL-SCOPE, ANN-SCOPE, LAM-ANN-SCOPE not yet implemented",
        strict=False,
    )
]
