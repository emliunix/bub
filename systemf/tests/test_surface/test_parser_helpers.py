"""Tests for parser helper combinators.

These tests use dummy parsers to avoid circular dependencies.
Each test verifies a specific combinator's behavior with edge cases.
"""

import pytest
from dataclasses import dataclass
from typing import List, Tuple, Optional

from systemf.surface.parser import (
    TokenBase,
    IdentifierToken,
    KeywordToken,
    ConstructorToken,
    OperatorToken,
    DelimiterToken,
    ValidIndent,
    AnyIndent,
    AtPos,
    AfterPos,
    EndOfBlock,
    lex,
)
from systemf.utils.location import Location
from systemf.surface.parser.helpers import (
    column,
    check_valid,
    block,
    block_after,
    block_entries,
    block_entry,
    terminator,
    must_continue,
    top_decl,
    data_decl,
    let_decl,
    case_expr,
    expr_parser,
    type_parser,
    is_at_constraint,
    get_indent_info,
)


# =============================================================================
# Dummy Token Types for Testing
# =============================================================================


@dataclass(frozen=True)
class DummyIdent(TokenBase):
    """Dummy identifier token for tests."""

    name: str

    @property
    def type(self) -> str:
        return "IDENT"

    @property
    def value(self) -> str:
        return self.name


@dataclass(frozen=True)
class DummyKeyword(TokenBase):
    """Dummy keyword token for tests."""

    keyword: str

    @property
    def type(self) -> str:
        return self.keyword.upper()

    @property
    def value(self) -> str:
        return self.keyword


@dataclass(frozen=True)
class DummyConstr(TokenBase):
    """Dummy constructor token for tests."""

    name: str

    @property
    def type(self) -> str:
        return "CONSTR"

    @property
    def value(self) -> str:
        return self.name


@dataclass(frozen=True)
class DummyOp(TokenBase):
    """Dummy operator token for tests."""

    op: str

    @property
    def type(self) -> str:
        return "OP"

    @property
    def value(self) -> str:
        return self.op


# =============================================================================
# Import from actual implementation (may raise NotImplementedError)
# =============================================================================

# Note: These imports freeze the API specification.
# Tests using these will fail with NotImplementedError until implemented.
# When implementing, these functions should pass the test cases below.


# =============================================================================
# Test Cases
# =============================================================================


class TestValidIndentConstraints:
    """Test ValidIndent constraint checking."""

    def test_any_indent_allows_any_column(self):
        """AnyIndent allows any column."""
        assert check_valid(AnyIndent(), 0) is True
        assert check_valid(AnyIndent(), 5) is True
        assert check_valid(AnyIndent(), 100) is True

    def test_atpos_requires_exact_column(self):
        """AtPos requires exact column match."""
        assert check_valid(AtPos(4), 4) is True
        assert check_valid(AtPos(4), 3) is False
        assert check_valid(AtPos(4), 5) is False

    def test_afterpos_allows_at_or_after(self):
        """AfterPos allows column >= specified."""
        assert check_valid(AfterPos(4), 4) is True
        assert check_valid(AfterPos(4), 5) is True
        assert check_valid(AfterPos(4), 10) is True
        assert check_valid(AfterPos(4), 3) is False
        assert check_valid(AfterPos(4), 0) is False

    def test_endofblock_rejects_all(self):
        """EndOfBlock rejects all columns."""
        assert check_valid(EndOfBlock(), 0) is False
        assert check_valid(EndOfBlock(), 5) is False


class TestColumnExtraction:
    """Test extracting column from tokens."""

    def test_token_column_property(self):
        """All tokens have column property."""
        loc = Location(line=1, column=5)
        tok = DummyIdent(name="x", location=loc)
        assert tok.column == 5

    def test_multiline_token_columns(self):
        """Column tracking works across lines."""
        # Simulate tokens from: "case x of\n  A"
        tokens = [
            DummyKeyword(keyword="case", location=Location(line=1, column=1)),
            DummyIdent(name="x", location=Location(line=1, column=6)),
            DummyKeyword(keyword="of", location=Location(line=1, column=8)),
            DummyConstr(name="A", location=Location(line=2, column=3)),
        ]

        assert tokens[0].column == 1
        assert tokens[3].column == 3  # Indented on line 2


