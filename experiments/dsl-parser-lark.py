#!/usr/bin/env python3
"""
Workflow DSL Parser - Lark Implementation

Implements a Haskell-like, indentation-based DSL for workflow definitions.

Syntax:
    - Indentation-based blocks
    - :: type annotations
    - Primitive types: int, str, bool
    - llm builtin function
    - Function definitions
    - Let bindings
"""

from lark import Lark, Transformer, Tree, Token
from lark.indenter import Indenter
from dataclasses import dataclass
from typing import Optional, List, Any
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
class LetBinding:
    name: str
    type_: Type
    value: Any  # Expression


@dataclass
class LLMCall:
    prompt: str
    context: Optional[Any] = None


@dataclass
class FunctionDef:
    name: str
    params: List[TypedParam]
    return_type: Type
    doc: Optional[str]
    body: List[Any]  # Statements


@dataclass
class Program:
    functions: List[FunctionDef]


# =============================================================================
# Lark Grammar Definition
# =============================================================================

WORKFLOW_GRAMMAR = r"""
    ?start: program

    program: function_def*

    function_def: "def" name "(" [param_list] ")" ["->" type] ":" docstring block
                | "def" name "(" [param_list] ")" "::" type block

    param_list: param ("," param)*

    param: NAME "::" type

    type: NAME

    docstring: STRING

    block: _INDENT statement+ _DEDENT

    ?statement: let_binding
              | llm_call
              | return_stmt

    let_binding: "let" NAME "::" type "=" expression

    llm_call: "llm" STRING [context_clause]

    context_clause: "with" expression

    return_stmt: "return" expression

    ?expression: NAME
               | STRING
               | NUMBER
               | llm_call

    // Terminals
    NAME: /[a-zA-Z_][a-zA-Z0-9_]*/
    STRING: /"[^"]*"/
         | /'[^']*'/
    NUMBER: /-?\d+(\.\d+)?/

    COMMENT: /#.*/

    %import common.WS_INLINE
    %ignore WS_INLINE
    %ignore COMMENT
"""


class TreeIndenter(Indenter):
    """Custom indenter for Lark to handle Python-style indentation."""

    NL_type = "_NEWLINE"
    OPEN_PAREN_types = []
    CLOSE_PAREN_types = []
    INDENT_type = "_INDENT"
    DEDENT_type = "_DEDENT"
    tab_len = 4


# =============================================================================
# Transformer: Convert Lark Tree to AST
# =============================================================================


class WorkflowTransformer(Transformer):
    """Transform Lark parse tree into our AST."""

    def program(self, items):
        return Program(functions=list(items))

    def function_def(self, items):
        # items: [name, params, return_type?, docstring?, block]
        name = str(items[0])
        params = items[1] if items[1] else []

        # Find return type
        return_type = Type("void")
        doc = None
        body_start = 2

        for i, item in enumerate(items[2:], 2):
            if isinstance(item, Type):
                return_type = item
                body_start = i + 1
            elif isinstance(item, str) and item.startswith('"'):
                doc = item
                body_start = i + 1
            elif isinstance(item, list):
                body = item
                break

        return FunctionDef(
            name=name,
            params=params,
            return_type=return_type,
            doc=doc,
            body=items[-1] if isinstance(items[-1], list) else [],
        )

    def param_list(self, items):
        return list(items)

    def param(self, items):
        name = str(items[0])
        type_ = items[1]
        return TypedParam(name=name, type_=type_)

    def type(self, items):
        return Type(name=str(items[0]))

    def let_binding(self, items):
        name = str(items[0])
        type_ = items[1]
        value = items[2]
        return LetBinding(name=name, type_=type_, value=value)

    def llm_call(self, items):
        prompt = str(items[0])
        context = items[1] if len(items) > 1 else None
        return LLMCall(prompt=prompt, context=context)

    def return_stmt(self, items):
        return items[0]

    def NAME(self, token):
        return str(token)

    def STRING(self, token):
        return str(token)

    def NUMBER(self, token):
        if "." in str(token):
            return float(token)
        return int(token)


# =============================================================================
# Parser Interface
# =============================================================================


class WorkflowParser:
    """Main parser interface for Workflow DSL."""

    def __init__(self):
        # Note: Lark's indentation support requires postlex transformer
        # For simplicity, we'll use a basic version without full indentation
        self.parser = Lark(WORKFLOW_GRAMMAR, parser="lalr", debug=True, propagate_positions=True)
        self.transformer = WorkflowTransformer()

    def parse(self, text: str) -> Program:
        """Parse workflow DSL text into AST."""
        # Pre-process: handle indentation manually for now
        text = self._preprocess_indentation(text)
        tree = self.parser.parse(text)
        return self.transformer.transform(tree)

    def _preprocess_indentation(self, text: str) -> str:
        """
        Simple indentation preprocessor.
        Converts indentation to explicit INDENT/DEDENT tokens.
        """
        lines = text.split("\n")
        result = []
        indent_stack = [0]

        for line in lines:
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue

            indent = len(line) - len(stripped)

            if indent > indent_stack[-1]:
                result.append("_INDENT")
                indent_stack.append(indent)
            elif indent < indent_stack[-1]:
                while indent < indent_stack[-1]:
                    indent_stack.pop()
                    result.append("_DEDENT")

            result.append(stripped)

        # Close remaining blocks
        while len(indent_stack) > 1:
            indent_stack.pop()
            result.append("_DEDENT")

        return "\n".join(result)


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
    let issues :: list = llm "Find bugs in the code" with content
    return issues


def main():
    let result :: AnalysisResult = analyze_code("src/main.py")
    return result
'''


def main():
    """Demo the parser."""
    parser = WorkflowParser()

    print("=" * 70)
    print("Workflow DSL Parser - Lark Implementation")
    print("=" * 70)
    print()
    print("Input DSL:")
    print("-" * 70)
    print(EXAMPLE_WORKFLOW)
    print()

    try:
        ast = parser.parse(EXAMPLE_WORKFLOW)
        print("Parse successful!")
        print()
        print("AST:")
        print("-" * 70)
        print(json.dumps(ast, default=lambda o: o.__dict__, indent=2))
    except Exception as e:
        print(f"Parse error: {e}")
        raise


if __name__ == "__main__":
    main()
