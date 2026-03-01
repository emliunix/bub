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
    """Base class for keyword tokens (data, let, in, case, of, forall, type).

    Subclasses should override the type property.
    """

    keyword: str

    @property
    def value(self) -> str:
        return self.keyword

    @property
    def type(self) -> str:
        """Default implementation returns uppercase keyword."""
        return self.keyword.upper()

    def __str__(self) -> str:
        return f"{self.type}({self.value!r})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.value!r}, {self.location})"


# Specific keyword token classes


@dataclass(frozen=True)
class LambdaToken(TokenBase):
    """Lambda token (small lambda)."""

    symbol: str

    @property
    def type(self) -> str:
        return "LAMBDA"

    @property
    def value(self) -> str:
        return self.symbol


@dataclass(frozen=True)
class TypeLambdaToken(TokenBase):
    """Type lambda token (big lambda)."""

    symbol: str

    @property
    def type(self) -> str:
        return "TYPELAMBDA"

    @property
    def value(self) -> str:
        return self.symbol


@dataclass(frozen=True)
class DataToken(KeywordToken):
    """Data declaration keyword: data"""

    pass


@dataclass(frozen=True)
class LetToken(KeywordToken):
    """Let binding keyword: let"""

    pass


@dataclass(frozen=True)
class InToken(KeywordToken):
    """In keyword for let bindings"""

    pass


@dataclass(frozen=True)
class CaseToken(KeywordToken):
    """Case expression keyword: case"""

    pass


@dataclass(frozen=True)
class OfToken(KeywordToken):
    """Of keyword for case expressions"""

    pass


@dataclass(frozen=True)
class ForallToken(KeywordToken):
    """Forall keyword (universal quantifier)."""

    @property
    def type(self) -> str:
        return "FORALL"


@dataclass(frozen=True)
class TypeToken(KeywordToken):
    """Type declaration keyword: type"""

    pass


@dataclass(frozen=True)
class IfToken(KeywordToken):
    """If keyword: if"""

    pass


@dataclass(frozen=True)
class ThenToken(KeywordToken):
    """Then keyword: then"""

    pass


@dataclass(frozen=True)
class ElseToken(KeywordToken):
    """Else keyword: else"""

    pass


@dataclass(frozen=True)
class PrimTypeToken(KeywordToken):
    """Primitive type keyword: prim_type"""

    pass


@dataclass(frozen=True)
class PrimOpToken(KeywordToken):
    """Primitive operator keyword: prim_op"""

    pass


class OperatorType:
    """Operator types for OperatorToken.

    This class uses class attributes to define operator type constants
    for type safety and IDE support.
    """

    ARROW = "ARROW"  # ->
    DARROW = "DARROW"  # =>
    EQ = "EQ"  # ==
    NEQ = "NEQ"  # /=
    LT = "LT"  # <
    GT = "GT"  # >
    LE = "LE"  # <=
    GE = "GE"  # >=
    PLUS = "PLUS"  # +
    MINUS = "MINUS"  # -
    STAR = "STAR"  # *
    SLASH = "SLASH"  # /
    AND = "AND"  # &&
    OR = "OR"  # ||
    APPEND = "APPEND"  # ++
    EQUALS = "EQUALS"  # =
    COLON = "COLON"  # :
    BAR = "BAR"  # |
    AT = "AT"  # @
    DOT = "DOT"  # .
    LAMBDA = "LAMBDA"  # \ or λ
    TYPELAMBDA = "TYPELAMBDA"  # /\ or Λ

    ALL = frozenset(
        [
            ARROW,
            DARROW,
            EQ,
            NEQ,
            LT,
            GT,
            LE,
            GE,
            PLUS,
            MINUS,
            STAR,
            SLASH,
            AND,
            OR,
            APPEND,
            EQUALS,
            COLON,
            BAR,
            AT,
            DOT,
            LAMBDA,
            TYPELAMBDA,
        ]
    )


@dataclass(frozen=True)
class OperatorToken(TokenBase):
    """Operator token."""

    operator: str
    op_type: str  # One of OperatorType constants

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


class DelimiterType:
    """Delimiter types for DelimiterToken.

    This class uses class attributes to define delimiter type constants
    for type safety and IDE support.
    """

    LPAREN = "LPAREN"  # (
    RPAREN = "RPAREN"  # )
    LBRACKET = "LBRACKET"  # [
    RBRACKET = "RBRACKET"  # ]
    LBRACE = "LBRACE"  # {
    RBRACE = "RBRACE"  # }
    COMMA = "COMMA"  # ,

    ALL = frozenset([LPAREN, RPAREN, LBRACKET, RBRACKET, LBRACE, RBRACE, COMMA])


@dataclass(frozen=True)
class DelimiterToken(TokenBase):
    """Delimiter token (parentheses, brackets, braces, comma)."""

    delimiter: str
    delim_type: str  # One of DelimiterType constants

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
    "OperatorType",
    "DelimiterToken",
    "DelimiterType",
    "PragmaToken",
    "DocstringToken",
    "EOFToken",
    "LexerError",
    "TokenTypeStr",
]
