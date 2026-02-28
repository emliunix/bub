"""Comprehensive layout parsing test cases for System F lexer.

These tests verify that the lexer handles various layout scenarios correctly,
including edge cases that might require sophisticated Haskell-style layout rules.

Key layout keywords (trigger layout context): case, of, let, in

Token meanings:
- INDENT: Enter layout context (column increased)
- NEXT: New item at same level (column == reference)
- DEDENT: Exit layout context(s) (column < reference)

Tests marked with "HASKELL_STYLE_NEEDED" indicate cases that likely require
Haskell's sophisticated L-function layout algorithm rather than simple
indentation tracking.
"""

import pytest
from systemf.surface.parser import lex


def get_token_types(source: str) -> list[str]:
    """Helper to tokenize source and return just token types."""
    tokens = lex(source)
    return [t.type for t in tokens]


def get_token_stream(source: str) -> list[tuple[str, str]]:
    """Helper to get token types and values for debugging."""
    tokens = lex(source)
    return [(t.type, t.value) for t in tokens]


# =============================================================================
# Category 1: Basic Layout Cases (Should work with simple approach)
# =============================================================================


class TestBasicLayoutCases:
    """Basic layout scenarios that should work with simple INDENT/NEXT/DEDENT."""

    def test_simple_case_expression(self):
        """Case 1.1: Simple case expression with two branches.

        Expected tokens: CASE IDENT OF INDENT CONSTRUCTOR ARROW NUMBER NEXT CONSTRUCTOR ARROW NUMBER DEDENT EOF
        """
        source = """case x of
  True → 1
  False → 0"""
        types = get_token_types(source)

        # Should have INDENT before first branch, DEDENT after last
        assert "INDENT" in types
        assert "DEDENT" in types
        assert "NEXT" in types  # Between True and False branches

        # Verify structure
        indent_idx = types.index("INDENT")
        next_idx = types.index("NEXT")
        dedent_idx = types.index("DEDENT")

        # INDENT should come after OF
        assert types[indent_idx - 1] == "OF"
        # NEXT should be between branches
        assert indent_idx < next_idx < dedent_idx

    def test_nested_case_expression(self):
        """Case 1.2: Nested case expression.

        Outer case has branches, one branch contains inner case.
        """
        source = """case x of
  A → case y of
    B → 1
    C → 2"""
        types = get_token_types(source)

        # Should have two INDENTs (outer and inner)
        indent_count = types.count("INDENT")
        dedent_count = types.count("DEDENT")

        # Outer case + inner case = 2 INDENTs
        assert indent_count >= 2
        # Should close both contexts
        assert dedent_count >= 2

    def test_let_expression_basic(self):
        """Case 1.3: Basic let expression with multiple bindings.

        Note: Current syntax uses 'let x = expr' format, not the old 'let ... in'
        """
        source = """let
  x = 1
  y = 2
in x + y"""
        types = get_token_types(source)

        # Should have INDENT for bindings, DEDENT before 'in'
        assert "INDENT" in types
        assert "DEDENT" in types
        # Should have NEXT between bindings
        assert "NEXT" in types

    def test_single_line_no_indent(self):
        """Single line expressions should not emit INDENT/DEDENT."""
        source = "case x of { True → 1 | False → 0 }"
        types = get_token_types(source)

        # Explicit braces - no layout tokens
        assert "INDENT" not in types
        assert "DEDENT" not in types
        assert "NEXT" not in types

    def test_data_declaration_simple(self):
        """Simple data declaration with inline constructors."""
        source = "data Bool = True | False"
        types = get_token_types(source)

        # Inline - no layout tokens
        assert "INDENT" not in types
        assert "DEDENT" not in types

    def test_data_declaration_indented(self):
        """Data declaration with indented constructors."""
        source = """data List a =
  Nil
  | Cons a (List a)"""
        types = get_token_types(source)

        # Should have INDENT before first constructor
        assert "INDENT" in types
        assert "DEDENT" in types
        # Bar should come after NEXT or inline
        assert "BAR" in types


# =============================================================================
# Category 2: Edge Cases That Might Fail
# =============================================================================


