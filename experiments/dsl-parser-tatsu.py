#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#     "tatsu>=5.13.0",
# ]
# requires-python = ">=3.12"
# ///

"""
Workflow DSL Parser - TatSu Implementation

Implements a Haskell-like, indentation-based DSL for workflow definitions using TatSu PEG parser.

Syntax:
    - Indentation-based blocks
    - :: type annotations
    - Primitive types: int, str, bool
    - llm builtin function
    - Function definitions
    - Let bindings
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Union
import json
import tatsu


# =============================================================================
# AST Node Definitions
# =============================================================================


@dataclass
class Type:
    """Type annotation node."""

    name: str


@dataclass
class TypedParam:
    """Function parameter with type annotation."""

    name: str
    type_: Type


@dataclass
class LetBinding:
    """Let binding: let name :: type = expression."""

    name: str
    type_: Type
    value: Any  # Expression


@dataclass
class LLMCall:
    """LLM builtin call: llm "prompt" [with context]."""

    prompt: str
    context: Optional[Any] = None


@dataclass
class ReturnStmt:
    """Return statement."""

    value: Any


@dataclass
class FunctionDef:
    """Function definition with docstring and body."""

    name: str
    params: List[TypedParam]
    return_type: Type
    doc: Optional[str]
    body: List[Any]  # Statements


@dataclass
class Program:
    """Root program node containing all function definitions."""

    functions: List[FunctionDef]


@dataclass
class Identifier:
    """Variable reference."""

    name: str


@dataclass
class Literal:
    """String or numeric literal."""

    value: Union[str, int, float]


# =============================================================================
# Grammar Definition
# =============================================================================

WORKFLOW_GRAMMAR = (
    r"""
    @@grammar::WorkflowDSL
    @@left_recursion :: True
    
    # Entry point
    start = program $;
    
    # Program contains zero or more function definitions
    program = function_def:* ;
    
    # Function definition: def name(params) -> type: docstring block
    function_def =
        | 'def' name:name '(' ~ param_list:? ')' '->' return_type:type ':' docstring:? block:statement_block
        | 'def' name:name '(' ~ param_list:? ')' '::' return_type:type block:statement_block
    ;
    
    # Parameter list: comma-separated typed parameters
    param_list = ','.{param}+ ;
    
    # Single typed parameter: name :: type
    param = name:name '::' type:type ;
    
    # Type annotation
    type = name:name ;
    
    # Docstring (triple-quoted string)
    docstring = doc:docstring_literal ;
    
    docstring_literal = '"""
    ' /(?s)(.*?)(?=""")/ '
    """' ;
    
    # Statement block (handles indentation)
    statement_block = statements:statement:+ ;
    
    # Statements
    statement = 
        | let_binding
        | return_stmt
        | llm_call
    ;
    
    # Let binding: let name :: type = expression
    let_binding = 'let' name:name '::' type:type '=' value:expression ;
    
    # Return statement: return expression
    return_stmt = 'return' value:expression ;
    
    # LLM call: llm "prompt" [with context]
    llm_call = 'llm' prompt:string context_clause:? ;
    
    # Context clause: with expression
    context_clause = 'with' context:expression ;
    
    # Expressions
    expression =
        | llm_call
        | string
        | number
        | name
    ;
    
    # Terminals
    name = /[a-zA-Z_][a-zA-Z0-9_]*/ ;
    
    string = '"' value:/[^"]*/ '"' 
           | "'" value:/[^']*/ "'"
    ;
    
    number = value:decimal ;
    
    decimal = /-?\d+(\.\d+)?/ ;
    
    # Whitespace and comments
    @whitespace
    @ignorecase :: False
    
    # Custom whitespace handling
    @whitespace :: /[ \t]*(#[^\n]*\n[ \t]*|(?s)/\*.*?\*/[ \t]*)*/
"""
)


# =============================================================================
# Indentation Preprocessor
# =============================================================================