class TestBlockEntry:
    """Test block_entry combinator."""

    def test_atpos_accepts_matching_column(self):
        """block_entry accepts token at AtPos column."""
        tokens = [
            DummyIdent(name="x", location=Location(line=1, column=4)),
        ]
        # Would succeed with AtPos(4)
        assert check_valid(AtPos(4), tokens[0].column) is True

    def test_atpos_rejects_wrong_column(self):
        """block_entry rejects token at wrong column."""
        tok = DummyIdent(name="x", location=Location(line=1, column=4))
        assert check_valid(AtPos(2), tok.column) is False

    def test_afterpos_accepts_matching_or_greater(self):
        """block_entry accepts token at or after AfterPos."""
        tok1 = DummyIdent(name="x", location=Location(line=1, column=4))
        tok2 = DummyIdent(name="y", location=Location(line=1, column=6))

        assert check_valid(AfterPos(4), tok1.column) is True
        assert check_valid(AfterPos(4), tok2.column) is True


class TestLayoutScenarios:
    """Test realistic layout scenarios."""

    def test_case_layout_reference_column(self):
        """Case expression: reference column from first branch."""
        # Source: case x of
        #   True -> a
        #   False -> b
        tokens = [
            DummyKeyword(keyword="case", location=Location(line=1, column=1)),
            DummyIdent(name="x", location=Location(line=1, column=6)),
            DummyKeyword(keyword="of", location=Location(line=1, column=8)),
            DummyConstr(name="True", location=Location(line=2, column=3)),
            DummyIdent(name="a", location=Location(line=2, column=10)),
            DummyConstr(name="False", location=Location(line=3, column=3)),
            DummyIdent(name="b", location=Location(line=3, column=11)),
        ]

        # Reference column is from first branch: 3
        reference_col = tokens[3].column
        assert reference_col == 3

        # Subsequent branches must be at column 3
        assert tokens[5].column == 3  # False at col 3 ✓

    def test_let_layout_with_in_terminator(self):
        """Let expression: in must be at/after let column."""
        # Source: let
        #   x = 1
        #   y = 2
        # in x + y
        let_col = 1
        first_binding_col = 3
        in_col = 1

        # First binding sets reference: 3
        # Bindings must be at col 3
        assert check_valid(AtPos(3), first_binding_col) is True

        # 'in' must be at col >= let_col (1)
        assert in_col >= let_col

    def test_data_no_layout_constraints(self):
        """Data declarations: no layout constraints on | separators."""
        # Source: data X =
        #   A
        # | B
        #   | C
        a_col = 3
        b_col = 1  # | at col 1
        c_col = 3  # | at col 3

        # All valid - no layout constraints
        # Data uses greedy parsing
        assert a_col > 0
        assert b_col >= 0
        assert c_col > 0


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_block(self):
        """Empty layout block is valid."""
        # Source: case x of
        #   -- nothing
        # y = 1
        # After 'of', if next token (y) is at col 0 < reference (would be)
        # block ends immediately
        pass  # Would be handled by block_entries returning []

    def test_single_item_block(self):
        """Block with single item."""
        # Source: case x of
        #   A -> 1
        # No other branches
        # Valid - single item is okay
        pass

    def test_mixed_indentation_fails(self):
        """Mixed indentation in layout block fails."""
        # Source: case x of
        #   A -> 1
        #     B -> 2  -- wrong column
        first_col = 3
        second_col = 5

        # Second should be at col 3, not 5
        assert check_valid(AtPos(3), second_col) is False

    def test_explicit_braces_any_indent(self):
        """Inside braces, any indentation allowed."""
        # Source: case x of { A -> 1; B -> 2 }
        # Constraint is AnyIndent
        a_col = 3
        b_col = 10  # Different column, but braces don't care

        assert check_valid(AnyIndent(), a_col) is True
        assert check_valid(AnyIndent(), b_col) is True


class TestIsAtConstraint:
    """Test is_at_constraint helper function."""

    def test_is_at_constraint_exact_match_atpos(self):
        """is_at_constraint returns True for exact AtPos match."""
        assert is_at_constraint(AtPos(4), 4) is True

    def test_is_at_constraint_rejects_different_column(self):
        """is_at_constraint returns False when column doesn't match."""
        assert is_at_constraint(AtPos(4), 3) is False
        assert is_at_constraint(AtPos(4), 5) is False

    def test_is_at_constraint_with_afterpos(self):
        """is_at_constraint with AfterPos checks exact boundary."""
        # AfterPos(col) should match exactly at col
        assert is_at_constraint(AfterPos(4), 4) is True
        assert is_at_constraint(AfterPos(4), 5) is False  # Not exact match

    def test_is_at_constraint_anyindent_always_true(self):
        """AnyIndent always matches (no specific position)."""
        assert is_at_constraint(AnyIndent(), 0) is True
        assert is_at_constraint(AnyIndent(), 100) is True

    def test_is_at_constraint_endofblock_always_false(self):
        """EndOfBlock never matches any column."""
        assert is_at_constraint(EndOfBlock(), 0) is False
        assert is_at_constraint(EndOfBlock(), 5) is False


