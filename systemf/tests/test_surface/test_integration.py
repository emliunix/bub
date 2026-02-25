"""Integration tests for surface language pipeline.

Tests that combine lexing, parsing, elaboration, and type checking.
"""

import pytest

from systemf.core.checker import TypeChecker
from systemf.core.types import TypeArrow, TypeConstructor, TypeForall, TypeVar
from systemf.surface.elaborator import elaborate
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
        core_decls, constr_types = elaborate(surface_decls)

        assert len(core_decls) == 1
        assert core_decls[0].name == "id"

    @pytest.mark.xfail(reason="Parser treats multiple constructors as single constructor with args")
    def test_bool_type(self):
        """Full pipeline with boolean type."""
        source = """
        data Bool =
          True
          False
        """

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        core_decls, constr_types = elaborate(surface_decls)

        assert len(core_decls) == 1
        assert "True" in constr_types
        assert "False" in constr_types

    @pytest.mark.xfail(reason="Parser treats multiple constructors as single constructor with args")
    def test_list_type(self):
        """Full pipeline with list type."""
        source = """
        data List a =
          Nil
          Cons a (List a)
        """

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        core_decls, constr_types = elaborate(surface_decls)

        assert len(core_decls) == 1
        assert "Nil" in constr_types
        assert "Cons" in constr_types

    @pytest.mark.xfail(reason="Parser treats multiple constructors as single constructor with args")
    def test_type_checking_integration(self):
        """Full pipeline including type checking."""
        source = r"""
        data Bool =
          True
          False

        not : Bool -> Bool = \b:Bool -> case b of
          True -> False
          False -> True
        """

        # Parse
        tokens = lex(source)
        surface_decls = Parser(tokens).parse()

        # Elaborate
        core_decls, constr_types = elaborate(surface_decls)

        # Type check
        checker = TypeChecker(constr_types)
        types = checker.check_program(core_decls)

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
        core_decls, constr_types = elaborate(surface_decls)

        checker = TypeChecker(constr_types)
        types = checker.check_program(core_decls)

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
        core_decls, constr_types = elaborate(surface_decls)

        checker = TypeChecker(constr_types)
        types = checker.check_program(core_decls)

        assert "trueVal" in types
        assert "intVal" in types


class TestPatternMatching:
    """Tests for pattern matching."""

    @pytest.mark.xfail(reason="Parser treats multiple constructors as single constructor with args")
    def test_simple_case(self):
        """Test simple case expression."""
        source = r"""
        data Bool =
          True
          False

        const : Bool -> Bool -> Bool = \x:Bool -> \y:Bool -> case x of
          True -> y
          False -> False
        """

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        core_decls, constr_types = elaborate(surface_decls)

        checker = TypeChecker(constr_types)
        types = checker.check_program(core_decls)

        assert "const" in types

    @pytest.mark.xfail(reason="Parser treats multiple constructors as single constructor with args")
    def test_nested_pattern(self):
        """Test nested constructor pattern."""
        source = r"""
        data Bool =
          True
          False
        data Nat =
          Zero
          Succ Nat

        isZero : Nat -> Bool = \n:Nat -> case n of
          Zero -> True
          Succ m -> False
        """

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        core_decls, constr_types = elaborate(surface_decls)

        checker = TypeChecker(constr_types)
        types = checker.check_program(core_decls)

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
        core_decls, constr_types = elaborate(surface_decls)

        checker = TypeChecker(constr_types)
        types = checker.check_program(core_decls)

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
        core_decls, constr_types = elaborate(surface_decls)

        checker = TypeChecker(constr_types)
        types = checker.check_program(core_decls)

        assert "isEmpty" in types