class IndentationPreprocessor:
    """
    Preprocesses Python-style indentation into explicit INDENT/DEDENT tokens.
    This is necessary because TatSu doesn't have built-in indentation support
    like Lark's Indenter.
    """

    INDENT_TOKEN = "__INDENT__"
    DEDENT_TOKEN = "__DEDENT__"

    def process(self, text: str) -> str:
        """
        Convert Python-style indentation to explicit tokens.

        The algorithm:
        1. Track current indentation level
        2. When indentation increases: insert INDENT token
        3. When indentation decreases: insert DEDENT token(s)
        4. Mark statement boundaries with NEWLINE
        """
        lines = text.split("\n")
        result = []
        indent_stack = [0]

        for line in lines:
            stripped = line.lstrip()

            # Skip empty lines and comment-only lines
            if not stripped or stripped.startswith("#"):
                continue

            # Calculate indentation level
            indent = len(line) - len(stripped)

            # Handle indentation changes
            if indent > indent_stack[-1]:
                # Increase indent
                result.append(self.INDENT_TOKEN)
                indent_stack.append(indent)
            elif indent < indent_stack[-1]:
                # Decrease indent - may need multiple DEDENTs
                while indent < indent_stack[-1]:
                    indent_stack.pop()
                    result.append(self.DEDENT_TOKEN)

            # Add the actual line content
            result.append(stripped)
            result.append("\n")  # Explicit newline for statement separation

        # Close any remaining open blocks
        while len(indent_stack) > 1:
            indent_stack.pop()
            result.append(self.DEDENT_TOKEN)

        return " ".join(result)

    def restore_structure(self, text: str) -> str:
        """
        Alternative: Use braces to represent blocks instead of INDENT/DEDENT.
        This makes the grammar simpler.
        """
        lines = text.split("\n")
        result = []
        indent_stack = [0]

        for line in lines:
            stripped = line.lstrip()

            # Skip empty lines and comments
            if not stripped or stripped.startswith("#"):
                continue

            indent = len(line) - len(stripped)

            # Handle dedent (close blocks)
            while indent < indent_stack[-1]:
                indent_stack.pop()
                result.append("}")

            # Handle indent (open new block)
            if indent > indent_stack[-1]:
                # Remove the colon from previous line if present
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
# Grammar with Brace-Based Blocks (Simpler for TatSu)
# =============================================================================

WORKFLOW_GRAMMAR_BRACES = (
    r"""
    @@grammar::WorkflowDSL
    @@left_recursion :: True
    
    # Entry point
    start = program $;
    
    # Program contains zero or more function definitions
    program = function_def:* ;
    
    # Function definition with brace-delimited block
    function_def =
        | 'def' name:name '(' ~ ')' '->' return_type:type ':' docstring:? '{' body:statement:* '}'
        | 'def' name:name '(' ~ param_list:params ')' '->' return_type:type ':' docstring:? '{' body:statement:* '}'
    ;
    
    # Parameter list: comma-separated typed parameters
    params = ','.{param}+ ;
    
    # Single typed parameter: name :: type
    param = name:name '::' type:type ->
        TypedParam(name=$name, type_=Type(name=$type))
    ;
    
    # Type annotation
    type = name:name ;
    
    # Docstring (triple-quoted string)
    docstring = '"""
    ' doc:/(?s)(.*?)(?=""")/ '
    """' ;
    
    # Statements
    statement = 
        | let_binding
        | return_stmt
        | llm_call_standalone
    ;
    
    # Let binding: let name :: type = expression
    let_binding = 'let' name:name '::' type:type '=' value:expression ';' ->
        LetBinding(name=$name, type_=Type(name=$type), value=$value)
    ;
    
    # Return statement: return expression
    return_stmt = 'return' value:expression ';' ->
        ReturnStmt(value=$value)
    ;
    
    # Standalone LLM call (not in expression context)
    llm_call_standalone = call:llm_call ';' -> $call
    ;
    
    # LLM call: llm "prompt" [with context]
    llm_call = 'llm' prompt:string context_clause:? ->
        LLMCall(prompt=$prompt, context=$1)
    ;
    
    # Context clause: with expression
    context_clause = 'with' context:expression -> $context;
    
    # Expressions
    expression =
        | llm_call
        | string
        | number
        | identifier
    ;
    
    identifier = name:name -> Identifier(name=$name) ;
    
    # Terminals
    name = /[a-zA-Z_][a-zA-Z0-9_]*/ ;
    
    string = '"' value:/[^"]*/ '"' 
           | "'" value:/[^']*/ "'"
    ;
    
    number = value:/-?\d+(\.\d+)?/ -> Literal(value=float($value) if '.' in $value else int($value)) ;
"""
)


