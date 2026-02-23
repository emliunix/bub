#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#     "tatsu>=5.13.0",
# ]
# requires-python = ">=3.12"
# ///

"""
Workflow DSL Parser - TatSu Implementation (Final Working Version)

Uses brace-based blocks instead of indentation for TatSu compatibility.
Converts Python-style indentation to braces in preprocessing.
"""

from typing import Optional, List, Any, Union
import tatsu
from tatsu import exceptions

# Import shared AST types
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
    LLMCall,
    Expression,
    Statement,
)


# =============================================================================
# Indentation to Braces Preprocessor
# =============================================================================


class IndentationPreprocessor:
    """Converts Python-style indentation to brace-delimited blocks."""

    def process(self, text: str) -> str:
        """Convert Python-style indentation to braces."""
        lines = text.split("\n")
        result = []
        indent_stack = [0]

        for line in lines:
            stripped = line.lstrip()

            # Skip empty lines and comments
            if not stripped or stripped.startswith("#"):
                continue

            indent = len(line) - len(stripped)

            # Handle dedent
            while indent < indent_stack[-1]:
                indent_stack.pop()
                result.append("}")

            # Handle indent
            if indent > indent_stack[-1]:
                # Remove colon from previous line if present
                if result and result[-1].endswith(":"):
                    result[-1] = result[-1][:-1]
                result.append("{")
                indent_stack.append(indent)

            result.append(stripped)

        # Close remaining blocks
        while len(indent_stack) > 1:
            indent_stack.pop()
            result.append("}")

        return "\n".join(result)


# =============================================================================
# Grammar Definition
# =============================================================================

WORKFLOW_GRAMMAR = r"""@@grammar::WorkflowDSL
@@left_recursion :: True

start = program $;

program = {function_def}* ;

function_def = 'def' name '(' ')' '{' {statement}* '}'
             | 'def' name '(' ')' '->' type '{' {statement}* '}'
             | 'def' name '(' params ')' '{' {statement}* '}'
             | 'def' name '(' params ')' '->' type '{' {statement}* '}'
;

return_type = type;

params = ','.{param}+ ;

param = name '::' type;

type = name;

statement = let_binding | return_stmt | llm_call_standalone | pass_stmt ;

pass_stmt = 'pass' ;

let_binding = 'let' name '::' type '=' expression ;

return_stmt = 'return' expression ;

llm_call_standalone = llm_call ;

llm_call = 'llm' string [context_clause] ;

context_clause = 'with' expression ;

expression = llm_call | string | number | identifier ;

identifier = name;

name = /[a-zA-Z_][a-zA-Z0-9_]*/ ;

string = '"' /[^"]*/ '"' | "'" /[^']*/ "'" ;

number = /-?[0-9]+([.][0-9]+)?/ ;
"""


# =============================================================================
# Semantic Actions
# =============================================================================


