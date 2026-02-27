"""Parsy-based parser for System F surface language.

Implements a monadic parser using parsy combinators and @generate decorator
for Haskell-like do-notation syntax.
"""

from __future__ import annotations

import parsy
from parsy import Parser as P, Result, generate

from systemf.surface.ast import (
    SurfaceAbs,
    SurfaceAnn,
    SurfaceApp,
    SurfaceBranch,
    SurfaceCase,
    SurfaceConstructor,
    SurfaceConstructorInfo,
    SurfaceDataDeclaration,
    SurfaceDeclaration,
    SurfaceIntLit,
    SurfaceLet,
    SurfaceOp,
    SurfacePattern,
    SurfacePragma,
    SurfacePrimOpDecl,
    SurfacePrimTypeDecl,
    SurfaceStringLit,
    SurfaceTerm,
    SurfaceTermDeclaration,
    SurfaceToolCall,
    SurfaceType,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceTypeArrow,
    SurfaceTypeConstructor,
    SurfaceTypeForall,
    SurfaceTypeVar,
    SurfaceVar,
)
from systemf.surface.lexer import Lexer
from systemf.surface.types import Token
from systemf.utils.location import Location


class ParseError(Exception):
    """Error during parsing."""

    def __init__(self, message: str, location: Location):
        super().__init__(f"{location}: {message}")
        self.location = location


# =============================================================================
# Token Primitives
# =============================================================================


def match_token(token_type: str) -> P:
    """Match a token of specific type."""

    @P
    def match(tokens: list[Token], index: int) -> Result:
        if index < len(tokens) and tokens[index].type == token_type:
            return Result.success(index + 1, tokens[index])
        return Result.failure(index, f"expected {token_type}")

    return match


def match_value(token_type: str, value: str) -> P:
    """Match a token with specific type and value."""

    @P
    def match(tokens: list[Token], index: int) -> Result:
        if index < len(tokens):
            tok = tokens[index]
            if tok.type == token_type and tok.value == value:
                return Result.success(index + 1, tok)
        return Result.failure(index, f"expected {token_type}({value!r})")

    return match


# =============================================================================
# Token Matchers
# =============================================================================

# Keywords
DATA = match_token("DATA")
LET = match_token("LET")
IN = match_token("IN")
CASE = match_token("CASE")
OF = match_token("OF")
FORALL = match_token("FORALL")
LAMBDA = match_token("LAMBDA")
TYPELAMBDA = match_token("TYPELAMBDA")

# Docstrings
DOCSTRING_PRECEDING = match_token("DOCSTRING_PRECEDING").map(lambda t: t.value)
DOCSTRING_INLINE = match_token("DOCSTRING_INLINE").map(lambda t: t.value)

# Operators
ARROW = match_token("ARROW")
EQUALS = match_token("EQUALS")
COLON = match_token("COLON")
BAR = match_token("BAR")
AT = match_token("AT")
DOT = match_token("DOT")

# Arithmetic operators
PLUS = match_token("PLUS")
MINUS = match_token("MINUS")
STAR = match_token("STAR")
SLASH = match_token("SLASH")

# Comparison operators
EQ = match_token("EQ")
LT = match_token("LT")
GT = match_token("GT")
LE = match_token("LE")
GE = match_token("GE")

# Delimiters
LPAREN = match_token("LPAREN")
RPAREN = match_token("RPAREN")
LBRACKET = match_token("LBRACKET")
RBRACKET = match_token("RBRACKET")
LBRACE = match_token("LBRACE")
RBRACE = match_token("RBRACE")

# Indentation tokens
INDENT = match_token("INDENT")
DEDENT = match_token("DEDENT")

# Values
IDENT = match_token("IDENT").map(lambda t: t.value)
CONSTRUCTOR = match_token("CONSTRUCTOR").map(lambda t: t.value)
NUMBER = match_token("NUMBER").map(lambda t: t.value)
STRING = match_token("STRING").map(lambda t: t.value)
EOF = match_token("EOF")

# Pragma tokens
PRAGMA_START = match_token("PRAGMA_START")
PRAGMA_END = match_token("PRAGMA_END")
PRAGMA_CONTENT = match_token("PRAGMA_CONTENT").map(lambda t: t.value)
LLM = match_token("LLM").map(lambda t: t.value)
TOOL = match_token("TOOL").map(lambda t: t.value)

# Primitive declaration tokens
PRIM_TYPE = match_token("PRIM_TYPE")
PRIM_OP = match_token("PRIM_OP")


# =============================================================================
# Helper Functions
# =============================================================================