# =============================================================================
# Semantic Actions for AST Construction
# =============================================================================


class WorkflowSemantics:
    """
    Semantic actions for the workflow DSL grammar.

    This class defines methods that are called during parsing to construct
    the AST nodes. Each method corresponds to a grammar rule.
    """

    def start(self, ast):
        """Process the start rule - returns the Program node."""
        if ast is None:
            return Program(functions=[])
        if not isinstance(ast, list):
            ast = [ast]
        return Program(functions=ast)

    def program(self, ast):
        """Collect all function definitions."""
        if ast is None:
            return []
        if not isinstance(ast, list):
            return [ast]
        return ast

    def function_def(self, ast):
        """
        Process function definition.

        ast structure varies based on which alternative matched:
        - No params: [name, return_type, docstring?, body]
        - With params: [name, params, return_type, docstring?, body]
        """
        if ast is None:
            return None

        # Determine which form we have based on length and types
        if len(ast) == 4:
            # def name() -> type: docstring { body }
            name, return_type, doc, body = ast
            params = []
        elif len(ast) == 5:
            # def name(params) -> type: docstring { body }
            name, params, return_type, doc, body = ast
            if not isinstance(params, list):
                params = [params]
        else:
            # Try to parse dynamically
            name = ast[0]
            body = ast[-1]

            # Look for params (list), return_type (Type), doc (str or None)
            params = []
            return_type = Type("void")
            doc = None

            for item in ast[1:-1]:
                if isinstance(item, list) and item and isinstance(item[0], TypedParam):
                    params = item
                elif isinstance(item, str) and '"""' in item:
                    doc = item
                elif isinstance(item, Type):
                    return_type = item

        # Ensure body is a list
        if body is None:
            body = []
        elif not isinstance(body, list):
            body = [body]

        # Extract docstring if present (it will be a tuple from the docstring rule)
        if isinstance(doc, tuple) and len(doc) == 2:
            doc = doc[1]  # Extract the content

        return FunctionDef(
            name=str(name),
            params=params if params else [],
            return_type=Type(str(return_type)) if isinstance(return_type, str) else return_type,
            doc=doc if doc and doc != "None" else None,
            body=body,
        )

    def params(self, ast):
        """Process parameter list."""
        if ast is None:
            return []
        if not isinstance(ast, list):
            return [ast]
        return ast

    def param(self, ast):
        """Process single parameter: name :: type."""
        if ast is None or len(ast) < 2:
            return TypedParam(name="", type_=Type("void"))
        name, type_name = ast[0], ast[1]
        return TypedParam(name=str(name), type_=Type(str(type_name)))

    def type(self, ast):
        """Process type annotation."""
        if ast is None:
            return Type("void")
        return Type(str(ast))

    def docstring(self, ast):
        """Process docstring - return the content."""
        if ast is None:
            return None
        if isinstance(ast, tuple) and len(ast) >= 2:
            return ast[1]
        return str(ast)

    def statement(self, ast):
        """Process statement."""
        return ast

    def let_binding(self, ast):
        """Process let binding: let name :: type = value."""
        if ast is None or len(ast) < 3:
            return LetBinding(name="", type_=Type("void"), value=None)
        name, type_name, value = ast[0], ast[1], ast[2]
        return LetBinding(name=str(name), type_=Type(str(type_name)), value=value)

    def return_stmt(self, ast):
        """Process return statement."""
        if ast is None:
            return ReturnStmt(value=None)
        return ReturnStmt(value=ast)

    def llm_call(self, ast):
        """Process LLM call: llm "prompt" [with context]."""
        if ast is None:
            return LLMCall(prompt="", context=None)

        if isinstance(ast, list) and len(ast) >= 1:
            prompt = str(ast[0])
            context = ast[1] if len(ast) > 1 else None
        else:
            prompt = str(ast)
            context = None

        return LLMCall(prompt=prompt, context=context)

    def context_clause(self, ast):
        """Process context clause: with expression."""
        if ast is None or len(ast) < 1:
            return None
        # ast[0] is the expression after 'with'
        return ast[0] if ast else None

    def expression(self, ast):
        """Process expression."""
        return ast

    def identifier(self, ast):
        """Process identifier reference."""
        if ast is None:
            return Identifier(name="")
        return Identifier(name=str(ast))

    def string(self, ast):
        """Process string literal."""
        if ast is None:
            return Literal(value="")
        if isinstance(ast, tuple):
            return Literal(value=str(ast[1]))
        if isinstance(ast, str):
            return Literal(value=ast)
        return Literal(value=str(ast))

    def number(self, ast):
        """Process numeric literal."""
        if ast is None:
            return Literal(value=0)

        try:
            if isinstance(ast, str):
                if "." in ast:
                    return Literal(value=float(ast))
                return Literal(value=int(ast))
            return Literal(value=ast)
        except (ValueError, TypeError):
            return Literal(value=0)


