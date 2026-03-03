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
    ForallToken,
    DocstringToken,
    DocstringType,
)
from systemf.surface.types import (
    SurfaceType,
    SurfaceTypeConstructor,
    SurfaceTypeVar,
)

# Type variable for generic parsers
T = TypeVar("T")

# =============================================================================
# Token Matching Helpers
# =============================================================================


def match_token(token_type: str) -> P[TokenBase]:
    """Match a token of the given type by string (deprecated, use typed version).

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


def match_arrow() -> P[OperatorToken]:
    """Match an arrow token (-> or →).

    Returns:
        Parser that returns the matched arrow operator token
    """

    @P
    def parser(tokens: list, index: int) -> Result:
        if index >= len(tokens):
            return Result.failure(index, "expected arrow")
        token = tokens[index]
        if isinstance(token, OperatorToken) and token.op_type == "ARROW":
            return Result.success(index + 1, token)
        return Result.failure(index, f"expected arrow, got {token.type}")

    return parser


def match_forall() -> P[ForallToken]:
    """Match a forall token (forall keyword or ∀).

    Returns:
        Parser that returns the matched forall token
    """

    @P
    def parser(tokens: list, index: int) -> Result:
        if index >= len(tokens):
            return Result.failure(index, "expected forall")
        token = tokens[index]
        if isinstance(token, ForallToken):
            return Result.success(index + 1, token)
        return Result.failure(index, f"expected forall, got {token.type}")

    return parser


def match_inline_docstring() -> P[str | None]:
    """Match an inline docstring token (-- ^ doc).

    Returns:
        Parser that returns the docstring content or None
    """

    @P
    def parser(tokens: list, index: int) -> Result:
        if index >= len(tokens):
            return Result.success(index, None)
        token = tokens[index]
        if isinstance(token, DocstringToken) and token.docstring_type == DocstringType.INLINE:
            return Result.success(index + 1, token.content)
        return Result.success(index, None)

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

    return SurfaceTypeTuple(elements=elements, location=loc)


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

        # Try identifier (type constructor or type variable based on naming convention)
        ident_token = yield match_token("IDENT").optional()
        if ident_token is not None:
            from systemf.surface.types import SurfaceTypeConstructor, SurfaceTypeVar

            name = ident_token.value
            loc = ident_token.location
            # Uppercase names are type constructors, lowercase are type variables
            if name[0].isupper():
                return SurfaceTypeConstructor(name=name, args=[], location=loc)
            else:
                return SurfaceTypeVar(name=name, location=loc)

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
    from systemf.surface.types import SurfaceTypeConstructor

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

    # Build type constructor with arguments
    if not args:
        return first

    # The first element must be a type constructor name
    # We use SurfaceTypeConstructor to represent applied types like "List Int"
    match first:
        case SurfaceTypeConstructor(name=name, args=[], location=_):
            return SurfaceTypeConstructor(name=name, args=args, location=loc)
        case SurfaceTypeVar(name=name, location=_):
            # For type variables (like in higher-kinded contexts),
            # we still use constructor representation
            return SurfaceTypeConstructor(name=name, args=args, location=loc)
        case _:
            # Fallback: if first is already a constructor with args, append to it
            match first:
                case SurfaceTypeConstructor(name=name, args=existing_args, location=_):
                    return SurfaceTypeConstructor(
                        name=name, args=existing_args + args, location=loc
                    )
                case _:
                    # For other cases, try to extract name
                    return SurfaceTypeConstructor(name=str(first), args=args, location=loc)


@generate
def type_arrow_parser() -> P[SurfaceType]:
    """Parse a function type (with arrows).

    Grammar: type_app ("-- ^ doc" "->" type_arrow)?
    Right-associative: A -> B -> C = A -> (B -> C)

    Supports inline docstrings: String -- ^ Input text -> String

    Returns:
        SurfaceType - the parsed function type
    """
    from systemf.surface.types import SurfaceTypeArrow

    # Parse left side
    left = yield type_app_parser
    loc = left.location

    # Check for inline docstring before arrow
    param_doc = yield match_inline_docstring().optional()

    # Check for arrow (accepts both ASCII -> and Unicode →)
    arrow = yield match_arrow().optional()
    if arrow is None:
        return left

    # Parse right side (recursively for right-associativity)
    right = yield type_arrow_parser
    return SurfaceTypeArrow(arg=left, ret=right, param_doc=param_doc, location=loc)


@generate
def type_forall_parser() -> P[SurfaceType]:
    """Parse a universally quantified type.

    Grammar: forall ident+. type
    Example: forall a. a -> a

    Returns:
        SurfaceType - the parsed forall type
    """
    from systemf.surface.types import SurfaceTypeForall

    # Match forall keyword (forall or ∀)
    forall_token = yield match_forall()
    loc = forall_token.location

    # Parse one or more type variable names
    var_tokens = yield match_token("IDENT").at_least(1)

    # Match dot
    yield match_symbol(".")

    # Parse body type (use _type_parser to allow nested foralls)
    body = yield _type_parser

    # Build nested foralls from right to left
    result = body
    for var_token in reversed(var_tokens):
        result = SurfaceTypeForall(var=var_token.value, body=result, location=loc)

    return result


def _ensure_consumed(inner: P[T]) -> P[T]:
    """Wrap a parser to ensure all tokens are consumed.

    Returns an index pointing past the last token to satisfy parsy's eof check.
    """

    @P
    def parser(tokens: list, index: int) -> Result:
        result = inner(tokens, index)

        if not result.status:
            return result

        # Check that we've consumed all tokens
        if result.index != len(tokens):
            # There are unconsumed tokens - this is a parse error
            return Result.failure(result.index, "expected EOF")

        # Success - return index pointing to end of stream
        return Result.success(len(tokens), result.value)

    return parser


def type_parser() -> P[SurfaceType]:
    """Type parser - parses forall types and arrow types.

    This parser does NOT ensure all tokens are consumed - it's designed
    for use within other parsers. Entry points should use `<< eof` to
    ensure complete consumption.

    Returns:
        SurfaceType - the parsed type
    """
    return alt(
        type_forall_parser,
        type_arrow_parser,
    )


# Initialize the forward declaration with the actual parser
_type_parser.become(type_parser())


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
    # Main parser (internal use, no EOF handling)
    "type_parser",
]
