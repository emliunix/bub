# Workflow DSL - Experimental Language Specification

**Version:** 0.1.0  
**Date:** 2026-02-22  
**Purpose:** Research language for parsing experiments

---

## 1. Overview

A minimal, Haskell-inspired DSL for defining agent workflows. Designed for parsing experimentation.

### Design Principles
- **Indentation-based blocks** (Python-style) - no braces
- **Haskell-style type annotations** - `name :: Type`
- **Minimal surface area** - only essential constructs
- **LLM-first** - builtin `llm` function for agent calls

---

## 2. Lexical Structure

### 2.1 Whitespace
- **Indentation is significant** - defines block structure
- **Consistent indentation** - 4 spaces (no tabs)
- **Blank lines ignored**

### 2.2 Comments
```
# This is a comment (to end of line)
```

### 2.3 Literals

| Type | Example | Pattern |
|------|---------|---------|
| Integer | `42`, `-17` | `-?\d+` |
| Float | `3.14`, `-0.5` | `-?\d+\.\d+` |
| String | `"hello"`, `'world'` | `"[^"]*"` or `'[^']*'` |
| Boolean | `True`, `False` | Case-sensitive |

### 2.4 Keywords (Reserved)
```
def      # Function definition
let      # Variable binding
return   # Return statement
llm      # LLM call builtin
with     # Context for LLM call
True     # Boolean literal
False    # Boolean literal
```

### 2.5 Operators
```
::       # Type annotation
->       # Return type arrow
( )      # Parentheses
:        # Block starter
=        # Assignment
,        # Parameter separator
```

### 2.6 Identifiers
- **Pattern:** `[a-zA-Z_][a-zA-Z0-9_]*`
- **Case-sensitive**
- **Cannot start with digit**
- **Cannot be keyword**

---

## 3. Types

### 3.1 Primitive Types

| Type | Description | Examples |
|------|-------------|----------|
| `int` | Integer | `42`, `0`, `-10` |
| `float` | Floating point | `3.14`, `-0.001` |
| `str` | String | `"hello"` |
| `bool` | Boolean | `True`, `False` |

### 3.2 Composite Types (Future)
- `list[T]` - Homogeneous list
- `option[T]` - Optional value
- `result[T, E]` - Success/Failure

### 3.3 User-Defined Types
- **Simple identifiers** treated as types
- No type declarations yet (just names)
- Examples: `AnalysisResult`, `Config`, `User`

---

## 4. Grammar

### 4.1 Program Structure

```ebnf
program ::= function_def*

function_def ::= "def" identifier "(" param_list? ")" return_type? ":" docstring? block

param_list ::= param ("," param)*

param ::= identifier "::" type

return_type ::= "->" type

type ::= identifier

docstring ::= STRING

block ::= NEWLINE INDENT statement+ DEDENT
```

### 4.2 Statements

```ebnf
statement ::= let_binding
            | llm_call_stmt
            | return_stmt
            | expression

let_binding ::= "let" identifier "::" type "=" expression

llm_call_stmt ::= "llm" STRING context_clause?

context_clause ::= "with" expression

return_stmt ::= "return" expression
```

### 4.3 Expressions

```ebnf
expression ::= identifier
             | literal
             | llm_call_expr
             | "(" expression ")"

literal ::= INTEGER
          | FLOAT
          | STRING
          | BOOLEAN

llm_call_expr ::= "llm" STRING context_clause?

identifier ::= [a-zA-Z_][a-zA-Z0-9_]*
```

---

## 5. Examples

### 5.1 Minimal Function
```
def greet():
    return "hello"
```

### 5.2 Function with Parameters and Types
```
def add(x :: int, y :: int) -> int:
    return x + y
```

### 5.3 LLM Call
```
def summarize(text :: str) -> str:
    let result :: str = llm "Summarize this text concisely"
    return result
```

### 5.4 LLM Call with Context
```
def analyze(code :: str) -> AnalysisResult:
    let issues :: list = llm "Find bugs in this code" with code
    return issues
```

### 5.5 Full Example
```
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
```

---

## 6. Semantics

### 6.1 Scoping
- **Function scope** - parameters and let bindings visible in function body
- **No nested functions** (yet)
- **No global variables** (yet)

### 6.2 Evaluation
- **Eager** - expressions evaluated immediately
- **Sequential** - statements execute in order
- **Last expression** in block is return value (if no explicit return)

### 6.3 LLM Calls
- **Builtin function** - `llm` is magic, not user-defined
- **String argument** - the prompt
- **Optional context** - additional data via `with`
- **Returns** - result of LLM call (type-checked at runtime)

---

## 7. Parser Requirements

### 7.1 Must Handle
- [x] Indentation-based blocks
- [x] Type annotations with `::`
- [x] Function definitions with params and return types
- [x] Let bindings
- [x] LLM calls (with and without context)
- [x] Return statements
- [x] Docstrings
- [x] Comments

### 7.2 Error Handling
- **Indentation errors** - mismatched indentation levels
- **Type annotation errors** - missing `::` or invalid type
- **Syntax errors** - unexpected tokens, missing delimiters
- **Clear error messages** - line/column numbers, expected vs got

### 7.3 AST Structure
```
Program
└── functions: List[FunctionDef]

FunctionDef
├── name: str
├── params: List[TypedParam]
├── return_type: Type
├── doc: Optional[str]
└── body: List[Statement]

TypedParam
├── name: str
└── type: Type

LetBinding
├── name: str
├── type: Type
└── value: Expression

LLMCall
├── prompt: str
└── context: Optional[Expression]

Return
└── value: Expression

Type
└── name: str
```

---

## 8. Research Questions

1. **Indentation handling** - Preprocess vs integrated in parser?
2. **Error recovery** - Can parser continue after error?
3. **Performance** - Startup time vs parse speed?
4. **Extensibility** - How easy to add new constructs?
5. **Error quality** - Are error messages helpful?
6. **Tooling** - Can we get syntax highlighting, LSP?

---

## 9. Testing

### 9.1 Valid Programs
- Empty program
- Single function, no params
- Function with params and types
- Function with docstring
- Let binding
- LLM call without context
- LLM call with context
- Multiple functions
- Comments

### 9.2 Invalid Programs (Should Error)
- Inconsistent indentation
- Missing type annotation
- Invalid identifier
- Unclosed string
- Unexpected token

---

## 10. Future Extensions (Out of Scope)

- Type inference (let without annotation)
- Pattern matching (case/of)
- Higher-order functions
- Generics/parametric types
- Modules/imports
- Effects system
- Async/await

---

*This is a living document for experimental purposes.*
