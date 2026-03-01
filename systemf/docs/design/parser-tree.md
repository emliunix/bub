# Parser Refactor: Tree of Parsers

## Overview

This document maps the parser structure for the System F surface language refactor.
Based on Idris2's parser design with explicit constraint passing.

## Parser Hierarchy

```
Program (Top Level)
│
├── Declarations
│   ├── data_decl: data X = A | B
│   │   └── NOT layout-sensitive (| can be at any column)
│   │
│   ├── let_decl: let ... in ...
│   │   └── block(let_binding)  ← layout here
│   │
│   └── top_decl: general top-level
│       └── Used in: block(top_decl) for where clauses
│
└── Expressions (expr_parser)
    ├── Atoms (no layout)
    │   ├── Variable/Constructor
    │   ├── Literal
    │   ├── Paren: ( expr )
    │   └── Lambda: λx → e
    │
    ├── Applications (no layout)
    │   └── f x y (left associative)
    │
    ├── Operators (no layout)
    │   ├── Arithmetic: +, -, *, /
    │   ├── Comparison: ==, /=, <, >
    │   └── Logical: &&, ||
    │
    └── Layout-sensitive (need constraint)
        ├── case_expr: case e of branches
        │   └── block(case_alt)  ← layout here
        │
        └── let_expr: let bindings in e
            └── block(let_binding)  ← layout here

Types (type_parser)
├── forall_type: ∀a. t
├── arrow_type: A → B
└── app_type: F A B
```

## Constraint Flow

### When Constraints Are Needed

1. **Entering Layout Mode** (capture column)
   ```python
   # After 'case ... of' or 'let'
   col = yield column()  # peek at first token
   block(AtPos(col), item_parser)
   ```

2. **Inside Layout Blocks** (validate/continue)
   ```python
   # Each item checks:
   if not check_valid(constraint, token.column):
       fail("invalid indentation")
   
   # After item, check terminator:
   new_constraint = yield terminator(constraint, start_col)
   if new_constraint == EndOfBlock:
       stop parsing items
   ```

3. **Nested Layout** (stack constraints)
   ```systemf
   case x of          # capture col 2
     True → let       # in case block, capture col 8
       y = 1          # in let block at col 10
     in y             # check >= 2 (case), not >= 10
   ```

### Constraint Types

- `AnyIndent`: Inside braces `{ }`, anything goes
- `AtPos(n)`: Must be exactly at column n
- `AfterPos(n)`: Must be at or after column n (after semicolon)
- `EndOfBlock`: Block has ended

## Helper Combinators

### Core Infrastructure
```
column() → Parser[int]
  └─ Returns current token's column (peek)

check_valid(constraint, col) → bool
  └─ Validates column against constraint

is_at_constraint(constraint, col) → bool
  └─ Exact match check
```

### Block Parsing
```
block(item) → Parser[List[T]]
  ├─ Tries: { item; item; } with AnyIndent
  └─ Or: layout mode with AtPos(first_col)

block_after(min_col, item) → Parser[List[T]]
  └─ Block indented at least min_col

block_entries(constraint, item) → Parser[List[T]]
  ├─ Loop:
  │   ├─ block_entry(constraint, item)
  │   ├─ terminator(constraint, start_col)
  │   └─ repeat until EndOfBlock

block_entry(constraint, item) → Parser[(T, ValidIndent)]
  ├─ Check token.column satisfies constraint
  ├─ Parse item
  └─ Return (value, updated_constraint)
```

### Terminators
```
terminator(constraint, start_col) → Parser[ValidIndent]
  ├─ EOF → EndOfBlock
  ├─ ; → AfterPos (for next item)
  ├─ } → EndOfBlock
  ├─ col <= start_col → EndOfBlock (dedent)
  └─ col > start_col → same constraint (continue)

must_continue(constraint, expected?) → Parser[None]
  ├─ EndOfBlock → fail("Unexpected end of expression")
  └─ _ → success
```

## Parser Dependencies

### Expression Dependencies
```
expr_parser(constraint)
  ├─ Uses: atom, app, op_expr
  ├─ Uses: case_expr(constraint)  ← needs constraint
  └─ Uses: let_expr(constraint)   ← needs constraint

case_expr(constraint)
  ├─ Uses: expr_parser(constraint) for scrutinee
  ├─ Uses: column() to capture branch column
  └─ Uses: block(case_alt) with new constraint

let_expr(constraint)
  ├─ Uses: column() to capture binding column
  ├─ Uses: block(let_binding) with new constraint
  ├─ Uses: must_continue(constraint, "in")
  └─ Uses: expr_parser(constraint) for body
```

