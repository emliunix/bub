"""Tests for surface language lexer.

Tests for indentation-aware lexer including:
- Basic token recognition
- INDENT/DEDENT token emission
- Indentation error handling
- Newline and comment handling
"""

import pytest

from systemf.surface.lexer import Lexer, LexerError, Token, lex
from systemf.utils.location import Location


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
        """Tokenize simple identifiers and operators."""
        tokens = lex("x y z")
        types = [t.type for t in tokens]
        assert types == ["IDENT", "IDENT", "IDENT", "EOF"]

    def test_keywords(self):
        """Tokenize keywords."""
        source = "data let case of forall type"
        tokens = lex(source)
        types = [t.type for t in tokens[:-1]]  # Exclude EOF
        assert types == ["DATA", "LET", "CASE", "OF", "FORALL", "TYPE"]

    def test_in_keyword_still_recognized(self):
        """The 'in' keyword is still recognized by lexer (though not used in new syntax)."""
        # The lexer still has 'in' as a keyword for backward compatibility
        tokens = lex("in")
        assert tokens[0].type == "IN"
        assert tokens[0].value == "in"

    def test_operators(self):
        """Tokenize operators."""
        source = "-> => = : | @ ."
        tokens = lex(source)
        types = [t.type for t in tokens[:-1]]  # Exclude EOF
        assert types == ["ARROW", "DARROW", "EQUALS", "COLON", "BAR", "AT", "DOT"]

    def test_delimiters(self):
        """Tokenize delimiters."""
        source = "( ) [ ] { } ,"
        tokens = lex(source)
        types = [t.type for t in tokens[:-1]]  # Exclude EOF
        assert types == ["LPAREN", "RPAREN", "LBRACKET", "RBRACKET", "LBRACE", "RBRACE", "COMMA"]


# =============================================================================
# Identifier Tests
# =============================================================================


class TestIdentifiers:
    """Tests for identifier tokenization."""

    def test_lowercase_ident(self):
        """Lowercase names are identifiers."""
        tokens = lex("hello")
        assert tokens[0].type == "IDENT"
        assert tokens[0].value == "hello"

    def test_underscore_ident(self):
        """Names starting with underscore are identifiers."""
        tokens = lex("_foo")
        assert tokens[0].type == "IDENT"
        assert tokens[0].value == "_foo"

    def test_uppercase_constr(self):
        """Uppercase names are constructors."""
        tokens = lex("Hello")
        assert tokens[0].type == "CONSTRUCTOR"
        assert tokens[0].value == "Hello"

    def test_constructor_with_args(self):
        """Constructor names are uppercase."""
        tokens = lex("Cons Nil Just Nothing")
        types = [t.type for t in tokens[:-1]]  # Exclude EOF
        assert all(t == "CONSTRUCTOR" for t in types)

    def test_alphanumeric_ident(self):
        """Identifiers can contain numbers."""
        tokens = lex("x1 y2 z3")
        assert tokens[0].value == "x1"
        assert tokens[1].value == "y2"
        assert tokens[2].value == "z3"


# =============================================================================
# Number Tests
# =============================================================================


class TestNumbers:
    """Tests for number literals."""

    def test_number(self):
        """Numbers are tokenized."""
        tokens = lex("123")
        assert tokens[0].type == "NUMBER"
        assert tokens[0].value == "123"

    def test_number_in_context(self):
        """Numbers in larger expressions."""
        tokens = lex("let x = 42")
        assert tokens[3].type == "NUMBER"
        assert tokens[3].value == "42"


# =============================================================================
# Lambda and Type Lambda Tests
# =============================================================================


class TestLambdaTokens:
    """Tests for lambda and type lambda tokens."""

    def test_lambda(self):
        """Backslash is lambda."""
        tokens = lex(r"\x -> x")
        assert tokens[0].type == "LAMBDA"

    def test_type_lambda(self):
        """Slash-backslash is type lambda."""
        tokens = lex(r"/\a. x")
        assert tokens[0].type == "TYPELAMBDA"


# =============================================================================
# Comment Tests
# =============================================================================


class TestComments:
    """Tests for comment handling."""

    def test_line_comment(self):
        """Line comments are ignored."""
        tokens = lex("x -- this is a comment")
        assert len(tokens) == 2  # IDENT, EOF
        assert tokens[0].value == "x"

    def test_comment_at_start(self):
        """Comments at start of line."""
        tokens = lex("-- comment\nx")
        assert len(tokens) == 2
        assert tokens[0].value == "x"

    def test_multiple_comments(self):
        """Multiple comments are ignored."""
        tokens = lex("x -- comment 1\ny -- comment 2")
        types = [t.type for t in tokens[:-1]]
        assert types == ["IDENT", "IDENT"]


# =============================================================================
# Location Tests
# =============================================================================