# =============================================================================
# Simplified Grammar (Working Version)
# =============================================================================

# This is a simpler, working version of the grammar that avoids complex semantic actions
WORKFLOW_GRAMMAR_SIMPLE = (
    r"""
    @@grammar::WorkflowDSL
    @@left_recursion :: True
    
    start = program $;
    
    program = function_def:* ;
    
    function_def = 'def' name '(' ')' '->' type ':' docstring:? '{' body:statement:* '}'
                 | 'def' name '(' params ')' '->' type ':' docstring:? '{' body:statement:* '}'
    ;
    
    params = ','.{param}+ ;
    
    param = name '::' type ;
    
    type = name ;
    
    docstring = '"""
    ' /(?s)(.*?)(?=""")/ '
    """' ;
    
    statement = let_binding | return_stmt | llm_call_standalone ;
    
    let_binding = 'let' name '::' type '=' expression ';' ;
    
    return_stmt = 'return' expression ';' ;
    
    llm_call_standalone = llm_call ';' ;
    
    llm_call = 'llm' string context_clause:? ;
    
    context_clause = 'with' expression ;
    
    expression = llm_call | string | number | name ;
    
    name = /[a-zA-Z_][a-zA-Z0-9_]*/ ;
    
    string = '"' /[^"]*/ '"' | "'" /[^']*/ "'" ;
    
    number = /-?\d+(\.\d+)?/ ;
"""
)


# =============================================================================
# AST Builder - Converts TatSu Parse Tree to AST
# =============================================================================