@P
def peek_token(tokens: list[Token], index: int) -> Result:
    """Peek at next token without consuming."""
    if index < len(tokens):
        return Result.success(index, tokens[index])
    return Result.failure(index, "unexpected end of input")


# Forward declarations for recursive parsers
term_parser: P = parsy.forward_declaration()
type_parser: P = parsy.forward_declaration()
decl_term_parser: P = parsy.forward_declaration()  # Parser that stops at decl boundaries
simple_term_parser: P = parsy.forward_declaration()  # Non-greedy term parser for branch bodies
decl_simple_term_parser: P = parsy.forward_declaration()  # Non-greedy decl term parser


# =============================================================================
# Indentation-Aware Combinators
# =============================================================================


def indented_block(content_parser: P) -> P:
    """Create a parser for INDENT content DEDENT sequence.

    Used for parsing content that is indented relative to its parent.
    """

    @generate
    def block_parser():
        yield INDENT
        content = yield content_parser
        yield DEDENT
        return content

    return block_parser


def indented_many(item_parser: P) -> P:
    """Create a parser for one or more indented items (no separator).

    Each item must be at the same indentation level within the block.
    """

    @generate
    def many_parser():
        yield INDENT
        first = yield item_parser
        items = [first]
        # Parse remaining items - each at the same indentation level
        while True:
            # Peek at next token to check if we're still in the block
            next_tok = yield peek_token
            if next_tok.type == "DEDENT":
                break
            # Try to parse another item
            item = yield item_parser.optional()
            if item is None:
                break
            items.append(item)
        yield DEDENT
        return items

    return many_parser


# =============================================================================
# Type Parsers
# =============================================================================


@generate
def atom_type():
    """Parse atomic type: ident | CON | ( type )."""
    # Parenthesized type
    paren = yield (LPAREN >> type_parser << RPAREN).optional()
    if paren is not None:
        return paren

    # Type variable
    ident = yield match_token("IDENT").optional()
    if ident is not None:
        return SurfaceTypeVar(ident.value, ident.location)

    # Type constructor
    con = yield match_token("CONSTRUCTOR").optional()
    if con is not None:
        return SurfaceTypeConstructor(con.value, [], con.location)

    # No match - fail
    yield parsy.fail("expected type")


@generate
def app_type():
    """Parse type application (left-associative)."""
    loc_token = yield peek_token
    loc = loc_token.location
    atoms = yield atom_type.at_least(1)

    if len(atoms) == 1:
        return atoms[0]

    # Build left-associative application chain
    result = atoms[0]
    for next_atom in atoms[1:]:
        match result:
            case SurfaceTypeConstructor(name, args, location):
                # Add to existing constructor args
                result = SurfaceTypeConstructor(name, args + [next_atom], location)
            case _:
                # Start new constructor
                result = SurfaceTypeConstructor(str(result), [next_atom], loc)
    return result


@generate
def arrow_type():
    """Parse arrow type (right-associative)."""
    arg = yield app_type
    arrow = yield (ARROW >> arrow_type).optional()
    if arrow is not None:
        loc = arg.location
        return SurfaceTypeArrow(arg, arrow, loc)
    return arg


@generate
def forall_type():
    """Parse forall type."""
    loc_token = yield FORALL
    loc = loc_token.location
    vars = yield IDENT.at_least(1)
    yield DOT
    body = yield forall_type | arrow_type

    # Build nested forall from right to left
    for var in reversed(vars):
        body = SurfaceTypeForall(var, body, loc)
    return body


# Define the actual type parser
type_parser.become(forall_type | arrow_type)


# =============================================================================
# Term Parsers
# =============================================================================


