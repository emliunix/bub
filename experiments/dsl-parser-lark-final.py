#!/usr/bin/env python3
"""
Workflow DSL Parser - Lark Implementation (Production Ready)

Implements a Haskell-like, indentation-based DSL for workflow definitions.
Uses Lark's built-in Indenter class for Python-style indentation.

Syntax:
    - Indentation-based blocks
    - :: type annotations
    - Primitive types: int, str, bool
    - llm builtin function
    - Function definitions
    - Let bindings
"""

from lark import Lark, Transformer, Token, Tree
from lark.indenter import Indenter
from lark.exceptions import UnexpectedToken, UnexpectedCharacters
from dataclasses import dataclass
from typing import Optional, List, Any
import json
import re

from dsl_ast import (
    Program,
    FunctionDef,
    LetBinding,
    ReturnStmt,
    ExprStmt,
    TypedParam,
    Type,
    Identifier,
    StringLiteral,
    IntegerLiteral,
    FloatLiteral,
    BoolLiteral,
    LLMCall,
)


# =============================================================================
# Source Location Tracking
# =============================================================================


@dataclass
class SourceLoc:
    """Source code location for error reporting."""

    line: int
    column: int
    end_line: Optional[int] = None
    end_column: Optional[int] = None

    def __str__(self) -> str:
        if self.end_line and self.end_line != self.line:
            return f"line {self.line}:{self.column} to line {self.end_line}:{self.end_column}"
        return f"line {self.line}:{self.column}"


# =============================================================================
# Custom Parser Exceptions
# =============================================================================


class WorkflowParseError(Exception):
    """Custom parse error with user-friendly messages."""

    def __init__(
        self,
        message: str,
        loc: Optional[SourceLoc] = None,
        expected: Optional[List[str]] = None,
        got: Optional[str] = None,
    ):
        self.message = message
        self.loc = loc
        self.expected = expected or []
        self.got = got
        super().__init__(self.format_message())

    def format_message(self) -> str:
        parts = ["Parse Error"]
        if self.loc:
            parts.append(f"at {self.loc}")
        parts.append(f": {self.message}")

        if self.expected and self.got:
            parts.append(f"\n  Expected: {', '.join(self.expected)}")
            parts.append(f"\n  Got: {self.got}")

        return "".join(parts)


# =============================================================================
# Grammar Definition
# =============================================================================

# Build grammar with proper escaping
# Triple-quoted strings: """...""" or '''...'''
_TRIPLE_DOUBLE = r'"""[^"]*"""'
_TRIPLE_SINGLE = r"'''[^']*'''"
_SINGLE_DOUBLE = r'"[^"]*"'
_SINGLE_SINGLE = r"'[^']*'"

WORKFLOW_GRAMMAR = rf"""
    ?start: _NL* program

    program: function_def*

    function_def: "def" NAME "(" param_list? ")" return_type? ":" _NL body

    param_list: param ("," param)*

    param: NAME "::" type_expr

    return_type: "->" type_expr

    type_expr: NAME

    body: _INDENT statement+ _DEDENT

    ?statement: let_binding
              | llm_call_stmt
              | return_stmt
              | pass_stmt
              | expr_stmt

    let_binding: "let" NAME "::" type_expr "=" expression _NL

    llm_call_stmt: llm_call _NL

    return_stmt: "return" expression? _NL

    pass_stmt: "pass" _NL

    expr_stmt: expression _NL

    ?expression: atom
               | llm_call

    llm_call: "llm" STRING context_clause?

    context_clause: "with" expression

    ?atom: NAME -> identifier
         | STRING -> string
         | NUMBER -> number
         | "True" -> true
         | "False" -> false

    // Terminals
    NAME: /[a-zA-Z_][a-zA-Z0-9_]*/
    STRING: /{_TRIPLE_DOUBLE}/s | /{_TRIPLE_SINGLE}/s | /{_SINGLE_DOUBLE}/ | /{_SINGLE_SINGLE}/
    NUMBER: /-?\d+(\.\d+)?/

    COMMENT: /#[^\n]*/

    // Newline matches \n plus any following whitespace (important for indenter!)
    _NL: (/\r?\n[\t ]*/ | COMMENT)+

    %declare _INDENT _DEDENT
    %import common.WS_INLINE
    %ignore WS_INLINE
"""


