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

from dataclasses import dataclass, field
from parsy import Parser as P, Result, generate

from systemf.surface.parser.types import (
    TokenBase,
    KeywordToken,
    OperatorToken,
    DelimiterToken,
    IdentifierToken,
    ConstructorToken,
    DocstringToken,
    PragmaToken,
    DocstringType,
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
)

# Import expression parser for term declaration bodies
from systemf.surface.parser.expressions import expr_parser as _expr_parser_factory
from systemf.surface.parser.helpers import AnyIndent, AtPos, AfterPos, ValidIndent, column


@dataclass(kw_only=True)
class _ParserState:
    """Immutable state container for the top-level declaration parser.

    This dataclass encapsulates the state that changes during parsing,
    making the state transitions explicit and easier to reason about.
    """

    declarations: list[SurfaceDeclaration] = field(default_factory=list)
    current_docstrings: list[str] = field(default_factory=list)
    current_pragmas: dict[str, str] = field(default_factory=dict)

    def with_docstring(self, content: str) -> _ParserState:
        """Return new state with docstring added."""
        return _ParserState(
            declarations=self.declarations,
            current_docstrings=[*self.current_docstrings, content],
            current_pragmas=self.current_pragmas,
        )

    def with_pragma(self, key: str, value: str) -> _ParserState:
        """Return new state with pragma added."""
        new_pragmas = dict(self.current_pragmas)
        new_pragmas[key] = value
        return _ParserState(
            declarations=self.declarations,
            current_docstrings=self.current_docstrings,
            current_pragmas=new_pragmas,
        )

    def with_declaration(self, decl: SurfaceDeclaration) -> _ParserState:
        """Return new state with declaration added and accumulators reset."""
        return _ParserState(
            declarations=[*self.declarations, decl], current_docstrings=[], current_pragmas={}
        )

    def get_docstring(self) -> str | None:
        """Get concatenated docstring or None if empty."""
        if not self.current_docstrings:
            return None
        return " ".join(self.current_docstrings)

    def get_pragmas(self) -> dict[str, str] | None:
        """Get pragmas dict or None if empty."""
        if not self.current_pragmas:
            return None
        return dict(self.current_pragmas)


def skip_inline_docstrings() -> P[None]:
    """Skip any inline docstring tokens (-- ^).

    Returns:
        Parser that consumes and ignores inline docstrings
    """

    @P
    def parser(tokens: list, index: int) -> Result:
        i = index
        while i < len(tokens):
            token = tokens[i]
            if isinstance(token, DocstringToken) and token.docstring_type == DocstringType.INLINE:
                i += 1
            else:
                break
        return Result.success(i, None)

    return parser


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
# Type Parser (imported from type_parser module)
# =============================================================================

# Type parsers are imported from type_parser module:
# - type_atom_parser: parses atomic types
# - type_parser: main type parser for types and arrows


# =============================================================================
# Constructor Parser (for data declarations)
# =============================================================================


