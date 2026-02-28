"""Parser types for System F surface language.

This module contains all types used by the parser including:
- Layout constraint types
- Token types
- Lexer-related types
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from systemf.utils.location import Location


# =============================================================================
# Layout Constraint Types
# =============================================================================


@dataclass(frozen=True)
class AnyIndent:
    """Inside braces, no column checking.

    Used when parsing explicit brace-delimited blocks like:
    { item1; item2; item3 }
    """

    pass


@dataclass(frozen=True)
class AtPos:
    """Must be at exact column.

    Used for layout mode where all items must align:
      item1
      item2  <- must be at same column as item1
    """

    col: int


@dataclass(frozen=True)
class AfterPos:
    """At or after column.

    Used when items must be indented past a minimum:
      parent
        child1  <- must be at col >= parent's col
        child2
    """

    col: int


@dataclass(frozen=True)
class EndOfBlock:
    """Block has ended.

    Returned by terminator when block should close.
    Any check against EndOfBlock fails.
    """

    pass


# Union type for all layout constraints
ValidIndent = AnyIndent | AtPos | AfterPos | EndOfBlock


# =============================================================================
# Token Types
# =============================================================================


class Token(Protocol):
    """Protocol for all tokens.

    All token types implement this protocol with type and value properties
    for pattern matching compatibility.
    """

    @property
    def type(self) -> str:
        """Get the token type identifier."""
        ...

    @property
    def value(self) -> str:
        """Get the token value as a string."""
        ...

    @property
    def location(self) -> Location:
        """Get the source location of this token."""
        ...


@dataclass(frozen=True)
class TokenBase:
    """Base class for all tokens with location information.

    All concrete token types should inherit from this class to ensure
    consistent location tracking.
    """

    location: Location

    @property
    def column(self) -> int:
        """Get the column number of this token."""
        return self.location.column

    @property
    def line(self) -> int:
        """Get the line number of this token."""
        return self.location.line


@dataclass(frozen=True)
class IdentifierToken(TokenBase):
    """Identifier token (lowercase or underscore start)."""

    name: str

    @property
    def value(self) -> str:
        return self.name

    @property
    def type(self) -> str:
        return "IDENT"

    def __str__(self) -> str:
        return f"{self.type}({self.value!r})"

    def __repr__(self) -> str:
        return f"IdentifierToken({self.value!r}, {self.location})"


@dataclass(frozen=True)
class ConstructorToken(TokenBase):
    """Constructor token (uppercase start)."""

    name: str

    @property
    def value(self) -> str:
        return self.name

    @property
    def type(self) -> str:
        return "CONSTRUCTOR"

    def __str__(self) -> str:
        return f"{self.type}({self.value!r})"

    def __repr__(self) -> str:
        return f"ConstructorToken({self.value!r}, {self.location})"


@dataclass(frozen=True)
class NumberToken(TokenBase):
    """Numeric literal token."""

    number: str

    @property
    def value(self) -> str:
        return self.number

    @property
    def type(self) -> str:
        return "NUMBER"

    def __str__(self) -> str:
        return f"{self.type}({self.value!r})"

    def __repr__(self) -> str:
        return f"NumberToken({self.value!r}, {self.location})"


@dataclass(frozen=True)
class StringToken(TokenBase):
    """String literal token."""

    string: str

    @property
    def value(self) -> str:
        return self.string

    @property
    def type(self) -> str:
        return "STRING"

    def __str__(self) -> str:
        return f"{self.type}({self.value!r})"

    def __repr__(self) -> str:
        return f"StringToken({self.value!r}, {self.location})"


@dataclass(frozen=True)
class KeywordToken(TokenBase):
    """Keyword token (data, let, in, case, of, forall, type)."""

    keyword: str

    @property
    def value(self) -> str:
        return self.keyword

    @property
    def type(self) -> str:
        return self.keyword.upper()

    def __str__(self) -> str:
        return f"{self.type}({self.value!r})"

    def __repr__(self) -> str:
        return f"KeywordToken({self.value!r}, {self.location})"


@dataclass(frozen=True)
class OperatorToken(TokenBase):
    """Operator token."""

    operator: str
    op_type: str  # The token type name (ARROW, EQUALS, etc.)

    @property
    def value(self) -> str:
        return self.operator

    @property
    def type(self) -> str:
        return self.op_type

    def __str__(self) -> str:
        return f"{self.type}({self.value!r})"

    def __repr__(self) -> str:
        return f"OperatorToken({self.value!r}, {self.location})"


@dataclass(frozen=True)
class DelimiterToken(TokenBase):
    """Delimiter token (parentheses, brackets, braces, comma)."""

    delimiter: str
    delim_type: str  # The token type name (LPAREN, RPAREN, etc.)

    @property
    def value(self) -> str:
        return self.delimiter

    @property
    def type(self) -> str:
        return self.delim_type

    def __str__(self) -> str:
        return f"{self.type}({self.value!r})"

    def __repr__(self) -> str:
        return f"DelimiterToken({self.value!r}, {self.location})"


@dataclass(frozen=True)
class PragmaToken:
    """Pragma token (START, CONTENT, or END)."""

    pragma_type: str  # "PRAGMA_START", "PRAGMA_CONTENT", or "PRAGMA_END"
    content: str
    location: Location

    @property
    def value(self) -> str:
        return self.content

    @property
    def type(self) -> str:
        return self.pragma_type

    def __str__(self) -> str:
        return f"{self.type}({self.value!r})"

    def __repr__(self) -> str:
        return f"PragmaToken({self.value!r}, {self.location})"


@dataclass(frozen=True)
class DocstringToken:
    """Docstring token (-- | or -- ^)."""

    docstring_type: str  # "DOCSTRING_PRECEDING" or "DOCSTRING_INLINE"
    content: str
    location: Location

    @property
    def value(self) -> str:
        return self.content

    @property
    def type(self) -> str:
        return self.docstring_type

    def __str__(self) -> str:
        return f"{self.type}({self.value!r})"

    def __repr__(self) -> str:
        return f"DocstringToken({self.value!r}, {self.location})"


@dataclass(frozen=True)
class EOFToken(TokenBase):
    """End of file token."""

    @property
    def value(self) -> str:
        return ""

    @property
    def type(self) -> str:
        return "EOF"

    def __str__(self) -> str:
        return f"{self.type}({self.value!r})"

    def __repr__(self) -> str:
        return f"EOFToken({self.location})"


class LexerError(Exception):
    """Error during lexical analysis."""

    def __init__(self, message: str, location: Location):
        super().__init__(f"{location}: {message}")
        self.location = location


class TokenType:
    """Token types for the System F surface language lexer.

    This class uses class attributes instead of Enum for string compatibility
    with the existing parser which expects token types as strings.
    """

    # Whitespace and comments (skipped during normal tokenization)
    WHITESPACE = "WHITESPACE"
    COMMENT = "COMMENT"

    # Keywords
    DATA = "DATA"
    LET = "LET"
    IN = "IN"
    CASE = "CASE"
    OF = "OF"
    FORALL = "FORALL"
    TYPE = "TYPE"
    IF = "IF"
    THEN = "THEN"
    ELSE = "ELSE"
    PRIM_TYPE = "PRIM_TYPE"
    PRIM_OP = "PRIM_OP"

    # Multi-character operators
    ARROW = "ARROW"  # ->
    DARROW = "DARROW"  # =>
    LAMBDA = "LAMBDA"  # \
    TYPELAMBDA = "TYPELAMBDA"  # /\

    # Arithmetic operators
    PLUS = "PLUS"  # +
    MINUS = "MINUS"  # -
    STAR = "STAR"  # *
    SLASH = "SLASH"  # /

    # Comparison operators
    EQ = "EQ"  # ==
    NEQ = "NEQ"  # /=
    LT = "LT"  # <
    GT = "GT"  # >
    LE = "LE"  # <=
    GE = "GE"  # >=

    # Logical operators
    AND = "AND"  # &&
    OR = "OR"  # ||

    # String operators
    APPEND = "APPEND"  # ++

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
    STRING = "STRING"  # String literals

    # End of file
    EOF = "EOF"

    # Pragma tokens
    PRAGMA_START = "PRAGMA_START"
    PRAGMA_CONTENT = "PRAGMA_CONTENT"
    PRAGMA_END = "PRAGMA_END"

    # Docstring tokens
    DOCSTRING_PRECEDING = "DOCSTRING_PRECEDING"
    DOCSTRING_INLINE = "DOCSTRING_INLINE"

    # All token types as a set for quick lookup
    ALL = frozenset(
        [
            WHITESPACE,
            COMMENT,
            DATA,
            LET,
            IN,
            CASE,
            OF,
            FORALL,
            TYPE,
            IF,
            THEN,
            ELSE,
            PRIM_TYPE,
            PRIM_OP,
            ARROW,
            DARROW,
            LAMBDA,
            TYPELAMBDA,
            PLUS,
            MINUS,
            STAR,
            SLASH,
            EQ,
            NEQ,
            LT,
            GT,
            LE,
            GE,
            AND,
            OR,
            APPEND,
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
            STRING,
            EOF,
            PRAGMA_START,
            PRAGMA_CONTENT,
            PRAGMA_END,
            DOCSTRING_PRECEDING,
            DOCSTRING_INLINE,
        ]
    )

    # Tokens that are skipped in normal output (whitespace, comments)
    SKIPPABLE = frozenset([WHITESPACE, COMMENT])

    # Keywords for syntax highlighting or validation
    KEYWORDS = frozenset(
        [DATA, LET, IN, CASE, OF, FORALL, TYPE, IF, THEN, ELSE, PRIM_TYPE, PRIM_OP]
    )


# Type alias for token type strings
TokenTypeStr = str


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Layout constraints
    "AnyIndent",
    "AtPos",
    "AfterPos",
    "EndOfBlock",
    "ValidIndent",
    # Token types
    "Token",
    "TokenBase",
    "IdentifierToken",
    "ConstructorToken",
    "NumberToken",
    "StringToken",
    "KeywordToken",
    "OperatorToken",
    "DelimiterToken",
    "PragmaToken",
    "DocstringToken",
    "EOFToken",
    "LexerError",
    "TokenType",
    "TokenTypeStr",
]
