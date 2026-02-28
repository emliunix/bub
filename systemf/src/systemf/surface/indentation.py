"""Indentation-aware parser combinators.

This module provides fundamental combinators for parsing indented syntax.
These helpers serve universal structural parsing purposes across the codebase.

⚠️ WARNING: Care should be taken when modifying any of these helpers.
They are foundational primitives that affect parsing structure throughout
the entire parser. Changes here can have wide-ranging consequences.

Core Combinators:
- indented_block: Required indentation wrapper
- indented_opt: Optional indentation (tries indented, falls back to inline)

Usage Example:
    # Required indentation
    body = yield indented_block(statement_parser)

    # Optional indentation
    body = yield indented_opt(expression_parser)
"""

from parsy import generate, Parser as P

from systemf.surface.parser import Token


def indented_block(content_parser: P) -> P:
    """Create a parser for INDENT content DEDENT sequence.

    Requires the content to be at a higher indentation level.
    Consumes the INDENT token, parses content, then consumes DEDENT.

    Args:
        content_parser: Parser for the indented content

    Returns:
        Parser that succeeds only if content is properly indented
    """
    from systemf.surface.parser import INDENT, DEDENT

    @generate
    def block_parser():
        yield INDENT
        content = yield content_parser
        yield DEDENT
        return content

    return block_parser


def indented_opt(content_parser: P) -> P:
    """Create a parser that accepts optional indentation.

    Tries indented form first, falls back to inline form if no INDENT.

    Syntax alternatives:
        INDENT content DEDENT   # indented form (preferred)
        content                 # inline form (fallback)

    Args:
        content_parser: Parser for the content

    Returns:
        Parser that accepts content in either indented or inline form
    """

    @generate
    def opt_parser():
        # Try indented form first
        indented_form = yield indented_block(content_parser).optional()
        if indented_form is not None:
            return indented_form
        # Otherwise parse inline
        return (yield content_parser)

    return opt_parser