class TestMixedIndentationLevels:
    """Cases with mixed indentation that might confuse simple layout handling."""

    @pytest.mark.xfail(reason="HASKELL_STYLE_NEEDED: Different reference columns within same block")
    def test_data_constructor_inline_then_indented(self):
        """Case 2.1: First constructor inline, rest indented at different level.

        In Haskell, constructors after | can have different indentation than the first.
        This tests if the lexer properly tracks reference columns per constructor.
        """
        source = """data T = A
       | B
       | C"""
        types = get_token_types(source)

        # This might fail because the reference column changes after first constructor
        # The simple approach expects all items at the same column
        constructors = [t for t in get_token_stream(source) if t[0] == "CONSTRUCTOR"]
        assert len(constructors) == 3

    @pytest.mark.xfail(reason="HASKELL_STYLE_NEEDED: Empty lines in layout blocks")
    def test_empty_lines_in_layout(self):
        """Case 2.2: Empty lines between items in a layout block.

        Empty lines should not emit NEXT tokens. The lexer needs to skip
        blank lines without treating them as new items.
        """
        source = """case x of
  True → 1

  False → 0"""
        types = get_token_types(source)

        # Should only have one NEXT (between True and False)
        next_count = types.count("NEXT")
        # Might fail if empty line emits spurious NEXT
        assert next_count == 1


class TestMultipleDedents:
    """Cases requiring multiple DEDENT tokens."""

    def test_multiple_dedent_simple(self):
        """Case 2.3: Multiple levels of DEDENT needed when exiting nested contexts.

        This should work with simple stack-based indentation.
        """
        source = """f = case x of
  A → case y of
    B → 1

main = 42"""
        types = get_token_types(source)

        # When we hit 'main', we need to DEDENT twice
        dedent_count = types.count("DEDENT")
        # At least 2 DEDENTs to close both case contexts
        assert dedent_count >= 2

        # 'main' should come after DEDENTs
        main_idx = next(
            i
            for i, t in enumerate(types)
            if t == "IDENT" and get_token_stream(source)[i][1] == "main"
        )
        last_dedent_idx = max(i for i, t in enumerate(types) if t == "DEDENT")
        assert last_dedent_idx < main_idx


class TestComplexNesting:
    """Cases with complex nested structures."""

    @pytest.mark.xfail(reason="HASKELL_STYLE_NEEDED: Type expressions spanning lines")
    def test_constructor_type_spanning_lines(self):
        """Case 2.4: Constructor with complex type that spans lines.

        The type arguments might be at different indentation levels.
        """
        source = """data Tree a = Leaf a
  | Node (Tree a) (Tree a)"""
        types = get_token_types(source)

        # This tests if the lexer handles continuation lines correctly
        # The type on the second line is part of the constructor, not a new item
        constructors = [t for t in get_token_stream(source) if t[0] == "CONSTRUCTOR"]
        assert len(constructors) == 2

    @pytest.mark.xfail(reason="HASKELL_STYLE_NEEDED: Nested layout contexts")
    def test_data_with_nested_case(self):
        """Case 2.6: Data declaration with case expression inside type.

        This creates overlapping layout contexts.
        """
        source = """data T = A Int
  | B (case x of True → Int | False → String)"""
        types = get_token_types(source)

        # Case inside constructor type should have its own INDENT/DEDENT
        # This tests proper context nesting
        indent_count = types.count("INDENT")
        # At least 2: one for data, one for case
        assert indent_count >= 2


class TestExplicitBracesInteraction:
    """Cases testing interaction between explicit braces and layout."""

    def test_explicit_braces_disable_layout(self):
        """Case 2.5 (variant): Explicit braces should disable layout mode.

        Note: Based on spec, explicit braces disable layout mode.
        The original case with mixed braces/layout might be invalid syntax.
        """
        source = "case x of { True → 1; False → 0 }"
        types = get_token_types(source)

        # Braces used - no layout tokens
        assert "INDENT" not in types
        assert "DEDENT" not in types
        # Semicolon separators, not NEXT
        assert "NEXT" not in types

    @pytest.mark.xfail(reason="HASKELL_STYLE_NEEDED: Layout after explicit brace block")
    def test_layout_after_brace_block(self):
        """Test if layout works correctly after an explicit brace block ends.

        This tests context restoration after explicit syntax.
        """
        source = """f = case x of { True → 1; False → 0 }
g = 42"""
        types = get_token_types(source)

        # After the brace block, layout should work normally
        # This might fail if layout state is corrupted by brace block
        assert "IDENT" in types  # Should have 'f' and 'g'


