#!/usr/bin/env python3
"""
Workflow DSL Parser - Pratt Parser Implementation (Top-Down Operator Precedence)

A hand-rolled parser using the Pratt parsing algorithm for a Haskell-like,
indentation-based workflow DSL.

Reference: Bob Nystrom's "Pratt Parsers: Expression Parsing Made Easy"
Algorithm: expr(rbp=0) -> parse expression with right binding power

Language Features:
    - Indentation-based blocks (Python-style)
    - Type annotations with :: (Haskell-style)
    - Primitive types: int, str, bool
    - Function definitions with parameters and return types
    - Let bindings: let name :: type = expression
    - LLM builtin call: llm "prompt" or llm "prompt" with context
    - Return statements: return expression
    - Docstrings for functions
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Callable, Dict, Tuple
from enum import Enum, auto
import json
import re


# =============================================================================
# AST Node Definitions
# =============================================================================


@dataclass
class Type:
    """Type annotation node."""

    name: str

    def __repr__(self) -> str:
        return f"Type({self.name})"


@dataclass
class TypedParam:
    """Function parameter with type annotation."""

    name: str
    type_: Type

    def __repr__(self) -> str:
        return f"Param({self.name} :: {self.type_.name})"


@dataclass
class LLMCall:
    """LLM builtin function call."""

    prompt: str
    context: Optional[Any] = None

    def __repr__(self) -> str:
        if self.context:
            return f'LLMCall("{self.prompt}" with {self.context})'
        return f'LLMCall("{self.prompt}")'


@dataclass
class LetBinding:
    """Let binding: let name :: type = value."""

    name: str
    type_: Type
    value: Any  # Expression

    def __repr__(self) -> str:
        return f"Let({self.name} :: {self.type_.name} = {self.value})"


@dataclass
class ReturnStmt:
    """Return statement."""

    value: Any  # Expression

    def __repr__(self) -> str:
        return f"Return({self.value})"


@dataclass
class Identifier:
    """Variable identifier."""

    name: str

    def __repr__(self) -> str:
        return f"Id({self.name})"


@dataclass
class Literal:
    """Literal value (string, number, bool)."""

    value: Any

    def __repr__(self) -> str:
        return f"Literal({self.value!r})"


@dataclass
class FunctionDef:
    """Function definition."""

    name: str
    params: List[TypedParam]
    return_type: Type
    doc: Optional[str]
    body: List[Any]  # Statements

    def __repr__(self) -> str:
        return f"FunctionDef({self.name}({len(self.params)} params) -> {self.return_type.name})"


@dataclass
class Program:
    """Root program node."""

    functions: List[FunctionDef] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"Program({len(self.functions)} functions)"


# =============================================================================
# Token Definitions
# =============================================================================


class TokenType(Enum):
    # Literals
    STRING = auto()
    NUMBER = auto()
    IDENTIFIER = auto()

    # Keywords
    DEF = auto()
    LET = auto()
    RETURN = auto()
    WITH = auto()

    # Type keywords (also identifiers in other contexts)
    INT = auto()
    STR = auto()
    BOOL = auto()

    # Operators and delimiters
    COLON_COLON = auto()  # ::
    ARROW = auto()  # ->
    COLON = auto()  # :
    EQUALS = auto()  # =
    LPAREN = auto()  # (
    RPAREN = auto()  # )
    COMMA = auto()  # ,

    # Indentation
    INDENT = auto()
    DEDENT = auto()
    NEWLINE = auto()

    # Special
    EOF = auto()


@dataclass
class Token:
    """Token produced by the lexer."""

    type: TokenType
    value: Any
    line: int
    column: int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r})"


# =============================================================================
# Lexer / Tokenizer
# =============================================================================


class LexerError(Exception):
    """Lexer error with position information."""

    pass


class Lexer:
    """
    Tokenizer for the workflow DSL.

    Handles:
    - Keywords and identifiers
    - String and numeric literals
    - Operators and delimiters
    - Indentation tracking (Python-style)
    - Comments (skip them)
    """

    KEYWORDS: Dict[str, TokenType] = {
        "def": TokenType.DEF,
        "let": TokenType.LET,
        "return": TokenType.RETURN,
        "with": TokenType.WITH,
        "int": TokenType.INT,
        "str": TokenType.STR,
        "bool": TokenType.BOOL,
    }

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.indent_stack = [0]  # Stack of indentation levels
        self.pending_tokens: List[Token] = []  # For INDENT/DEDENT tokens

    def error(self, msg: str) -> None:
        raise LexerError(f"{msg} at line {self.line}, column {self.column}")

    def peek(self, offset: int = 0) -> str:
        pos = self.pos + offset
        if pos >= len(self.source):
            return "\0"
        return self.source[pos]

    def advance(self) -> str:
        char = self.peek()
        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        self.pos += 1
        return char

    def skip_whitespace_inline(self) -> None:
        """Skip whitespace except newlines."""
        while self.peek() not in "\n\0" and self.peek().isspace():
            self.advance()

    def skip_comment(self) -> None:
        """Skip # comments."""
        if self.peek() == "#":
            while self.peek() not in "\n\0":
                self.advance()

    def read_string(self) -> str:
        """Read a double-quoted string."""
        quote = self.advance()  # Consume opening quote
        assert quote == '"'
        result = []
        while self.peek() != '"' and self.peek() != "\0":
            char = self.advance()
            if char == "\\":
                # Handle escape sequences
                escape_char = self.advance()
                if escape_char == "n":
                    result.append("\n")
                elif escape_char == "t":
                    result.append("\t")
                elif escape_char == "\\":
                    result.append("\\")
                elif escape_char == '"':
                    result.append('"')
                else:
                    result.append(escape_char)
            else:
                result.append(char)
        if self.peek() != '"':
            self.error("Unterminated string literal")
        self.advance()  # Consume closing quote
        return "".join(result)

    def read_number(self) -> Token:
        """Read a numeric literal (integer or float)."""
        start_line, start_col = self.line, self.column
        result = []

        while self.peek().isdigit():
            result.append(self.advance())

        if self.peek() == "." and self.peek(1).isdigit():
            result.append(self.advance())  # Consume '.'
            while self.peek().isdigit():
                result.append(self.advance())
            value = float("".join(result))
        else:
            value = int("".join(result))

        return Token(TokenType.NUMBER, value, start_line, start_col)

    def read_identifier(self) -> Token:
        """Read an identifier or keyword."""
        start_line, start_col = self.line, self.column
        result = []

        while self.peek().isalnum() or self.peek() == "_":
            result.append(self.advance())

        text = "".join(result)

        # Check if it's a keyword
        if text in self.KEYWORDS:
            return Token(self.KEYWORDS[text], text, start_line, start_col)
        else:
            return Token(TokenType.IDENTIFIER, text, start_line, start_col)

    def process_indentation(self) -> List[Token]:
        """
        Process Python-style indentation at the start of a line.
        Returns INDENT/DEDENT tokens as needed.
        """
        tokens = []

        # Count spaces at current position
        indent = 0
        while self.peek() == " ":
            indent += 1
            self.advance()

        if indent > self.indent_stack[-1]:
            # Indentation increased
            self.indent_stack.append(indent)
            tokens.append(Token(TokenType.INDENT, indent, self.line, self.column))
        elif indent < self.indent_stack[-1]:
            # Indentation decreased - may need multiple DEDENTs
            while indent < self.indent_stack[-1]:
                self.indent_stack.pop()
                tokens.append(Token(TokenType.DEDENT, self.indent_stack[-1], self.line, self.column))
            if indent != self.indent_stack[-1]:
                self.error(f"Invalid dedent to column {indent}")

        return tokens

    def get_next_token(self) -> Token:
        """Get the next token from the input."""
        # Return any pending indentation tokens first
        if self.pending_tokens:
            return self.pending_tokens.pop(0)

        # Skip inline whitespace and comments
        self.skip_whitespace_inline()
        self.skip_comment()

        start_line, start_col = self.line, self.column
        char = self.peek()

        # End of input
        if char == "\0":
            # Emit remaining DEDENTs
            dedents = []
            while len(self.indent_stack) > 1:
                self.indent_stack.pop()
                dedents.append(Token(TokenType.DEDENT, 0, start_line, start_col))
            if dedents:
                self.pending_tokens.extend(dedents[1:])
                return dedents[0]
            return Token(TokenType.EOF, None, start_line, start_col)

        # Newline - check for indentation changes
        if char == "\n":
            self.advance()
            # Process next line's indentation
            self.pending_tokens = self.process_indentation()
            return Token(TokenType.NEWLINE, "\n", start_line, start_col)

        # String literal
        if char == '"':
            return Token(TokenType.STRING, self.read_string(), start_line, start_col)

        # Number literal
        if char.isdigit():
            return self.read_number()

        # Identifier or keyword
        if char.isalpha() or char == "_":
            return self.read_identifier()

        # Multi-character operators
        if char == ":" and self.peek(1) == ":":
            self.advance()
            self.advance()
            return Token(TokenType.COLON_COLON, "::", start_line, start_col)

        if char == "-" and self.peek(1) == ">":
            self.advance()
            self.advance()
            return Token(TokenType.ARROW, "->", start_line, start_col)

        # Single-character operators
        singles = {
            ":": TokenType.COLON,
            "=": TokenType.EQUALS,
            "(": TokenType.LPAREN,
            ")": TokenType.RPAREN,
            ",": TokenType.COMMA,
        }

        if char in singles:
            self.advance()
            return Token(singles[char], char, start_line, start_col)

        self.error(f"Unexpected character: {char!r}")

    def tokenize(self) -> List[Token]:
        """Tokenize the entire source into a list of tokens."""
        tokens = []
        while True:
            token = self.get_next_token()
            tokens.append(token)
            if token.type == TokenType.EOF:
                break
        return tokens


