"""Expression-level parsing tests.

This module tests expression parsing in isolation.
Declaration and program-level parsing are tested separately.

Tiered testing strategy:
1. Tier 1: Atoms (vars, literals, constructors)
2. Tier 2: Abstraction (lambda, type lambda)
3. Tier 3: Application (function app, type app)
4. Tier 4: Case expressions and pattern matching
5. Tier 5: Complex nesting

If any helper emerges that cannot be decomposed further, factor it out
into systemf/surface/indentation.py or similar with its own isolated tests.
"""

import pytest
from parsy import generate

from systemf.surface.parser import lex
from systemf.surface.parser import (
    atom_parser,
    app_parser,
    lambda_parser,
    type_abs_parser,
    case_parser,
    term_parser,
    match_token,
    INDENT,
    DEDENT,
)
from systemf.surface.indentation import indented_opt


class TestTier1Atoms:
    """Variables, literals, constructors."""

    def test_variable(self):
        """Parse simple variable."""
        tokens = lex("x")
        result, _ = atom_parser.parse_partial(tokens)
        assert result.name == "x"

    def test_integer_literal(self):
        """Parse integer literal."""
        tokens = lex("42")
        result, _ = atom_parser.parse_partial(tokens)
        assert result.value == 42

    def test_string_literal(self):
        """Parse string literal."""
        tokens = lex('"hello"')
        result, _ = atom_parser.parse_partial(tokens)
        assert result.value == "hello"

    def test_constructor(self):
        """Parse data constructor."""
        tokens = lex("True")
        result, _ = atom_parser.parse_partial(tokens)
        assert result.name == "True"

    def test_parenthesized_expression(self):
        """Parse (expr)."""
        tokens = lex("(x)")
        result, _ = atom_parser.parse_partial(tokens)
        assert result.name == "x"


class TestTier2Abstraction:
    """Lambda and type lambda expressions."""

    def test_lambda_inline(self):
        """λx → x (inline body)."""
        tokens = lex("λx → x")
        result, _ = lambda_parser.parse_partial(tokens)
        assert result.var == "x"

    def test_lambda_indented(self):
        """λx →
        body (indented body)."""
        code = """λx →
  x"""
        tokens = lex(code)
        result, _ = lambda_parser.parse_partial(tokens)
        assert result.var == "x"

    def test_type_lambda_inline(self):
        """Λa. x (inline)."""
        tokens = lex("Λa. x")
        result, _ = type_abs_parser.parse_partial(tokens)
        assert result.var == "a"

    def test_type_lambda_indented(self):
        """Λa.
        x (indented)."""
        code = """Λa.
  x"""
        tokens = lex(code)
        result, _ = type_abs_parser.parse_partial(tokens)
        assert result.var == "a"


class TestTier3Application:
    """Function application and type application."""

    def test_simple_application(self):
        """f x"""
        tokens = lex("f x")
        result, _ = app_parser.parse_partial(tokens)
        # Should be App(App(f, x))
        assert result is not None

    def test_multi_argument_application(self):
        """f x y z"""
        tokens = lex("f x y z")
        result, _ = app_parser.parse_partial(tokens)
        assert result is not None

    def test_type_application_at(self):
        """f @Int"""
        tokens = lex("f @Int")
        result, _ = app_parser.parse_partial(tokens)
        assert result is not None

    def test_type_application_bracket(self):
        """f [Int]"""
        tokens = lex("f [Int]")
        result, _ = app_parser.parse_partial(tokens)
        assert result is not None


class TestTier4CaseExpressions:
    """Case expressions and pattern matching."""

    def test_case_single_branch_inline(self):
        """case x of True → y"""
        tokens = lex("case x of True → y")
        result, _ = case_parser.parse_partial(tokens)
        assert len(result.branches) == 1

    def test_case_multi_branch_inline(self):
        """case x of True → y | False → z"""
        tokens = lex("case x of True → y | False → z")
        result, _ = case_parser.parse_partial(tokens)
        assert len(result.branches) == 2

    def test_case_indented_branches(self):
        """case x of
        True → y
        False → z"""
        code = """case x of
  True → y
  False → z"""
        tokens = lex(code)
        result, _ = case_parser.parse_partial(tokens)
        assert len(result.branches) == 2

    def test_case_brace_syntax(self):
        """case x of { | True → y | False → z }"""
        tokens = lex("case x of { | True → y | False → z }")
        result, _ = case_parser.parse_partial(tokens)
        assert len(result.branches) == 2

    def test_pattern_constructor_no_args(self):
        """case x of True → y"""
        tokens = lex("case x of True → y")
        result, _ = case_parser.parse_partial(tokens)
        assert result.branches[0].pattern.constructor == "True"
        assert result.branches[0].pattern.vars == []

    def test_pattern_constructor_with_args(self):
        """case x of Just a → y"""
        tokens = lex("case x of Just a → y")
        result, _ = case_parser.parse_partial(tokens)
        assert result.branches[0].pattern.constructor == "Just"
        assert result.branches[0].pattern.vars == ["a"]

    def test_pattern_constructor_multi_args(self):
        """case x of Cons y ys → z"""
        tokens = lex("case x of Cons y ys → z")
        result, _ = case_parser.parse_partial(tokens)
        assert result.branches[0].pattern.constructor == "Cons"
        assert result.branches[0].pattern.vars == ["y", "ys"]


class TestTier5ComplexNesting:
    """Complex nested expressions."""

    def test_nested_case_in_lambda(self):
        """λx → case x of True → False | False → True"""
        code = "λx → case x of True → False | False → True"
        tokens = lex(code)
        result, _ = term_parser.parse_partial(tokens)
        assert result is not None

    def test_case_with_nested_case_branch(self):
        """case x of
        True → case y of A → B
        False → C"""
        code = """case x of
  True →
    case y of A → B
  False → C"""
        tokens = lex(code)
        result, _ = case_parser.parse_partial(tokens)
        assert len(result.branches) == 2

    def test_application_in_case_branch(self):
        """case x of Cons y ys → f y ys"""
        tokens = lex("case x of Cons y ys → f y ys")
        result, _ = case_parser.parse_partial(tokens)
        assert len(result.branches) == 1

    def test_type_application_in_lambda(self):
        """Λa. λx:a → x"""
        tokens = lex("Λa. λx:a → x")
        result, _ = term_parser.parse_partial(tokens)
        assert result is not None


class TestIndentationHelpersUsed:
    """Verify indented_opt is used correctly in expression contexts."""

    def test_indented_opt_in_lambda_body(self):
        """Lambda body uses indented_opt."""
        # Inline form
        tokens1 = lex("λx → y")
        result1, _ = lambda_parser.parse_partial(tokens1)
        assert result1.body.name == "y"

        # Indented form
        code2 = """λx →
  y"""
        tokens2 = lex(code2)
        result2, _ = lambda_parser.parse_partial(tokens2)
        assert result2.body.name == "y"

    def test_indented_opt_in_case_branch(self):
        """Case branch body uses indented_opt."""
        # Inline form
        tokens1 = lex("case x of True → y")
        result1, _ = case_parser.parse_partial(tokens1)
        assert result1.branches[0].body.name == "y"

        # Indented form
        code2 = """case x of
  True →
    y"""
        tokens2 = lex(code2)
        result2, _ = case_parser.parse_partial(tokens2)
        assert result2.branches[0].body.name == "y"


# Note: Tests for declarations, programs, and module-level constructs
# are intentionally excluded from this file. They belong in:
# - test_declarations.py (for let, data, etc.)
# - test_program.py (for full module parsing)
# - test_integration.py (for end-to-end)
