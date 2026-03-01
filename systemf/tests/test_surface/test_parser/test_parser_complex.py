"""Complex layout parsing tests.

Tests for nested layout scenarios that exercise the full parser stack.
These tests verify that layout constraints flow correctly through nested constructs.
"""

import pytest
from dataclasses import dataclass
from typing import List

from systemf.surface.parser import (
    TokenBase,
    IdentifierToken,
    KeywordToken,
    ConstructorToken,
    OperatorToken,
    DelimiterToken,
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
    block_entries,
    block_entry,
    terminator,
    must_continue,
)


# =============================================================================
# Complex Layout Scenario: Nested case + let
# =============================================================================
#
# Source:
#   case x of          -- parent indent = 0
#     True -> let      -- True at col 2, let at col 8 (> 2 ✓)
#       y = 1          -- y at col 4 (> 2 ✓, matches let's block)
#     in y + 1         -- in must be >= col 2 ✓
#     False -> 0       -- False at col 2 (matches True's column ✓)
#
# This tests:
# 1. Case branches at consistent column (2)
# 2. Nested let bindings at deeper column (4)
# 3. 'in' keyword validation relative to parent (>= 2)
# 4. Multiple branches maintaining layout


class TestNestedCaseLet:
    """Test nested case expressions with let bindings."""

    def test_case_branches_at_consistent_column(self):
        """Case branches must be at the same column."""
        source = """case x of
  True -> 1
  False -> 0"""

        tokens = lex(source)

        # Find 'True' and 'False' tokens
        true_tok = next(t for t in tokens if hasattr(t, "value") and t.value == "True")
        false_tok = next(t for t in tokens if hasattr(t, "value") and t.value == "False")

        # Both should be at same column (2 spaces indent = column 3)
        # Note: columns are 1-indexed, so 2 spaces = column 3
        assert true_tok.column == 3
        assert false_tok.column == 3

        # Check consistency with AtPos constraint
        assert check_valid(AtPos(3), true_tok.column)
        assert check_valid(AtPos(3), false_tok.column)

    def test_let_bindings_deeper_than_case(self):
        """Let bindings must be indented past the case branch."""
        source = """case x of
  True -> let
    y = 1
    z = 2
  in y + z"""

        tokens = lex(source)

        # Find column positions
        true_tok = next(t for t in tokens if hasattr(t, "value") and t.value == "True")
        y_tok = next(t for t in tokens if hasattr(t, "value") and t.value == "y")
        z_tok = next(t for t in tokens if hasattr(t, "value") and t.value == "z")
        in_tok = next(t for t in tokens if hasattr(t, "value") and t.value == "in")

        # Case branch at col 3 (2 spaces indent, 1-indexed)
        assert true_tok.column == 3

        # Let bindings at col 5 (4 spaces indent, deeper than case)
        assert y_tok.column == 5
        assert z_tok.column == 5

        # 'in' at col 3 (>= case column, same as branch)
        assert in_tok.column == 3

    def test_in_keyword_must_be_at_or_after_parent_column(self):
        """'in' must not be dedented past the parent's reference column."""
        # This is a layout validation test
        # 'in' at col 2 when parent is at col 2 should pass
        assert check_valid(AfterPos(2), 2)  # At boundary
        assert check_valid(AfterPos(2), 4)  # Indented further

    def test_nested_constraint_validation(self):
        """Constraints flow correctly through nested blocks."""
        # Outer: case branches at AtPos(2)
        # Inner: let bindings at AtPos(4)

        # Branch at col 2 is valid
        assert check_valid(AtPos(2), 2)

        # Binding at col 4 is valid for let block
        assert check_valid(AtPos(4), 4)

        # But binding at col 4 is NOT at case branch column
        assert not check_valid(AtPos(2), 4)

    def test_terminator_detects_branch_end(self):
        """Terminator detects when we've left the case block."""
        # After parsing a branch, if we see a token at col <= branch_col,
        # that's a terminator

        # Token at same column as reference = new branch (not terminator in layout mode)
        # Actually in our design, same col means continue
        # Dedent means end
        pass  # TODO: Implement when we have full parser


class TestMixedExplicitAndLayout:
    """Test mixing explicit braces with layout."""

    def test_explicit_braces_override_layout(self):
        """Inside { }, layout rules don't apply."""
        # Note: No semicolons since lexer doesn't have SEMICOLON token
        source = """{
  x = 1
  y = 2
}"""
        tokens = lex(source)

        types = [t.type if hasattr(t, "type") else str(type(t).__name__) for t in tokens]

        # Check braces are present
        assert any("LBRACE" in str(t) or "{" in str(t) for t in types)
        assert any("RBRACE" in str(t) or "}" in str(t) for t in types)

    def test_mixed_case_with_explicit_branches(self):
        """Case can use explicit braces for branches."""
        # Note: Using newlines instead of semicolons since lexer doesn't have SEMICOLON
        source = """case x of {
  True -> 1
  False -> 0
}"""
        tokens = lex(source)

        # Should parse without layout constraints
        # AnyIndent mode inside braces
        pass  # TODO: Implement when we have full parser


class TestErrorCases:
    """Test layout error detection."""

    def test_inconsistent_branch_indentation(self):
        """Branches at different columns should fail."""
        # True at col 2, False at col 4 - should be error
        true_col = 2
        false_col = 4

        # False at col 4 does NOT satisfy AtPos(2)
        assert not check_valid(AtPos(2), false_col)

    def test_dedented_let_binding(self):
        """Let binding dedented past case branch should fail."""
        # Case branch at col 2
        # Binding at col 0 - violates constraint
        binding_col = 0

        # Does NOT satisfy AtPos(4) or even AfterPos(2)
        assert not check_valid(AtPos(4), binding_col)
        assert not check_valid(AfterPos(2), binding_col)

    def test_in_keyword_dedented(self):
        """'in' dedented past 'let' column should fail."""
        # 'let' at col 8 (for example)
        # 'in' at col 0 - definitely wrong
        in_col = 0

        assert not check_valid(AfterPos(8), in_col)