def constr_parser() -> P[SurfaceConstructorInfo]:
    """Parse a data constructor: CONSTRUCTOR [type_atom*].

    Returns:
        SurfaceConstructorInfo with constructor name and type arguments
    """

    @P
    def parser(tokens: list, index: int) -> Result:
        i = index

        # Skip any inline docstrings before constructor name
        skip_result = skip_inline_docstrings()(tokens, i)
        if skip_result.status:
            i = skip_result.index

        # Match constructor name
        con_result = match_constructor()(tokens, i)
        if not con_result.status:
            return con_result
        con_token = con_result.value
        name = con_token.value
        loc = con_token.location
        i = con_result.index

        # Parse type arguments greedily until no more type atoms
        # The topDecl parser sets boundaries, so we parse until the type atom parser fails
        # But stop if we see a BAR (constructor separator) - that's not a type argument
        # Also stop if we see what looks like a term declaration (identifier followed by :)
        args: list[SurfaceType] = []
        while i < len(tokens):
            # Stop at constructor separator (|)
            if isinstance(tokens[i], OperatorToken) and tokens[i].operator == "|":
                break

            # Stop if this looks like a term declaration (identifier : type)
            # This prevents consuming identifiers that are actually function names
            if isinstance(tokens[i], IdentifierToken):
                # Check if next token is a colon - if so, this is likely a term declaration
                if i + 1 < len(tokens):
                    next_token = tokens[i + 1]
                    if isinstance(next_token, OperatorToken) and next_token.operator == ":":
                        break

            # Try to parse a type atom
            arg_result = type_atom_parser()(tokens, i)
            if not arg_result.status:
                break
            # Make sure we actually advanced
            if arg_result.index <= i:
                break
            args.append(arg_result.value)
            i = arg_result.index

        return Result.success(
            i, SurfaceConstructorInfo(name=name, args=args, docstring=None, location=loc)
        )

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
    def parser():
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

        # Skip any inline docstrings before first constructor
        yield skip_inline_docstrings()

        # Parse first constructor
        first_constr = yield constr_parser()

        # Parse additional constructors separated by "|"
        rest_constrs: list[SurfaceConstructorInfo] = []
        while True:
            # Skip any inline docstrings
            yield skip_inline_docstrings()

            # Try to match "|"
            pipe = yield (match_symbol("|")).optional()
            if pipe is None:
                break

            # Skip any inline docstrings after "|"
            yield skip_inline_docstrings()

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

    return parser


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

        # Parse type
        ty = yield type_parser()

        # Match "=" for definition
        yield match_symbol("=")

        # Capture column of first body token for layout constraint
        # Multi-line bodies should stop when we see a token at/before this column
        body_col = yield column()
        body_constraint = AfterPos(col=body_col - 1)

        # Parse expression body with layout constraint
        body = yield _expr_parser_factory(body_constraint)

        return SurfaceTermDeclaration(
            name=name,
            type_annotation=ty,
            body=body,
            location=loc,
            docstring=None,
            pragma=None,
        )

    return parser


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

    return parser


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

        # Parse type
        ty = yield type_parser()

        return SurfacePrimOpDecl(
            name=name,
            type_annotation=ty,
            location=loc,
            docstring=None,
            pragma=None,
        )

    return parser


# =============================================================================
# Main Declaration Entry Point
# =============================================================================


def decl_parser() -> P[SurfaceDeclaration]:
    """Main declaration parser - tries all declaration types with metadata.

    Tries in order:
    1. Data declaration
    2. Term declaration
    3. Primitive type declaration
    4. Primitive operation declaration

    Handles docstrings (-- |) and pragmas ({-# ... #-}) that appear before
    the declaration.

    Returns:
        The parsed declaration with docstring and pragma metadata attached
    """

    # Use top_decl_parser which handles metadata accumulation
    # and return just the first declaration
    @P
    def parser(tokens: list, index: int) -> Result:
        result = top_decl_parser()(tokens, index)
        if result.status:
            declarations = result.value
            if declarations:
                return Result.success(result.index, declarations[0])
            return Result.failure(index, "expected at least one declaration")
        return Result.failure(index, result.expected)

    return parser


# =============================================================================
# Multiple Declarations Parser with Metadata
# =============================================================================


def _try_parse_declaration(
    token: TokenBase,
    tokens: list,
    i: int,
    data_p: P[SurfaceDataDeclaration],
    prim_type_p: P[SurfacePrimTypeDecl],
    prim_op_p: P[SurfacePrimOpDecl],
    term_p: P[SurfaceTermDeclaration],
) -> tuple[bool, SurfaceDeclaration | None, str | None, int]:
    """Try to parse a declaration starting at the given token.

    Returns:
        Tuple of (can_start_decl, decl_result, decl_type, new_index)
        - can_start_decl: whether this token type can start a declaration
        - decl_result: the parsed declaration or None
        - decl_type: the type of declaration ("data", "term", etc.) or None
        - new_index: the index after parsing, or current index if failed
    """
    match token:
        case KeywordToken(keyword="data"):
            result = data_p(tokens, i)
            if result.status:
                return (True, result.value, "data", result.index)
            return (True, None, None, i)
        case KeywordToken(keyword="prim_type"):
            result = prim_type_p(tokens, i)
            if result.status:
                return (True, result.value, "prim_type", result.index)
            return (True, None, None, i)
        case KeywordToken(keyword="prim_op"):
            result = prim_op_p(tokens, i)
            if result.status:
                return (True, result.value, "prim_op", result.index)
            return (True, None, None, i)
        case IdentifierToken():
            result = term_p(tokens, i)
            if result.status:
                return (True, result.value, "term", result.index)
            return (True, None, None, i)
        case _:
            return (False, None, None, i)