# =============================================================================
# Pratt Parser Implementation
# =============================================================================


class ParseError(Exception):
    """Parser error with position information."""

    pass


# Binding power (precedence) levels
# Higher number = tighter binding
BP_NONE = 0
BP_ASSIGNMENT = 10  # =
BP_COMMA = 20  # ,
BP_ARROW = 30  # ->
BP_WITH = 40  # with
BP_TYPE_ANNOT = 50  # ::
BP_CALL = 60  # function calls
BP_PRIMARY = 70  # literals, identifiers


class Parser:
    """
    Pratt parser (top-down operator precedence parser) for the workflow DSL.

    The core algorithm:
        def expr(rbp=0):
            token = next()
            left = nud(token)  # Null denotation (prefix/atomic)
            while rbp < lbp(peek()):  # Left binding power
                token = next()
                left = led(left, token)  # Left denotation (infix/postfix)
            return left

    nud (null denotation): Handles prefix operators and atomic expressions
    led (left denotation): Handles infix and postfix operators
    lbp (left binding power): Returns the precedence of an infix operator
    """

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.current_indent = 0

    def error(self, msg: str) -> None:
        token = self.peek()
        raise ParseError(f"{msg} at line {token.line}, column {token.column}")

    def peek(self, offset: int = 0) -> Token:
        pos = self.pos + offset
        if pos >= len(self.tokens):
            return self.tokens[-1]  # Return EOF
        return self.tokens[pos]

    def next(self) -> Token:
        token = self.peek()
        self.pos += 1
        return token

    def expect(self, token_type: TokenType) -> Token:
        """Consume and return the next token if it matches, else error."""
        token = self.next()
        if token.type != token_type:
            self.error(f"Expected {token_type.name}, got {token.type.name}")
        return token

    def match(self, *token_types: TokenType) -> bool:
        """Check if the next token matches any of the given types."""
        return self.peek().type in token_types

    def skip_newlines(self) -> None:
        """Skip NEWLINE tokens."""
        while self.match(TokenType.NEWLINE):
            self.next()

    # =========================================================================
    # Binding Power (Precedence)
    # =========================================================================

    def lbp(self, token: Token) -> int:
        """
        Left binding power for infix operators.
        Returns the precedence level for the given token type.
        """
        binding_powers = {
            TokenType.EQUALS: BP_ASSIGNMENT,
            TokenType.COMMA: BP_COMMA,
            TokenType.ARROW: BP_ARROW,
            TokenType.WITH: BP_WITH,
            TokenType.COLON_COLON: BP_TYPE_ANNOT,
            TokenType.LPAREN: BP_CALL,
        }
        return binding_powers.get(token.type, BP_NONE)

    # =========================================================================
    # nud (Null Denotation) - Prefix and Atomic Expressions
    # =========================================================================

    def nud(self, token: Token) -> Any:
        """
        Null denotation: Parse prefix and atomic expressions.

        Called when a token appears at the beginning of an expression
        (no left-hand side).
        """
        handlers = {
            TokenType.IDENTIFIER: self._nud_identifier,
            TokenType.STRING: self._nud_string,
            TokenType.NUMBER: self._nud_number,
            TokenType.INT: self._nud_type_keyword,
            TokenType.STR: self._nud_type_keyword,
            TokenType.BOOL: self._nud_type_keyword,
            TokenType.LPAREN: self._nud_grouping,
        }

        handler = handlers.get(token.type)
        if handler:
            return handler(token)
        else:
            self.error(f"Unexpected token: {token.type.name}")

    def _nud_identifier(self, token: Token) -> Identifier:
        """Parse an identifier."""
        return Identifier(token.value)

    def _nud_string(self, token: Token) -> Literal:
        """Parse a string literal."""
        return Literal(token.value)

    def _nud_number(self, token: Token) -> Literal:
        """Parse a number literal."""
        return Literal(token.value)

    def _nud_type_keyword(self, token: Token) -> Type:
        """Parse a type keyword (int, str, bool)."""
        return Type(token.value)

    def _nud_grouping(self, token: Token) -> Any:
        """Parse a parenthesized expression."""
        expr = self.expr()
        self.expect(TokenType.RPAREN)
        return expr

    # =========================================================================
    # led (Left Denotation) - Infix and Postfix Expressions
    # =========================================================================

    def led(self, left: Any, token: Token) -> Any:
        """
        Left denotation: Parse infix and postfix expressions.

        Called when a token appears after an expression (has left-hand side).
        """
        handlers = {
            TokenType.COLON_COLON: self._led_type_annotation,
            TokenType.ARROW: self._led_arrow,
            TokenType.LPAREN: self._led_call,
            TokenType.EQUALS: self._led_assignment,
        }

        handler = handlers.get(token.type)
        if handler:
            return handler(left, token)
        else:
            self.error(f"Unexpected infix token: {token.type.name}")

    def _led_type_annotation(self, left: Any, token: Token) -> Tuple[Any, Type]:
        """
        Parse type annotation: expr :: type
        Returns a tuple of (expr, type) for the caller to handle.
        """
        type_expr = self.expr(BP_TYPE_ANNOT)
        if not isinstance(type_expr, Type):
            # Type can also be an identifier
            if isinstance(type_expr, Identifier):
                type_expr = Type(type_expr.name)
            else:
                self.error("Expected type after ::")
        return (left, type_expr)

    def _led_arrow(self, left: Any, token: Token) -> Any:
        """Parse arrow type: type -> type (used in function signatures)."""
        # For now, we don't support complex arrow types in expressions
        # This is mainly used in function definitions
        right = self.expr(BP_ARROW)
        return (left, "->", right)

    def _led_call(self, left: Any, token: Token) -> Any:
        """Parse function call: expr(args)."""
        # Parse argument list
        args = []
        if not self.match(TokenType.RPAREN):
            args.append(self.expr())
            while self.match(TokenType.COMMA):
                self.next()
                args.append(self.expr())
        self.expect(TokenType.RPAREN)

        # For now, return a simple representation
        # In a full implementation, this would be a Call node
        return {"call": left, "args": args}

    def _led_assignment(self, left: Any, token: Token) -> Any:
        """Parse assignment: left = right."""
        right = self.expr(BP_ASSIGNMENT - 1)  # Right associative
        return {"assign": left, "value": right}

    # =========================================================================
    # Core Expression Parser (Pratt Algorithm)
    # =========================================================================

    def expr(self, rbp: int = BP_NONE) -> Any:
        """
        Parse an expression using the Pratt algorithm.

        rbp: Right binding power - minimum precedence to continue parsing.
             Higher rbp means stop at lower precedence operators.
        """
        token = self.next()
        left = self.nud(token)

        # Continue while the next token has higher left binding power
        while rbp < self.lbp(self.peek()):
            token = self.next()
            left = self.led(left, token)

        return left

    # =========================================================================
    # Statement Parsing
    # =========================================================================

    def parse_statement(self) -> Any:
        """Parse a single statement."""
        self.skip_newlines()

        if self.match(TokenType.DEF):
            return self.parse_function_def()
        elif self.match(TokenType.LET):
            return self.parse_let_binding()
        elif self.match(TokenType.RETURN):
            return self.parse_return()
        elif self.match(TokenType.EOF):
            return None
        else:
            # Try to parse as expression statement or LLM call
            return self.parse_expression_or_llm_call()

    def parse_function_def(self) -> FunctionDef:
        """
        Parse a function definition:
            def name(params) -> type:
                docstring
                body
        """
        self.expect(TokenType.DEF)
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        # Parse parameters
        params = []
        self.expect(TokenType.LPAREN)

        if not self.match(TokenType.RPAREN):
            # Parse first parameter
            param = self.parse_param()
            params.append(param)

            # Parse additional parameters
            while self.match(TokenType.COMMA):
                self.next()
                param = self.parse_param()
                params.append(param)

        self.expect(TokenType.RPAREN)

        # Parse return type
        return_type = Type("void")
        if self.match(TokenType.ARROW):
            self.next()
            type_name = self.expect(TokenType.IDENTIFIER).value
            return_type = Type(type_name)

        # Expect colon
        self.expect(TokenType.COLON)
        self.expect(TokenType.NEWLINE)
        self.expect(TokenType.INDENT)

        # Parse docstring (optional)
        doc = None
        self.skip_newlines()
        if self.match(TokenType.STRING):
            doc = self.next().value
            self.skip_newlines()

        # Parse body
        body = []
        while not self.match(TokenType.DEDENT, TokenType.EOF):
            stmt = self.parse_statement()
            if stmt:
                body.append(stmt)
            self.skip_newlines()

        if self.match(TokenType.DEDENT):
            self.next()

        return FunctionDef(name=name, params=params, return_type=return_type, doc=doc, body=body)

    def parse_param(self) -> TypedParam:
        """Parse a typed parameter: name :: type."""
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        self.expect(TokenType.COLON_COLON)

        # Get type
        if self.match(TokenType.INT, TokenType.STR, TokenType.BOOL):
            type_token = self.next()
            type_name = type_token.value
        else:
            type_name = self.expect(TokenType.IDENTIFIER).value

        return TypedParam(name=name, type_=Type(type_name))

    def parse_let_binding(self) -> LetBinding:
        """
        Parse a let binding:
            let name :: type = expression
        """
        self.expect(TokenType.LET)
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        # Parse type annotation
        self.expect(TokenType.COLON_COLON)

        if self.match(TokenType.INT, TokenType.STR, TokenType.BOOL):
            type_token = self.next()
            type_name = type_token.value
        elif self.match(TokenType.IDENTIFIER):
            type_name = self.next().value
        else:
            self.error("Expected type after :: in let binding")
            type_name = "unknown"

        type_ = Type(type_name)

        # Parse value
        self.expect(TokenType.EQUALS)

        # Check for LLM call
        if self.match(TokenType.IDENTIFIER) and self.peek().value == "llm":
            value = self.parse_llm_call()
        else:
            value = self.expr()

        return LetBinding(name=name, type_=type_, value=value)

    def parse_llm_call(self) -> LLMCall:
        """
        Parse an LLM builtin call:
            llm "prompt"
            llm "prompt" with context
        """
        llm_token = self.next()  # Consume 'llm' identifier

        # Expect string prompt
        prompt_token = self.expect(TokenType.STRING)
        prompt = prompt_token.value

        # Check for context clause
        context = None
        if self.match(TokenType.WITH):
            self.next()  # Consume 'with'
            context = self.expr()

        return LLMCall(prompt=prompt, context=context)

    def parse_return(self) -> ReturnStmt:
        """Parse a return statement: return expression."""
        self.expect(TokenType.RETURN)

        if self.match(TokenType.NEWLINE, TokenType.DEDENT, TokenType.EOF):
            return ReturnStmt(value=None)
        else:
            value = self.expr()
            return ReturnStmt(value=value)

    def parse_expression_or_llm_call(self) -> Any:
        """
        Parse either an LLM call or a general expression.
        Handles the case where 'llm' appears at statement level.
        """
        if self.match(TokenType.IDENTIFIER) and self.peek().value == "llm":
            return self.parse_llm_call()
        else:
            return self.expr()

    # =========================================================================
    # Program Parsing
    # =========================================================================

    def parse_program(self) -> Program:
        """Parse the entire program."""
        program = Program()

        while not self.match(TokenType.EOF):
            self.skip_newlines()

            if self.match(TokenType.EOF):
                break

            if self.match(TokenType.DEF):
                func = self.parse_function_def()
                program.functions.append(func)
            else:
                # Top-level statements not in a function
                stmt = self.parse_statement()
                if stmt:
                    pass  # Could store top-level statements

            self.skip_newlines()

        return program