@generate
def atom_base():
    """Parse base atom: paren | tool_call | ident | con | number."""
    # Parenthesized term
    paren = yield (LPAREN >> term_parser << RPAREN).optional()
    if paren is not None:
        return paren

    # Tool call: @tool_name arg1 arg2 ...
    at_tok = yield match_token("AT").optional()
    if at_tok is not None:
        tool_name_tok = yield match_token("IDENT")
        tool_name = tool_name_tok.value
        tool_loc = at_tok.location

        # Parse tool arguments (atoms), stopping at boundaries
        args = []
        while True:
            # Check for declaration boundary
            is_boundary = yield is_decl_boundary
            if is_boundary:
                break

            # Check for indentation boundary
            at_indent_boundary = yield is_indent_boundary
            if at_indent_boundary:
                break

            # Try to parse next argument
            next_atom = yield atom_base.optional()
            if next_atom is None:
                break
            args.append(next_atom)

        return SurfaceToolCall(tool_name, args, tool_loc)

    # Variable
    ident = yield match_token("IDENT").optional()
    if ident is not None:
        return SurfaceVar(ident.value, ident.location)

    # Number literal
    num = yield match_token("NUMBER").optional()
    if num is not None:
        return SurfaceIntLit(int(num.value), num.location)

    # String literal
    string = yield match_token("STRING").optional()
    if string is not None:
        return SurfaceStringLit(string.value, string.location)

    # Constructor application or nullary constructor
    con = yield match_token("CONSTRUCTOR").optional()
    if con is not None:
        con_name = con.value
        con_loc = con.location

        # Parse constructor arguments (atoms), stopping at various boundaries
        args = []
        while True:
            # Check for declaration boundary before trying to parse next atom
            is_boundary = yield is_decl_boundary
            if is_boundary:
                break

            # Check for indentation boundary
            at_indent_boundary = yield is_indent_boundary
            if at_indent_boundary:
                break

            # Check for pattern boundary (CONSTRUCTOR followed by IDENT or ARROW)
            # This prevents consuming the next pattern in a case expression as an argument
            at_pattern_boundary = yield is_pattern_boundary
            if at_pattern_boundary:
                break

            next_atom = yield atom_base.optional()
            if next_atom is None:
                break
            args.append(next_atom)

        return SurfaceConstructor(con_name, args, con_loc)

    # No match - fail
    yield parsy.fail("expected term")


@generate
def atom_parser():
    """Parse atom with post-fix operators."""
    atom = yield atom_base

    # Post-fix operators: @T, [T], :T
    while True:
        # Type application with @
        type_app = yield (AT >> type_parser).optional()
        if type_app is not None:
            atom = SurfaceTypeApp(atom, type_app, atom.location)
            continue

        # Type application with brackets
        type_bracket = yield (LBRACKET >> type_parser << RBRACKET).optional()
        if type_bracket is not None:
            atom = SurfaceTypeApp(atom, type_bracket, atom.location)
            continue

        # Type annotation
        type_ann = yield (COLON >> type_parser).optional()
        if type_ann is not None:
            atom = SurfaceAnn(atom, type_ann, atom.location)
            continue

        break

    return atom


@generate
def app_parser():
    """Parse application (left-associative) with post-fix operators."""
    loc_token = yield peek_token
    loc = loc_token.location

    # Parse first atom
    result = yield atom_base

    # Continue parsing: either application or post-fix operators
    while True:
        # Try post-fix type application with @
        type_app = yield (AT >> type_parser).optional()
        if type_app is not None:
            result = SurfaceTypeApp(result, type_app, result.location)
            continue

        # Try post-fix type application with brackets
        type_bracket = yield (LBRACKET >> type_parser << RBRACKET).optional()
        if type_bracket is not None:
            result = SurfaceTypeApp(result, type_bracket, result.location)
            continue

        # Try post-fix type annotation
        type_ann = yield (COLON >> type_parser).optional()
        if type_ann is not None:
            result = SurfaceAnn(result, type_ann, result.location)
            continue

        # Check for indentation boundary before trying application
        at_indent_boundary = yield is_indent_boundary
        if at_indent_boundary:
            break

        # Try next atom for application
        next_atom = yield atom_base.optional()
        if next_atom is not None:
            result = SurfaceApp(result, next_atom, loc)
            continue

        break

    return result


# =============================================================================
# Operator Precedence Parser
# =============================================================================


# Operator precedence levels (higher number = tighter binding)
# Level 7: * /
# Level 6: + -
# Level 5: == < > <= >=
# Level 4: Application (handled separately)
# Level 3: -> (type arrow, not term operator)
# Level 2: \ (lambda, not handled here)
# Level 1: let (not handled here)

OPERATOR_PRECEDENCE: dict[str, int] = {
    "*": 7,
    "/": 7,
    "+": 6,
    "-": 6,
    "==": 5,
    "<": 5,
    ">": 5,
    "<=": 5,
    ">=": 5,
}


