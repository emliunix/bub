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

# Wire parsers together to resolve circular dependencies:
# - declarations.type_parser provides the type parser
# - expressions.expr_parser provides the expression parser
# - declarations needs expr_parser for term bodies
# - expressions needs type_parser for annotations

# Wire parsers together to resolve circular dependencies:
# - expressions.expr_parser provides the expression parser (takes ValidIndent)
# - declarations.type_parser() returns the type parser
# - declarations needs expr_parser for term bodies
# - expressions needs type_parser for annotations

# Get the raw type parser (without EOF handling) for internal use
# The public type_parser() wraps it with EOF handling for tests
type_parser_instance = declarations._raw_type_parser()

# Wire type parsers in both modules (they have separate forward declarations)
# Use the raw parser for recursive calls so parenthesized types work correctly
expressions.set_type_parser(type_parser_instance)
declarations.set_type_parser(type_parser_instance)

# Create an expression parser with AnyIndent constraint for use in declarations
# We use parsy's generate to create a parser that calls expr_parser(AnyIndent())
from parsy import generate as parsy_generate


@parsy_generate
def _expr_parser_for_declarations():
    """Expression parser with AnyIndent constraint for declarations."""
    result = yield expressions.expr_parser(AnyIndent())
    return result


declarations.set_expr_parser(_expr_parser_for_declarations)

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
    data_parser,
    term_parser,
    prim_type_parser,
    prim_op_parser,
    type_parser,
    constr_parser,
    match_ident,
    match_constructor,
)


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
    tokens = [t for t in lex(source) if t.type != "EOF"]
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
    tokens = [t for t in lex(source) if t.type != "EOF"]
    return declarations.decl_parser().parse(tokens)


def parse_type(source: str):
    """Parse a type from source code.

    Args:
        source: The source code string to parse

    Returns:
        The parsed surface type

    Raises:
        ParseError: If parsing fails
    """
    tokens = [t for t in lex(source) if t.type != "EOF"]
    return type_parser_instance.parse(tokens)


# Legacy API compatibility aliases
parse_term = parse_expression


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
    parser = Parser(tokens)
    return parser.parse()


class ParseError(Exception):
    """Error during parsing."""

    def __init__(self, message: str, location=None):
        from systemf.utils.location import Location

        loc_str = f"{location}" if location else "unknown location"
        super().__init__(f"{loc_str}: {message}")
        self.location = location


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
        from systemf.surface.types import SurfaceDeclaration

        # Filter EOF tokens for compatibility
        filtered = [t for t in self.tokens if getattr(t, "type", None) != "EOF"]
        try:
            result = decl_parser().parse(filtered)
            # Ensure we return a list
            if isinstance(result, list):
                return result
            return [result]
        except Exception as e:
            # Extract location from error if possible
            loc = None
            if hasattr(e, "index") and e.index < len(self.tokens):
                loc = getattr(self.tokens[e.index], "location", None)
            raise ParseError(str(e), loc)

    def parse_term(self):
        """Parse a single term.

        Returns:
            Parsed surface term

        Raises:
            ParseError: If parsing fails
        """
        filtered = [t for t in self.tokens if getattr(t, "type", None) != "EOF"]
        try:
            return (expr_parser(AnyIndent()) << eof).parse(filtered)
        except Exception as e:
            loc = None
            if hasattr(e, "index") and e.index < len(self.tokens):
                loc = getattr(self.tokens[e.index], "location", None)
            raise ParseError(str(e), loc)

    def parse_type(self):
        """Parse a single type.

        Returns:
            Parsed surface type

        Raises:
            ParseError: If parsing fails
        """
        filtered = [t for t in self.tokens if getattr(t, "type", None) != "EOF"]
        try:
            return type_parser_instance.parse(filtered)
        except Exception as e:
            loc = None
            if hasattr(e, "index") and e.index < len(self.tokens):
                loc = getattr(self.tokens[e.index], "location", None)
            raise ParseError(str(e), loc)


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
    # Legacy compatibility
    "parse_term",
    "Parser",
    "ParseError",
]
