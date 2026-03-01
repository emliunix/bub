"""Parser helper combinators for System F layout-sensitive parsing.

This module provides the core layout-aware parser combinators following
Idris2's approach with explicit constraint passing.

Key design:
- No global state - constraints passed explicitly
- Column-aware token parsing
- Block handling with layout or explicit braces
"""

from __future__ import annotations

from typing import TypeVar, Callable, List, Tuple, Optional
from parsy import Parser as P, Result, generate, eof, peek, success, fail

from .types import (
    TokenBase,
    ValidIndent,
    AnyIndent,
    AtPos,
    AfterPos,
    EndOfBlock,
    DelimiterToken,
)

# Type variable for parsed items
T = TypeVar("T")


# =============================================================================
# Core Infrastructure
# =============================================================================


def column() -> P[int]:
    """Get the column of the current token.

    Returns a parser that succeeds with the current token's start column.
    Used to capture the reference column for layout blocks.

    Example:
        After parsing `case x of`, call `column()` to get the column
        of the first branch token.
    """

    @P
    def parser(tokens: list, index: int) -> Result:
        if index >= len(tokens):
            return Result.failure(index, "expected token")
        token = tokens[index]
        return Result.success(index, token.column)

    return parser


def check_valid(constraint: ValidIndent, col: int) -> bool:
    """Check if a column satisfies a constraint.

    Args:
        constraint: The layout constraint to check against
        col: The column number to check

    Returns:
        True if col satisfies the constraint, False otherwise

    Examples:
        >>> check_valid(AnyIndent(), 5)
        True
        >>> check_valid(AtPos(4), 4)
        True
        >>> check_valid(AtPos(4), 5)
        False
    """
    match constraint:
        case AnyIndent():
            return True
        case AtPos(c):
            return col == c
        case AfterPos(c):
            return col >= c
        case EndOfBlock():
            return False
    return False


def is_at_constraint(constraint: ValidIndent, col: int) -> bool:
    """Check if a column is exactly at the constraint position.

    Like check_valid but specifically for exact match.
    Useful for determining if we're at a new item vs continuation.

    Args:
        constraint: The layout constraint
        col: Column to check

    Returns:
        True if col matches constraint's exact position

    Example:
        >>> is_at_constraint(AtPos(4), 4)
        True
        >>> is_at_constraint(AtPos(4), 5)
        False
    """
    match constraint:
        case AnyIndent():
            return True
        case AtPos(c):
            return col == c
        case AfterPos(c):
            return col == c
        case EndOfBlock():
            return False
    return False


def get_indent_info(token: TokenBase) -> int:
    """Extract column (indentation info) from a token.

    Args:
        token: Any token with location info

    Returns:
        The token's start column

    Example:
        >>> get_indent_info(ident_token)
        4
    """
    return token.column


# =============================================================================
# Block Parsing Combinators
# =============================================================================


def block(item: Callable[[ValidIndent], P[T]]) -> P[List[T]]:
    """Parse a block that can be either explicit braces or layout-indented.

    Tries to parse:
    1. Explicit braces: `{ item; item; ... }` (uses AnyIndent)
    2. Layout mode: indented block starting at current position (uses AtPos)

    In layout mode:
    - Captures column of first token as reference
    - All subsequent items must be at that exact column
    - Block ends when token is at or before reference column

    Args:
        item: A parser that takes a ValidIndent constraint and returns T

    Returns:
        A parser that returns a list of parsed items

    Examples:
        >>> block(branch_parser).parse("{ A -> 1; B -> 2 }")
        [Branch(...), Branch(...)]

        >>> block(branch_parser).parse("A -> 1\nB -> 2")  # At same column
        [Branch(...), Branch(...)]
    """
    raise NotImplementedError("block() not yet implemented")


def block_after(min_col: int, item: Callable[[ValidIndent], P[T]]) -> P[List[T]]:
    """Parse a block indented at least min_col spaces.

    Used when we need items to be indented past a specific column.
    Falls back to empty list if not indented enough.

    Args:
        min_col: Minimum column for items (inclusive)
        item: Parser for individual items

    Returns:
        Parser that returns list of items, or empty list if not indented

    Example:
        >>> block_after(4, binding_parser).parse("    x = 1\n    y = 2")
        [Binding(...), Binding(...)]
    """
    raise NotImplementedError("block_after() not yet implemented")


