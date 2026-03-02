"""System F surface language parser package.

Layout-sensitive parser following Idris2's approach with explicit
constraint passing.

Modules:
- types: Token types and layout constraint types (ValidIndent, TokenBase, etc.)
- lexer: Lexer and tokenizer (lex, Lexer)
- helpers: Parser combinators (block, terminator, etc.)
- declarations: Declaration parsers (data, let, etc.) and type parser
- expressions: Expression parsers (case, lambda, etc.)
"""

from __future__ import annotations

from parsy import eof

# Re-export token types and layout constraints
from systemf.surface.parser.types import (
    TokenBase,
    ValidIndent,
    AnyIndent,
    AtPos,
    AfterPos,
    EndOfBlock,
    Location,
    Token,
    IdentifierToken,
    ConstructorToken,
    NumberToken,
    StringToken,
    KeywordToken,
    LambdaToken,
    TypeLambdaToken,
    DataToken,
    LetToken,
    InToken,
    CaseToken,
    OfToken,
    ForallToken,
    TypeToken,
    IfToken,
    ThenToken,
    ElseToken,
    PrimTypeToken,
    PrimOpToken,
    OperatorToken,
    OperatorType,
    DelimiterToken,
    DelimiterType,
    PragmaToken,
    DocstringToken,
    EOFToken,
    LexerError,
)

# Re-export lexer
from systemf.surface.parser.lexer import Lexer, lex

# Re-export helpers
from systemf.surface.parser.helpers import (
    column,
    check_valid,
    block,
    block_entries,
    terminator,
    must_continue,
)

# Import expression and declaration modules
from systemf.surface.parser import expressions, declarations

# Re-export expression parsers
from systemf.surface.parser.expressions import (
    expr_parser,
    atom_parser,
    app_parser,
    lambda_parser,
    type_abs_parser,
    case_parser,
    let_parser,
    if_parser,
    pattern_parser,
    case_alt,
    let_binding,
    match_token,
    match_keyword,
    match_symbol,
    variable_parser,
    constructor_parser,
    literal_parser,
    paren_parser,
    atom_base_parser,
)

# Re-export declaration parsers
from systemf.surface.parser.declarations import (
    decl_parser,
    top_decl_parser,
    data_parser,
    term_parser,
    prim_type_parser,
    prim_op_parser,
    constr_parser,
    match_ident,
    match_constructor,
)

# Re-export type parser
from systemf.surface.parser.type_parser import type_parser


# Convenience function for parsing expressions
def parse_expression(source: str):
    """Parse an expression from source code.

    Args:
        source: The source code string to parse

    Returns:
        The parsed surface term

    Raises:
        ParseError: If parsing fails
    """
    tokens = list(lex(source))
    return (expressions.expr_parser(AnyIndent()) << eof).parse(tokens)


def parse_declaration(source: str):
    """Parse a declaration from source code.

    Args:
        source: The source code string to parse

    Returns:
        The parsed surface declaration

    Raises:
        ParseError: If parsing fails
    """
    tokens = list(lex(source))
    return (declarations.decl_parser() << eof).parse(tokens)


def parse_type(source: str):
    """Parse a type from source code.

    Args:
        source: The source code string to parse

    Returns:
        The parsed surface type

    Raises:
        ParseError: If parsing fails
    """
    tokens = list(lex(source))
    return (type_parser() << eof).parse(tokens)


def parse_program(source: str, filename: str = "<stdin>") -> list:
    """Parse a complete program from source code.

    Convenience function that lexes and parses source code into a list
    of surface declarations.

    Args:
        source: The source code string to parse
        filename: Optional filename for error reporting

    Returns:
        List of parsed surface declarations

    Raises:
        ParseError: If parsing fails
    """
    tokens = list(lex(source, filename))
    try:
        result = top_decl_parser().parse(tokens)
        return result if isinstance(result, list) else [result]
    except Exception as e:
        raise _extract_parse_error(e, tokens)