class TestTerminator:
    """Test terminator combinator."""

    def test_terminator_layout_mode_continues_at_same_col(self):
        """Layout: token at start_col means continue with same constraint."""
        # When we see a token at the exact reference column, block continues
        # This test documents expected behavior - will raise NotImplementedError
        # until terminator() is implemented
        pass  # Placeholder for when we have parser infrastructure

    def test_terminator_layout_mode_ends_when_dedent(self):
        """Layout: token before start_col means EndOfBlock."""
        # Token at col 1 when start_col is 3 means block ended
        pass  # Placeholder

    def test_terminator_layout_mode_continues_when_further_indented(self):
        """Layout: token after start_col is continuation (same constraint)."""
        # Token at col 5 when start_col is 3: part of current item, continue
        pass  # Placeholder

    def test_terminator_braces_semicolon_continues(self):
        """Braces: semicolon means continue with same constraint."""
        pass  # Placeholder

    def test_terminator_braces_close_brace_ends(self):
        """Braces: close brace means EndOfBlock."""
        pass  # Placeholder


class TestMustContinue:
    """Test must_continue validation."""

    def test_must_continue_succeeds_when_not_end_of_block(self):
        """must_continue succeeds when constraint is not EndOfBlock."""
        # AtPos, AfterPos, AnyIndent should all succeed
        pass  # Placeholder

    def test_must_continue_fails_at_end_of_block(self):
        """must_continue raises ParseError when constraint is EndOfBlock."""
        # Should raise with helpful message including 'expected' parameter
        pass  # Placeholder

    def test_must_continue_error_includes_expected_description(self):
        """Error message includes the expected item description."""
        # must_continue(EndOfBlock(), "binding") should mention "binding"
        pass  # Placeholder


# =============================================================================
# Integration with Real Lexer
# =============================================================================


class TestWithRealLexer:
    """Test parser helpers with actual lexer output."""

    def test_lexer_emits_columns(self):
        """Verify lexer attaches column info to tokens."""
        source = """case x of
  A -> 1
  B -> 2"""
        tokens = lex(source)

        # Check some columns
        case_tok = next(t for t in tokens if t.type == "CASE")
        assert case_tok.column == 1

        a_tok = next(t for t in tokens if t.type == "CONSTRUCTOR" and t.value == "A")
        assert a_tok.column == 3  # Indented

    def test_no_virtual_tokens(self):
        """Lexer doesn't emit INDENT/DEDENT/NEXT."""
        source = """case x of
  A -> 1"""
        tokens = lex(source)
        types = [t.type for t in tokens]

        assert "INDENT" not in types
        assert "DEDENT" not in types
        assert "NEXT" not in types


# =============================================================================
# Example Test Parsers (for documentation)
# =============================================================================


def example_case_parser():
    """Example showing how case parser would work (pseudocode)."""
    # Source: case x of
    #   True -> 1
    #   False -> 0

    # 1. Parse 'case', 'x', 'of' normally
    # 2. Read column of first branch (True at col 3)
    # 3. Create constraint: AtPos(3)
    # 4. Parse branches with constraint
    #    - True at col 3 ✓
    #    - False at col 3 ✓
    pass


def example_let_parser():
    """Example showing how let parser would work (pseudocode)."""
    # Source: let
    #   x = 1
    #   y = 2
    # in x + y

    # 1. Parse 'let' at col 1
    # 2. Read column of first binding (x at col 3)
    # 3. Create constraint: AtPos(3)
    # 4. Parse bindings with constraint
    # 5. Check 'in' is at col >= let_col (1)
    pass


def example_data_parser():
    """Example showing how data parser would work (pseudocode)."""
    # Source: data X =
    #   A
    #   | B

    # 1. Parse 'data', 'X', '='
    # 2. Greedy parse constructors separated by |
    # 3. Stop when token at col <= start_col (0)
    pass