def make_op_parser(atom_parser: P, min_precedence: int = 0) -> P:
    """Create a precedence-climbing parser for infix operators.

    This implements the precedence climbing algorithm for parsing binary
    operators with different precedence levels.

    Args:
        atom_parser: Parser for atomic expressions (higher precedence)
        min_precedence: Minimum precedence level to parse at this level

    Returns:
        Parser for expressions at this precedence level or higher
    """

    @generate
    def op_parser():
        # Parse the left operand
        left = yield atom_parser

        while True:
            # Peek at the next token to see if it's an operator
            next_tok = yield peek_token

            # Check if it's an operator token
            op_symbol = None
            if next_tok.type == "STAR":
                op_symbol = "*"
            elif next_tok.type == "SLASH":
                op_symbol = "/"
            elif next_tok.type == "PLUS":
                op_symbol = "+"
            elif next_tok.type == "MINUS":
                op_symbol = "-"
            elif next_tok.type == "EQ":
                op_symbol = "=="
            elif next_tok.type == "LT":
                op_symbol = "<"
            elif next_tok.type == "GT":
                op_symbol = ">"
            elif next_tok.type == "LE":
                op_symbol = "<="
            elif next_tok.type == "GE":
                op_symbol = ">="
            else:
                # Not an operator, we're done
                break

            precedence = OPERATOR_PRECEDENCE[op_symbol]

            # If operator precedence is less than minimum, stop here
            if precedence < min_precedence:
                break

            # Consume the operator
            if op_symbol == "*":
                yield STAR
            elif op_symbol == "/":
                yield SLASH
            elif op_symbol == "+":
                yield PLUS
            elif op_symbol == "-":
                yield MINUS
            elif op_symbol == "==":
                yield EQ
            elif op_symbol == "<":
                yield LT
            elif op_symbol == ">":
                yield GT
            elif op_symbol == "<=":
                yield LE
            elif op_symbol == ">=":
                yield GE

            # Parse the right operand with higher precedence
            # (for left-associative operators)
            right = yield make_op_parser(atom_parser, precedence + 1)

            # Build the operator node
            loc = left.location
            left = SurfaceOp(left, op_symbol, right, loc)

        return left

    return op_parser


# Create the operator expression parser using app_parser as the atomic base
op_expr_parser = make_op_parser(app_parser)


@P
def is_decl_boundary(tokens: list[Token], index: int) -> Result:
    """Check if we're at a declaration boundary (IDENT/CONSTRUCTOR followed by = or :)."""
    if index < len(tokens):
        current = tokens[index]
        if current.type in ("IDENT", "CONSTRUCTOR"):
            if index + 1 < len(tokens):
                next_tok = tokens[index + 1]
                if next_tok.type in ("COLON", "EQUALS"):
                    return Result.success(index, True)
    return Result.success(index, False)


@P
def is_indent_boundary(tokens: list[Token], index: int) -> Result:
    """Check if we're at an indentation boundary (DEDENT or end of input)."""
    if index >= len(tokens):
        return Result.success(index, True)
    if tokens[index].type == "DEDENT":
        return Result.success(index, True)
    return Result.success(index, False)


@P
def is_pattern_boundary(tokens: list[Token], index: int) -> Result:
    """Check if we're at a pattern boundary (CONSTRUCTOR followed by IDENT or ARROW).

    This is used when parsing constructor applications to know when to stop,
    as the next CONSTRUCTOR might be the start of a new pattern in a case expression.
    """
    if index < len(tokens):
        current = tokens[index]
        if current.type == "CONSTRUCTOR":
            if index + 1 < len(tokens):
                next_tok = tokens[index + 1]
                # If followed by IDENT or ARROW, it's likely a pattern, not an arg
                if next_tok.type in ("IDENT", "ARROW"):
                    return Result.success(index, True)
    return Result.success(index, False)


@generate
def decl_app_parser():
    """Parse application for declaration body, stopping at declaration boundaries."""
    loc_token = yield peek_token
    loc = loc_token.location

    # Parse first atom
    result = yield atom_base

    # Continue parsing: either application or post-fix operators
    while True:
        # Try post-fix type application with @
        type_app = yield (AT >> type_parser).optional()
        if type_app is not None:
            result = SurfaceTypeApp(result, type_app, result.location)
            continue

        # Try post-fix type application with brackets
        type_bracket = yield (LBRACKET >> type_parser << RBRACKET).optional()
        if type_bracket is not None:
            result = SurfaceTypeApp(result, type_bracket, result.location)
            continue

        # Try post-fix type annotation
        type_ann = yield (COLON >> type_parser).optional()
        if type_ann is not None:
            result = SurfaceAnn(result, type_ann, result.location)
            continue

        # Check for declaration boundary before trying application
        is_boundary = yield is_decl_boundary
        if is_boundary:
            break

        # Check for indentation boundary
        at_indent_boundary = yield is_indent_boundary
        if at_indent_boundary:
            break

        # Try next atom for application
        next_atom = yield atom_base.optional()
        if next_atom is not None:
            result = SurfaceApp(result, next_atom, loc)
            continue

        break

    return result


