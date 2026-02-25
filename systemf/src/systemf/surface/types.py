"""Type definitions for surface language lexer.

Provides TokenType enum and related type definitions for the indentation-aware lexer.
"""

from __future__ import annotations

from enum import auto


class TokenType:
    """Token types for the System F surface language lexer.

    This class uses class attributes instead of Enum for string compatibility
    with the existing parser which expects token types as strings.
    """

    # Whitespace and comments (skipped during normal tokenization)
    WHITESPACE = "WHITESPACE"
    COMMENT = "COMMENT"

    # Indentation tokens (new for indentation-aware parsing)
    INDENT = "INDENT"  # Increased indentation level
    DEDENT = "DEDENT"  # Decreased indentation level
    NEWLINE = "NEWLINE"  # Explicit newline (may be used instead of implicit)

    # Keywords
    DATA = "DATA"
    LET = "LET"
    IN = "IN"
    CASE = "CASE"
    OF = "OF"
    FORALL = "FORALL"
    TYPE = "TYPE"

    # Multi-character operators
    ARROW = "ARROW"  # ->
    DARROW = "DARROW"  # =>
    LAMBDA = "LAMBDA"  # \
    TYPELAMBDA = "TYPELAMBDA"  # /\

    # Single-character operators
    EQUALS = "EQUALS"  # =
    COLON = "COLON"  # :
    BAR = "BAR"  # |
    AT = "AT"  # @
    DOT = "DOT"  # .

    # Delimiters
    LPAREN = "LPAREN"  # (
    RPAREN = "RPAREN"  # )
    LBRACKET = "LBRACKET"  # [
    RBRACKET = "RBRACKET"  # ]
    LBRACE = "LBRACE"  # {
    RBRACE = "RBRACE"  # }
    COMMA = "COMMA"  # ,

    # Identifiers and constructors
    CONSTRUCTOR = "CONSTRUCTOR"  # Type/constructor names (Uppercase)
    IDENT = "IDENT"  # Variables (lowercase or underscore)

    # Literals
    NUMBER = "NUMBER"  # Numeric literals

    # End of file
    EOF = "EOF"

    # All token types as a set for quick lookup
    ALL = frozenset(
        [
            WHITESPACE,
            COMMENT,
            INDENT,
            DEDENT,
            NEWLINE,
            DATA,
            LET,
            IN,
            CASE,
            OF,
            FORALL,
            TYPE,
            ARROW,
            DARROW,
            LAMBDA,
            TYPELAMBDA,
            EQUALS,
            COLON,
            BAR,
            AT,
            DOT,
            LPAREN,
            RPAREN,
            LBRACKET,
            RBRACKET,
            LBRACE,
            RBRACE,
            COMMA,
            CONSTRUCTOR,
            IDENT,
            NUMBER,
            EOF,
        ]
    )

    # Tokens that are skipped in normal output (whitespace, comments)
    SKIPPABLE = frozenset([WHITESPACE, COMMENT])

    # Indentation-related tokens
    INDENTATION = frozenset([INDENT, DEDENT, NEWLINE])

    # Keywords for syntax highlighting or validation
    KEYWORDS = frozenset([DATA, LET, IN, CASE, OF, FORALL, TYPE])


# Type alias for token type strings
TokenTypeStr = str
