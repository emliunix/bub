"""Stateful layout-aware parser for System F.

Uses a stack-based approach to track layout contexts (let, case, etc.).
Each context tracks:
- keyword_col: Column where the keyword appears (box left edge)
- content_col: Column where first content appears (box content edge)
"""

from dataclasses import dataclass
from typing import Optional, List
from parsy import generate, Parser, match_token, seq

from systemf.surface.parser import Token


@dataclass
class LayoutContext:
    """A layout context (box) tracking indentation rules."""

    keyword: str  # "let", "case", etc.
    keyword_col: int  # Column where keyword appears (box edge)
    content_col: Optional[int] = None  # Column of first content (None until seen)

    def can_start_content(self, col: int) -> bool:
        """Check if column can start content (col > keyword_col)."""
        return col > self.keyword_col

    def is_at_content_level(self, col: int) -> bool:
        """Check if column is at the content level."""
        if self.content_col is None:
            return False
        return col == self.content_col

    def is_left_of_box(self, col: int) -> bool:
        """Check if column is left of the box (should close context)."""
        return col < self.keyword_col


class LayoutStack:
    """Stack of layout contexts for nested structures."""

    def __init__(self):
        self.stack: List[LayoutContext] = []

    def push(self, keyword: str, keyword_col: int) -> None:
        """Push a new layout context."""
        self.stack.append(LayoutContext(keyword, keyword_col))

    def pop(self) -> Optional[LayoutContext]:
        """Pop the top context."""
        if self.stack:
            return self.stack.pop()
        return None

    def current(self) -> Optional[LayoutContext]:
        """Get the current (top) context."""
        if self.stack:
            return self.stack[-1]
        return None

    def set_content_col(self, col: int) -> bool:
        """Set the content column for current context."""
        if self.stack and self.stack[-1].content_col is None:
            self.stack[-1].content_col = col
            return True
        return False

    def should_close_contexts(self, col: int) -> List[LayoutContext]:
        """Return list of contexts that should be closed at this column."""
        to_close = []
        # Close contexts from top down while col < context.keyword_col
        for ctx in reversed(self.stack):
            if ctx.is_left_of_box(col):
                to_close.append(ctx)
            else:
                break
        return list(reversed(to_close))  # Return in pop order


# Global layout stack (per-parse)
_layout_stack: LayoutStack = LayoutStack()


def init_layout_stack() -> None:
    """Initialize fresh layout stack for a new parse."""
    global _layout_stack
    _layout_stack = LayoutStack()


def get_layout_stack() -> LayoutStack:
    """Get the current layout stack."""
    return _layout_stack


# =============================================================================
# Layout-Aware Parser Combinators
# =============================================================================


def keyword_with_layout(keyword: str) -> Parser:
    """Parse a layout keyword and push context.

    Example: 'let', 'case', 'of'
    """

    @generate
    def parser():
        tok = yield match_token(keyword.upper())
        stack = get_layout_stack()
        stack.push(keyword, tok.column)
        return tok

    return parser


@generate
def layout_content():
    """Parse first item in layout, setting content column."""
    stack = get_layout_stack()
    ctx = stack.current()

    if ctx is None:
        raise ValueError("No layout context active")

    # Peek at next token to check column
    tok = yield match_token("IDENT") | match_token("CONSTRUCTOR")

    if ctx.content_col is None:
        # First item - must be indented past keyword
        if not ctx.can_start_content(tok.column):
            raise ValueError(
                f"First item in {ctx.keyword} block must be indented. "
                f"Expected column > {ctx.keyword_col}, got {tok.column}"
            )
        ctx.content_col = tok.column

    return tok


@generate
def layout_item():
    """Parse an item at current layout level.

    Checks column matches content_col. Returns token if valid.
    """
    stack = get_layout_stack()
    ctx = stack.current()

    if ctx is None:
        raise ValueError("No layout context active")

    tok = yield match_token("IDENT") | match_token("CONSTRUCTOR")

    if ctx.content_col is None:
        raise ValueError(f"Content column not set for {ctx.keyword} context")

    if tok.column != ctx.content_col:
        raise ValueError(f"Item must be at column {ctx.content_col}, got {tok.column}")

    return tok


@generate
def layout_terminator(terminator: str):
    """Parse a terminator keyword (like 'in') that closes layout.

    Must be at or right of keyword column.
    """
    stack = get_layout_stack()
    ctx = stack.current()

    if ctx is None:
        raise ValueError("No layout context active")

    tok = yield match_token(terminator.upper())

    if tok.column < ctx.keyword_col:
        raise ValueError(f"'{terminator}' must be at column >= {ctx.keyword_col}, got {tok.column}")

    # Pop the context
    stack.pop()

    return tok


# =============================================================================
# Complete Layout Expressions
# =============================================================================


@generate
def let_expr():
    """Parse let expression with layout.

    let x = 1
        y = 2
    in x + y
    """
    init_layout_stack()

    yield keyword_with_layout("let")

    # First binding (sets content column)
    first = yield layout_content()
    # ... parse rest of binding ...

    # More bindings at same level
    # bindings = yield many(layout_item() >> binding())

    # Terminator
    yield layout_terminator("in")

    # Body expression
    # body = yield expr()

    return {"type": "let", "first": first}


@generate
def case_expr():
    """Parse case expression with layout.

    case x of
      A → 1
      B → 2
    """
    init_layout_stack()

    yield match_token("CASE")
    # scrutinee = yield expr()
    yield keyword_with_layout("of")

    # First branch
    first = yield layout_content()
    # ... parse branch ...

    # More branches
    # branches = yield many(layout_item() >> branch())

    # Case ends on dedent (column < keyword_col)
    # Check for dedent and pop context
    stack = get_layout_stack()
    if stack.current():
        stack.pop()

    return {"type": "case", "first": first}


# =============================================================================
# Tests
# =============================================================================


def test_layout_stack():
    """Test layout stack operations."""
    init_layout_stack()
    stack = get_layout_stack()

    # Push let context at col 4
    stack.push("let", 4)
    ctx = stack.current()
    assert ctx.keyword == "let"
    assert ctx.keyword_col == 4
    assert ctx.content_col is None

    # Set content col
    assert stack.set_content_col(8)
    assert ctx.content_col == 8

    # Check columns
    assert ctx.can_start_content(8)  # 8 > 4
    assert ctx.is_at_content_level(8)
    assert not ctx.is_at_content_level(4)
    assert ctx.is_left_of_box(2)  # 2 < 4

    # Push nested case
    stack.push("of", 8)
    nested = stack.current()
    assert nested.keyword == "of"

    # Pop back
    stack.pop()
    assert stack.current().keyword == "let"

    print("Layout stack tests passed!")


if __name__ == "__main__":
    test_layout_stack()
