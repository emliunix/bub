"""Type parser for System F surface language.

Extracted from declarations.py to eliminate circular dependencies.
Types are parsed independently and have no dependencies on expressions.

Parsers implemented:
- Type atoms (variables, constructors, parenthesized types)
- Type applications (constructor applied to arguments)
- Function types (arrows)
- Universal quantification (forall)
- Tuple types
"""

from __future__ import annotations

from typing import TypeVar
import parsy
from parsy import Parser as P, Result, generate, alt, fail

from systemf.surface.parser.types import (
    TokenBase,
    KeywordToken,
    OperatorToken,
    DelimiterToken,
    IdentifierToken,
    ConstructorToken,
)
from systemf.surface.types import (
    SurfaceType,
)

# Type variable for generic parsers
T = TypeVar("T")

# =============================================================================
# Token Matching Helpers
# =============================================================================


def match_token(token_type: str) -> P[TokenBase]:
    """Match a token of the given type.

    Args:
        token_type: The token type to match (e.g., "IDENT", "NUMBER")

    Returns:
        Parser that returns the matched token
    """

    @P
    def parser(tokens: list, index: int) -> Result:
        if index >= len(tokens):
            return Result.failure(index, f"expected {token_type}")
        token = tokens[index]
        if token.type == token_type:
            return Result.success(index + 1, token)
        return Result.failure(index, f"expected {token_type}, got {token.type}")

    return parser


def match_keyword(value: str) -> P[KeywordToken]:
    """Match a keyword token with the given value.

    Args:
        value: The keyword to match (e.g., "data", "let")

    Returns:
        Parser that returns the matched keyword token
    """

    @P
    def parser(tokens: list, index: int) -> Result:
        if index >= len(tokens):
            return Result.failure(index, f"expected keyword '{value}'")
        token = tokens[index]
        if isinstance(token, KeywordToken) and token.keyword == value:
            return Result.success(index + 1, token)
        return Result.failure(index, f"expected keyword '{value}', got {token.type}")

    return parser


def match_symbol(value: str) -> P[OperatorToken | DelimiterToken]:
    """Match an operator or delimiter token with the given value.

    Args:
        value: The symbol to match (e.g., "=", "|", ":")

    Returns:
        Parser that returns the matched operator/delimiter token
    """

    @P
    def parser(tokens: list, index: int) -> Result:
        if index >= len(tokens):
            return Result.failure(index, f"expected symbol '{value}'")
        token = tokens[index]
        if isinstance(token, OperatorToken) and token.operator == value:
            return Result.success(index + 1, token)
        if isinstance(token, DelimiterToken) and token.delimiter == value:
            return Result.success(index + 1, token)
        return Result.failure(index, f"expected symbol '{value}'")

    return parser


# =============================================================================
# Forward Declaration for Recursive Type Parser
# =============================================================================

_type_parser: P[SurfaceType] = parsy.forward_declaration()


# =============================================================================
# Type Parsers
# =============================================================================


@generate
def type_tuple_parser() -> P[SurfaceType]:
    """Parse a tuple type: (t1, t2, ..., tn).

    Sugar for nested Pair types: Pair t1 (Pair t2 (... tn))

    Returns:
        SurfaceTypeTuple containing the elements
    """
    from systemf.surface.types import SurfaceTypeTuple

    open_paren = yield match_symbol("(")
    loc = open_paren.location

    # Parse first element
    first = yield _type_parser
    elements = [first]

    # Parse comma-separated elements
    while True:
        yield match_symbol(",")
        elem = yield _type_parser
        elements.append(elem)

        # Check if we're at the closing paren
        close_paren = yield match_symbol(")").optional()
        if close_paren is not None:
            break

    return SurfaceTypeTuple(elements, loc)


def type_atom_parser() -> P[SurfaceType]:
    """Parse a type atom (base type without arrows).

    Tries in order:
    1. Type variable (identifier)
    2. Type constructor
    3. Parenthesized type

    Returns:
        SurfaceType - the parsed atomic type
    """

    @generate
    def parser():
        # Try parenthesized type first
        open_paren = yield match_symbol("(").optional()
        if open_paren is not None:
            inner = yield _type_parser
            yield match_symbol(")")
            return inner

        # Try type constructor
        con_token = yield match_token("CONSTRUCTOR").optional()
        if con_token is not None:
            from systemf.surface.types import SurfaceTypeConstructor

            return SurfaceTypeConstructor(con_token.value, [], con_token.location)

        # Try type variable
        var_token = yield match_token("IDENT").optional()
        if var_token is not None:
            from systemf.surface.types import SurfaceTypeVar

            return SurfaceTypeVar(var_token.value, var_token.location)

        # No match - return None (will be handled by optional)
        return None

    return parser


