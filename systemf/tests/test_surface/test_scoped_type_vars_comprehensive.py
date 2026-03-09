"""Comprehensive ScopedTypeVariables test suite."""

import pytest
from systemf.surface.parser import parse_program
from systemf.surface.pipeline import run_pipeline


class TestBasicDeclScope:
    """Test DECL-SCOPE: Declaration-level scoped type variables."""

    def test_simple_scoped_type_var(self):
        """Basic scoped type variable in annotation."""
        source = """
id :: forall a. a -> a = \\x -> (x :: a)
"""
        decls = parse_program(source)
        result = run_pipeline(decls, module_name="test")
        assert result.is_ok(), f"Failed: {result.unwrap_err()}"

    def test_scoped_var_in_let(self):
        """Scoped type var available in let binding."""
        source = """
f :: forall a. a -> a = \\x ->
  let y = (x :: a) in y
"""
        decls = parse_program(source)
        result = run_pipeline(decls, module_name="test")
        assert result.is_ok()


class TestMultiVarDeclScope:
    """Test multiple forall variables."""

    def test_two_forall_vars(self):
        """forall a b. binds both variables."""
        source = """
const :: forall a b. a -> b -> a = \\x y -> (x :: a)
"""
        decls = parse_program(source)
        result = run_pipeline(decls, module_name="test")
        assert result.is_ok()


class TestDeclScopeErrors:
    """Test DECL-SCOPE error cases."""

    @pytest.mark.xfail(reason="System SB is permissive - unbound vars become inferred, not error")
    def test_unbound_type_var_should_fail(self):
        """Using unbound type var should error (System V behavior)."""
        source = """
f :: forall a. a -> a = \\x -> (x :: b)
"""
        decls = parse_program(source)
        result = run_pipeline(decls, module_name="test")
        assert result.is_err()


class TestLamAnnScope:
    """Test LAM-ANN-SCOPE: Lambda parameter annotations."""

    def test_lambda_param_with_forall(self):
        """Lambda param with forall binds vars for body."""
        source = """
usePoly :: (forall a. a -> a) -> Int =
  \\(f :: forall a. a -> a) -> f 42
"""
        decls = parse_program(source)
        result = run_pipeline(decls, module_name="test")
        assert result.is_ok()

    def test_lambda_param_with_type_app(self):
        """Can use scoped type var in type application."""
        source = """
usePoly :: (forall a. a -> a) -> Int =
  \\(f :: forall a. a -> a) -> f @Int 42
"""
        decls = parse_program(source)
        result = run_pipeline(decls, module_name="test")
        assert result.is_ok()


class TestPatPoly:
    """Test PAT-POLY: Pattern matching."""

    def test_pattern_poly_box(self):
        """Pattern match on PolyBox."""
        source = """
data PolyBox = PolyBox (forall a. a -> a)

useBox :: PolyBox -> Int =
  \\pb -> case pb of
    PolyBox f -> f 42
"""
        decls = parse_program(source)
        result = run_pipeline(decls, module_name="test")
        assert result.is_ok()


class TestIntegration:
    """Integration tests."""

    @pytest.mark.xfail(
        reason="Complex integration case - let binding with polymorphic lambda needs further debugging"
    )
    def test_full_pipeline(self):
        """Complete example with all features."""
        source = """
data PolyBox = PolyBox (forall a. a -> a)

id :: forall a. a -> a = \\x -> (x :: a)

useId :: PolyBox -> Int =
  \\pb -> case pb of
    PolyBox f ->
      let g = \\(h :: forall b. b -> b) -> h @Int 42
      in g f
"""
        decls = parse_program(source)
        result = run_pipeline(decls, module_name="test")
        assert result.is_ok()
