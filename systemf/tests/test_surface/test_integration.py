"""Integration tests for surface language pipeline.

Tests that combine lexing, parsing, elaboration, and type checking.
"""

import pytest

from systemf.core.checker import TypeChecker
from systemf.core.types import TypeArrow, TypeConstructor, TypeForall, TypeVar
from systemf.surface.elaborator import elaborate
from systemf.core.module import Module
from systemf.surface.lexer import lex
from systemf.surface.parser import Parser


class TestFullPipeline:
    """End-to-end tests for the complete pipeline."""

    def test_simple_identity(self):
        """Full pipeline: parse and elaborate identity function."""
        source = r"""
        id : forall a. a -> a = /\a. \x:a -> x
        """

        # Parse
        tokens = lex(source)
        surface_decls = Parser(tokens).parse()

        # Elaborate
        module = elaborate(surface_decls)

        assert len(module.declarations) == 1
        assert module.declarations[0].name == "id"

    def test_bool_type(self):
        """Full pipeline with boolean type."""
        source = """
        data Bool =
          True
          | False
        """

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        module = elaborate(surface_decls)

        assert len(module.declarations) == 1
        assert "True" in module.constructor_types
        assert "False" in module.constructor_types

    def test_list_type(self):
        """Full pipeline with list type."""
        source = """
        data List a =
          Nil
          | Cons a (List a)
        """

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        module = elaborate(surface_decls)

        assert len(module.declarations) == 1
        assert "Nil" in module.constructor_types
        assert "Cons" in module.constructor_types

    @pytest.mark.xfail(reason="Parser treats multiple constructors as single constructor with args")
    def test_type_checking_integration(self):
        """Full pipeline including type checking."""
        source = r"""
        data Bool =
          True
          | False

        not : Bool -> Bool = \b:Bool -> case b of
          True -> False
          False -> True
        """

        # Parse
        tokens = lex(source)
        surface_decls = Parser(tokens).parse()

        # Elaborate
        module = elaborate(surface_decls)

        # Type check
        checker = TypeChecker(module.constructor_types)
        types = checker.check_program(module.declarations)

        assert "not" in types
        assert types["not"] == TypeArrow(TypeConstructor("Bool", []), TypeConstructor("Bool", []))


class TestPolymorphism:
    """Tests for polymorphic function handling."""

    def test_polymorphic_identity(self):
        """Test polymorphic identity function."""
        source = r"""
        id : forall a. a -> a = /\a. \x:a -> x
        """

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        module = elaborate(surface_decls)

        checker = TypeChecker(module.constructor_types)
        types = checker.check_program(module.declarations)

        assert "id" in types
        assert isinstance(types["id"], TypeForall)

    @pytest.mark.xfail(reason="Parser treats multiple constructors as single constructor with args")
    def test_type_application(self):
        """Test type application."""
        source = r"""
        data Int =
          IntVal
        data Bool =
          True
          False

        trueVal : Bool = True
        intVal : Int = IntVal
        """

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        module = elaborate(surface_decls)

        checker = TypeChecker(module.constructor_types)
        types = checker.check_program(module.declarations)

        assert "trueVal" in types
        assert "intVal" in types


class TestPatternMatching:
    """Tests for pattern matching."""

    def test_simple_case(self):
        """Test simple case expression."""
        source = r"""
        data Bool =
          True
          | False

        const : Bool -> Bool -> Bool = \x:Bool -> \y:Bool -> case x of
          True -> y
          False -> False
        """

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        module = elaborate(surface_decls)

        checker = TypeChecker(module.constructor_types)
        types = checker.check_program(module.declarations)

        assert "const" in types

    def test_nested_pattern(self):
        """Test nested constructor pattern."""
        source = r"""
        data Bool =
          True
          | False
        data Nat =
          Zero
          | Succ Nat

        isZero : Nat -> Bool = \n:Nat -> case n of
          Zero -> True
          Succ m -> False
        """

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        module = elaborate(surface_decls)

        checker = TypeChecker(module.constructor_types)
        types = checker.check_program(module.declarations)

        assert "isZero" in types


class TestComplexExamples:
    """Tests for more complex examples."""

    def test_compose(self):
        """Test compose function."""
        source = r"""
        compose : forall a b c. (b -> c) -> (a -> b) -> a -> c = /\a. /\b. /\c. \f:(b -> c) -> \g:(a -> b) -> \x:a -> f (g x)
        """

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        module = elaborate(surface_decls)

        checker = TypeChecker(module.constructor_types)
        types = checker.check_program(module.declarations)

        assert "compose" in types

    @pytest.mark.xfail(reason="Parser treats multiple constructors as single constructor with args")
    def test_list_map(self):
        """Test list map function (simplified)."""
        source = r"""
        data List a =
          Nil
          Cons a (List a)
        data Bool =
          True
          False

        isEmpty : forall a. List a -> Bool = /\a. \xs:(List a) -> case xs of
          Nil -> True
          Cons x xs -> False
        """

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        module = elaborate(surface_decls)

        checker = TypeChecker(module.constructor_types)
        types = checker.check_program(module.declarations)

        assert "isEmpty" in types