@generate
def lambda_parser():
    r"""Parse lambda abstraction with optional indentation for multi-line bodies.

    Syntax:
        \x -> expr                    (single-line)
        \x ->
          expr                        (multi-line with indentation)
    """
    loc_token = yield LAMBDA
    loc = loc_token.location
    var = yield IDENT
    # For lambda annotations, only parse app_type (not arrow_type) to avoid
    # consuming the lambda arrow as a type arrow
    var_type = yield (COLON >> app_type).optional()
    yield ARROW
    # Check for optional indented block or single-line body
    body = yield indented_block(term_parser) | term_parser
    return SurfaceAbs(var, var_type, body, loc)


@generate
def let_parser():
    """Parse let binding with indentation-aware body.

    New syntax:
        let x = value
          body

    Instead of old:
        let x = value in body
    """
    loc_token = yield LET
    loc = loc_token.location
    name = yield IDENT
    yield EQUALS
    value = yield term_parser
    body = yield indented_block(term_parser)
    return SurfaceLet(name, value, body, loc)


@generate
def case_parser():
    """Parse case expression with both syntaxes.

    Syntax 1 - Indented style:
        case expr of
          Pat1 -> expr1
          Pat2 -> expr2

    Syntax 2 - Explicit style:
        case expr of {
          | Pat1 -> expr1
          | Pat2 -> expr2
        }
    """
    loc_token = yield CASE
    loc = loc_token.location
    scrutinee = yield term_parser
    yield OF

    # Check for explicit brace syntax
    lbrace = yield LBRACE.optional()
    if lbrace is not None:
        # Explicit style: { | Pat -> expr | ... }
        branches = yield explicit_branches_parser
        yield RBRACE
    else:
        # Indented style
        branches = yield indented_many(branch_parser)

    return SurfaceCase(scrutinee, branches, loc)


@generate
def type_abs_parser():
    """Parse type abstraction."""
    loc_token = yield TYPELAMBDA
    loc = loc_token.location
    var = yield IDENT
    yield DOT
    body = yield term_parser
    return SurfaceTypeAbs(var, body, loc)


# Declaration-aware versions that stop at declaration boundaries
@generate
def decl_lambda_parser():
    """Parse lambda abstraction (declaration context) with optional indentation."""
    loc_token = yield LAMBDA
    loc = loc_token.location
    var = yield IDENT
    var_type = yield (COLON >> app_type).optional()
    yield ARROW
    # Check for optional indented block or single-line body
    body = yield indented_block(decl_term_parser) | decl_term_parser
    return SurfaceAbs(var, var_type, body, loc)


@generate
def decl_let_parser():
    """Parse let binding (declaration context) with indentation-aware body."""
    loc_token = yield LET
    loc = loc_token.location
    name = yield IDENT
    yield EQUALS
    value = yield decl_term_parser
    body = yield indented_block(decl_term_parser)
    return SurfaceLet(name, value, body, loc)


@generate
def decl_explicit_branch_parser():
    """Parse a branch in explicit { | } syntax (declaration context)."""
    loc_token = yield peek_token
    loc = loc_token.location
    yield BAR
    pat = yield pattern_parser
    yield ARROW
    body = yield decl_simple_term_parser
    return SurfaceBranch(pat, body, loc)


@generate
def decl_explicit_branches_parser():
    """Parse branches in explicit { | } syntax (declaration context)."""
    first = yield decl_explicit_branch_parser
    rest = yield (decl_explicit_branch_parser).many()
    return [first] + rest


@generate
def decl_case_parser():
    """Parse case expression (declaration context) with both syntaxes."""
    loc_token = yield CASE
    loc = loc_token.location
    scrutinee = yield decl_term_parser
    yield OF

    # Check for explicit brace syntax
    lbrace = yield LBRACE.optional()
    if lbrace is not None:
        # Explicit style: { | Pat -> expr | ... }
        branches = yield decl_explicit_branches_parser
        yield RBRACE
    else:
        # Indented style
        branches = yield indented_many(decl_branch_parser)

    return SurfaceCase(scrutinee, branches, loc)


@generate
def decl_type_abs_parser():
    """Parse type abstraction (declaration context)."""
    loc_token = yield TYPELAMBDA
    loc = loc_token.location
    var = yield IDENT
    yield DOT
    body = yield decl_term_parser
    return SurfaceTypeAbs(var, body, loc)


# Create declaration versions of operator parsers
# These use decl_app_parser as the base instead of app_parser
decl_op_expr_parser = make_op_parser(decl_app_parser)

# Define the actual term parsers
# Use op_expr_parser for expression-level parsing (includes operators)
term_parser.become(lambda_parser | let_parser | case_parser | type_abs_parser | op_expr_parser)
decl_term_parser.become(
    decl_lambda_parser
    | decl_let_parser
    | decl_case_parser
    | decl_type_abs_parser
    | decl_op_expr_parser
)