@generate
def type_app_parser() -> P[SurfaceType]:
    """Parse a type application (constructor applied to arguments).

    Example: List Int, Maybe a

    Returns:
        SurfaceType - the parsed type application or atomic type
    """
    from systemf.surface.types import SurfaceTypeApp

    # Try tuple first (it starts with '('), then regular atom
    tuple_result = yield type_tuple_parser.optional()
    if tuple_result is not None:
        return tuple_result

    # Parse first type atom (constructor or variable)
    first = yield type_atom_parser()
    if first is None:
        yield fail("expected type")
        return None  # Unreachable, but satisfies type checker

    loc = first.location

    # Parse additional type atoms for application
    # Stop if we reach EOF or a token that can't start a type atom
    args: list[SurfaceType] = []
    while True:
        # Check if we're at EOF - if so, stop gracefully
        at_eof = yield parsy.peek(parsy.eof).optional()
        if at_eof is not None:
            break

        # Try to parse a type atom
        arg = yield type_atom_parser().optional()
        if arg is None:
            break
        args.append(arg)

    # Build left-associative application chain
    if not args:
        return first

    result = first
    for arg in args:
        result = SurfaceTypeApp(result, arg, loc)

    return result


@generate
def type_arrow_parser() -> P[SurfaceType]:
    """Parse a function type (with arrows).

    Grammar: type_app ("->" type_arrow)?
    Right-associative: A -> B -> C = A -> (B -> C)

    Returns:
        SurfaceType - the parsed function type
    """
    from systemf.surface.types import SurfaceTypeArrow

    # Parse left side
    left = yield type_app_parser
    loc = left.location

    # Check for arrow
    arrow = yield match_symbol("->").optional()
    if arrow is None:
        return left

    # Parse right side (recursively for right-associativity)
    right = yield type_arrow_parser
    return SurfaceTypeArrow(left, right, loc)


@generate
def type_forall_parser() -> P[SurfaceType]:
    """Parse a universally quantified type.

    Grammar: forall ident+. type
    Example: forall a. a -> a

    Returns:
        SurfaceType - the parsed forall type
    """
    from systemf.surface.types import SurfaceTypeForall

    # Match "forall" keyword
    forall_token = yield match_keyword("forall")
    loc = forall_token.location

    # Parse one or more type variable names
    var_tokens = yield match_token("IDENT").at_least(1)

    # Match dot
    yield match_symbol(".")

    # Parse body type
    body = yield type_arrow_parser

    # Build nested foralls from right to left
    result = body
    for var_token in reversed(var_tokens):
        result = SurfaceTypeForall(var_token.value, result, loc)

    return result


def _make_eof_compatible(inner: P[T]) -> P[T]:
    """Wrap a parser to handle EOF token from lex().

    Tests use lex() directly which includes EOF token, but the internal
    parsers don't expect it. This wrapper strips EOF before parsing and
    returns an index pointing past the EOF token to satisfy parsy's eof check.
    """

    @P
    def parser(tokens: list, index: int) -> Result:
        # Filter out EOF tokens for parsing
        filtered = [t for t in tokens if getattr(t, "type", None) != "EOF"]
        result = inner(filtered, index)

        if not result.status:
            return result

        # Check that we've consumed all non-EOF tokens
        if result.index != len(filtered):
            # There are unconsumed tokens - this is a parse error
            return Result.failure(result.index, "expected EOF")

        # Success - return index pointing to end of original stream
        # This satisfies parsy's eof check which expects to be at the end
        return Result.success(len(tokens), result.value)

    return parser


def _raw_type_parser() -> P[SurfaceType]:
    """Raw type parser without EOF handling - for internal use.

    Returns:
        SurfaceType - the parsed type
    """
    return alt(
        type_forall_parser,
        type_arrow_parser,
    )


def type_parser() -> P[SurfaceType]:
    """Main type parser - tries forall types and arrow types.

    This is the public entry point that handles EOF tokens from lex().

    Returns:
        SurfaceType - the parsed type
    """
    return _make_eof_compatible(_raw_type_parser())


# Initialize the forward declaration with the actual parser
_type_parser.become(_raw_type_parser())


__all__ = [
    # Token matching helpers
    "match_token",
    "match_keyword",
    "match_symbol",
    # Type parsers
    "type_atom_parser",
    "type_app_parser",
    "type_arrow_parser",
    "type_forall_parser",
    "type_tuple_parser",
    # Main entry points
    "type_parser",
    "_raw_type_parser",
]
