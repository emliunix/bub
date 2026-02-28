"""Tests for System F lexer.

Tests basic tokenization without virtual indentation tokens.
The lexer now just emits raw tokens with location information.
Layout handling is done by the stateful parser using column tracking.
"""

import pytest

from systemf.surface.parser import Lexer, lex, LexerError


# =============================================================================
# Basic Token Tests
# =============================================================================


class TestBasicTokens:
    """Tests for basic token recognition."""

    def test_empty_source(self):
        """Empty source should return just EOF."""
        tokens = lex("")
        assert len(tokens) == 1
        assert tokens[0].type == "EOF"

    def test_simple_tokens(self):
        """Tokenize simple identifiers."""
        tokens = lex("x y z")
        types = [t.type for t in tokens]
        assert types == ["IDENT", "IDENT", "IDENT", "EOF"]

    def test_keywords(self):
        """Tokenize keywords."""
        source = "data let in case of forall type if then else"
        tokens = lex(source)
        types = [t.type for t in tokens[:-1]]  # Exclude EOF
        assert types == ["DATA", "LET", "IN", "CASE", "OF", "FORALL", "TYPE", "IF", "THEN", "ELSE"]

    def test_operators(self):
        """Tokenize operators."""
        source = "-> => = : | @ . ++ && || /="
        tokens = lex(source)
        types = [t.type for t in tokens[:-1]]  # Exclude EOF
        assert types == [
            "ARROW",
            "DARROW",
            "EQUALS",
            "COLON",
            "BAR",
            "AT",
            "DOT",
            "APPEND",
            "AND",
            "OR",
            "NEQ",
        ]

    def test_arithmetic_operators(self):
        """Tokenize arithmetic operators."""
        source = "+ - * /"
        tokens = lex(source)
        types = [t.type for t in tokens[:-1]]  # Exclude EOF
        assert types == ["PLUS", "MINUS", "STAR", "SLASH"]

    def test_comparison_operators(self):
        """Tokenize comparison operators."""
        source = "== < > <= >="
        tokens = lex(source)
        types = [t.type for t in tokens[:-1]]  # Exclude EOF
        assert types == ["EQ", "LT", "GT", "LE", "GE"]

    def test_delimiters(self):
        """Tokenize delimiters."""
        source = "( ) [ ] { }"
        tokens = lex(source)
        types = [t.type for t in tokens[:-1]]  # Exclude EOF
        assert types == ["LPAREN", "RPAREN", "LBRACKET", "RBRACKET", "LBRACE", "RBRACE"]


# =============================================================================
# Location Tests
# =============================================================================


class TestTokenLocations:
    """Tests for token location tracking (column info)."""

    def test_token_columns(self):
        """Each token should have column information."""
        tokens = lex("x y")
        # x at col 1, y at col 3
        assert tokens[0].column == 1
        assert tokens[1].column == 3

    def test_multiline_columns(self):
        """Column tracking works across lines."""
        source = """case x of
  A -> 1"""
        tokens = lex(source)

        # Find case keyword at col 1
        case_tok = next(t for t in tokens if t.type == "CASE")
        assert case_tok.column == 1

        # Find A constructor at col 3 (indented)
        a_tok = next(t for t in tokens if t.type == "CONSTRUCTOR" and t.value == "A")
        assert a_tok.column == 3


# =============================================================================
# Complex Examples
# =============================================================================


class TestComplexExamples:
    """Tests for complete code examples."""

    def test_simple_case_expression(self):
        """Case expression with indentation."""
        source = """case x of
  True -> 1
  False -> 0"""
        tokens = lex(source)
        types = [t.type for t in tokens]

        # No virtual tokens - just raw tokens
        expected = [
            "CASE",
            "IDENT",
            "OF",
            "CONSTRUCTOR",
            "ARROW",
            "NUMBER",
            "CONSTRUCTOR",
            "ARROW",
            "NUMBER",
            "EOF",
        ]
        assert types == expected

    def test_let_expression(self):
        """Let expression with indentation."""
        source = """let
  x = 1
  y = 2
in x + y"""
        tokens = lex(source)
        types = [t.type for t in tokens]

        # No virtual tokens
        assert "LET" in types
        assert "IN" in types
        # Check columns
        let_tok = next(t for t in tokens if t.type == "LET")
        assert let_tok.column == 1

    def test_data_declaration(self):
        """Data declaration with constructors."""
        source = """data Bool = True | False"""
        tokens = lex(source)
        types = [t.type for t in tokens]

        expected = ["DATA", "CONSTRUCTOR", "EQUALS", "CONSTRUCTOR", "BAR", "CONSTRUCTOR", "EOF"]
        assert types == expected


# =============================================================================
# Error Handling
# =============================================================================


class TestLexerErrors:
    """Tests for lexer error handling."""

    def test_unexpected_character(self):
        """Lexer should raise error for unexpected characters."""
        with pytest.raises(LexerError):
            lex("x $ y")


# =============================================================================
# Helper Functions
# =============================================================================


def get_token_columns(source: str) -> list[tuple[str, int]]:
    """Get (type, column) pairs for all tokens."""
    tokens = lex(source)
    return [(t.type, t.column) for t in tokens]


def test_column_tracking():
    """Verify column tracking in lexer."""
    source = """let x = 1
    y = 2"""
    cols = get_token_columns(source)

    # let at col 1, x at col 5, = at col 7, 1 at col 9
    assert cols[0] == ("LET", 1)
    assert cols[1] == ("IDENT", 5)
    assert cols[2] == ("EQUALS", 7)
    assert cols[3] == ("NUMBER", 9)

    # y at col 5 (second line)
    assert cols[4] == ("IDENT", 5)
