"""Unit tests for expression parsers.

Tests for individual expression parsers from expressions.py.
These tests validate the grammar from syntax.md Section 3.
"""

import pytest
from systemf.surface.parser import (
    expr_parser,
    atom_parser,
    app_parser,
    lambda_parser,
    type_abs_parser,
    case_parser,
    let_parser,
    if_parser,
    AnyIndent,
    lex,
)
from systemf.surface.types import (
    SurfaceVar,
    SurfaceConstructor,
    SurfaceLit,
    SurfaceAbs,
    SurfaceTypeAbs,
    SurfaceApp,
    SurfaceCase,
    SurfaceLet,
)


class TestAtomParser:
    """Test atom parser for basic terms."""

    def test_variable(self):
        """Parse a variable."""
        tokens = lex("x")
        result = atom_parser().parse(tokens)
        assert isinstance(result, SurfaceVar)
        assert result.name == "x"

    def test_constructor(self):
        """Parse a constructor."""
        tokens = lex("True")
        result = atom_parser().parse(tokens)
        assert isinstance(result, SurfaceConstructor)
        assert result.name == "True"

    def test_integer_literal(self):
        """Parse an integer literal."""
        tokens = lex("42")
        result = atom_parser().parse(tokens)
        assert isinstance(result, SurfaceLit)
        assert result.value == 42

    def test_string_literal(self):
        """Parse a string literal."""
        tokens = lex('"hello"')
        result = atom_parser().parse(tokens)
        assert isinstance(result, SurfaceLit)
        assert result.value == "hello"

    def test_parenthesized_expression(self):
        """Parse a parenthesized expression."""
        tokens = lex("(x)")
        result = atom_parser().parse(tokens)
        assert isinstance(result, SurfaceVar)
        assert result.name == "x"


class TestLambdaParser:
    """Test lambda abstraction parser."""

    def test_simple_lambda(self):
        """Parse λx → x."""
        tokens = lex("λx → x")
        result = lambda_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceAbs)
        assert result.var == "x"

    def test_lambda_with_type_annotation(self):
        """Parse λx:Int → x."""
        tokens = lex("λx:Int → x")
        result = lambda_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceAbs)
        assert result.var == "x"

    def test_lambda_multiple_params(self):
        """Parse λx y → x."""
        tokens = lex("λx y → x")
        result = lambda_parser(AnyIndent()).parse(tokens)
        # Should parse as nested abs: λx. (λy. x)
        assert isinstance(result, SurfaceAbs)


class TestTypeAbstractionParser:
    """Test type abstraction parser (Λ)."""

    def test_simple_type_abs(self):
        """Parse Λa. x."""
        tokens = lex("Λa. x")
        result = type_abs_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceTypeAbs)

    def test_type_abs_with_lambda(self):
        """Parse Λa. λx:a → x."""
        tokens = lex("Λa. λx:a → x")
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceTypeAbs)


class TestApplicationParser:
    """Test function application parser."""

    def test_simple_application(self):
        """Parse f x."""
        tokens = lex("f x")
        result = app_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceApp)

    def test_multiple_application(self):
        """Parse f x y z."""
        tokens = lex("f x y z")
        result = app_parser(AnyIndent()).parse(tokens)
        # Should be left-associated: ((f x) y) z
        assert isinstance(result, SurfaceApp)

    def test_type_application(self):
        """Parse identity @Int 42."""
        tokens = lex("identity @Int 42")
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceApp)


class TestIfParser:
    """Test if-then-else parser."""

    def test_simple_if(self):
        """Parse if True then 1 else 0."""
        tokens = lex("if True then 1 else 0")
        result = if_parser(AnyIndent()).parse(tokens)
        assert result is not None

    def test_if_with_layout(self):
        """Parse if with multi-line layout."""
        source = """if x > 0 then
  x
else
  negate x"""
        tokens = lex(source)
        result = expr_parser(AnyIndent()).parse(tokens)
        assert result is not None


