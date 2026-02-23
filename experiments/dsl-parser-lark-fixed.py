#!/usr/bin/env python3
"""
Workflow DSL Parser - Lark Implementation (Proper Indentation Support)

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
from dataclasses import dataclass
from typing import Optional, List, Any, Union
import json


# =============================================================================
# AST Node Definitions
# =============================================================================


@dataclass
class Type:
    name: str


@dataclass
class TypedParam:
    name: str
    type_: Type


@dataclass
class Identifier:
    name: str


@dataclass
class Literal:
    value: Union[str, int, float, bool]


@dataclass
class LetBinding:
    name: str
    type_: Type
    value: Any  # Expression


@dataclass
class LLMCall:
    prompt: str
    context: Optional[Any] = None


@dataclass
class ReturnStmt:
    value: Any


@dataclass
class FunctionDef:
    name: str
    params: List[TypedParam]
    return_type: Optional[Type]
    doc: Optional[str]
    body: List[Any]


@dataclass
class Program:
    functions: List[FunctionDef]


# =============================================================================
# Lark Grammar with Proper Indentation Support
# =============================================================================

WORKFLOW_GRAMMAR = r"""
    ?start: _NL* program

    program: function_def*

    function_def: "def" NAME "(" param_list? ")" return_type? ":" _NL body

    param_list: param ("," param)*

    param: NAME "::" type_expr

    return_type: "->" type_expr

    type_expr: NAME

    body: docstring block
        | block

    docstring: STRING _NL

    block: _INDENT statement+ _DEDENT

    ?statement: let_binding
              | llm_call_stmt
              | return_stmt
              | expression _NL

    let_binding: "let" NAME "::" type_expr "=" expression _NL

    llm_call_stmt: llm_call _NL

    return_stmt: "return" expression _NL

    llm_call: "llm" STRING context_clause?

    context_clause: "with" expression

    ?expression: atom
               | llm_call

    atom: NAME -> identifier
        | STRING -> string
        | NUMBER -> number
        | "True" -> true
        | "False" -> false

    // Terminals
    NAME: /[a-zA-Z_][a-zA-Z0-9_]*/
    STRING: /"[^"]*"/ | /'[^']*'/
    NUMBER: /-?\d+(\.\d+)?/

    COMMENT: /#[^\n]*/

    // Newline matches \n plus any following whitespace (important for indenter!)
    _NL: (/\r?\n[\t ]*/ | COMMENT)+

    %declare _INDENT _DEDENT
    %import common.WS_INLINE
    %ignore WS_INLINE
"""


class WorkflowIndenter(Indenter):
    """
    Custom indenter for Workflow DSL.

    Based on PythonIndenter but customized for our grammar.
    """

    NL_type = "_NL"
    OPEN_PAREN_types = ["LPAR", "LSQB", "LBRACE"]
    CLOSE_PAREN_types = ["RPAR", "RSQB", "RBRACE"]
    INDENT_type = "_INDENT"
    DEDENT_type = "_DEDENT"
    tab_len = 4


# =============================================================================
# Transformer: Convert Lark Tree to AST
# =============================================================================


class WorkflowTransformer(Transformer):
    """Transform Lark parse tree into our AST."""

    def program(self, items):
        # Filter out None and _NL tokens
        functions = [item for item in items if item is not None and not isinstance(item, Token)]
        return Program(functions=functions)

    def function_def(self, items):
        # Items: NAME, param_list?, return_type?, body (which contains docstring and block)
        name = str(items[0])

        # Parse optional components
        params = []
        return_type = None

        idx = 1
        if idx < len(items) and isinstance(items[idx], list):
            params = items[idx]
            idx += 1

        if idx < len(items) and isinstance(items[idx], Type):
            return_type = items[idx]
            idx += 1

        # Last item is body tuple: (docstring?, statements)
        doc = None
        body = []
        if idx < len(items):
            body_result = items[idx]
            if isinstance(body_result, tuple):
                doc, body = body_result
            elif isinstance(body_result, list):
                body = body_result

        return FunctionDef(name=name, params=params, return_type=return_type, doc=doc, body=body)

    def body(self, items):
        # Body can be: docstring block OR just block
        if len(items) == 2 and isinstance(items[0], str):
            # Has docstring: (docstring, block)
            return (items[0], items[1])
        elif len(items) == 1:
            # No docstring: just block
            return (None, items[0])
        else:
            return (None, items)
        self.transformer = WorkflowTransformer()

    def parse(self, text: str) -> Program:
        """Parse workflow DSL text into AST."""
        tree = self.parser.parse(text)
        return self.transformer.transform(tree)


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


def main():
    """Demo the parser."""
    print("=" * 70)
    print("Workflow DSL Parser - Lark Implementation (with Indenter)")
    print("=" * 70)
    print()
    print("Input DSL:")
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
        print(json.dumps(ast, default=lambda o: o.__dict__, indent=2))
    except Exception as e:
        print(f"❌ Parse error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