class TestLocations:
    """Tests for source location tracking."""

    def test_line_tracking(self):
        """Line numbers are tracked correctly."""
        tokens = lex("x\ny")
        assert tokens[0].location.line == 1
        assert tokens[1].location.line == 2

    def test_column_tracking(self):
        """Column numbers are tracked correctly."""
        tokens = lex("x y z")
        assert tokens[0].location.column == 1
        assert tokens[1].location.column == 3
        assert tokens[2].location.column == 5

    def test_filename(self):
        """Filename is included in location."""
        tokens = lex("x", filename="test.sf")
        assert tokens[0].location.file == "test.sf"


# =============================================================================
# Indentation Token Tests
# =============================================================================


class TestIndentTokens:
    """Tests for INDENT/DEDENT token emission."""

    def test_no_indent_single_line(self):
        """Single line has no INDENT/DEDENT."""
        tokens = lex("x y z", skip_indent=False)
        types = [t.type for t in tokens]
        assert "INDENT" not in types
        assert "DEDENT" not in types

    def test_simple_indent(self):
        """Simple indentation emits INDENT/DEDENT."""
        tokens = lex("let x = 1\n  x", skip_indent=False)
        types = [t.type for t in tokens]
        assert "INDENT" in types
        assert "DEDENT" in types

    def test_indent_token_position(self):
        """INDENT appears after let binding, before body."""
        tokens = lex("let x = 1\n  x", skip_indent=False)
        types = [t.type for t in tokens]
        # Should be: LET, IDENT, EQUALS, NUMBER, INDENT, IDENT, DEDENT, EOF
        assert types == ["LET", "IDENT", "EQUALS", "NUMBER", "INDENT", "IDENT", "DEDENT", "EOF"]

    def test_multiple_indent_levels(self):
        """Multiple indentation levels emit multiple INDENTs."""
        source = """let x = 1
  let y = 2
    y"""
        tokens = lex(source, skip_indent=False)
        indent_count = sum(1 for t in tokens if t.type == "INDENT")
        dedent_count = sum(1 for t in tokens if t.type == "DEDENT")
        assert indent_count == 2
        assert dedent_count == 2

    def test_multiple_dedent(self):
        """Large dedent emits multiple DEDENT tokens."""
        source = """let x = 1
  let y = 2
    y
x"""
        tokens = lex(source, skip_indent=False)
        types = [t.type for t in tokens]
        # After the inner body 'y', we should have two DEDENTs to get back to level 0
        dedent_indices = [i for i, t in enumerate(types) if t == "DEDENT"]
        assert len(dedent_indices) >= 2

    def test_dedent_at_eof(self):
        """EOF triggers DEDENTs to close all open blocks."""
        source = """let x = 1
  x"""
        tokens = lex(source, skip_indent=False)
        types = [t.type for t in tokens]
        # Last token before EOF should be DEDENT
        assert types[-2] == "DEDENT"
        assert types[-1] == "EOF"

    def test_blank_lines_ignored(self):
        """Blank lines don't affect indentation tracking."""
        source = """let x = 1

  x"""
        tokens = lex(source, skip_indent=False)
        types = [t.type for t in tokens]
        # Should still have just one INDENT/DEDENT pair
        assert types.count("INDENT") == 1
        assert types.count("DEDENT") == 1

    def test_comment_lines_ignored(self):
        """Comment-only lines don't affect indentation tracking."""
        source = """let x = 1
  -- this is a comment
  x"""
        tokens = lex(source, skip_indent=False)
        types = [t.type for t in tokens]
        # Should have one INDENT/DEDENT pair
        assert types.count("INDENT") == 1
        assert types.count("DEDENT") == 1

    def test_case_with_indented_branches(self):
        """Case expression with indented branches."""
        source = """case x of
  True -> y
  False -> z"""
        tokens = lex(source, skip_indent=False)
        types = [t.type for t in tokens]
        assert "INDENT" in types
        assert "DEDENT" in types

    def test_data_declaration_indent(self):
        """Data declaration with indented constructors."""
        source = """data Bool =
  True
  False"""
        tokens = lex(source, skip_indent=False)
        types = [t.type for t in tokens]
        assert "INDENT" in types
        assert "DEDENT" in types


# =============================================================================
# Indentation Error Tests
# =============================================================================


class TestIndentErrors:
    """Tests for indentation error handling."""

    def test_mixed_tabs_spaces(self):
        """Mixed tabs and spaces in same indentation raise error."""
        source = "let x = 1\n \tx"  # space then tab on same line
        with pytest.raises(LexerError) as exc_info:
            lex(source, skip_indent=False)
        assert "Mixed tabs and spaces" in str(exc_info.value)

    def test_inconsistent_indent(self):
        """Inconsistent indentation (not matching previous levels) raises error."""
        source = """let x = 1
  let y = 2
      y
   x"""  # 3 spaces doesn't match any previous level (0, 2)
        with pytest.raises(LexerError) as exc_info:
            lex(source, skip_indent=False)
        assert "Inconsistent indentation" in str(exc_info.value)


# =============================================================================
# Error Tests
# =============================================================================