# Define simple term parsers for branch bodies (use atom_parser instead of app_parser)
# Note: We don't use op_expr_parser here because branch bodies need to stop at
# branch boundaries (BAR, DEDENT). Operators in branches need to be handled
# by parsing them differently.
simple_term_parser.become(lambda_parser | let_parser | case_parser | type_abs_parser | atom_parser)
decl_simple_term_parser.become(
    decl_lambda_parser | decl_let_parser | decl_case_parser | decl_type_abs_parser | atom_parser
)


# =============================================================================
# Pattern and Branch Parsers
# =============================================================================
# Pattern and Branch Parsers
# =============================================================================


@generate
def pattern_parser():
    """Parse pattern: CON ident*."""
    loc_token = yield peek_token
    loc = loc_token.location
    con = yield match_token("CONSTRUCTOR")
    vars = yield IDENT.many()
    return SurfacePattern(con.value, vars, loc)


@generate
def branch_parser():
    """Parse branch: pattern -> term."""
    loc_token = yield peek_token
    loc = loc_token.location
    pat = yield pattern_parser
    yield ARROW
    body = yield simple_term_parser
    return SurfaceBranch(pat, body, loc)


@generate
def decl_branch_parser():
    """Parse branch: pattern -> term (declaration context)."""
    loc_token = yield peek_token
    loc = loc_token.location
    pat = yield pattern_parser
    yield ARROW
    body = yield decl_simple_term_parser
    return SurfaceBranch(pat, body, loc)


@generate
def explicit_branch_parser():
    """Parse a branch in explicit { | } syntax.

    Syntax: | pattern -> term
    The | is required for explicit syntax.
    """
    loc_token = yield peek_token
    loc = loc_token.location
    yield BAR
    pat = yield pattern_parser
    yield ARROW
    body = yield simple_term_parser
    return SurfaceBranch(pat, body, loc)


@generate
def branch_body_parser():
    """Parse branch body that allows applications but stops at branch boundaries.

    Uses atom_base for the first atom, then tries to apply more atoms
    while respecting branch boundaries (BAR for next branch, RBRACE for end).
    """
    loc_token = yield peek_token
    loc = loc_token.location

    # Parse first atom
    result = yield atom_base

    # Continue parsing: try to apply more atoms
    while True:
        # Check for postfix type application with @
        type_app = yield (AT >> type_parser).optional()
        if type_app is not None:
            result = SurfaceTypeApp(result, type_app, result.location)
            continue

        # Try postfix type application with brackets
        type_bracket = yield (LBRACKET >> type_parser << RBRACKET).optional()
        if type_bracket is not None:
            result = SurfaceTypeApp(result, type_bracket, result.location)
            continue

        # Try postfix type annotation
        type_ann = yield (COLON >> type_parser).optional()
        if type_ann is not None:
            result = SurfaceAnn(result, type_ann, result.location)
            continue

        # Check for branch boundary before trying application
        peeked = yield peek_token
        if peeked.type in ("BAR", "RBRACE"):
            break

        # Try next atom for application
        next_atom = yield atom_base.optional()
        if next_atom is not None:
            result = SurfaceApp(result, next_atom, loc)
            continue

        break

    return result


@generate
def explicit_branches_parser():
    """Parse branches in explicit { | } syntax.

    Syntax: | Pat1 -> expr1 | Pat2 -> expr2 ...
    """
    first = yield explicit_branch_parser
    rest = yield (explicit_branch_parser).many()
    return [first] + rest


def sep_by(parser: P, sep: P) -> P:
    """Parse zero or more parser separated by sep."""

    @generate
    def sep_by_parser():
        first = yield parser
        rest = yield (sep >> parser).many()
        return [first] + rest

    return sep_by_parser.optional() | parsy.success([])


def sep_by1(parser: P, sep: P) -> P:
    """Parse one or more parser separated by sep."""

    @generate
    def sep_by1_parser():
        first = yield parser
        rest = yield (sep >> parser).many()
        return [first] + rest

    return sep_by1_parser


# =============================================================================
# Declaration Parsers
# =============================================================================