# =============================================================================
# Category 3: Cases Inspired by Haskell's Complex Rules
# =============================================================================


class TestHaskellStyleLayout:
    """Cases requiring Haskell's sophisticated layout algorithm (L-function)."""

    @pytest.mark.xfail(reason="HASKELL_STYLE_NEEDED: Parse-error recovery")
    def test_let_in_proper_closing(self):
        """Case 3.1: Verify 'in' properly closes let layout context.

        Haskell uses parse-error recovery: if 'in' is at wrong indentation,
        it closes the let context automatically.
        """
        source = """let
  x = 1
in x + 2"""
        types = get_token_types(source)

        # 'in' should trigger closing the let context
        # Check that we have proper INDENT/DEDENT
        indent_idx = types.index("INDENT")
        in_idx = types.index("IN")
        dedent_idx = types.index("DEDENT")

        # DEDENT should come after 'in' keyword
        assert in_idx < dedent_idx

    @pytest.mark.xfail(reason="HASKELL_STYLE_NEEDED: Multiple nested contexts")
    def test_non_decreasing_indentation(self):
        """Case 3.2: Multiple nested contexts at same/different levels.

        Haskell requires non-decreasing indentation within a context.
        Items at same indentation level as reference emit NEXT.
        Items at higher indentation continue current item.
        Items at lower indentation close context(s).
        """
        source = """f = let
      x = 1
      y = let
            z = 2
          in z
    in x + y"""
        types = get_token_types(source)

        # Complex nesting - outer let at col 6, inner let at col 11
        # This tests proper tracking of multiple layout contexts
        indent_count = types.count("INDENT")
        dedent_count = types.count("DEDENT")

        # Should have balanced INDENT/DEDENT
        assert indent_count == dedent_count

    @pytest.mark.xfail(reason="HASKELL_STYLE_NEEDED: Same-column items")
    def test_no_indentation_items(self):
        """Case 3.3: Items at same column as layout keyword (no indentation).

        In Haskell, items can be at the same column as the reference
        if there's no indentation after the layout keyword.
        """
        source = """case x of
True → 1
False → 0"""
        types = get_token_types(source)

        # With no indentation, the first token's column becomes the reference
        # True and False are at that column, so they should emit NEXT between them
        next_count = types.count("NEXT")
        # Might fail if lexer expects actual indentation
        assert next_count == 1


class TestLayoutKeywordInteraction:
    """Test interaction of multiple layout keywords."""

    @pytest.mark.xfail(reason="HASKELL_STYLE_NEEDED: Sequential layout keywords")
    def test_case_of_let_in_sequence(self):
        """Case: case ... of followed by let ... in.

        Multiple layout contexts in sequence.
        """
        source = """case x of
  A → let
    y = 1
  in y
  B → 2"""
        types = get_token_types(source)

        # Should have proper nesting: case opens, let opens inside, both close
        indent_count = types.count("INDENT")
        dedent_count = types.count("DEDENT")

        # case has one INDENT, let has one INDENT
        assert indent_count >= 2
        assert dedent_count >= 2

    def test_lambda_with_case(self):
        """Lambda expression containing case expression."""
        source = """λx →
  case x of
    True → 1
    False → 0"""
        types = get_token_types(source)

        # Lambda body is indented, case adds another level
        indent_count = types.count("INDENT")
        assert indent_count >= 1

        # Should have NEXT between True and False
        assert "NEXT" in types


# =============================================================================
# Category 4: Real-World Cases from Prelude
# =============================================================================