class WorkflowSemantics:
    """Converts TatSu parse tree to shared AST."""

    def program(self, ast):
        if ast is None:
            return []
        if not isinstance(ast, list):
            return [ast]
        return ast

    def start(self, ast):
        if ast is None:
            return Program(functions=[])
        if not isinstance(ast, list):
            ast = [ast]
        return Program(functions=[f for f in ast if isinstance(f, FunctionDef)])

    def function_def(self, ast):
        """Process function definition."""
        if ast is None:
            return None

        # Handle two structures:
        # No params, no return_type: ['def', name, '(', ')', '{', [statements], '}']
        # No params, with return_type: ['def', name, '(', ')', '->', return_type, '{', [statements], '}']
        # With params, no return_type: ['def', name, '(', params, ')', '{', [statements], '}']
        # With params, with return_type: ['def', name, '(', params, ')', '->', return_type, '{', [statements], '}']

        name = str(ast[1])

        # Check for params at index 3
        params = []
        idx = 3
        if ast[idx] != ")":
            # Has params
            params_data = ast[idx]
            params = self._process_params(params_data)
            idx += 1
        # Skip ')'
        if idx < len(ast) and ast[idx] == ")":
            idx += 1

        # Check for return_type (type after '->')
        return_type = None
        if idx < len(ast) and ast[idx] == "->":
            idx += 1  # Skip '->'
            if idx < len(ast) and ast[idx] not in ["{", "}"]:
                return_type = Type(str(ast[idx]))
                idx += 1

        # Skip '{'
        if idx < len(ast) and ast[idx] == "{":
            idx += 1

        # Get body
        body = []
        if idx < len(ast) and ast[idx] != "}":
            body_data = ast[idx]
            if isinstance(body_data, list):
                body = [s for s in body_data if s is not None]
            idx += 1

        return FunctionDef(
            name=name,
            params=params,
            return_type=return_type,
            doc=None,
            body=body,
        )

    def _process_params(self, params_data):
        """Process parameter list from TatSu."""
        if params_data is None:
            return []

        result = []
        # params_data is a list from TatSu's ','.{param}+
        if isinstance(params_data, list):
            for p in params_data:
                if p is not None:
                    # Each param from TatSu is [name, '::', type]
                    if isinstance(p, (list, tuple)) and len(p) >= 3:
                        result.append(TypedParam(name=str(p[0]), type_=Type(str(p[2]))))
        return result

    def param(self, ast):
        """Process single parameter - just return as-is."""
        return ast

    def return_type(self, ast):
        return ast

    def statement(self, ast):
        return ast

    def pass_stmt(self, ast):
        """Process pass statement - returns None to be filtered out."""
        return None

    def let_binding(self, ast):
        """Process let binding: let name :: type = expression"""
        if ast is None or len(ast) < 6:
            return None
        # ast: ['let', name, '::', type, '=', value]
        name = str(ast[1])
        type_name = str(ast[3])
        value = ast[5]

        # Process value
        if isinstance(value, str):
            # Try to convert to number
            try:
                if "." in value:
                    value = FloatLiteral(value=float(value))
                else:
                    value = IntegerLiteral(value=int(value))
            except ValueError:
                value = Identifier(name=value)
        elif not isinstance(value, (IntegerLiteral, FloatLiteral, StringLiteral, LLMCall, Identifier)):
            value = Identifier(name=str(value))

        return LetBinding(name=name, type_=Type(type_name), value=value)

    def return_stmt(self, ast):
        """Process return statement: return expression"""
        if ast is None or len(ast) < 2:
            return None
        value = ast[1]

        # Process value
        if isinstance(value, str):
            try:
                if "." in value:
                    value = FloatLiteral(value=float(value))
                else:
                    value = IntegerLiteral(value=int(value))
            except ValueError:
                value = Identifier(name=value)
        elif not isinstance(value, (IntegerLiteral, FloatLiteral, StringLiteral, LLMCall, Identifier)):
            value = Identifier(name=str(value))

        return ReturnStmt(value=value)

    def llm_call_standalone(self, ast):
        return ast

    def llm_call(self, ast):
        """Process LLM call: llm "prompt" [with context]"""
        if ast is None:
            return LLMCall(prompt="", context=None)

        prompt = ""
        context = None

        if len(ast) > 1:
            prompt_data = ast[1]
            if isinstance(prompt_data, str):
                prompt = prompt_data

        if len(ast) > 2 and ast[2] is not None:
            context_data = ast[2]
            if isinstance(context_data, str):
                context = Identifier(name=context_data)
            else:
                context = context_data

        return LLMCall(prompt=prompt, context=context)

    def context_clause(self, ast):
        return ast

    def expression(self, ast):
        return ast

    def identifier(self, ast):
        if isinstance(ast, str):
            return Identifier(name=ast)
        return ast

    def string(self, ast):
        if isinstance(ast, str):
            return StringLiteral(value=ast)
        return StringLiteral(value="")

    def number(self, ast):
        if isinstance(ast, str):
            try:
                if "." in ast:
                    return FloatLiteral(value=float(ast))
                else:
                    return IntegerLiteral(value=int(ast))
            except ValueError:
                return IntegerLiteral(value=0)
        return IntegerLiteral(value=0)


# =============================================================================
# Main Parser
# =============================================================================


class WorkflowParser:
    """Main parser interface."""

    def __init__(self):
        self.preprocessor = IndentationPreprocessor()
        self.grammar = tatsu.compile(WORKFLOW_GRAMMAR)

    def parse(self, text: str) -> Program:
        """Parse DSL text into AST."""
        preprocessed = self.preprocessor.process(text)
        semantics = WorkflowSemantics()

        try:
            result = self.grammar.parse(preprocessed, semantics=semantics)
        except exceptions.FailedToken as e:
            line = getattr(e, "line", "?")
            column = getattr(e, "column", "?")
            raise SyntaxError(f"Parse error at line {line}, column {column}: {e}") from e
        except exceptions.FailedParse as e:
            line = getattr(e, "line", "?")
            column = getattr(e, "column", "?")
            raise SyntaxError(f"Parse error at line {line}, column {column}: {e}") from e
        except Exception as e:
            raise SyntaxError(f"Parse error: {e}") from e

        if isinstance(result, Program):
            return result

        if isinstance(result, list):
            return Program(functions=[f for f in result if isinstance(f, FunctionDef)])

        return Program(functions=[])


if __name__ == "__main__":
    # Run tests
    import sys

    sys.path.insert(0, ".")
    from dsl_tests import run_parser_tests

    run_parser_tests(WorkflowParser, "TatSu")
