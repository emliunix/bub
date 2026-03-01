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
        """Empty source should return empty list (no EOF token)."""
        tokens = lex("")
        assert len(tokens) == 0

    def test_simple_tokens(self):
        """Tokenize simple identifiers."""
        tokens = lex("x y z")
        types = [t.type for t in tokens]
        assert types == ["IDENT", "IDENT", "IDENT"]

    def test_keywords(self):
        """Tokenize keywords."""
        source = "data let in case of forall type if then else"
        tokens = lex(source)
        types = [t.type for t in tokens]
        assert types == ["DATA", "LET", "IN", "CASE", "OF", "FORALL", "TYPE", "IF", "THEN", "ELSE"]

    def test_operators(self):
        """Tokenize operators."""
        source = "-> => = : | @ . ++ && || /="
        tokens = lex(source)
        types = [t.type for t in tokens]
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
        types = [t.type for t in tokens]
        assert types == ["PLUS", "MINUS", "STAR", "SLASH"]

    def test_comparison_operators(self):
        """Tokenize comparison operators."""
        source = "== < > <= >="
        tokens = lex(source)
        types = [t.type for t in tokens]
        assert types == ["EQ", "LT", "GT", "LE", "GE"]

    def test_delimiters(self):
        """Tokenize delimiters."""
        source = "( ) [ ] { }"
        tokens = lex(source)
        types = [t.type for t in tokens]
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

        expected = ["DATA", "CONSTRUCTOR", "EQUALS", "CONSTRUCTOR", "BAR", "CONSTRUCTOR"]
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


# =============================================================================
# Unicode Token Tests
# =============================================================================


class TestUnicodeTokens:
    """Tests for unicode token recognition (TYPELAMBDA, LAMBDA, ARROW)."""

    def test_type_lambda_ascii(self):
        """Tokenize /\\ as TYPELAMBDA."""
        tokens = lex("/\\")
        assert len(tokens) == 1  # TYPELAMBDA only (no EOF)
        assert tokens[0].type == "TYPELAMBDA"
        assert tokens[0].value == "/\\"

    def test_type_lambda_unicode(self):
        """Tokenize Λ as TYPELAMBDA."""
        tokens = lex("Λ")
        assert len(tokens) == 1  # TYPELAMBDA only (no EOF)
        assert tokens[0].type == "TYPELAMBDA"
        assert tokens[0].value == "Λ"

    def test_lambda_ascii(self):
        """Tokenize \\ as LAMBDA."""
        tokens = lex("\\")
        assert len(tokens) == 1  # LAMBDA only (no EOF)
        assert tokens[0].type == "LAMBDA"
        assert tokens[0].value == "\\"

    def test_lambda_unicode(self):
        """Tokenize λ as LAMBDA."""
        tokens = lex("λ")
        assert len(tokens) == 1  # LAMBDA only (no EOF)
        assert tokens[0].type == "LAMBDA"
        assert tokens[0].value == "λ"

    def test_arrow_ascii(self):
        """Tokenize -> as ARROW."""
        tokens = lex("->")
        assert len(tokens) == 1  # ARROW only (no EOF)
        assert tokens[0].type == "ARROW"
        assert tokens[0].value == "->"

    def test_arrow_unicode(self):
        """Tokenize → as ARROW."""
        tokens = lex("→")
        assert len(tokens) == 1  # ARROW only (no EOF)
        assert tokens[0].type == "ARROW"
        assert tokens[0].value == "→"

    def test_forall_unicode(self):
        """Tokenize ∀ as FORALL (preserves unicode in keyword field)."""
        tokens = lex("∀")
        assert len(tokens) == 1  # FORALL only (no EOF)
        assert tokens[0].type == "FORALL"
        assert tokens[0].value == "∀"  # Preserves original unicode

    def test_type_abstraction_tokens(self):
        """Tokenize complete type abstraction."""
        tokens = lex("Λa. x")
        types = [t.type for t in tokens]
        assert types == ["TYPELAMBDA", "IDENT", "DOT", "IDENT"]

    def test_lambda_with_type_annotation_tokens(self):
        """Tokenize lambda with type annotation."""
        tokens = lex("λx:Int -> x")
        types = [t.type for t in tokens]
        assert types == ["LAMBDA", "IDENT", "COLON", "CONSTRUCTOR", "ARROW", "IDENT"]

    def test_mixed_unicode_ascii(self):
        """Tokenize mix of unicode and ASCII symbols."""
        # Using unicode lambda but ASCII arrow
        tokens = lex("λx -> x")
        types = [t.type for t in tokens]
        assert types == ["LAMBDA", "IDENT", "ARROW", "IDENT"]

        # Using ASCII lambda but unicode arrow
        tokens = lex("\\x → x")
        types = [t.type for t in tokens]
        assert types == ["LAMBDA", "IDENT", "ARROW", "IDENT"]