class ParseError(Exception):
    """Error during parsing."""

    def __init__(self, message: str, location=None):
        from systemf.utils.location import Location

        loc_str = f"{location}" if location else "unknown location"
        super().__init__(f"{loc_str}: {message}")
        self.location = location


def _extract_parse_error(e: Exception, tokens: list) -> ParseError:
    """Extract location from exception and create ParseError.

    Properly bounds checks before accessing token list.
    """
    loc = None
    # Safely get index from exception
    idx = getattr(e, "index", None)
    if idx is not None and isinstance(idx, int) and 0 <= idx < len(tokens):
        loc = getattr(tokens[idx], "location", None)
    return ParseError(str(e), loc)


class Parser:
    """Compatibility wrapper for old Parser API.

    Provides the same interface as the old Parser class:
    - Parser(tokens) - initialize with token list
    - parse() - parse declarations
    - parse_term() - parse a single term
    - parse_type() - parse a single type
    """

    def __init__(self, tokens: list):
        """Initialize parser with token list.

        Args:
            tokens: List of tokens from lexer
        """
        self.tokens = tokens

    def parse(self):
        """Parse token stream into declarations.

        Returns:
            List of parsed surface declarations

        Raises:
            ParseError: If parsing fails
        """
        try:
            result = top_decl_parser().parse(self.tokens)
            return result if isinstance(result, list) else [result]
        except Exception as e:
            raise _extract_parse_error(e, self.tokens)

    def parse_term(self):
        """Parse a single term.

        Returns:
            Parsed surface term

        Raises:
            ParseError: If parsing fails
        """
        try:
            return (expr_parser(AnyIndent()) << eof).parse(self.tokens)
        except Exception as e:
            raise _extract_parse_error(e, self.tokens)

    def parse_type(self):
        """Parse a single type.

        Returns:
            Parsed surface type

        Raises:
            ParseError: If parsing fails
        """
        try:
            return (type_parser() << eof).parse(self.tokens)
        except Exception as e:
            raise _extract_parse_error(e, self.tokens)


__all__ = [
    # Layout constraints and locations
    "ValidIndent",
    "AnyIndent",
    "AtPos",
    "AfterPos",
    "EndOfBlock",
    "Location",
    # Token types
    "Token",
    "TokenBase",
    "IdentifierToken",
    "ConstructorToken",
    "NumberToken",
    "StringToken",
    "KeywordToken",
    "LambdaToken",
    "TypeLambdaToken",
    "DataToken",
    "LetToken",
    "InToken",
    "CaseToken",
    "OfToken",
    "ForallToken",
    "TypeToken",
    "IfToken",
    "ThenToken",
    "ElseToken",
    "PrimTypeToken",
    "PrimOpToken",
    "OperatorToken",
    "OperatorType",
    "DelimiterToken",
    "DelimiterType",
    "PragmaToken",
    "DocstringToken",
    "EOFToken",
    "LexerError",
    # Lexer
    "Lexer",
    "lex",
    # Helpers
    "column",
    "check_valid",
    "block",
    "block_entries",
    "terminator",
    "must_continue",
    # Expression parsers
    "expr_parser",
    "atom_parser",
    "app_parser",
    "lambda_parser",
    "type_abs_parser",
    "if_parser",
    "case_parser",
    "let_parser",
    "pattern_parser",
    "case_alt",
    "let_binding",
    "match_token",
    "match_keyword",
    "match_symbol",
    "variable_parser",
    "constructor_parser",
    "literal_parser",
    "paren_parser",
    "atom_base_parser",
    # Declaration parsers
    "decl_parser",
    "top_decl_parser",
    "data_parser",
    "term_parser",
    "prim_type_parser",
    "prim_op_parser",
    "type_parser",
    "constr_parser",
    "match_ident",
    "match_constructor",
    # Convenience functions
    "parse_expression",
    "parse_declaration",
    "parse_type",
    "parse_program",
]
