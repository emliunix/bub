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

# Forward declaration for the type parser (circular dependency with expressions)
_type_parser: P[SurfaceType] = parsy.forward_declaration()

# Forward declaration for the expression parser (set externally)
_expr_parser: P[SurfaceTerm] | None = None


# =============================================================================
# Type Parser
# =============================================================================


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
    # Parse first type atom
    first = yield type_atom_parser()
    loc = first.location

    # Parse additional type atoms for application
    args: list[SurfaceType] = []
    while True:
        arg = yield type_atom_parser().optional()
        if arg is None:
            break
        args.append(arg)

    # Build left-associative application chain
    if not args:
        return first

    from systemf.surface.types import SurfaceTypeApp

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


def type_parser() -> P[SurfaceType]:
    """Main type parser - tries forall types and arrow types.

    Returns:
        SurfaceType - the parsed type
    """
    return alt(
        type_forall_parser,
        type_arrow_parser,
    )


# =============================================================================
# Constructor Parser (for data declarations)
# =============================================================================


@generate
def constr_parser() -> P[SurfaceConstructorInfo]:
    """Parse a data constructor: CONSTRUCTOR [type_atom*].

    Returns:
        SurfaceConstructorInfo with constructor name and type arguments
    """
    con_token = yield match_constructor()
    name = con_token.value
    loc = con_token.location

    # Parse type arguments greedily until no more type atoms
    args: list[SurfaceType] = []
    while _type_parser is not None:
        # Try to parse a type atom
        arg_result = yield _type_parser.optional()
        if arg_result is None:
            break
        args.append(arg_result)

    return SurfaceConstructorInfo(name=name, args=args, docstring=None, location=loc)


# =============================================================================
# Declaration Parsers
# =============================================================================


@generate
def data_parser() -> P[SurfaceDataDeclaration]:
    """Parse a data declaration: data CONSTRUCTOR [ident*] = constr ("|" constr)*.

    Grammar: data CONSTRUCTOR [ident*] = constr ("|" constr)*
    NOT layout-sensitive - constructors can be on any line

    Returns:
        SurfaceDataDeclaration with type name, parameters, and constructors
    """
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
    first_constr = yield constr_parser

    # Parse additional constructors separated by "|"
    rest_constrs: list[SurfaceConstructorInfo] = []
    while True:
        # Try to match "|"
        pipe = yield (match_symbol("|")).optional()
        if pipe is None:
            break

        # Parse next constructor
        constr = yield constr_parser
        rest_constrs.append(constr)

    constructors = [first_constr] + rest_constrs

    return SurfaceDataDeclaration(
        name=name,
        params=params,
        constructors=constructors,
        location=loc,
        docstring=None,
    )


@generate
def term_parser() -> P[SurfaceTermDeclaration]:
    """Parse a term declaration: ident : type = expr.

    Combines type signature AND definition.
    Example: add x y : Int = x + y

    Returns:
        SurfaceTermDeclaration with name, type annotation, and body
    """
    # Parse identifier name
    name_token = yield match_ident()
    name = name_token.value
    loc = name_token.location

    # Match ":" for type annotation
    yield match_symbol(":")

    # Parse type (requires type parser to be set)
    if _type_parser is None:
        raise RuntimeError("Type parser not set. Call set_type_parser() first.")
    ty = yield _type_parser

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


@generate
def prim_type_parser() -> P[SurfacePrimTypeDecl]:
    """Parse a primitive type declaration: prim_type CONSTRUCTOR.

    Returns:
        SurfacePrimTypeDecl with the primitive type name
    """
    # Match "prim_type" keyword
    prim_token = yield match_keyword("prim_type")
    loc = prim_token.location

    # Parse constructor name
    name_token = yield match_constructor()
    name = name_token.value

    return SurfacePrimTypeDecl(name=name, location=loc, docstring=None)


@generate
def prim_op_parser() -> P[SurfacePrimOpDecl]:
    """Parse a primitive operation declaration: prim_op ident : type.

    Returns:
        SurfacePrimOpDecl with name and type annotation
    """
    # Match "prim_op" keyword
    prim_token = yield match_keyword("prim_op")
    loc = prim_token.location

    # Parse identifier name
    name_token = yield match_ident()
    name = name_token.value

    # Match ":" for type annotation
    yield match_symbol(":")

    # Parse type (requires type parser to be set)
    if _type_parser is None:
        raise RuntimeError("Type parser not set. Call set_type_parser() first.")
    ty = yield _type_parser

    return SurfacePrimOpDecl(
        name=name,
        type_annotation=ty,
        location=loc,
        docstring=None,
        pragma=None,
    )


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
    return alt(
        data_parser,
        prim_type_parser,
        prim_op_parser,
        term_parser,
    )


# =============================================================================
# Public API
# =============================================================================


def set_type_parser(parser: P[SurfaceType]) -> None:
    """Set the type parser for type annotations.

    This should be called by the module that implements type parsing
    to allow mutual recursion between declaration and type parsers.

    Args:
        parser: The type parser to use
    """
    global _type_parser
    _type_parser = parser


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
    "set_type_parser",
    "set_expr_parser",
]