class TestTokenIdentity:
    """Tests to ensure token types are correctly identified."""

    def test_token_types_are_not_generic_operators(self):
        """Critical tokens should have specific types, not generic OPERATOR."""
        # These should NOT be tokenized as generic OPERATOR
        critical_tokens = {
            "Λ": "TYPELAMBDA",
            "/\\": "TYPELAMBDA",
            "λ": "LAMBDA",
            "\\": "LAMBDA",
            "->": "ARROW",
            "→": "ARROW",
            "∀": "FORALL",
        }

        for source, expected_type in critical_tokens.items():
            tokens = lex(source)
            actual_type = tokens[0].type
            assert actual_type == expected_type, (
                f"Expected {expected_type} for '{source}', got {actual_type}"
            )

    def test_lambda_doesnt_match_type_lambda(self):
        """λ and Λ should be different token types."""
        lambda_token = lex("λ")[0]
        type_lambda_token = lex("Λ")[0]

        assert lambda_token.type == "LAMBDA"
        assert type_lambda_token.type == "TYPELAMBDA"
        assert lambda_token.type != type_lambda_token.type

    def test_arrow_variants_equivalent(self):
        """-> and → should both be ARROW type."""
        ascii_arrow = lex("->")[0]
        unicode_arrow = lex("→")[0]

        assert ascii_arrow.type == "ARROW"
        assert unicode_arrow.type == "ARROW"
        assert ascii_arrow.type == unicode_arrow.type


# =============================================================================
# Docstring Tests (Whitespace Tolerance)
# =============================================================================


class TestDocstringWhitespaceTolerance:
    """Tests for docstring whitespace tolerance edge cases."""

    def test_docstring_no_space_after_dashes(self):
        """Docstring --| should be recognized without space."""
        from systemf.surface.parser.types import DocstringToken

        tokens = lex("--| This is a docstring")
        assert len(tokens) == 1
        assert isinstance(tokens[0], DocstringToken)
        assert tokens[0].content == "This is a docstring"

    def test_docstring_with_space_after_dashes(self):
        """Docstring -- | should be recognized with space."""
        from systemf.surface.parser.types import DocstringToken

        tokens = lex("-- | This is a docstring")
        assert len(tokens) == 1
        assert isinstance(tokens[0], DocstringToken)
        assert tokens[0].content == "This is a docstring"

    def test_inline_docstring_no_space_after_dashes(self):
        """Inline docstring --^ should be recognized without space."""
        from systemf.surface.parser.types import DocstringToken

        tokens = lex("x --^ inline doc")
        assert len(tokens) == 2  # IDENT and DOCSTRING
        assert isinstance(tokens[1], DocstringToken)
        assert tokens[1].content == "inline doc"

    def test_inline_docstring_with_space_after_dashes(self):
        """Inline docstring -- ^ should be recognized with space."""
        from systemf.surface.parser.types import DocstringToken

        tokens = lex("x -- ^ inline doc")
        assert len(tokens) == 2  # IDENT and DOCSTRING
        assert isinstance(tokens[1], DocstringToken)
        assert tokens[1].content == "inline doc"

    def test_docstring_merging_with_mixed_whitespace(self):
        """Docstring merging should work with mixed whitespace patterns."""
        from systemf.surface.parser.types import DocstringToken

        # First line has space, continuation doesn't
        source = """-- | First line
-- continuation"""
        tokens = lex(source)
        assert len(tokens) == 1
        assert isinstance(tokens[0], DocstringToken)
        assert "First line" in tokens[0].content
        assert "continuation" in tokens[0].content

    def test_regular_comment_not_docstring(self):
        """Regular comments should not be tokenized."""
        tokens = lex("x -- regular comment")
        assert len(tokens) == 1
        assert tokens[0].type == "IDENT"