class WorkflowIndenter(Indenter):
    """Custom indenter for Workflow DSL."""

    NL_type = "_NL"
    OPEN_PAREN_types = ["LPAR", "LSQB", "LBRACE"]
    CLOSE_PAREN_types = ["RPAR", "RSQB", "RBRACE"]
    INDENT_type = "_INDENT"
    DEDENT_type = "_DEDENT"
    tab_len = 4


# =============================================================================
# AST Transformer
# =============================================================================


class WorkflowTransformer(Transformer):
    """Transform Lark parse tree into our AST with source locations."""

    def _get_loc_from_token(self, token: Token) -> SourceLoc:
        """Extract source location from a token."""
        return SourceLoc(
            line=token.line,
            column=token.column,
            end_line=getattr(token, "end_line", token.line),
            end_column=getattr(token, "end_column", token.column + len(str(token.value))),
        )

    def _strip_quotes(self, s: str) -> str:
        """Remove quotes from string literal."""
        if (s.startswith('"""') and s.endswith('"""')) or (s.startswith("'''") and s.endswith("'''")):
            return s[3:-3]
        elif (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        return s

    def program(self, items):
        functions = [item for item in items if item is not None and not isinstance(item, Token)]
        return Program(functions=functions)

    def function_def(self, items):
        name_token = items[0]
        name = str(name_token)

        # Parse optional components
        # Grammar: "def" NAME "(" param_list? ")" return_type? ":" _NL body
        # items: [NAME, param_list?, return_type?, body]
        params = []
        return_type = None
        body = []

        # Scan remaining items
        remaining = items[1:]

        # First optional: param_list (list of TypedParam)
        if remaining and isinstance(remaining[0], list):
            # Check if it's param_list (contains TypedParam) or body
            if remaining[0] and isinstance(remaining[0][0], TypedParam):
                params = remaining.pop(0)

        # Second optional: return_type (Type object)
        if remaining and isinstance(remaining[0], Type):
            return_type = remaining.pop(0)

        # Last item should be body (list of statements)
        if remaining:
            body_result = remaining[-1]  # Take the last item as body
            if isinstance(body_result, list):
                body = body_result
            else:
                body = [body_result]

        # Filter out None values (from pass_stmt, etc.)
        body = [stmt for stmt in body if stmt is not None]

        # Extract docstring: if first statement is a string literal, it's the docstring
        doc = None
        if body and isinstance(body[0], ExprStmt) and isinstance(body[0].expr, StringLiteral):
            doc = body[0].expr.value
            body = body[1:]  # Remove docstring from body

        return FunctionDef(name=name, params=params, return_type=return_type, doc=doc, body=body)

    def param_list(self, items):
        return items

    def param(self, items):
        name = str(items[0])
        type_obj = items[1]  # Already a Type object from type_expr
        return TypedParam(name=name, type_=type_obj)

    def type_expr(self, items):
        return Type(name=str(items[0]))

    def return_type(self, items):
        return items[0]

    def body(self, items):
        # Body is the list of statements inside _INDENT/_DEDENT
        # Filter out tokens and None values
        return [item for item in items if item is not None and not isinstance(item, Token)]

    def block(self, items):
        return [item for item in items if not isinstance(item, Token)]

    def let_binding(self, items):
        name = str(items[0])
        type_ = items[1]
        value = items[2]
        return LetBinding(name=name, type_=type_, value=value)

    def llm_call_stmt(self, items):
        return items[0]

    def return_stmt(self, items):
        if items:
            value = items[0]
            if isinstance(value, Token) and value.type == "_NL":
                return ReturnStmt(value=Identifier(name="None"))
            return ReturnStmt(value=value)
        return ReturnStmt(value=Identifier(name="None"))

    def pass_stmt(self, items):
        return None

    def expr_stmt(self, items):
        if items and items[0] is not None:
            return ExprStmt(expr=items[0])
        return None

    def llm_call(self, items):
        prompt_token = items[0]
        prompt = self._strip_quotes(str(prompt_token))

        context = None
        if len(items) > 1:
            context = items[1]

        return LLMCall(prompt=prompt, context=context)

    def context_clause(self, items):
        return items[0]

    def identifier(self, items):
        return Identifier(name=str(items[0]))

    def string(self, items):
        s = str(items[0])
        return StringLiteral(value=self._strip_quotes(s))

    def number(self, items):
        s = str(items[0])
        if "." in s:
            return FloatLiteral(value=float(s))
        return IntegerLiteral(value=int(s))

    def true(self, items):
        return BoolLiteral(value=True)

    def false(self, items):
        return BoolLiteral(value=False)


# =============================================================================
# Parser Class
# =============================================================================


class WorkflowParser:
    """Parser for the Workflow DSL using Lark with indentation support."""

    def __init__(self):
        self.parser = Lark(
            WORKFLOW_GRAMMAR,
            parser="lalr",
            postlex=WorkflowIndenter(),
            debug=False,
            propagate_positions=True,
        )
        self.transformer = WorkflowTransformer()

    def parse(self, text: str) -> Program:
        """Parse workflow DSL text into AST."""
        try:
            tree = self.parser.parse(text)
            return self.transformer.transform(tree)
        except UnexpectedToken as e:
            expected = [str(tok) for tok in e.expected]
            got = str(e.token)
            loc = SourceLoc(line=e.line, column=e.column)

            msg = f"Unexpected token '{e.token.value}'"
            if expected:
                msg += f". Expected: {', '.join(expected)}"

            raise WorkflowParseError(message=msg, loc=loc, expected=expected, got=got) from e
        except UnexpectedCharacters as e:
            loc = SourceLoc(line=e.line, column=e.column)
            raise WorkflowParseError(message=f"Unexpected character: {e.char!r}", loc=loc) from e
        except Exception as e:
            if isinstance(e, WorkflowParseError):
                raise
            raise WorkflowParseError(message=f"Parse error: {str(e)}", loc=None) from e


# =============================================================================
# Example Usage
# =============================================================================

EXAMPLE_WORKFLOW = '''
def analyze_code(filename :: str) -> AnalysisResult:
    """
    Analyze source code for issues.
    Returns structured analysis with findings.
    """
    let content :: str = llm "Read and summarize the file"
    let issues :: list = llm "Find bugs" with content
    return issues


def main():
    let result :: AnalysisResult = analyze_code("src/main.py")
    return result
'''


ERROR_EXAMPLE = """
def bad_function()
    let x = 1
    return x
"""


def main():
    """Demo the parser."""
    print("=" * 70)
    print("Workflow DSL Parser - Lark Implementation (Production Ready)")
    print("=" * 70)
    print()

    print("Test 1: Valid DSL")
    print("-" * 70)
    print(EXAMPLE_WORKFLOW)
    print()

    parser = WorkflowParser()

    try:
        ast = parser.parse(EXAMPLE_WORKFLOW)
        print("✅ Parse successful!")
        print()
        print("AST:")
        print("-" * 70)
        from dsl_ast import ast_to_dict

        print(json.dumps(ast_to_dict(ast), indent=2))
    except WorkflowParseError as e:
        print(f"❌ Parse error: {e}")

    print()
    print("=" * 70)
    print("Test 2: Invalid DSL (Missing colon)")
    print("-" * 70)
    print(ERROR_EXAMPLE)
    print()

    try:
        ast = parser.parse(ERROR_EXAMPLE)
        print("✅ Parse successful!")
    except WorkflowParseError as e:
        print(f"❌ Parse error:")
        print(f"   {e}")


if __name__ == "__main__":
    main()