class TestCaseParser:
    """Test case expression parser."""

    def test_simple_case(self):
        """Parse case x of True → 1 | False → 0."""
        tokens = lex("case x of True → 1")
        result = case_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceCase)

    def test_case_with_layout(self):
        """Parse case with layout branches."""
        source = """case x of
  True → 1
  False → 0"""
        tokens = lex(source)
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceCase)
        assert len(result.branches) == 2

    def test_case_with_pattern(self):
        """Parse case with constructor pattern."""
        source = """case mx of
  Just x → x
  Nothing → 0"""
        tokens = lex(source)
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceCase)

    def test_nested_case(self):
        """Parse nested case expressions."""
        source = """case x of
  True → case y of
    Just z → z
    Nothing → 0
  False → 1"""
        tokens = lex(source)
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceCase)

    def test_case_with_tuple_pattern(self):
        """Parse case with tuple pattern."""
        from systemf.surface.types import SurfacePatternTuple

        source = """case p of
  (x, y) → x + y"""
        tokens = lex(source)
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceCase)
        assert isinstance(result.branches[0].pattern, SurfacePatternTuple)
        assert len(result.branches[0].pattern.elements) == 2

    def test_case_with_triple_pattern(self):
        """Parse case with triple pattern."""
        from systemf.surface.types import SurfacePatternTuple

        source = """case t of
  (a, b, c) → a"""
        tokens = lex(source)
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceCase)
        assert isinstance(result.branches[0].pattern, SurfacePatternTuple)
        assert len(result.branches[0].pattern.elements) == 3

    def test_case_with_braces(self):
        """Parse case with explicit braces: case x of { True → 1 | False → 0 }."""
        source = "case x of { True → 1 | False → 0 }"
        tokens = lex(source)
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceCase)
        assert len(result.branches) == 2
        assert result.branches[0].pattern.constructor == "True"
        assert result.branches[1].pattern.constructor == "False"

    def test_case_with_braces_multiple_patterns(self):
        """Parse case with braces and multiple patterns."""
        source = "case mx of { Nothing → 0 | Just x → x }"
        tokens = lex(source)
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceCase)
        assert len(result.branches) == 2

    def test_nested_case_with_braces(self):
        """Parse nested case with outer layout and inner braces."""
        source = """case x of
  True → case y of { Just z → z | Nothing → 0 }
  False → 1"""
        tokens = lex(source)
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceCase)
        assert len(result.branches) == 2

    def test_case_braces_vs_layout_equivalence(self):
        """Verify case produces same structure with braces or layout."""
        # Layout version
        layout_source = """case x of
  True → 1
  False → 0"""
        layout_tokens = lex(layout_source)
        layout_result = expr_parser(AnyIndent()).parse(layout_tokens)

        # Braces version
        braces_source = "case x of { True → 1 | False → 0 }"
        braces_tokens = lex(braces_source)
        braces_result = expr_parser(AnyIndent()).parse(braces_tokens)

        # Both should produce 2 branches
        assert len(layout_result.branches) == len(braces_result.branches) == 2
        # Branch patterns should be equivalent (check constructor name)
        assert (
            layout_result.branches[0].pattern.constructor
            == braces_result.branches[0].pattern.constructor
        )
        assert (
            layout_result.branches[1].pattern.constructor
            == braces_result.branches[1].pattern.constructor
        )


class TestLetParser:
    """Test let expression parser."""

    def test_simple_let(self):
        """Parse let x = 1 in x + 1."""
        tokens = lex("let x = 1 in x + 1")
        result = let_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceLet)

    def test_let_single_binding(self):
        """Parse let with single binding."""
        tokens = lex("let x = 1 in x")
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceLet)
        assert len(result.bindings) == 1

    def test_let_multiple_bindings(self):
        """Parse let with multiple bindings."""
        source = """let
  x = 1
  y = 2
in x + y"""
        tokens = lex(source)
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceLet)
        assert len(result.bindings) == 2

    def test_let_with_type_annotation(self):
        """Parse let with type annotation."""
        tokens = lex("let x : Int = 1 in x")
        result = let_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceLet)

    def test_let_recursive(self):
        """Parse recursive let."""
        source = """let
  factorial n =
    if n == 0 then 1 else n * factorial (n - 1)
in factorial 5"""
        tokens = lex(source)
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceLet)


