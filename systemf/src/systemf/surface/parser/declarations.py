"""Declaration parsers for System F surface language.

Implements declaration parsers using the helper combinators.
Declarations are NOT layout-sensitive - they can appear at any column.

Parsers implemented:
- Data declarations: data CONSTRUCTOR [params] = constr ("|" constr)*
- Term declarations: ident : type = expr
- Primitive type declarations: prim_type CONSTRUCTOR
- Primitive operation declarations: prim_op ident : type
- Main declaration entry point
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
    SurfaceDeclaration,
    SurfaceDataDeclaration,
    SurfaceTermDeclaration,
    SurfacePrimTypeDecl,
    SurfacePrimOpDecl,
    SurfaceConstructorInfo,
    SurfaceType,
    SurfaceTerm,
)
from systemf.surface.parser.type_parser import (
    type_atom_parser,
    type_parser,
    _make_eof_compatible,
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


def match_ident() -> P[IdentifierToken]:
    """Match an identifier token.

    Returns:
        Parser that returns the matched identifier token
    """

    @P
    def parser(tokens: list, index: int) -> Result:
        if index >= len(tokens):
            return Result.failure(index, "expected identifier")
        token = tokens[index]
        if isinstance(token, IdentifierToken):
            return Result.success(index + 1, token)
        return Result.failure(index, f"expected identifier, got {token.type}")

    return parser


def match_constructor() -> P[ConstructorToken]:
    """Match a constructor token.

    Returns:
        Parser that returns the matched constructor token
    """

    @P
    def parser(tokens: list, index: int) -> Result:
        if index >= len(tokens):
            return Result.failure(index, "expected constructor")
        token = tokens[index]
        if isinstance(token, ConstructorToken):
            return Result.success(index + 1, token)
        return Result.failure(index, f"expected constructor, got {token.type}")

    return parser


# =============================================================================
# Forward Declarations for Recursive Parsers
# =============================================================================

# Forward declaration for the expression parser (set externally)
_expr_parser: P[SurfaceTerm] | None = None


# =============================================================================
# Type Parser (imported from type_parser module)
# =============================================================================

# Type parsers are imported from type_parser module:
# - type_atom_parser: parses atomic types
# - _raw_type_parser: raw type parser without EOF handling
# - type_parser: main type parser with EOF handling


# =============================================================================
# Constructor Parser (for data declarations)
# =============================================================================


def constr_parser() -> P[SurfaceConstructorInfo]:
    """Parse a data constructor: CONSTRUCTOR [type_atom*].

    Returns:
        SurfaceConstructorInfo with constructor name and type arguments
    """

    @generate
    def parser():
        con_token = yield match_constructor()
        name = con_token.value
        loc = con_token.location

        # Parse type arguments greedily until no more type atoms
        # Use type_atom_parser, not _type_parser, to avoid consuming too much
        # (e.g., "a = Nothing" where "=" should stop parsing)
        args: list[SurfaceType] = []
        while True:
            # Check if we're at EOF - if so, stop gracefully
            at_eof = yield parsy.peek(parsy.eof).optional()
            if at_eof is not None:
                break

            # Try to parse a type atom
            arg_result = yield type_atom_parser().optional()
            if arg_result is None:
                break
            args.append(arg_result)

        return SurfaceConstructorInfo(name=name, args=args, docstring=None, location=loc)

    return parser


# =============================================================================
# Declaration Parsers
# =============================================================================


def data_parser() -> P[SurfaceDataDeclaration]:
    """Parse a data declaration: data CONSTRUCTOR [ident*] = constr ("|" constr)*.

    Grammar: data CONSTRUCTOR [ident*] = constr ("|" constr)*
    NOT layout-sensitive - constructors can be on any line

    Returns:
        SurfaceDataDeclaration with type name, parameters, and constructors
    """

    @generate
    def inner():
        # Match "data" keyword
        data_token = yield match_keyword("data")
        loc = data_token.location

        # Parse type constructor name
        name_token = yield match_constructor()
        name = name_token.value

        # Parse optional type parameters (identifiers)
        params_tokens = yield match_ident().many()
        params = [t.value for t in params_tokens]

        # Match "=" symbol
        yield match_symbol("=")

        # Parse first constructor
        first_constr = yield constr_parser()

        # Parse additional constructors separated by "|"
        rest_constrs: list[SurfaceConstructorInfo] = []
        while True:
            # Try to match "|"
            pipe = yield (match_symbol("|")).optional()
            if pipe is None:
                break

            # Parse next constructor
            constr = yield constr_parser()
            rest_constrs.append(constr)

        constructors = [first_constr] + rest_constrs

        return SurfaceDataDeclaration(
            name=name,
            params=params,
            constructors=constructors,
            location=loc,
            docstring=None,
        )

    return _make_eof_compatible(inner)


def term_parser() -> P[SurfaceTermDeclaration]:
    """Parse a term declaration: ident : type = expr.

    Combines type signature AND definition.
    Example: add x y : Int = x + y

    Returns:
        SurfaceTermDeclaration with name, type annotation, and body
    """

    @generate
    def parser():
        # Parse identifier name
        name_token = yield match_ident()
        name = name_token.value
        loc = name_token.location

        # Match ":" for type annotation
        yield match_symbol(":")

        # Parse type (type_parser has no EOF handling, term_parser handles it)
        ty = yield type_parser()

        # Match "=" for definition
        yield match_symbol("=")

        # Parse expression body (requires expression parser to be set)
        if _expr_parser is None:
            raise RuntimeError("Expression parser not set. Call set_expr_parser() first.")
        body = yield _expr_parser

        return SurfaceTermDeclaration(
            name=name,
            type_annotation=ty,
            body=body,
            location=loc,
            docstring=None,
            pragma=None,
        )

    return _make_eof_compatible(parser)


def prim_type_parser() -> P[SurfacePrimTypeDecl]:
    """Parse a primitive type declaration: prim_type CONSTRUCTOR.

    Returns:
        SurfacePrimTypeDecl with the primitive type name
    """

    @generate
    def parser():
        # Match "prim_type" keyword
        prim_token = yield match_keyword("prim_type")
        loc = prim_token.location

        # Parse constructor name
        name_token = yield match_constructor()
        name = name_token.value

        return SurfacePrimTypeDecl(name=name, location=loc, docstring=None)

    return _make_eof_compatible(parser)


def prim_op_parser() -> P[SurfacePrimOpDecl]:
    """Parse a primitive operation declaration: prim_op ident : type.

    Returns:
        SurfacePrimOpDecl with name and type annotation
    """

    @generate
    def parser():
        # Match "prim_op" keyword
        prim_token = yield match_keyword("prim_op")
        loc = prim_token.location

        # Parse identifier name
        name_token = yield match_ident()
        name = name_token.value

        # Match ":" for type annotation
        yield match_symbol(":")

        # Parse type (type_parser has no EOF handling, prim_op_parser handles it)
        ty = yield type_parser()

        return SurfacePrimOpDecl(
            name=name,
            type_annotation=ty,
            location=loc,
            docstring=None,
            pragma=None,
        )

    return _make_eof_compatible(parser)


# =============================================================================
# Main Declaration Entry Point
# =============================================================================


def decl_parser() -> P[SurfaceDeclaration]:
    """Main declaration parser - tries all declaration types.

    Tries in order:
    1. Data declaration
    2. Term declaration
    3. Primitive type declaration
    4. Primitive operation declaration

    Returns:
        The parsed declaration
    """
    inner = alt(
        data_parser(),
        prim_type_parser(),
        prim_op_parser(),
        term_parser(),
    )
    return _make_eof_compatible(inner)


# =============================================================================
# Public API
# =============================================================================


def set_expr_parser(parser: P[SurfaceTerm]) -> None:
    """Set the expression parser for term bodies.

    This should be called by the module that implements expression parsing
    to allow term declarations to parse their right-hand sides.

    Args:
        parser: The expression parser to use
    """
    global _expr_parser
    _expr_parser = parser


__all__ = [
    # Token matching
    "match_token",
    "match_keyword",
    "match_symbol",
    "match_ident",
    "match_constructor",
    # Constructor parser
    "constr_parser",
    # Declaration parsers
    "data_parser",
    "term_parser",
    "prim_type_parser",
    "prim_op_parser",
    "decl_parser",
    # Parser setup
    "set_expr_parser",
]
