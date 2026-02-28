"""Parser helper combinators for System F layout-sensitive parsing.

This module provides the core layout-aware parser combinators following
Idris2's approach with explicit constraint passing.

Key design:
- No global state - constraints passed explicitly
- Column-aware token parsing
- Block handling with layout or explicit braces

NOTE: These are skeleton implementations for type checking.
Actual implementations will be added later.
"""

from __future__ import annotations

from typing import TypeVar, Callable, List, Tuple, Optional
from parsy import Parser

from .types import TokenBase, ValidIndent, AnyIndent, AtPos, AfterPos, EndOfBlock

# Type variable for parsed items
T = TypeVar("T")


# =============================================================================
# Core Infrastructure
# =============================================================================


def column() -> Parser[int]:
    """Get the column of the current token.

    Returns a parser that succeeds with the current token's start column.
    Used to capture the reference column for layout blocks.

    Example:
        After parsing `case x of`, call `column()` to get the column
        of the first branch token.
    """
    raise NotImplementedError("column() not yet implemented")


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
    raise NotImplementedError("check_valid() not yet implemented")


# =============================================================================
# Block Parsing Combinators
# =============================================================================


def block(item: Callable[[ValidIndent], Parser[T]]) -> Parser[List[T]]:
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


def block_after(min_col: int, item: Callable[[ValidIndent], Parser[T]]) -> Parser[List[T]]:
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


def block_entries(
    constraint: ValidIndent, item: Callable[[ValidIndent], Parser[T]]
) -> Parser[List[T]]:
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
    constraint: ValidIndent, item: Callable[[ValidIndent], Parser[T]]
) -> Parser[Tuple[T, ValidIndent]]:
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


def terminator(constraint: ValidIndent, start_col: int) -> Parser[ValidIndent]:
    """Check for block terminators and return updated constraint.

    In braces mode:
    - `;` found: continue with same constraint
    - `}` found: return EndOfBlock

    In layout mode:
    - Token at column == start_col: new item (return same constraint)
    - Token at column < start_col: end block (return EndOfBlock)
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


def must_continue(constraint: ValidIndent, expected: Optional[str] = None) -> Parser[None]:
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
# Declarations
# =============================================================================


def top_decl(constraint: ValidIndent) -> Parser:
    """Parse a top-level declaration.

    Handles:
    - Data declarations: data X = A | B
    - Let declarations: let ... in ...
    - Type declarations

    Uses greedy parsing - declaration ends when next token at
    column <= constraint start is found.

    Args:
        constraint: ValidIndent constraint (usually from top-level block)

    Returns:
        Parser for declaration AST node
    """
    raise NotImplementedError("top_decl() not yet implemented")


def data_decl(constraint: ValidIndent) -> Parser:
    """Parse a data declaration: data X = A | B | ...

    Data declarations are NOT layout-sensitive. The `|` separator
    can appear at any column. Declaration ends greedily when
    next top-level token is encountered.

    Args:
        constraint: Parent constraint for determining where decl ends

    Returns:
        Parser for DataDecl AST node

    Examples:
        >>> data_decl(AnyIndent()).parse("data Bool = True | False")
        DataDecl(name='Bool', constructors=[...])

        >>> data_decl(AnyIndent()).parse("data X =\n  A\n  | B")
        DataDecl(name='X', constructors=[...])
    """
    raise NotImplementedError("data_decl() not yet implemented")


def let_decl(constraint: ValidIndent) -> Parser:
    """Parse a let declaration: let bindings in expr

    Let declarations ARE layout-sensitive:
    1. Parse 'let'
    2. Read column of first binding -> reference column
    3. Parse all bindings at reference column (layout block)
    4. Check 'in' is at column >= 'let' column
    5. Parse body expression

    Args:
        constraint: Parent constraint

    Returns:
        Parser for LetDecl AST node

    Example:
        >>> let_decl(AnyIndent()).parse("let x = 1 in x + 2")
        LetDecl(bindings=[...], body=...)

        >>> let_decl(AnyIndent()).parse("let\n  x = 1\n  y = 2\nin x + y")
        LetDecl(bindings=[...], body=...)
    """
    raise NotImplementedError("let_decl() not yet implemented")


# =============================================================================
# Expressions
# =============================================================================


def case_expr(constraint: ValidIndent) -> Parser:
    """Parse a case expression: case scrutinee of branches

    Case expressions ARE layout-sensitive:
    1. Parse 'case', scrutinee, 'of'
    2. Read column of first branch -> reference column
    3. Parse branches at reference column
    4. Each branch: pattern -> expression

    Args:
        constraint: Parent constraint

    Returns:
        Parser for CaseExpr AST node

    Example:
        >>> case_expr(AnyIndent()).parse("case x of True -> 1 | False -> 0")
        CaseExpr(scrutinee=..., branches=[...])

        >>> case_expr(AnyIndent()).parse("case x of\n  True -> 1\n  False -> 0")
        CaseExpr(scrutinee=..., branches=[...])
    """
    raise NotImplementedError("case_expr() not yet implemented")


def expr_parser(constraint: ValidIndent) -> Parser:
    """Parse an expression with layout awareness.

    Handles:
    - Variables, constructors
    - Applications
    - Lambdas: \\x -> expr
    - Case expressions (layout)
    - Let expressions (layout)
    - Literals

    Args:
        constraint: Layout constraint for nested expressions

    Returns:
        Parser for expression AST node
    """
    raise NotImplementedError("expr_parser() not yet implemented")


def type_parser(constraint: ValidIndent) -> Parser:
    """Parse a type expression.

    Handles:
    - Type variables
    - Type constructors
    - Forall: forall a. type or ∀a. type
    - Arrows: A -> B
    - Applications: F A

    Args:
        constraint: Layout constraint (usually AnyIndent for types)

    Returns:
        Parser for type AST node
    """
    raise NotImplementedError("type_parser() not yet implemented")


# =============================================================================
# Helper Functions
# =============================================================================


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
    raise NotImplementedError("is_at_constraint() not yet implemented")


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
    raise NotImplementedError("get_indent_info() not yet implemented")


__all__ = [
    # Core infrastructure
    "column",
    "check_valid",
    # Block combinators
    "block",
    "block_after",
    "block_entries",
    "block_entry",
    # Terminators
    "terminator",
    "must_continue",
    # Declarations
    "top_decl",
    "data_decl",
    "let_decl",
    # Expressions
    "case_expr",
    "expr_parser",
    "type_parser",
    # Helpers
    "is_at_constraint",
    "get_indent_info",
]
