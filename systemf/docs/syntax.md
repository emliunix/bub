# System F Surface Syntax Specification

**Version:** 0.3  
**Status:** Draft  
**Last Updated:** 2025-03-01

This document defines the concrete syntax of the System F surface language. The surface syntax is what programmers write; it desugars to a simpler core language.

## 1. Lexical Structure

### 1.1 Tokens

```
Keywords:      data, let, in, case, of, if, then, else, forall, prim_type, prim_op
Constructors:  [A-Z][a-zA-Z0-9_]*
Identifiers:   [a-z_][a-zA-Z0-9_]*
Operators:     +, -, *, /, ==, /=, <, >, <=, >=, &&, ||, ++
Reserved:      !! (list indexing - future), ! (reserved)
Delimiters:    ( ) { } [ ] @ | → . = : -> ,
Literals:      42, -7, "hello", 'c'
Layout:        Parser-level constraint checking (no virtual tokens)
```

### 1.2 Unicode Alternatives

```
ASCII     Unicode
-----------------
->        → (U+2192)
\         λ (U+03BB)  or  \\/ (ASCII)
/\\        Λ (U+039B)  or  /\\ (ASCII)
forall    ∀ (U+2200)
```

Both forms are accepted. Unicode is preferred for readability.

### 1.3 Layout-Aware Parsing