class ASTBuilder:
    """
    Converts TatSu parse tree (as dict/list structure) to typed AST.

    TatSu returns a nested structure of dicts and lists by default.
    This builder converts that to our typed dataclass AST.
    """

    def build(self, parse_tree: Any) -> Program:
        """Convert parse tree to AST."""
        if isinstance(parse_tree, dict):
            return self._build_program(parse_tree)
        elif isinstance(parse_tree, list):
            return Program(functions=[self._build_function_def(f) for f in parse_tree if f])
        else:
            return Program(functions=[])

    def _build_program(self, tree: dict) -> Program:
        """Build Program node."""
        functions = tree.get("function_def", [])
        if not isinstance(functions, list):
            functions = [functions]
        return Program(functions=[self._build_function_def(f) for f in functions if f])

    def _build_function_def(self, tree: Any) -> Optional[FunctionDef]:
        """Build FunctionDef node."""
        if tree is None:
            return None

        if isinstance(tree, dict):
            name = str(tree.get("name", ""))

            # Handle params - might be a list of params or single param
            params_data = tree.get("params", [])
            if params_data is None:
                params_data = []
            elif not isinstance(params_data, list):
                params_data = [params_data]
            params = [self._build_param(p) for p in params_data if p]

            return_type = self._build_type(tree.get("type", "void"))

            # Extract docstring
            doc = tree.get("docstring")
            if isinstance(doc, dict):
                doc = doc.get("doc")
            if isinstance(doc, tuple) and len(doc) > 1:
                doc = doc[1]

            # Handle body
            body_data = tree.get("body", [])
            if body_data is None:
                body_data = []
            elif not isinstance(body_data, list):
                body_data = [body_data]
            body = [self._build_statement(s) for s in body_data if s]

            return FunctionDef(name=name, params=params, return_type=return_type, doc=doc if doc else None, body=body)

        return None

    def _build_param(self, tree: Any) -> TypedParam:
        """Build TypedParam node."""
        if tree is None:
            return TypedParam(name="", type_=Type("void"))

        if isinstance(tree, dict):
            name = str(tree.get("name", ""))
            type_name = str(tree.get("type", "void"))
            return TypedParam(name=name, type_=Type(name=type_name))
        elif isinstance(tree, (list, tuple)) and len(tree) >= 2:
            return TypedParam(name=str(tree[0]), type_=Type(name=str(tree[1])))

        return TypedParam(name="", type_=Type("void"))

    def _build_type(self, tree: Any) -> Type:
        """Build Type node."""
        if tree is None:
            return Type("void")
        if isinstance(tree, str):
            return Type(name=tree)
        if isinstance(tree, dict):
            return Type(name=str(tree.get("name", "void")))
        return Type(name=str(tree))

    def _build_statement(self, tree: Any) -> Any:
        """Build statement node (LetBinding, ReturnStmt, or LLMCall)."""
        if tree is None:
            return None

        if isinstance(tree, dict):
            # Check which statement type this is
            if "let_binding" in tree:
                return self._build_let_binding(tree.get("let_binding", {}))
            elif "return_stmt" in tree:
                return self._build_return_stmt(tree.get("return_stmt", {}))
            elif "llm_call_standalone" in tree:
                return self._build_llm_call(tree.get("llm_call_standalone", {}))
            elif "llm_call" in tree:
                return self._build_llm_call(tree)

        return tree

    def _build_let_binding(self, tree: dict) -> LetBinding:
        """Build LetBinding node."""
        name = str(tree.get("name", ""))
        type_ = self._build_type(tree.get("type", "void"))
        value = self._build_expression(tree.get("value"))
        return LetBinding(name=name, type_=type_, value=value)

    def _build_return_stmt(self, tree: dict) -> ReturnStmt:
        """Build ReturnStmt node."""
        value = self._build_expression(tree.get("value"))
        return ReturnStmt(value=value)

    def _build_llm_call(self, tree: Any) -> LLMCall:
        """Build LLMCall node."""
        if isinstance(tree, dict):
            prompt = tree.get("string", "")
            if isinstance(prompt, dict):
                prompt = prompt.get("value", "")
            elif isinstance(prompt, (list, tuple)):
                prompt = prompt[1] if len(prompt) > 1 else str(prompt[0])

            context = None
            if "context_clause" in tree:
                ctx_data = tree["context_clause"]
                if isinstance(ctx_data, dict):
                    context = self._build_expression(ctx_data.get("context"))
        else:
            prompt = str(tree)
            context = None

        return LLMCall(prompt=str(prompt), context=context)

    def _build_expression(self, tree: Any) -> Any:
        """Build expression node."""
        if tree is None:
            return None

        if isinstance(tree, dict):
            if "llm_call" in tree:
                return self._build_llm_call(tree.get("llm_call", {}))
            elif "string" in tree:
                s = tree.get("string")
                if isinstance(s, dict):
                    return Literal(value=str(s.get("value", "")))
                elif isinstance(s, (list, tuple)):
                    return Literal(value=str(s[1] if len(s) > 1 else s[0]))
                return Literal(value=str(s))
            elif "number" in tree:
                n = tree.get("number")
                if isinstance(n, str):
                    return Literal(value=float(n) if "." in n else int(n))
                return Literal(value=n)
            elif "name" in tree:
                return Identifier(name=str(tree.get("name")))
        elif isinstance(tree, str):
            # Could be identifier or literal
            if tree.startswith('"') and tree.endswith('"'):
                return Literal(value=tree[1:-1])
            try:
                if "." in tree:
                    return Literal(value=float(tree))
                return Literal(value=int(tree))
            except ValueError:
                return Identifier(name=tree)

        return tree