class TestErrors:
    """Tests for lexer error handling."""

    def test_unknown_character(self):
        """Unknown characters raise error."""
        with pytest.raises(LexerError) as exc_info:
            lex("$")
        assert "Unexpected character" in str(exc_info.value)

    def test_error_location(self):
        """Error includes location information."""
        with pytest.raises(LexerError) as exc_info:
            lex("x\n$")
        # Line 2, column 1
        assert "2:" in str(exc_info.value) or "line 2" in str(exc_info.value)


# =============================================================================
# Complex Examples with New Syntax
# =============================================================================


class TestComplexExamples:
    """Tests for complex token sequences with indentation-aware syntax."""

    def test_let_binding(self):
        """Tokenize let binding (no 'in' keyword)."""
        tokens = lex("let x = 1")
        types = [t.type for t in tokens[:-1]]
        assert types == ["LET", "IDENT", "EQUALS", "NUMBER"]

    def test_let_binding_with_indent(self):
        """Tokenize let binding with indented body."""
        tokens = lex("let x = 1\n  x", skip_indent=False)
        types = [t.type for t in tokens[:-1]]
        assert types == ["LET", "IDENT", "EQUALS", "NUMBER", "INDENT", "IDENT", "DEDENT"]

    def test_lambda_expression(self):
        """Tokenize lambda expression."""
        tokens = lex(r"\x -> x")
        types = [t.type for t in tokens[:-1]]
        assert types == ["LAMBDA", "IDENT", "ARROW", "IDENT"]

    def test_annotated_lambda(self):
        """Tokenize lambda with type annotation."""
        tokens = lex(r"\x:Int -> x")
        types = [t.type for t in tokens[:-1]]
        assert types == ["LAMBDA", "IDENT", "COLON", "CONSTRUCTOR", "ARROW", "IDENT"]

    def test_type_application(self):
        """Tokenize type application."""
        tokens = lex("id @Int")
        types = [t.type for t in tokens[:-1]]
        assert types == ["IDENT", "AT", "CONSTRUCTOR"]

    def test_data_declaration_indentation(self):
        """Tokenize data declaration with indentation."""
        source = """data List a =
  Nil
  Cons a (List a)"""
        tokens = lex(source, skip_indent=False)
        types = [t.type for t in tokens[:-1]]
        # Should have: DATA, CONSTRUCTOR, IDENT, EQUALS, INDENT,
        #              CONSTRUCTOR, CONSTRUCTOR, IDENT, LPAREN, CONSTRUCTOR, IDENT, RPAREN,
        #              DEDENT
        assert "INDENT" in types
        assert "DEDENT" in types
        assert types[0] == "DATA"

    def test_case_expression_indentation(self):
        """Tokenize case expression with indentation."""
        source = """case x of
  True -> y
  False -> z"""
        tokens = lex(source, skip_indent=False)
        types = [t.type for t in tokens[:-1]]
        # Should have INDENT/DEDENT for the branches
        assert "INDENT" in types
        assert "DEDENT" in types
        # No braces or BAR in new syntax
        assert "LBRACE" not in types
        assert "RBRACE" not in types


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_whitespace_only(self):
        """Whitespace-only source returns EOF."""
        tokens = lex("   \n\t  ")
        assert len(tokens) == 1
        assert tokens[0].type == "EOF"

    def test_adjacent_operators(self):
        """Adjacent operators are tokenized separately."""
        tokens = lex("x->y")  # This should not be valid, but test parsing
        # Actually, 'x->y' is x -> y (with arrow operator)
        types = [t.type for t in tokens[:-1]]
        assert types == ["IDENT", "ARROW", "IDENT"]

    def test_long_identifier(self):
        """Long identifiers work correctly."""
        long_name = "a" * 100
        tokens = lex(long_name)
        assert tokens[0].type == "IDENT"
        assert tokens[0].value == long_name

    def test_unicode_not_supported(self):
        """Unicode characters may not be supported."""
        # This test documents behavior - unicode may raise error or be treated as identifier
        try:
            tokens = lex("λ")
            # If it works, great
        except LexerError:
            pass  # Also acceptable


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


class TestBackwardCompatibility:
    """Tests to ensure backward compatibility mode works."""

    def test_skip_indent_default(self):
        """By default, INDENT/DEDENT tokens are skipped."""
        source = """let x = 1
  x"""
        tokens = lex(source)  # skip_indent=True by default
        types = [t.type for t in tokens]
        assert "INDENT" not in types
        assert "DEDENT" not in types

    def test_skip_indent_explicit(self):
        """Explicit skip_indent=True skips INDENT/DEDENT."""
        source = """let x = 1
  x"""
        tokens = lex(source, skip_indent=True)
        types = [t.type for t in tokens]
        assert "INDENT" not in types
        assert "DEDENT" not in types

    def test_no_skip_indent(self):
        """skip_indent=False includes INDENT/DEDENT."""
        source = """let x = 1
  x"""
        tokens = lex(source, skip_indent=False)
        types = [t.type for t in tokens]
        assert "INDENT" in types
        assert "DEDENT" in types
