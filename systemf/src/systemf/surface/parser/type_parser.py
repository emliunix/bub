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

from typing import List, TypeVar

import parsy
from parsy import Parser, Result, alt, fail, generate

from systemf.surface.parser.helpers import match_token
from systemf.surface.parser.types import (
    ArrowToken,
    CommaToken,
    DelimiterToken,
    DocstringToken,
    DocstringType,
    DotToken,
    ForallToken,
    IdentifierToken,
    KeywordToken,
    LeftParenToken,
    OperatorToken,
    RightParenToken,
    TokenBase,
)
from systemf.surface.types import (
    SurfaceType,
    SurfaceTypeConstructor,
    SurfaceTypeVar,
)

# Type variable for generic parsers
T = TypeVar("T")
type P[T] = Parser[List[TokenBase], T]

# =============================================================================
# Token Matching Helpers
# =============================================================================


def match_forall() -> P[ForallToken]:
    """Match a forall token (forall keyword or ∀).

    Returns:
        Parser that returns the matched forall token
    """

    @Parser
    def parser(tokens: list, index: int) -> Result:
        if index >= len(tokens):
            return Result.failure(index, "expected forall")
        token = tokens[index]
        if isinstance(token, ForallToken):
            return Result.success(index + 1, token)
        return Result.failure(index, f"expected forall, got {str(token)}")

    return parser


def match_inline_docstring() -> P[str | None]:
    """Match an inline docstring token (-- ^ doc).

    Returns:
        Parser that returns the docstring content or None
    """

    @Parser
    def parser(tokens: list, index: int) -> Result:
        if index >= len(tokens):
            return Result.success(index, None)
        token = tokens[index]
        if isinstance(token, DocstringToken) and token.docstring_type == DocstringType.INLINE:
            return Result.success(index + 1, token.content)
        return Result.success(index, None)

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

    open_paren = yield match_token(LeftParenToken)
    loc = open_paren.location

    # Parse first element
    first = yield _type_parser
    elements = [first]

    # Parse comma-separated elements
    while True:
        yield match_token(CommaToken)
        elem = yield _type_parser
        elements.append(elem)

        # Check if we're at the closing paren
        close_paren = yield match_token(RightParenToken).optional()
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
        open_paren = yield match_token(LeftParenToken).optional()
        if open_paren is not None:
            inner = yield _type_parser
            yield match_token(RightParenToken)
            return inner

        # Try identifier (type constructor or type variable based on naming convention)
        ident_token = yield match_token(IdentifierToken).optional()
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
    arrow = yield match_token(ArrowToken).optional()
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
    var_tokens = yield match_token(IdentifierToken).at_least(1)

    # Match dot
    yield match_token(DotToken)

    # Parse body type (use _type_parser to allow nested foralls)
    body = yield _type_parser

    # Build nested foralls from right to left
    result = body
    for var_token in reversed(var_tokens):
        result = SurfaceTypeForall(var=var_token.value, body=result, location=loc)

    return result


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
    # Type parsers
    "type_atom_parser",
    "type_app_parser",
    "type_arrow_parser",
    "type_forall_parser",
    "type_tuple_parser",
    # Main parser (internal use, no EOF handling)
    "type_parser",
]