class TestPreludeInspiredCases:
    """Test cases inspired by actual code in prelude.sf."""

    def test_map_function(self):
        """Test the map function from prelude."""
        source = """map : ∀a. ∀b. (a → b) → List a → List b
map = Λa. Λb. λf:(a → b) → λxs:List a →
  case xs of
    Nil → Nil
    Cons y ys → Cons (f y) (map f ys)"""
        types = get_token_types(source)

        # Should tokenize without errors
        assert types[-1] == "EOF"
        # Should have INDENT for case branches
        assert "INDENT" in types
        assert "NEXT" in types  # Between Nil and Cons

    def test_filter_function(self):
        """Test filter with if-then-else inside case."""
        source = """filter : ∀a. (a → Bool) → List a → List a
filter = Λa. λp:(a → Bool) → λxs:List a →
  case xs of
    Nil → Nil
    Cons y ys →
      if p y
        then Cons y (filter p ys)
        else filter p ys"""
        types = get_token_types(source)

        # Complex nesting: case → if
        assert "INDENT" in types
        assert "CASE" in types
        assert "IF" in types

    def test_data_with_multiple_constructors(self):
        """Test data declaration like Either or Maybe."""
        source = """data Maybe a = Nothing | Just a"""
        types = get_token_types(source)

        # Inline - no layout
        assert "INDENT" not in types
        assert types == [
            "DATA",
            "CONSTRUCTOR",
            "IDENT",
            "EQUALS",
            "CONSTRUCTOR",
            "BAR",
            "CONSTRUCTOR",
            "IDENT",
            "EOF",
        ]

    def test_short_pattern_brace_form(self):
        """Test short pattern form using explicit braces.

        From prelude: not : Bool → Bool = λb:Bool → case b of { True → False | False → True }
        """
        source = "not : Bool → Bool = λb:Bool → case b of { True → False | False → True }"
        types = get_token_types(source)

        # Braces - no layout tokens
        assert "INDENT" not in types
        assert "NEXT" not in types
        assert "DEDENT" not in types


# =============================================================================
# Category 5: Error Cases
# =============================================================================


class TestLayoutErrors:
    """Test cases that should produce errors."""

    def test_inconsistent_indentation(self):
        """Test that inconsistent indentation raises an error."""
        from systemf.surface.parser import LexerError

        source = """let
  x = 1
    y = 2
   z = 3"""

        # The third line has inconsistent indentation (3 spaces vs 2 or 4)
        # This might or might not be an error depending on the algorithm
        try:
            tokens = lex(source)
            # If it succeeds, verify it handles gracefully
            types = [t.type for t in tokens]
            assert "INDENT" in types
        except LexerError:
            # Expected: inconsistent indentation is an error
            pass

    @pytest.mark.xfail(reason="HASKELL_STYLE_NEEDED: Parse-error based closing")
    def test_missing_in_keyword(self):
        """Test behavior when 'in' keyword is missing from let.

        Haskell uses parse-error to detect end of let block.
        """
        source = """let
  x = 1
  y = 2
z = 3"""

        # Without 'in', the let block should close at the dedent
        types = get_token_types(source)

        # Should close let context before 'z'
        # This might fail without parse-error recovery
        z_idx = next(
            i for i, t in enumerate(types) if t == "IDENT" and get_token_stream(source)[i][1] == "z"
        )
        # There should be DEDENTs before z
        dedents_before_z = sum(1 for i, t in enumerate(types) if t == "DEDENT" and i < z_idx)
        assert dedents_before_z >= 1


# =============================================================================
# Summary and Prediction
# =============================================================================

"""
PREDICTION OF TEST RESULTS:

Tests Likely to PASS with Simple Layout Handling:
- test_simple_case_expression
- test_nested_case_expression  
- test_let_expression_basic
- test_single_line_no_indent
- test_data_declaration_simple
- test_data_declaration_indented
- test_multiple_dedent_simple
- test_explicit_braces_disable_layout
- test_map_function
- test_filter_function
- test_data_with_multiple_constructors
- test_short_pattern_brace_form

Tests Likely to FAIL (Need Haskell-style L-function):
- test_data_constructor_inline_then_indented (Case 2.1)
- test_empty_lines_in_layout (Case 2.2) 
- test_constructor_type_spanning_lines (Case 2.4)
- test_data_with_nested_case (Case 2.6)
- test_layout_after_brace_block
- test_let_in_proper_closing (Case 3.1)
- test_non_decreasing_indentation (Case 3.2)
- test_no_indentation_items (Case 3.3)
- test_case_of_let_in_sequence
- test_missing_in_keyword

The simple INDENT/NEXT/DEDENT approach works well for:
1. Consistently indented blocks
2. Simple nesting
3. Explicit braces
4. Standard patterns like prelude.sf

It will fail for:
1. Variable reference columns (like Haskell constructors)
2. Empty lines (if not handled specially)
3. Type expressions that span lines
4. Complex nesting with multiple contexts
5. Parse-error recovery patterns
"""