def block_entries(constraint: ValidIndent, item: Callable[[ValidIndent], P[T]]) -> P[List[T]]:
    """Parse zero or more items with the given column constraint.

    Continues parsing items until:
    - Explicit terminator found (`}` or `;` in braces mode)
    - Token at/before start column found (layout mode)
    - End of input

    Args:
        constraint: The ValidIndent constraint for items
        item: Parser that takes constraint and returns T

    Returns:
        Parser returning list of zero or more items

    Example:
        >>> block_entries(AtPos(4), binding_parser).parse("x = 1\ny = 2")
        [Binding(...), Binding(...)]  # Both at column 4
    """
    raise NotImplementedError("block_entries() not yet implemented")


def block_entry(
    constraint: ValidIndent, item: Callable[[ValidIndent], P[T]]
) -> P[Tuple[T, ValidIndent]]:
    """Parse a single item and check its column against constraint.

    Args:
        constraint: Column constraint the item must satisfy
        item: Parser for the item (receives constraint)

    Returns:
        Tuple of (parsed_item, updated_constraint)

    Raises:
        ParseError: If item's column doesn't satisfy constraint

    Example:
        >>> block_entry(AtPos(4), ident_parser).parse("x")
        (Ident('x'), AtPos(4))
    """
    raise NotImplementedError("block_entry() not yet implemented")


# =============================================================================
# Terminators and Validation
# =============================================================================


def terminator(constraint: ValidIndent, start_col: int) -> P[ValidIndent]:
    """Check for block terminators and return updated constraint.

    In braces mode:
    - `;` found: continue with AfterPos constraint
    - `}` found: return EndOfBlock

    In layout mode:
    - Token at column <= start_col: end block (return EndOfBlock)
    - Token at column > start_col: continuation (return same constraint)

    Args:
        constraint: Current layout constraint
        start_col: Starting column of the block

    Returns:
        Updated constraint for next entry

    Example:
        >>> terminator(AtPos(4), 4).parse("")  # At same column
        AtPos(4)

        >>> terminator(AtPos(4), 4).parse("end")  # At column 0
        EndOfBlock()
    """
    raise NotImplementedError("terminator() not yet implemented")


def must_continue(constraint: ValidIndent, expected: Optional[str] = None) -> P[None]:
    """Verify we're still within the block and haven't hit a terminator.

    Used after keywords or between items to ensure layout hasn't ended
    unexpectedly.

    Args:
        constraint: Current constraint
        expected: Optional description of what we expected to find

    Raises:
        ParseError: If constraint is EndOfBlock

    Example:
        >>> must_continue(AtPos(4), "binding").parse("x")
        None  # Success, we're still in block
    """
    raise NotImplementedError("must_continue() not yet implemented")


# =============================================================================
# Declarations (NOT helpers - stub only)
# =============================================================================


def top_decl(constraint: ValidIndent) -> P:
    """Parse a top-level declaration. (STUB - not a helper)"""
    raise NotImplementedError("top_decl() is not a helper - implement in parser module")


def data_decl(constraint: ValidIndent) -> P:
    """Parse a data declaration. (STUB - not a helper)"""
    raise NotImplementedError("data_decl() is not a helper - implement in parser module")


def let_decl(constraint: ValidIndent) -> P:
    """Parse a let declaration. (STUB - not a helper)"""
    raise NotImplementedError("let_decl() is not a helper - implement in parser module")


# =============================================================================
# Expressions (NOT helpers - stub only)
# =============================================================================


def case_expr(constraint: ValidIndent) -> P:
    """Parse a case expression. (STUB - not a helper)"""
    raise NotImplementedError("case_expr() is not a helper - implement in parser module")


def expr_parser(constraint: ValidIndent) -> P:
    """Parse an expression. (STUB - not a helper)"""
    raise NotImplementedError("expr_parser() is not a helper - implement in parser module")


def type_parser(constraint: ValidIndent) -> P:
    """Parse a type expression. (STUB - not a helper)"""
    raise NotImplementedError("type_parser() is not a helper - implement in parser module")


__all__ = [
    # Core infrastructure
    "column",
    "check_valid",
    "is_at_constraint",
    "get_indent_info",
    # Block combinators
    "block",
    "block_after",
    "block_entries",
    "block_entry",
    # Terminators
    "terminator",
    "must_continue",
    # Declarations (stubs)
    "top_decl",
    "data_decl",
    "let_decl",
    # Expressions (stubs)
    "case_expr",
    "expr_parser",
    "type_parser",
]