def _attach_metadata(
    decl: SurfaceDeclaration,
    decl_type: str,
    state: _ParserState,
) -> SurfaceDeclaration:
    """Attach accumulated docstrings and pragmas to a declaration."""
    docstring = state.get_docstring()
    pragmas = state.get_pragmas()

    match decl_type:
        case "data":
            return SurfaceDataDeclaration(
                name=decl.name,
                params=decl.params,
                constructors=decl.constructors,
                location=decl.location,
                docstring=docstring,
                pragma=pragmas,
            )
        case "term":
            return SurfaceTermDeclaration(
                name=decl.name,
                type_annotation=decl.type_annotation,
                body=decl.body,
                location=decl.location,
                docstring=docstring,
                pragma=pragmas,
            )
        case "prim_type":
            return SurfacePrimTypeDecl(
                name=decl.name,
                location=decl.location,
                docstring=docstring,
                pragma=pragmas,
            )
        case "prim_op":
            return SurfacePrimOpDecl(
                name=decl.name,
                type_annotation=decl.type_annotation,
                location=decl.location,
                docstring=docstring,
                pragma=pragmas,
            )
        case _:
            return decl


def top_decl_parser() -> P[list[SurfaceDeclaration]]:
    """Parse multiple declarations with docstring/pragma accumulation.

    This is a two-pass design:
    - Pass 1: Accumulate docstrings (-- |) and pragmas ({-# ... #-}) before each declaration
    - Pass 2: On declaration token, parse declaration and attach accumulated metadata

    Docstring concatenation rules:
    - Multiple -- | lines → concatenate with single space
    - Empty -- | → empty string ""
    - No docstrings → docstring=None

    Pragma format:
    - {-# KEY content #-} → {"KEY": "content"}
    - Multiple pragmas are merged into a single dict

    Returns:
        List of parsed declarations with metadata attached
    """

    @P
    def parser(tokens: list, index: int) -> Result:
        state = _ParserState()
        i = index

        # Inner parsers
        data_p = data_parser()
        prim_type_p = prim_type_parser()
        prim_op_p = prim_op_parser()
        term_p = term_parser()

        while i < len(tokens):
            token = tokens[i]

            # Accumulate metadata (docstrings and pragmas) before declarations
            match token:
                case DocstringToken(docstring_type=DocstringType.PRECEDING):
                    state = state.with_docstring(token.content)
                    i += 1
                    continue
                case PragmaToken(key=key) if key:
                    state = state.with_pragma(key, token.value)
                    i += 1
                    continue

            # Try to parse a declaration
            can_start_decl, decl_result, decl_type, new_i = _try_parse_declaration(
                token, tokens, i, data_p, prim_type_p, prim_op_p, term_p
            )

            if decl_result is not None:
                # Attach accumulated metadata and update state
                updated_decl = _attach_metadata(decl_result, decl_type, state)
                state = state.with_declaration(updated_decl)
                i = new_i
            elif can_start_decl:
                # Token looked like it could start a declaration but parsing failed
                # This is an error - we expected a declaration but couldn't parse it
                return Result.failure(i, f"expected valid declaration starting with {token.type}")
            else:
                # Unknown token that doesn't start a declaration, skip it
                i += 1

        return Result.success(i, state.declarations)

    return parser


# =============================================================================
# Public API
# =============================================================================


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
    "top_decl_parser",
]