class TestOperatorParser:
    """Test operator expression parser."""

    def test_addition(self):
        """Parse x + y."""
        tokens = lex("x + y")
        result = expr_parser(AnyIndent()).parse(tokens)
        assert result is not None

    def test_arithmetic_precedence(self):
        """Parse x + y * z."""
        tokens = lex("x + y * z")
        result = expr_parser(AnyIndent()).parse(tokens)
        # Should be x + (y * z)
        assert result is not None

    def test_comparison(self):
        """Parse x > 0."""
        tokens = lex("x > 0")
        result = expr_parser(AnyIndent()).parse(tokens)
        assert result is not None

    def test_equality(self):
        """Parse x == y."""
        tokens = lex("x == y")
        result = expr_parser(AnyIndent()).parse(tokens)
        assert result is not None

    def test_complex_operator_expression(self):
        """Parse x + y * z == x + (y * z)."""
        tokens = lex("x + y * z == x + (y * z)")
        result = expr_parser(AnyIndent()).parse(tokens)
        assert result is not None

    def test_logical_operators(self):
        """Parse x > 0 && y < 10."""
        tokens = lex("x > 0 && y < 10")
        result = expr_parser(AnyIndent()).parse(tokens)
        assert result is not None


class TestComplexExpressions:
    """Test complex expression combinations."""

    def test_polymorphic_identity(self):
        """Parse identity function with type."""
        tokens = lex("λx:a → x")
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceAbs)

    def test_fold_definition(self):
        """Parse fold-like function."""
        source = """λf acc xs →
  case xs of
    Nil → acc
    Cons x rest → fold f (f acc x) rest"""
        tokens = lex(source)
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceAbs)

    def test_compose_function(self):
        """Parse compose function."""
        tokens = lex("λf g x → f (g x)")
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceAbs)

    def test_let_with_case(self):
        """Parse let with case inside."""
        source = """let
  head xs = case xs of Cons x _ → x
in head mylist"""
        tokens = lex(source)
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceLet)


class TestTupleParser:
    """Test tuple expression parser."""

    def test_tuple_pair(self):
        """Parse a pair tuple."""
        from systemf.surface.types import SurfaceTuple

        tokens = lex("(x, y)")
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceTuple)
        assert len(result.elements) == 2
        assert isinstance(result.elements[0], SurfaceVar)
        assert result.elements[0].name == "x"
        assert isinstance(result.elements[1], SurfaceVar)
        assert result.elements[1].name == "y"

    def test_tuple_triple(self):
        """Parse a triple tuple."""
        from systemf.surface.types import SurfaceTuple

        tokens = lex("(1, 2, 3)")
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceTuple)
        assert len(result.elements) == 3
        assert isinstance(result.elements[0], SurfaceLit)
        assert result.elements[0].value == 1

    def test_tuple_mixed(self):
        """Parse tuple with mixed elements."""
        from systemf.surface.types import SurfaceTuple, SurfaceLit, SurfaceConstructor

        tokens = lex("(1, True)")
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceTuple)
        assert isinstance(result.elements[0], SurfaceLit)
        assert isinstance(result.elements[1], SurfaceConstructor)

    def test_nested_tuple(self):
        """Parse nested tuples."""
        from systemf.surface.types import SurfaceTuple

        tokens = lex("((1, 2), 3)")
        result = expr_parser(AnyIndent()).parse(tokens)
        assert isinstance(result, SurfaceTuple)
        assert len(result.elements) == 2
        assert isinstance(result.elements[0], SurfaceTuple)
        assert isinstance(result.elements[1], SurfaceLit)