def parse_pragma_attributes(content: str) -> dict[str, str]:
    """Parse pragma content into key-value pairs.

    Format: directive key1=value1, key2=value2 ...
    Returns: dict of attributes (excluding the directive)

    Example:
        "LLM model=gpt-4, temperature=0.7" -> {"model": "gpt-4", "temperature": "0.7"}
    """
    attributes: dict[str, str] = {}

    # Split content but preserve quoted values
    parts = []
    current = ""
    in_quotes = False
    quote_char = None

    for char in content:
        if char in "\"'":
            if not in_quotes:
                in_quotes = True
                quote_char = char
                current += char
            elif char == quote_char:
                in_quotes = False
                quote_char = None
                current += char
            else:
                current += char
        elif char == "," and not in_quotes:
            parts.append(current.strip())
            current = ""
        else:
            current += char

    if current.strip():
        parts.append(current.strip())

    # Parse each part as key=value
    for part in parts:
        if "=" in part:
            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip()
            # Remove quotes if present
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            attributes[key] = value

    return attributes


@generate
def pragma_parser():
    """Parse pragma: {-# LLM key=value ... #-}."""
    loc_token = yield PRAGMA_START
    loc = loc_token.location

    # The pragma content should contain the directive and attributes
    content = yield PRAGMA_CONTENT

    # Parse content to extract directive and attributes
    content_parts = content.strip().split(None, 1)
    if not content_parts:
        raise ParseError("Empty pragma", loc)

    directive = content_parts[0]
    attr_string = content_parts[1] if len(content_parts) > 1 else ""

    # Parse attributes
    attributes = parse_pragma_attributes(attr_string)

    # Consume PRAGMA_END
    yield PRAGMA_END

    return SurfacePragma(directive, attributes, loc)


@generate
def constructor_parser():
    """Parse constructor: CON type_atom* [-- ^ docstring]."""
    con = yield match_token("CONSTRUCTOR")
    con_name = con.value
    con_loc = con.location

    # Parse argument types
    arg_types = []
    while True:
        # Check for declaration boundary first
        is_boundary = yield is_decl_boundary
        if is_boundary:
            break

        next_tok = yield peek_token
        if next_tok.type not in ("IDENT", "CONSTRUCTOR", "LPAREN"):
            break

        ty = yield atom_type
        arg_types.append(ty)

    # Capture optional inline docstring (-- ^)
    docstring = yield DOCSTRING_INLINE.optional()
    if docstring is not None:
        # Extract content after '-- ^' prefix
        # The token value includes the full comment like '-- ^ docstring text'
        # We need to find the ^ and take everything after it
        if "^" in docstring:
            docstring = docstring.split("^", 1)[1].strip()

    return SurfaceConstructorInfo(con_name, arg_types, docstring, con_loc)


@generate
def declaration_body():
    """Parse term as declaration body."""
    # Handle optional indentation after = (for multi-line declarations)
    yield INDENT.optional()
    # Use decl_term_parser which stops at declaration boundaries
    return (yield decl_term_parser)


@generate
def declaration_parser():
    """Parse any declaration with optional preceding docstring and pragma."""
    # Capture any preceding pragmas
    pragma = yield pragma_parser.optional()

    # Capture any preceding docstrings (-- |)
    docstrings = yield DOCSTRING_PRECEDING.many()
    preceding_docstring = None
    if docstrings:
        # Take the last docstring and extract content after '-- |'
        last_doc = docstrings[-1]
        if "|" in last_doc:
            preceding_docstring = last_doc.split("|", 1)[1].strip()

    # Peek at next token to determine declaration type
    next_tok = yield peek_token
    if next_tok.type == "DATA":
        result = yield data_declaration_with_docstring_and_pragma_parser(
            preceding_docstring, pragma
        )
    elif next_tok.type == "PRIM_TYPE":
        result = yield prim_type_decl_parser
    elif next_tok.type == "PRIM_OP":
        result = yield prim_op_decl_parser
    else:
        result = yield term_declaration_with_docstring_and_pragma_parser(
            preceding_docstring, pragma
        )
    return result


def data_declaration_with_docstring_and_pragma_parser(
    preceding_docstring: str | None = None, pragma: SurfacePragma | None = None
):
    """Create a parser for data declaration with preceding docstring and pragma."""

    @generate
    def parser():
        loc_token = yield DATA
        loc = loc_token.location
        name = yield CONSTRUCTOR
        params = yield IDENT.many()

        # Handle optional indentation before = (for = on new line)
        yield INDENT.optional()
        yield EQUALS

        # Handle optional indentation after = (for multi-line declarations)
        yield INDENT.optional()

        # Parse constructors separated by | (with optional indentation before each |)
        constrs = yield sep_by1(constructor_parser, (INDENT.optional() >> BAR))

        # Handle optional dedent at end
        yield DEDENT.optional()

        return SurfaceDataDeclaration(name, params, constrs, loc, preceding_docstring, pragma)

    return parser