# =============================================================================
# Parser Interface
# =============================================================================


class WorkflowParser:
    """Main parser interface for the Workflow DSL using Pratt parsing."""

    def __init__(self):
        pass

    def parse(self, source: str) -> Program:
        """Parse workflow DSL source into an AST."""
        # Tokenize
        lexer = Lexer(source)
        tokens = lexer.tokenize()

        # Filter out empty newlines at the start for cleaner parsing
        tokens = [t for t in tokens if t.type != TokenType.NEWLINE or tokens.index(t) > 0]

        # Parse
        parser = Parser(tokens)
        return parser.parse_program()


# =============================================================================
# Example Usage and Testing
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
    """Demo the Pratt parser implementation."""
    print("=" * 70)
    print("Workflow DSL Parser - Pratt Parser Implementation")
    print("=" * 70)
    print()
    print("Input DSL:")
    print("-" * 70)
    print(EXAMPLE_WORKFLOW)
    print()

    try:
        parser = WorkflowParser()
        ast = parser.parse(EXAMPLE_WORKFLOW)

        print("Parse successful!")
        print()
        print("AST Structure:")
        print("-" * 70)

        def serialize_ast(obj):
            """Custom JSON serializer for AST nodes."""
            if hasattr(obj, "__dataclass_fields__"):
                result = {}
                for field_name in obj.__dataclass_fields__:
                    value = getattr(obj, field_name)
                    result[field_name] = serialize_ast(value)
                # Add type information
                result["_type"] = obj.__class__.__name__
                return result
            elif isinstance(obj, list):
                return [serialize_ast(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: serialize_ast(v) for k, v in obj.items()}
            else:
                return obj

        ast_json = serialize_ast(ast)
        print(json.dumps(ast_json, indent=2))

        print()
        print("AST Summary:")
        print("-" * 70)
        print(f"Program has {len(ast.functions)} function(s)")
        for func in ast.functions:
            print(f"  - {func.name}({', '.join(p.name for p in func.params)}) -> {func.return_type.name}")
            print(f"    Doc: {func.doc}")
            for stmt in func.body:
                print(f"    Body: {stmt}")

    except LexerError as e:
        print(f"Lexer error: {e}")
        raise
    except ParseError as e:
        print(f"Parse error: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()