### Declaration Dependencies
```
program_parser
  └─ Uses: block(top_decl) for top-level sequence

top_decl(constraint)
  ├─ Uses: data_decl()  ← no constraint needed
  ├─ Uses: let_decl(constraint)  ← needs constraint for body
  └─ Can appear in: block(top_decl) for where clauses

let_decl(constraint)
  ├─ Uses: block(let_binding)  ← layout for bindings
  └─ Uses: expr_parser(constraint) for body

# Note: let_decl is BOTH a declaration AND can appear in expressions!
```

### The block(topDecl) Pattern

**Idris2 reference** (`Parser.idr` line ~150):
```idris
whereBlock : OriginDesc -> Int -> Rule (List PDecl)
whereBlock fname col
    = do decoratedKeyword fname "where"
         ds <- blockAfter col (topDecl fname)
         pure (collectDefs ds)
```

**System F equivalent:**
```python
def where_block(min_col: int) -> Parser[List[Declaration]]:
    yield keyword("where")
    # blockAfter ensures declarations are indented past 'where'
    decls = yield block_after(min_col, top_decl)
    return decls
```

**Key insight**: `block(top_decl)` parses a sequence where:
1. First declaration sets the reference column
2. Subsequent declarations must match that column
3. Block ends on dedent or EOF
4. Each declaration is parsed with the layout constraint

## Key Design Decisions

### 1. Pass Constraint Through Everything
- Even atoms that don't use it (for consistency)
- Alternative: Only pass to layout-sensitive parsers
- **Chosen**: Pass everywhere (Idris2 style)

### 2. Peek vs Consume
- `column()`: peek (doesn't consume)
- `terminator()`: peek (decides, doesn't consume token)
- `block_entry()`: consumes one item

### 3. First Token Sets Column
```python
# Layout mode:
col = yield column()  # peek at first binding
bindings = yield block_entries(AtPos(col), binding_parser)
```

### 4. Explicit Braces Win
```python
def block(item):
    return (brace_block(item) | layout_block(item))
```

### 5. Block with Declarations Pattern (Idris2 Style)

From Idris2's `whereBlock`:
```idris
whereBlock : OriginDesc -> Int -> Rule (List PDecl)
whereBlock fname col
    = do decoratedKeyword fname "where"
         ds <- blockAfter col (topDecl fname)
         pure (collectDefs ds)
```

**Key insight**: `block(topDecl(...))` is the pattern for parsing a sequence of declarations:
- `block()` captures the column of the first declaration
- Each `topDecl` is parsed with the constraint
- Terminator checks for layout end between declarations

**In System F:**
```python
def where_block(constraint: ValidIndent) -> Parser[List[Decl]]:
    # "where" keyword already parsed
    col = yield column()  # column of first declaration
    # Use AfterPos constraint since declarations can be at or after 'where' col
    decls = yield block_entries(AfterPos(col), top_decl)
    return decls
```

This pattern appears in:
- `where` clauses: `f x = ... where { declarations }`
- Top-level modules: sequence of declarations
- Local definitions in let/where

## Testing Strategy

### Unit Tests (test_helpers.py)
- Individual combinators
- Constraint checking
- Token validation

### Integration Tests (test_parser_complex.py)
- Nested layouts
- Mixed explicit/layout
- Error cases

### Edge Cases
- Empty blocks
- Single item blocks
- Dedent detection
- Semicolon handling

## Files

```
src/systemf/surface/parser/
├── __init__.py          # Public exports
├── types.py             # Token types, ValidIndent
├── lexer.py             # Tokenizer
├── helpers.py           # Core combinators (DONE)
├── declarations.py      # data_decl, let_decl, top_decl
└── expressions.py       # expr_parser, case_expr, etc.

tests/test_surface/test_parser/
├── test_helpers.py      # Unit tests (DONE)
└── test_parser_complex.py  # Integration tests (WIP)
```

## Next Steps

1. ✅ Implement helper combinators
2. ✅ Write real tests for helpers
3. ⏳ Implement expression parsers (expressions.py)
4. ⏳ Implement declaration parsers (declarations.py)
5. ⏳ Wire everything together in main parser
