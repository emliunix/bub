"""Type definitions for surface language lexer.

Provides typed token classes for the indentation-aware lexer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from systemf.utils.location import Location


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
class IdentifierToken:
    """Identifier token (lowercase or underscore start)."""

    name: str
    location: Location

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
class ConstructorToken:
    """Constructor token (uppercase start)."""

    name: str
    location: Location

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
class NumberToken:
    """Numeric literal token."""

    number: str
    location: Location

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
class KeywordToken:
    """Keyword token (data, let, in, case, of, forall, type)."""

    keyword: str
    location: Location

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
class OperatorToken:
    """Operator token."""

    operator: str
    location: Location
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
class DelimiterToken:
    """Delimiter token (parentheses, brackets, braces, comma)."""

    delimiter: str
    location: Location
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
class IndentationToken:
    """Indentation token (INDENT or DEDENT)."""

    indent_type: str  # "INDENT" or "DEDENT"
    level: str  # The indentation level as a string
    location: Location

    @property
    def value(self) -> str:
        return self.level

    @property
    def type(self) -> str:
        return self.indent_type

    def __str__(self) -> str:
        return f"{self.type}({self.value!r})"

    def __repr__(self) -> str:
        return f"IndentationToken({self.value!r}, {self.location})"


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
class EOFToken:
    """End of file token."""

    location: Location

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
    LLM = "LLM"
    TOOL = "TOOL"

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
            LLM,
            TOOL,
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
            PRAGMA_START,
            PRAGMA_CONTENT,
            PRAGMA_END,
            DOCSTRING_PRECEDING,
            DOCSTRING_INLINE,
        ]
    )

    # Tokens that are skipped in normal output (whitespace, comments)
    SKIPPABLE = frozenset([WHITESPACE, COMMENT])

    # Indentation-related tokens
    INDENTATION = frozenset([INDENT, DEDENT, NEWLINE])

    # Keywords for syntax highlighting or validation
    KEYWORDS = frozenset([DATA, LET, IN, CASE, OF, FORALL, TYPE, LLM, TOOL])


# Type alias for token type strings
TokenTypeStr = str