System F uses **Idris2-style layout parsing** with explicit constraint passing. Unlike token-based approaches (Python, Haskell's L-function), constraints are passed directly to parser combinators.

**Key Insight:** The parser, not the lexer, handles layout by checking token columns against constraints.

**Layout Keywords:** `let`, `case`, `of`

**No Virtual Tokens:** The lexer emits raw tokens only. Each token carries its source location (line, column).

**Implementation:** Layout-aware combinators are defined in `parser_helpers.py`.

**Example:**
```systemf
case x of
  True → a
  False → b
```

**Parser flow:**
1. Parse `case x of` (no layout yet)
2. After `of`, enter layout mode - read column of `True` (col 3)
3. `True → a` parsed at col 3 (constraint: `AtPos 3`)
4. `False` at col 3 matches constraint ✓
5. `False → b` parsed

**Invalid (same column):**
```systemf
case x of
True → a      -- ERROR: True at column 1, not indented
False → b
```

**Key Rule:** First item after layout keyword must be at column > keyword column.

**Explicit braces:** `{...}` disables layout checking (anything goes inside braces).

### 1.4 Builtin Operators

Surface syntax provides infix operators that desugar to primitive operations:

| Operator | Primitive | Type | Description |
|----------|-----------|------|-------------|
| `+` | `int_plus` | `Int → Int → Int` | Integer addition |
| `-` | `int_minus` | `Int → Int → Int` | Integer subtraction |
| `*` | `int_multiply` | `Int → Int → Int` | Integer multiplication |
| `/` | `int_divide` | `Int → Int → Int` | Integer division |
| `==` | `int_eq` | `Int → Int → Bool` | Integer equality |
| `/=` | `int_neq` | `Int → Int → Bool` | Integer inequality |
| `<` | `int_lt` | `Int → Int → Bool` | Less than |
| `>` | `int_gt` | `Int → Int → Bool` | Greater than |
| `<=` | `int_le` | `Int → Int → Bool` | Less than or equal |
| `>=` | `int_ge` | `Int → Int → Bool` | Greater than or equal |
| `&&` | `bool_and` | `Bool → Bool → Bool` | Logical AND |
| `\|\|` | `bool_or` | `Bool → Bool → Bool` | Logical OR |
| `++` | `string_concat` | `String → String → String` | String concatenation |

**Operator precedence** (high to low):
1. `*`, `/` (left-associative)
2. `+`, `-` (left-associative)
3. `==`, `/=`, `<`, `>`, `<=`, `>=` (non-associative)
4. `&&` (right-associative)
5. `||` (right-associative)

**Examples:**
```systemf
x + y * z          -- parses as: x + (y * z)
x == y + z         -- parses as: x == (y + z)
x ++ y ++ z        -- parses as: (x ++ y) ++ z (left-assoc)
x /= 0 && y > 5    -- parses as: (x /= 0) && (y > 5)
not a && b || c    -- parses as: ((not a) && b) || c
```

**Notes:**
- Logical negation uses `not` function (Haskell style), not `!` operator
- Comparison operators are non-associative: `a == b == c` is a syntax error
- Logical operators use short-circuit semantics (when evaluated)
- `!!` is reserved for list indexing (Haskell style): `xs !! 3`

## 2. Types

### 2.1 Type Grammar

```
type      ::= forall_type | arrow_type

forall_type ::= "∀" ident+ "." type
             |  "forall" ident+ "." type

arrow_type  ::= app_type ("→" arrow_type)?

app_type    ::= atom_type+

atom_type   ::= "(" type ")"
             |   tuple_type
             |   ident          -- type variable
             |   CONSTRUCTOR    -- type constructor

tuple_type  ::= "(" type ("," type)+ ")"
```

### 2.2 Rank-2 Types

Parentheses required for `forall` on the right of arrow:

```systemf
-- OK: ∀ on the left
map : ∀a. ∀b. (a → b) → List a → List b

-- OK: ∀ in parentheses on the right
const : ∀a. a → (∀b. b → a)

-- NOT SUPPORTED: ambiguous
const : ∀a. a → ∀b. b → a
```

**Why:** `∀a. a → ∀b. b → a` is syntactically ambiguous. It could mean:
- `∀a. a → (∀b. b → a)` (rank-2: b is chosen after a)
- `∀a. ∀b. a → b → a` (rank-1: both chosen together)

These have different meanings. Requiring parentheses makes the intent explicit.

### 2.3 Type Application

```
type_app ::= type "@" type
          |  type "[" type "]"
```

The `@` syntax is preferred. Use parentheses for complex types:

```systemf
f @Int                    -- simple
f @(List Int)             -- complex, requires parens
f @(∀a. a → a)            -- higher-rank, requires parens
```

### 2.4 Tuple Types

Tuple types are syntactic sugar for nested `Pair` applications:

```
tuple_type ::= "(" type ("," type)+ ")"
```

**Desugaring:**

```systemf
(Int, Bool)              -- sugar for: Pair Int Bool
(Int, Bool, String)      -- sugar for: Pair Int (Pair Bool String)
(a, b, c, d)             -- sugar for: Pair a (Pair b (Pair c d))
```

**Note:** Single-element parentheses `(Int)` are just grouping, not tuples. Tuples require at least two elements.

**Examples:**

```systemf
-- Function returning a pair
swap : ∀a. ∀b. (a, b) → (b, a)

-- Nested tuples
type Point3D = (Float, Float, Float)
type Color = (Int, Int, Int, Int)  -- RGBA
```

## 3. Expressions

### 3.1 Expression Grammar

```
expr      ::= lambda_expr
           |  type_abs_expr
           |  if_expr
           |  case_expr
           |  let_expr
           |  tuple_expr
           |  op_expr
```

### 3.2 Application

```
app_expr    ::= atom+ ("@" atom_type)*
```

Type applications bind tighter than value applications:

```
f @Int x y     -- parses as: (((f @Int) x) y)
f x @Int       -- ERROR: use (f x) @Int if you really need this
```

### 3.3 Tuple Expressions

Tuple expressions are syntactic sugar for nested `Pair` constructor applications:

```
tuple_expr  ::= "(" expr ("," expr)+ ")"
```

**Desugaring:**

```systemf
(x, y)                   -- sugar for: Pair x y
(1, 2, 3)                -- sugar for: Pair 1 (Pair 2 3)
(a, b, c, d)             -- sugar for: Pair a (Pair b (Pair c d))
```

**Note:** Single-element parentheses `(x)` are just grouping, not tuples.

**Examples:**

```systemf
-- Returning multiple values
swap : ∀a. ∀b. (a, b) → (b, a)
swap p = case p of (x, y) → (y, x)

-- Pattern matching on tuples
fst : ∀a. ∀b. (a, b) → a
fst p = case p of (x, _) → x

-- Nested tuples
point : (Float, (Float, Float))
point = (1.0, (2.0, 3.0))
```

### 3.4 If-Then-Else (3 Layout Styles)

**Style 1: All inline**
```systemf
if c then t else f
```

**Style 2: Then/else on new lines**
```systemf
if c
  then t
  else f
```

**Style 3: Bodies indented**
```systemf
if c then
  t
else
  f
```

All three are equivalent. The parser uses `indented_opt` for both `then` and `else` branches.

### 3.4 Case Expressions (2 Layout Styles)

**Style 1: Explicit Braces**
```systemf
case x of { True → a; False → b }
```

Branches separated by semicolons (`;`).

**Style 2: Indented**
```systemf
case x of
  True → a
  False → b
```

Branches separated by layout (NEXT tokens between items).

**Note:** Unlike data declarations, case expressions use `;` not `|` in explicit mode. This follows Haskell's convention.

#### Patterns

Patterns support constructor patterns, variable patterns, and tuple patterns:

```
pattern     ::= tuple_pattern
             |  CONSTRUCTOR [ident*]
             |  ident           -- variable pattern

tuple_pattern ::= "(" pattern ("," pattern)+ ")"
```

**Examples:**

```systemf
-- Constructor patterns
case xs of
  Nil → 0
  Cons x xs → x + length xs

-- Tuple patterns
case p of
  (x, y) → x + y
  (a, b, c) → a + b + c

-- Variable patterns (catch-all)
case x of
  0 → "zero"
  n → "non-zero: " ++ show n

-- Nested patterns
case mp of
  Nothing → 0
  Just (x, y) → x + y
```

### 3.5 Lambda (2 Layout Styles)

**Style 1: Inline**
```systemf
λx → x + 1
```

**Style 2: Indented**
```systemf
λx →
  x + 1
```

### 3.6 Let-In (3 Layout Styles)

Let supports multiple bindings followed by `in`:

**Style 1: All inline**
```systemf
let x = 1; y = 2 in x + y
```

**Style 2: Indented bindings**
```systemf
let
  x = 1
  y = 2
in x + y
```

**Style 3: Indented body**
```systemf
let x = 1; y = 2 in
  some
    long
    expression
```

**Style 4: Mixed (all indented)**
```systemf
let
  x = 1
  y = 2
in
  x + y
```

The `in` keyword is **required** and marks the end of bindings. The body expression after `in` can be inline or indented (using `indented_opt`). In inline style, bindings are separated by `;`. In indented style, each binding is on its own line at the same indentation level.

## 4. Patterns

### 4.1 Pattern Grammar

```
pattern   ::= CONSTRUCTOR [ident*]
```

**Examples:**
```systemf
True                -- nullary constructor
Just x              -- unary
Cons y ys           -- binary
Pair a b            -- binary
```

### 4.2 No Wildcard

There is no `_` wildcard pattern. Use explicit constructor names:

```systemf
-- Haskell style with wildcard:
case x of
  True -> "yes"
  _    -> "no"

-- System F (explicit):
case x of
  True → "yes"
  False → "no"
```

Rationale: Wildcards hide exhaustiveness checking. Explicit patterns are clearer.

## 5. Atoms

### 5.1 Atom Grammar

```
atom      ::= "(" expr ")"
           |   ident
           |   CONSTRUCTOR
           |   INT
           |   STRING
```

### 5.2 Postfix Operators

Atoms can have postfix operators:

```
atom_with_postfix ::= atom ("@" type)* (":" type)*
```

**Examples:**
```systemf
x : Int                   -- type annotation
f @Int                    -- type application
(f x) : Int               -- parens + annotation
```

## 6. Operator Precedence

Full precedence table (high to low):

```
Precedence | Operators                     | Associativity
-----------|-------------------------------|--------------
10.        | Atom, parentheses, literals   | -
9.         | Postfix @, [], :              | Right
8.         | Function application          | Left
7.         | *, /                          | Left
6.         | +, -                          | Left
5.         | ==, /=, <, >, <=, >=          | None
4.         | &&                            | Right
3.         | ||                            | Right
2.         | → (arrow in types)            | Right
1.         | λ, Λ, let, if, case           | Keywords
0.         | top-level declarations        | -
```

## 7. Declarations

### 7.1 Declaration Grammar

```
decl      ::= data_decl
           |  term_decl
           |  prim_type_decl
           |  prim_op_decl

data_decl ::= "data" CONSTRUCTOR [ident*] "=" constr ("|" constr)*

constr    ::= CONSTRUCTOR [type_atom*]

term_decl ::= ident ":" type "=" expr

prim_type_decl ::= "prim_type" CONSTRUCTOR

prim_op_decl   ::= "prim_op" ident ":" type
```

### 7.2 Data Declaration Layout

**Style 1: Inline**
```systemf
data Bool = True | False
data Maybe a = Nothing | Just a
```

**Style 2: Indented**
```systemf
data List a =
  Nil
  | Cons a (List a)
```

**Note:** Data declarations ALWAYS use `|` as the constructor separator (following Haskell). This is different from case expressions which use `;` in explicit brace mode.

## 8. Layout and Parser Combinators

### 8.1 Core Principle

Layout is handled at the **parser level**, not the lexer. Parser combinators check token columns against explicit constraints.

### 8.2 Constraint Types

Following Idris2's design:

```python
ValidIndent = AnyIndent | AtPos(int) | AfterPos(int) | EndOfBlock
```

- `AnyIndent`: Inside `{...}`, no column checking
- `AtPos(col)`: Must be at exact column
- `AfterPos(col)`: At or after column  
- `EndOfBlock`: Block has ended

### 8.3 Layout-Aware Combinators (from parser.helpers)

#### Core Infrastructure

**ValidIndent Type:**
```python
ValidIndent = AnyIndent | AtPos(int) | AfterPos(int) | EndOfBlock
```

#### Combinator Reference

**`column() -> Parser[int]`**
- Returns the column of the current token
- Used to capture the reference column for layout blocks
- Example: After `case x of`, call `column()` to get the column of the first branch

**`block(item: Callable[[ValidIndent], Parser[T]]) -> Parser[List[T]]`**
- Parses either `{ item; item; ... }` or a layout-indented block
- For explicit braces: uses `AnyIndent`, separators are `;`
- For layout mode: captures first token's column, uses `AtPos(col)`
- Returns list of parsed items

**`block_after(min_col: int, item: Callable[[ValidIndent], Parser[T]]) -> Parser[List[T]]`**
- Parses a block that must be indented at least `min_col`
- Uses `AfterPos(min_col)` as initial constraint
- Falls back to empty list if not indented enough

**`block_entries(constraint: ValidIndent, item: Callable[[ValidIndent], Parser[T]]) -> Parser[List[T]]`**
- Parses zero or more items with the given column constraint
- Handles terminators (`;` in braces, dedent in layout)
- Stops when terminator indicates end of block

**`block_entry(constraint: ValidIndent, item: Callable[[ValidIndent], Parser[T]]) -> Parser[Tuple[T, ValidIndent]]`**
- Parses a single item and checks its column against constraint
- Returns the parsed item and updated constraint for next entry
- Raises parse error if column doesn't satisfy constraint

**`terminator(constraint: ValidIndent, start_col: int) -> Parser[ValidIndent]`**
- Checks for block terminators
- In braces mode: looks for `;` (continue) or `}` (end)
- In layout mode: checks if current column <= start_col (end block)
- Returns updated constraint for next entry

**`must_continue(constraint: ValidIndent, expected: Optional[str]) -> Parser[None]`**
- Verifies we're still within the block
- Used after keywords to ensure layout hasn't ended
- Raises fatal error with helpful message if constraint is `EndOfBlock`

#### Parser Combinators

**`top_decl(constraint: ValidIndent) -> Parser[Decl]`**
- Parses top-level declarations
- Data, let, type declarations
- Uses greedy parsing for data (until next top-level token)

**`data_decl(constraint: ValidIndent) -> Parser[DataDecl]`**
- Parses `data X = A | B | ...`
- Constructors separated by `|`
- NOT layout-sensitive - `|` can be at any column
- Ends when next token at column <= constraint start column

**`let_decl(constraint: ValidIndent) -> Parser[LetDecl]`**
- Parses `let bindings in expr`
- Bindings form a layout block after `let`
- `in` must be at column >= let's column

**`case_expr(constraint: ValidIndent) -> Parser[CaseExpr]`**
- Parses `case scrutinee of branches`
- Branches form a layout block after `of`
- Each branch: pattern `->` expression

**`expr_parser(constraint: ValidIndent) -> Parser[Expr]`**
- Parses expressions with layout awareness
- Handles nested case, let, lambdas

**`type_parser(constraint: ValidIndent) -> Parser[Type]`**
- Parses type expressions
- Forall types, arrows, applications

### 8.4 Layout Rules by Construct

**Data declarations (NO layout):**
```systemf
data Bool = True | False          -- inline
data List a =                     -- multiline allowed
  Nil
  | Cons a (List a)              -- | can be at any column
```
Data uses greedy parsing with `|` as separator. Ends when next top-level token found.

**Case expressions (layout):**
```systemf
case x of
  True → a      -- Must align with first branch
  False → b     -- Must be at same column
```
After `of`, first branch sets reference column. Subsequent branches must match.

**Let expressions (layout):**
```systemf
let
  x = 1         -- Reference column from first binding
  y = 2         -- Must match
in x + y        -- 'in' must be at/after 'let' column
```

**Explicit braces override:**
```systemf
case x of { True → a; False → b }  -- No layout checking
```

### 8.5 Implementation Notes

**No global state:** Constraints passed explicitly to each parser.

**First-token reference:** Layout blocks use first token's column as reference.

**Top-level implicit block:** Entire module is implicit layout block at column 0.

## 9. Desugaring

Surface syntax desugars to core System F:

### 9.1 If-Then-Else
```systemf
if c then t else f
-- desugars to -->
case c of
  True → t
  False → f
```

### 9.2 Multi-Argument Lambda
**Value abstraction:**
```systemf
λx y → z
-- desugars to -->
λx → λy → z
```

**Type abstraction:**
```systemf
Λa b. body
-- desugars to -->
Λa. Λb. body
```

### 9.3 Operators
```systemf
x + y
-- desugars to -->
$prim.int_plus x y
```

### 9.4 Let-In

**Single binding:**
```systemf
let x = v in e
-- desugars to -->
(λx → e) v
```

**Multiple bindings:**
```systemf
let x = 1; y = 2 in e
-- desugars to -->
let x = 1 in let y = 2 in e
```

Note: Multiple bindings desugar to nested lets. The bindings are NOT mutually recursive. For recursion, use explicit fixpoint combinators.

## 10. Examples

### Example 1: Basic Functions
```systemf
-- Single argument
id : ∀a. a → a
id = Λa. λx:a → x

-- Multi-argument (desugars to nested)
const : ∀a. a → (∀b. b → a)
const = Λa b. λx y → x
```

### Example 2: List Operations
```systemf
map : ∀a. ∀b. (a → b) → List a → List b
map = Λa. Λb. λf:(a → b) → λxs:List a →
  case xs of
    Nil → Nil
    Cons y ys → Cons (f y) (map f ys)
```

### Example 3: Higher-Order
```systemf
compose : ∀a. ∀b. ∀c. (b → c) → (a → b) → a → c
compose = Λa. Λb. Λc. λf:(b → c) → λg:(a → b) → λx:a →
  f (g x)
```

### Example 4: Tuples
Tuples are provided via Pair types (Pair2 through Pair20 in prelude):
```systemf
-- Pair (2-tuple)
p : Pair Int String
p = Pair 1 "hello"

-- Access via pattern matching
fst : ∀a. ∀b. Pair a b → a
fst = Λa b. λp → case p of Pair x y → x
```

## 11. Parser Structure

### 11.1 Tiered Architecture

```
Tier 1 (indentation.py):  Fundamental combinators
  - indented_block
  - indented_opt

Tier 2 (parser.py):       Expression parsing
  - atom_parser
  - app_parser
  - lambda_parser
  - if_parser
  - case_parser
  - term_parser

Tier 3 (parser.py):       Type parsing
  - atom_type
  - app_type
  - arrow_type
  - forall_type
  - type_parser

Tier 4 (parser.py):       Declarations
  - data_decl_parser
  - term_decl_parser
  - program_parser
```

### 11.2 Design Principles

1. **Prelude-First:** The parser accepts valid `prelude.sf` syntax
2. **DRY:** Common patterns use helpers from `indentation.py`
3. **Test Tiering:** Expressions tested separately from declarations
4. **Explicit Over Implicit:** No wildcards, explicit constructors
5. **Simple Precedence:** Type app > Value app > Operators

## 12. Future Extensions (Not Implemented)

- Record types: `data Point = { x : Int, y : Int }`
- Pattern guards: `| p <- e -> f`
- List literals: `[1, 2, 3]`
- String interpolation: `"Hello, ${name}"`
- Type synonyms: `type String = List Char`
- Module imports: `import List`
- Tuple syntax: `(a, b, c)` desugaring to Pair types

---

**See Also:**
- `prelude.sf` - Canonical syntax examples
- `docs/architecture.md` - Implementation details
- `tests/test_surface/test_expressions.py` - Expression-level tests
