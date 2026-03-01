"""Expression parsers for System F surface language.

Implements expression parsers using the new helper combinators with explicit
constraint passing (Idris2-style layout-aware parsing).

Parsers implemented:
- Token matching helpers (match_token, match_keyword, match_symbol)
- Atom parsers (variable, constructor, literal, paren)
- Lambda and type abstraction parsers
- Application parser (left-associative)
- Main expression entry point
"""

from __future__ import annotations

from typing import Optional, TypeVar
import parsy
from parsy import Parser as P, Result, generate, alt, fail, seq

from systemf.surface.parser.type_parser import type_atom_parser
from systemf.surface.parser.helpers import (
    AfterPos,
    AnyIndent,
    AtPos,
    ValidIndent,
    block_entries,
    check_valid,
    column,
    must_continue,
)
from systemf.surface.parser.types import (
    TokenBase,
    KeywordToken,
    OperatorToken,
    DelimiterToken,
)
from systemf.surface.types import (
    SurfaceTerm,
    SurfaceVar,
    SurfaceAbs,
    SurfaceApp,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceConstructor,
    SurfaceIntLit,
    SurfaceStringLit,
    SurfaceAnn,
    SurfaceType,
    SurfaceCase,
    SurfaceBranch,
    SurfacePattern,
    SurfaceLet,
    SurfaceIf,
    SurfaceOp,
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
        value: The keyword to match (e.g., "let", "case")

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
        value: The symbol to match (e.g., "→", "(", ")")

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
# Operator Token Matchers
# =============================================================================

# Arithmetic operators
PLUS = match_token("PLUS")
MINUS = match_token("MINUS")
STAR = match_token("STAR")
SLASH = match_token("SLASH")

# Comparison operators
EQ = match_token("EQ")  # ==
NE = match_token("NE")  # /=
LT = match_token("LT")  # <
GT = match_token("GT")  # >
LE = match_token("LE")  # <=
GE = match_token("GE")  # >=

# Logical operators
AND = match_token("AND")  # &&
OR = match_token("OR")  # ||

# String concatenation
APPEND = match_token("APPEND")  # ++


# =============================================================================
# Forward Declarations for Recursive Parsers
# =============================================================================

# Forward declaration for the type parser (for type annotations)
_type_parser: P[SurfaceType] = parsy.forward_declaration()


# =============================================================================
# Atom Parsers (no constraint needed)
# =============================================================================


def variable_parser() -> P[SurfaceVar]:
    """Parse a variable reference: ident.

    Returns:
        SurfaceVar with the variable name and location
    """

    @generate
    def parser():
        token = yield match_token("IDENT")
        return SurfaceVar(token.value, token.location)

    return parser


def constructor_parser() -> P[SurfaceConstructor]:
    """Parse a constructor application or nullary constructor.

    Tries to parse arguments greedily until no more atoms can be parsed.

    Returns:
        SurfaceConstructor with the constructor name and arguments
    """

    @generate
    def parser():
        token = yield match_token("CONSTRUCTOR")
        name = token.value
        loc = token.location

        # Parse arguments greedily (constructor application)
        args: list[SurfaceTerm] = []
        while True:
            # Try to parse an atom argument
            arg_result = yield atom_parser().optional()
            if arg_result is None:
                break
            args.append(arg_result)

        return SurfaceConstructor(name, args, loc)

    return parser


def literal_parser() -> P[SurfaceIntLit | SurfaceStringLit]:
    """Parse an integer or string literal.

    Returns:
        SurfaceIntLit or SurfaceStringLit with the value and location
    """

    @generate
    def parser():
        # Try integer literal first
        num_token = yield match_token("NUMBER").optional()
        if num_token is not None:
            return SurfaceIntLit(int(num_token.value), num_token.location)

        # Try string literal
        str_token = yield match_token("STRING").optional()
        if str_token is not None:
            return SurfaceStringLit(str_token.value, str_token.location)

        # Neither matched - fail
        yield fail("expected literal")

    return parser


def tuple_parser() -> P[SurfaceTerm]:
    """Parse a tuple expression: (e1, e2, ..., en).

    Sugar for nested Pair constructors: Pair e1 (Pair e2 (... en))

    Returns:
        SurfaceTuple containing the elements
    """

    @generate
    def parser():
        from systemf.surface.types import SurfaceTuple

        open_paren = yield match_symbol("(")
        loc = open_paren.location

        # Parse first element
        first = yield expr_parser(AnyIndent())
        elements = [first]

        # Parse comma-separated elements
        while True:
            yield match_symbol(",")
            elem = yield expr_parser(AnyIndent())
            elements.append(elem)

            # Check if we're at the closing paren
            close_paren = yield match_symbol(")").optional()
            if close_paren is not None:
                break

        return SurfaceTuple(elements, loc)

    return parser


def paren_parser() -> P[SurfaceTerm]:
    """Parse a parenthesized expression: ( expr ) or tuple: (e1, e2, ..., en).

    Returns:
        The parsed expression inside the parentheses, or a tuple if commas are present

    Note: This parser requires the type parser to be set via set_type_parser()
    before it can parse expressions inside parentheses.
    """

    @generate
    def parser():
        # Try tuple first (it requires a comma)
        tuple_result = yield tuple_parser().optional()
        if tuple_result is not None:
            return tuple_result

        # Regular parenthesized expression
        yield match_symbol("(")
        # Parse expression with AnyIndent constraint inside parens
        expr = yield expr_parser(AnyIndent())
        yield match_symbol(")")
        return expr

    return parser


def atom_base_parser() -> P[SurfaceTerm]:
    """Parse a base atom (no post-fix operators).

    Tries paren, constructor, literal, or variable in that order.

    Returns:
        The parsed atomic term
    """

    @generate
    def parser():
        # Try parenthesized expression first
        paren = yield paren_parser().optional()
        if paren is not None:
            return paren

        # Try constructor (includes nullary constructors)
        con = yield constructor_parser().optional()
        if con is not None:
            return con

        # Try literal
        lit = yield literal_parser().optional()
        if lit is not None:
            return lit

        # Try variable
        var = yield variable_parser().optional()
        if var is not None:
            return var

        # No match - fail
        yield fail("expected atom")

    return parser


def atom_parser() -> P[SurfaceTerm]:
    """Parse an atom with optional post-fix operators.

    Post-fix operators include:
    - @T or [T]: Type application
    - :T: Type annotation

    Returns:
        The parsed atom, possibly wrapped in post-fix operators
    """

    @generate
    def parser():
        atom = yield atom_base_parser()

        # Apply post-fix operators greedily
        while True:
            # Type application with @
            type_app = yield (match_symbol("@") >> _type_parser).optional()
            if type_app is not None:
                atom = SurfaceTypeApp(atom, type_app, atom.location)
                continue

            # Type application with brackets
            type_bracket = yield (match_symbol("[") >> _type_parser << match_symbol("]")).optional()
            if type_bracket is not None:
                atom = SurfaceTypeApp(atom, type_bracket, atom.location)
                continue

            # Type annotation
            type_ann = yield (match_symbol(":") >> _type_parser).optional()
            if type_ann is not None:
                atom = SurfaceAnn(atom, type_ann, atom.location)
                continue

            break

        return atom

    return parser


# =============================================================================
# Application Parser
# =============================================================================


def app_parser(constraint: ValidIndent) -> P[SurfaceTerm]:
    """Parse function application (left-associative).

    Parses one or more atoms and combines them into left-associative
    applications: ((f x) y) z

    Args:
        constraint: Layout constraint for checking additional argument columns

    Returns:
        SurfaceApp tree or a single atom if only one parsed
    """

    @generate
    def parser():
        # Parse first atom
        first = yield atom_parser()
        loc = first.location

        # Parse additional atoms for application, respecting constraint
        args: list[SurfaceTerm] = []
        while True:
            # Check constraint before parsing next argument
            if not isinstance(constraint, AnyIndent):
                next_col = yield peek_column()
                if next_col > 0 and not check_valid(constraint, next_col):
                    break

            arg = yield atom_parser().optional()
            if arg is None:
                break
            args.append(arg)

        # Build left-associative application chain
        if not args:
            return first

        result = first
        for arg in args:
            result = SurfaceApp(result, arg, loc)

        return result

    return parser


def peek_column() -> P[int]:
    """Peek at the column of the next token without consuming it.

    Returns 0 if at end of input.
    """

    @P
    def parser(tokens: list, index: int) -> Result:
        if index >= len(tokens):
            return Result.success(index, 0)
        return Result.success(index, tokens[index].column)

    return parser


# =============================================================================
# Operator Expression Parsers
# =============================================================================


def multiplicative_parser(constraint: ValidIndent) -> P[SurfaceTerm]:
    """Parse multiplicative expressions: left (*|/) right.

    Highest precedence among operators, just above application.

    Args:
        constraint: Layout constraint (passed through to operands)

    Returns:
        SurfaceOp tree for multiplicative operations or a single term
    """

    @generate
    def parser():
        # Parse left operand (application level)
        left = yield app_parser(constraint)
        loc = left.location

        # Parse zero or more (*|/) right-operand pairs
        ops_and_rights = []
        while True:
            # Try each operator
            op = yield (STAR | SLASH).optional()
            if op is None:
                break
            right = yield app_parser(constraint)
            ops_and_rights.append((op, right))

        # Build left-associative tree
        result = left
        for op, right in ops_and_rights:
            result = SurfaceOp(result, op.value, right, loc)

        return result

    return parser


def additive_parser(constraint: ValidIndent) -> P[SurfaceTerm]:
    """Parse additive expressions: left (+|-|++) right.

    Lower precedence than multiplicative, higher than comparison.

    Args:
        constraint: Layout constraint (passed through to operands)

    Returns:
        SurfaceOp tree for additive operations or a single term
    """

    @generate
    def parser():
        # Parse left operand (multiplicative level)
        left = yield multiplicative_parser(constraint)
        loc = left.location

        # Parse zero or more (+|-|++) right-operand pairs
        ops_and_rights = []
        while True:
            # Try each operator
            op = yield (PLUS | MINUS | APPEND).optional()
            if op is None:
                break
            right = yield multiplicative_parser(constraint)
            ops_and_rights.append((op, right))

        # Build left-associative tree
        result = left
        for op, right in ops_and_rights:
            result = SurfaceOp(result, op.value, right, loc)

        return result

    return parser


def comparison_parser(constraint: ValidIndent) -> P[SurfaceTerm]:
    """Parse comparison expressions: left (==|/=|<|>|<=|>=) right.

    Lower precedence than additive, higher than logical.

    Args:
        constraint: Layout constraint (passed through to operands)

    Returns:
        SurfaceOp tree for comparison operations or a single term
    """

    @generate
    def parser():
        # Parse left operand (additive level)
        left = yield additive_parser(constraint)
        loc = left.location

        # Parse zero or more comparison-operator right-operand pairs
        ops_and_rights = []
        while True:
            # Try each comparison operator
            op = yield (EQ | NE | LT | GT | LE | GE).optional()
            if op is None:
                break
            right = yield additive_parser(constraint)
            ops_and_rights.append((op, right))

        # Build left-associative tree
        result = left
        for op, right in ops_and_rights:
            result = SurfaceOp(result, op.value, right, loc)

        return result

    return parser


def logical_and_parser(constraint: ValidIndent) -> P[SurfaceTerm]:
    """Parse logical AND expressions: left && right.

    Lower precedence than comparison, higher than logical OR.

    Args:
        constraint: Layout constraint (passed through to operands)

    Returns:
        SurfaceOp tree for logical AND or a single term
    """

    @generate
    def parser():
        # Parse left operand (comparison level)
        left = yield comparison_parser(constraint)
        loc = left.location

        # Parse zero or more && right-operand pairs
        ops_and_rights = []
        while True:
            op = yield AND.optional()
            if op is None:
                break
            right = yield comparison_parser(constraint)
            ops_and_rights.append((op, right))

        # Build left-associative tree
        result = left
        for op, right in ops_and_rights:
            result = SurfaceOp(result, op.value, right, loc)

        return result

    return parser


def logical_or_parser(constraint: ValidIndent) -> P[SurfaceTerm]:
    """Parse logical OR expressions: left || right.

    Lowest precedence among operators.

    Args:
        constraint: Layout constraint (passed through to operands)

    Returns:
        SurfaceOp tree for logical OR or a single term
    """

    @generate
    def parser():
        # Parse left operand (logical AND level)
        left = yield logical_and_parser(constraint)
        loc = left.location

        # Parse zero or more || right-operand pairs
        ops_and_rights = []
        while True:
            op = yield OR.optional()
            if op is None:
                break
            right = yield logical_and_parser(constraint)
            ops_and_rights.append((op, right))

        # Build left-associative tree
        result = left
        for op, right in ops_and_rights:
            result = SurfaceOp(result, op.value, right, loc)

        return result

    return parser


def op_parser(constraint: ValidIndent) -> P[SurfaceTerm]:
    """Parse operator expressions with proper precedence.

    Entry point for operator parsing. Handles all operator types
    with correct precedence and left-associativity.

    Args:
        constraint: Layout constraint (passed through to operands)

    Returns:
        SurfaceTerm possibly wrapped in SurfaceOp nodes
    """
    return logical_or_parser(constraint)


# =============================================================================
# Lambda and Type Abstraction Parsers
# =============================================================================


def lambda_parser(constraint: ValidIndent) -> P[SurfaceAbs]:
    """Parse a lambda abstraction: λx → e or \\x → e.

    Supports optional type annotation: λx:T → e
    Supports Haddock-style docstrings: λx -- ^ doc → e

    Args:
        constraint: Layout constraint (passed through to body parser)

    Returns:
        SurfaceAbs with the lambda abstraction
    """

    @generate
    def parser():
        # Match lambda symbol (LAMBDA token represents \\ or λ)
        lam_token = yield match_token("LAMBDA")
        loc = lam_token.location

        # Parse one or more parameter names
        var_tokens = yield match_token("IDENT").at_least(1)

        # For each parameter, try to parse optional type annotation
        # Build annotated_params: [(name, type_annotation), ...]
        annotated_params: list[tuple[str, SurfaceType | None]] = []
        for var_token in var_tokens:
            var_name = var_token.value
            # Optional type annotation for this parameter
            # Use type_atom_parser to avoid consuming '->' as part of a type arrow
            var_type = yield (match_symbol(":") >> type_atom_parser()).optional()
            annotated_params.append((var_name, var_type))

        # Optional parameter docstring (-- ^ style) - applies to last param
        param_doc_token = yield match_token("DOCSTRING_INLINE").optional()
        param_docstrings: list[str | None] = []
        if param_doc_token is not None:
            content = param_doc_token.value
            if "^" in content:
                param_docstrings.append(content.split("^", 1)[1].strip())
            else:
                param_docstrings.append("")

        # Parse arrow
        yield match_token("ARROW")

        # Parse body (respecting layout constraint)
        body = yield expr_parser(constraint)

        # Nest lambdas from right to left
        # λx y z → body  =>  λx → (λy → (λz → body))
        result = body
        # Reverse iterate to build nested structure
        for var_name, var_type in reversed(annotated_params):
            result = SurfaceAbs(
                var_name, var_type, result, loc, param_docstrings if result is body else []
            )

        return result

    return parser


def type_abs_parser(constraint: ValidIndent) -> P[SurfaceTypeAbs]:
    """Parse a type abstraction: Λa. e or /\\a. e.

    Args:
        constraint: Layout constraint (passed through to body parser)

    Returns:
        SurfaceTypeAbs with the type abstraction
    """

    @generate
    def parser():
        # Match type lambda symbol (TYPELAMBDA token represents Λ or /\\)
        lam_token = yield match_token("TYPELAMBDA")
        loc = lam_token.location

        # Parse type variable name(s)
        var_tokens = yield match_token("IDENT").at_least(1)

        # Parse dot
        yield match_token("DOT")

        # Parse body (respecting layout constraint)
        body = yield expr_parser(constraint)

        # Build nested type abstractions from right to left
        result = body
        for var_token in reversed(var_tokens):
            result = SurfaceTypeAbs(var_token.value, result, loc)

        return result

    return parser


# =============================================================================
# Pattern Parser (for case alternatives)
# =============================================================================


def pattern_base_parser() -> P[SurfacePattern]:
    """Parse a base pattern (variable or constructor).

    A base pattern is either:
    - A variable pattern: just an identifier
    - A constructor pattern: Constructor [var1 var2 ...]

    Returns:
        SurfacePattern for constructor or SurfacePattern for variable
    """

    @generate
    def parser():
        # Try constructor pattern first (CONSTRUCTOR followed by optional vars)
        con_token = yield match_token("CONSTRUCTOR").optional()
        if con_token is not None:
            constructor = con_token.value
            loc = con_token.location

            # Parse variable bindings (identifiers)
            vars = []
            while True:
                var_result = yield match_token("IDENT").optional()
                if var_result is None:
                    break
                vars.append(var_result.value)

            return SurfacePattern(constructor, vars, loc)

        # Try variable pattern (just an identifier)
        var_token = yield match_token("IDENT").optional()
        if var_token is not None:
            # Variable pattern is just a constructor with no args
            # (treated as a catch-all variable)
            return SurfacePattern(var_token.value, [], var_token.location)

        # No match
        yield fail("expected pattern")

    return parser


def pattern_tuple_parser() -> P[SurfacePattern]:
    """Parse a tuple pattern: (p1, p2, ..., pn).

    Sugar for nested Pair patterns: Pair p1 (Pair p2 (... pn))

    Returns:
        SurfacePatternTuple containing the elements
    """

    @generate
    def parser():
        from systemf.surface.types import SurfacePatternTuple

        open_paren = yield match_symbol("(")
        loc = open_paren.location

        # Parse first element using pattern_parser (handles nested tuples, constructors, vars)
        first = yield pattern_parser()
        elements = [first]

        # Parse comma-separated elements
        while True:
            yield match_symbol(",")
            elem = yield pattern_parser()
            elements.append(elem)

            # Check if we're at the closing paren
            close_paren = yield match_symbol(")").optional()
            if close_paren is not None:
                break

        return SurfacePatternTuple(elements, loc)

    return parser


def pattern_parser() -> P[SurfacePattern]:
    """Parse a pattern: CONSTRUCTOR [ident*], variable, or tuple pattern.

    Returns:
        SurfacePattern with constructor name and variable bindings, or tuple pattern
    """

    @generate
    def parser():
        # Try tuple pattern first (starts with '(')
        tuple_result = yield pattern_tuple_parser().optional()
        if tuple_result is not None:
            return tuple_result

        # Try base pattern (constructor or variable)
        return (yield pattern_base_parser())

    return parser


# =============================================================================
# Case Expression Parser (layout-sensitive)
# =============================================================================


def case_alt(constraint: ValidIndent) -> P[SurfaceBranch]:
    """Parse a single case branch: pattern → expr.

    Args:
        constraint: Layout constraint for the branch body

    Returns:
        SurfaceBranch with pattern and body expression
    """

    @generate
    def parser():
        pat = yield pattern_parser()
        loc = pat.location
        yield match_token("ARROW")

        # Transform constraint for the expression body (similar to let_binding)
        # This prevents the expression from consuming subsequent branches
        expr_constraint: ValidIndent
        match constraint:
            case AtPos(col):
                expr_constraint = AfterPos(col + 1)
            case _:
                expr_constraint = constraint

        body = yield expr_parser(expr_constraint)
        return SurfaceBranch(pat, body, loc)

    return parser


def case_parser(constraint: ValidIndent) -> P[SurfaceCase]:
    """Parse a case expression: case expr of branches.

    Layout-sensitive: captures column after 'of' and uses block_entries
    to parse branches at that indentation level.

    Args:
        constraint: Layout constraint (passed through to scrutinee)

    Returns:
        SurfaceCase with scrutinee and branches
    """

    @generate
    def parser():
        case_token = yield match_keyword("case")
        loc = case_token.location
        scrutinee = yield expr_parser(constraint)
        yield match_keyword("of")

        # Enter layout mode: capture column of first branch token
        col = yield column()
        branches = yield block_entries(AtPos(col), case_alt)

        return SurfaceCase(scrutinee, branches, loc)

    return parser


# =============================================================================
# Let Expression Parser (layout-sensitive)
# =============================================================================


def let_binding(constraint: ValidIndent) -> P[tuple[str, Optional[SurfaceType], SurfaceTerm]]:
    """Parse a single let binding: ident [params] [: type] = expr.

    Supports:
    - Simple binding: x = 1
    - Typed binding: x : Int = 1
    - Function binding: f x y = x + y (desugared to lambda)

    Args:
        constraint: Layout constraint for the binding start column

    Returns:
        Tuple of (var_name, optional_type, value)
    """

    @generate
    def parser():
        var_token = yield match_token("IDENT")
        var_name = var_token.value
        loc = var_token.location

        # Parse optional parameters (for function definitions like "f x y = ...")
        params = []
        while True:
            param_token = yield match_token("IDENT").optional()
            if param_token is None:
                break
            params.append(param_token.value)

        # Optional type annotation (applies to the whole function if params present)
        var_type = yield (match_symbol(":") >> _type_parser).optional()

        yield match_symbol("=")

        # For expression value, use AfterPos to allow spanning multiple columns
        # If constraint is AtPos(col), expression can use columns > col (not >=)
        # This prevents consuming the next binding which is at column col
        expr_constraint: ValidIndent
        match constraint:
            case AtPos(col):
                expr_constraint = AfterPos(col + 1)  # Strictly greater than binding column
            case _:
                expr_constraint = constraint

        value = yield expr_parser(expr_constraint)

        # If we have parameters, build a lambda abstraction
        # f x y = body  becomes  f = \x y -> body
        if params:
            # Build nested lambdas from right to left
            for param in reversed(params):
                value = SurfaceAbs(param, None, value, loc)

        return (var_name, var_type, value)

    return parser


def let_parser(constraint: ValidIndent) -> P[SurfaceTerm]:
    """Parse a let expression: let bindings in expr.

    Layout-sensitive: captures column after 'let' and uses block_entries
    to parse bindings at that indentation level.

    Args:
        constraint: Layout constraint (passed through to expressions)

    Returns:
        SurfaceLet with list of bindings and body
    """

    @generate
    def parser():
        let_token = yield match_keyword("let")
        loc = let_token.location

        # Enter layout mode: capture column of first binding token
        col = yield column()
        bindings = yield block_entries(AtPos(col), let_binding)

        # Validate 'in' keyword is at >= parent's column
        yield must_continue(constraint, "in")
        yield match_keyword("in")
        body = yield expr_parser(constraint)

        return SurfaceLet(bindings, body, loc)

    return parser


# =============================================================================
# If Expression Parser
# =============================================================================


def if_parser(constraint: ValidIndent) -> P[SurfaceIf]:
    """Parse an if-then-else expression: if expr then expr else expr.

    Args:
        constraint: Layout constraint (passed through to branch expressions)

    Returns:
        SurfaceIf with condition and branches
    """

    @generate
    def parser():
        if_token = yield match_keyword("if")
        loc = if_token.location
        cond = yield expr_parser(constraint)
        yield match_keyword("then")
        then_branch = yield expr_parser(constraint)
        yield match_keyword("else")
        else_branch = yield expr_parser(constraint)
        return SurfaceIf(cond, then_branch, else_branch, loc)

    return parser


# =============================================================================
# Main Expression Parser
# =============================================================================


def expr_parser(constraint: ValidIndent) -> P[SurfaceTerm]:
    """Main expression parser - tries all expression forms.

    Tries in order:
    1. Lambda abstraction
    2. Type abstraction
    3. If-then-else
    4. Case expression
    5. Let expression
    6. Operator expressions (includes application)

    Args:
        constraint: Layout constraint for layout-sensitive expressions

    Returns:
        The parsed expression
    """
    return alt(
        lambda_parser(constraint),
        type_abs_parser(constraint),
        if_parser(constraint),
        case_parser(constraint),
        let_parser(constraint),
        op_parser(constraint),
    )


# =============================================================================
# Public API
# =============================================================================


# Type parser setter (for use by declarations.py or type parser module)
def set_type_parser(parser: P[SurfaceType]) -> None:
    """Set the type parser for type annotations and applications.

    This should be called by the module that implements type parsing
    to allow mutual recursion between expression and type parsers.

    Args:
        parser: The type parser to use
    """
    global _type_parser
    _type_parser.become(parser)


__all__ = [
    # Token matching
    "match_token",
    "match_keyword",
    "match_symbol",
    # Atom parsers
    "variable_parser",
    "constructor_parser",
    "literal_parser",
    "paren_parser",
    "atom_base_parser",
    "atom_parser",
    # Pattern parsers
    "pattern_parser",
    # Expression parsers
    "app_parser",
    "lambda_parser",
    "type_abs_parser",
    "if_parser",
    "case_parser",
    "let_parser",
    "let_binding",
    "case_alt",
    "expr_parser",
    # Type parser setup
    "set_type_parser",
]