def term_declaration_with_docstring_and_pragma_parser(
    preceding_docstring: str | None = None, pragma: SurfacePragma | None = None
):
    """Create a parser for term declaration with preceding docstring and pragma."""

    @generate
    def parser():
        name_tok = yield match_token("IDENT")
        name = name_tok.value
        loc = name_tok.location
        type_ann = yield (COLON >> type_parser).optional()
        yield EQUALS
        body = yield declaration_body
        return SurfaceTermDeclaration(name, type_ann, body, loc, preceding_docstring, pragma)

    return parser


@generate
def data_declaration_with_docstring(preceding_docstring: str | None = None):
    """Parse data declaration with preceding docstring."""
    loc_token = yield DATA
    loc = loc_token.location
    name = yield CONSTRUCTOR
    params = yield IDENT.many()

    # Handle optional indentation before = (for = on new line)
    yield INDENT.optional()
    yield EQUALS

    # Handle optional indentation after = (for multi-line declarations)
    yield INDENT.optional()

    # Parse constructors separated by | (with optional indentation before each |)
    constrs = yield sep_by1(constructor_parser, (INDENT.optional() >> BAR))

    # Handle optional dedent at end
    yield DEDENT.optional()

    return SurfaceDataDeclaration(name, params, constrs, loc, preceding_docstring)


@generate
def term_declaration_with_docstring(preceding_docstring: str | None = None):
    """Parse term declaration with preceding docstring."""
    name_tok = yield match_token("IDENT")
    name = name_tok.value
    loc = name_tok.location
    type_ann = yield (COLON >> type_parser).optional()
    yield EQUALS
    body = yield declaration_body
    return SurfaceTermDeclaration(name, type_ann, body, loc, preceding_docstring)


@generate
def prim_type_decl_parser():
    """Parse primitive type declaration: prim_type Name."""
    loc_token = yield PRIM_TYPE
    name = yield CONSTRUCTOR  # Type names start with uppercase
    return SurfacePrimTypeDecl(name, loc_token.location)


@generate
def prim_op_decl_parser():
    """Parse primitive operation declaration: prim_op name : type."""
    loc_token = yield PRIM_OP
    name = yield IDENT  # Operation names start with lowercase
    yield COLON
    ty = yield type_parser
    return SurfacePrimOpDecl(name, ty, loc_token.location)


# Program parser
program_parser = (
    INDENT.optional() >> declaration_parser.sep_by(DEDENT.optional()) << DEDENT.optional() << EOF
)


# =============================================================================
# Parser Class and Convenience Functions
# =============================================================================


class Parser:
    """Parsy-based parser for surface language."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens

    def parse(self) -> list[SurfaceDeclaration]:
        """Parse token stream into declarations."""
        try:
            return program_parser.parse(self.tokens)
        except parsy.ParseError as e:
            loc = self._get_error_location(e)
            raise ParseError(f"expected {e.expected}", loc)

    def parse_term(self) -> SurfaceTerm:
        """Parse a single term."""
        try:
            return (term_parser << EOF).parse(self.tokens)
        except parsy.ParseError as e:
            loc = self._get_error_location(e)
            raise ParseError(f"expected {e.expected}", loc)

    def parse_type(self) -> SurfaceType:
        """Parse a single type."""
        try:
            return (type_parser << EOF).parse(self.tokens)
        except parsy.ParseError as e:
            loc = self._get_error_location(e)
            raise ParseError(f"expected {e.expected}", loc)

    def _get_error_location(self, e: parsy.ParseError) -> Location:
        idx = min(e.index, len(self.tokens) - 1)
        return self.tokens[idx].location


# Convenience functions (same API as old parser)
def parse_term(source: str, filename: str = "<stdin>") -> SurfaceTerm:
    """Parse a single term from source.

    Args:
        source: Source code string
        filename: Source filename for error messages

    Returns:
        Parsed surface term

    Example:
        >>> term = parse_term("\\x -> x")
        >>> print(term)
        \\x -> x
    """
    tokens = Lexer(source, filename).tokenize()
    try:
        return (term_parser << EOF).parse(tokens)
    except parsy.ParseError as e:
        idx = min(e.index, len(tokens) - 1)
        loc = tokens[idx].location
        raise ParseError(f"expected {e.expected}", loc)


def parse_program(source: str, filename: str = "<stdin>") -> list[SurfaceDeclaration]:
    """Parse a full program from source.

    Args:
        source: Source code string
        filename: Source filename for error messages

    Returns:
        List of surface declarations

    Example:
        >>> decls = parse_program("x = 1")
        >>> len(decls)
        1
    """
    tokens = Lexer(source, filename).tokenize()
    parser = Parser(tokens)
    return parser.parse()