# =============================================================================
# Main Parser Class
# =============================================================================


class WorkflowParser:
    """
    Main parser interface for Workflow DSL using TatSu.

    Usage:
        parser = WorkflowParser()
        ast = parser.parse(dsl_code)
    """

    def __init__(self):
        """Initialize the parser with compiled grammar."""
        self.preprocessor = IndentationPreprocessor()
        self.ast_builder = ASTBuilder()

        # Compile the grammar
        try:
            self.grammar = tatsu.compile(WORKFLOW_GRAMMAR_SIMPLE)
        except Exception as e:
            print(f"Grammar compilation error: {e}")
            raise

    def parse(self, text: str) -> Program:
        """
        Parse workflow DSL text into AST.

        Args:
            text: DSL source code with Python-style indentation

        Returns:
            Program AST node
        """
        # Preprocess indentation to braces
        preprocessed = self.preprocessor.restore_structure(text)

        # Parse with TatSu
        try:
            parse_tree = self.grammar.parse(preprocessed)
        except tatsu.exceptions.FailedToken as e:
            raise SyntaxError(f"Parse error at line {e.line}, column {e.column}: {e}") from e
        except tatsu.exceptions.FailedParse as e:
            raise SyntaxError(f"Parse error at line {e.line}, column {e.column}: {e}") from e

        # Convert to AST
        return self.ast_builder.build(parse_tree)

    def parse_to_tree(self, text: str) -> Any:
        """
        Parse and return the raw TatSu parse tree (for debugging).

        Args:
            text: DSL source code

        Returns:
            Raw parse tree (dict/list structure)
        """
        preprocessed = self.preprocessor.restore_structure(text)
        return self.grammar.parse(preprocessed)


# =============================================================================
# Example Usage
# =============================================================================

EXAMPLE_WORKFLOW = '''
def analyze_code(filename :: str) -> AnalysisResult:
    """
    Analyze source code for issues.
    """
    let content :: str = llm "Read and summarize the file"
    let issues :: list = llm "Find bugs" with content
    return issues
'''


def main():
    """Demo the TatSu-based parser."""
    print("=" * 70)
    print("Workflow DSL Parser - TatSu Implementation")
    print("=" * 70)
    print()

    parser = WorkflowParser()

    print("Input DSL:")
    print("-" * 70)
    print(EXAMPLE_WORKFLOW)
    print()

    print("Preprocessed (with braces):")
    print("-" * 70)
    preprocessed = parser.preprocessor.restore_structure(EXAMPLE_WORKFLOW)
    print(preprocessed)
    print()

    try:
        # Parse to AST
        ast = parser.parse(EXAMPLE_WORKFLOW)

        print("Parse successful!")
        print()

        print("AST:")
        print("-" * 70)
        print(json.dumps(ast, default=lambda o: o.__dict__, indent=2))

    except Exception as e:
        print(f"Parse error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
