---
role: Architect
expertise: ['Parser Design', 'Python', 'Formal Languages']
skills: []
type: design
priority: critical
dependencies: []
refers: []
kanban: tasks/7-kanban-systemf-parser-indentation-aware-refactoring.md
created: 2026-02-25T14:59:59.444467
---

# Task: Design Indentation-Aware Lexer

## Context
<!-- Background information and relevant context -->

## Files
- systemf/src/systemf/surface/lexer.py
- systemf/src/systemf/surface/parser.py
- systemf/tests/test_surface/test_lexer.py

## Description
Design an indentation-aware lexer that tracks indentation levels and emits INDENT/DEDENT tokens. The design should be compatible with the current parsy-based parser architecture. Include the token types needed, the indentation tracking algorithm, and how to handle edge cases like blank lines and comments.

## Work Log

### 2026-02-25: Design Indentation-Aware Lexer

**Architect Analysis:**

Examined current lexer implementation in `systemf/src/systemf/surface/lexer.py`:
- 172 lines, simple regex-based tokenizer
- Current token types: WHITESPACE, COMMENT, DATA, LET, IN, CASE, OF, FORALL, TYPE, ARROW, DARROW, LAMBDA, TYPELAMBDA, EQUALS, COLON, BAR, AT, DOT, LPAREN, RPAREN, LBRACKET, RBRACKET, LBRACE, RBRACE, COMMA, CONSTRUCTOR, IDENT, NUMBER, EOF
- Uses parsy-based parser that expects list of tokens
- Currently skips all whitespace (including newlines) and comments

**Design Decisions:**

1. **New Token Types to Add:**
   - `INDENT`: Emitted when indentation level increases
   - `DEDENT`: Emitted when indentation level decreases
   - Keep `EOF` but may emit DEDENTs before it to close open blocks

2. **Indentation Tracking Algorithm:**
   - Track a stack of indentation levels (column positions)
   - Initialize stack with [0] representing outermost level
   - For each new line, measure leading whitespace (spaces/tabs)
   - Skip blank lines (lines with only whitespace/comments)
   - If current > stack[-1]: emit INDENT, push current
   - If current < stack[-1]: pop and emit DEDENT until current == stack[-1]
   - If current not in stack: error (inconsistent indentation)

3. **Handling Edge Cases:**
   - **Blank lines**: Ignored for indentation tracking (continue scanning)
   - **Comments**: Line comments ignored, but newlines reset line tracking
   - **First non-blank line**: Must start at column 0 or be indented (error if not)
   - **EOF**: Emit DEDENTs to close all open blocks, then EOF
   - **Tab vs Space**: Error if mixed on same line; recommend spaces only
   - **Multiple dedents**: Emit multiple DEDENT tokens for large indentation drops

4. **TokenType Enum:**
   - Create `TokenType` enum in `systemf/src/systemf/surface/types.py`
   - Use enum values for token types instead of raw strings
   - Enables type safety and IDE completion

5. **Lexer Interface Changes:**
   - Constructor remains same: `Lexer(source, filename)`
   - `tokenize()` returns list[Token] as before
   - Add `_indent_stack: list[int]` for tracking levels
   - Add `_handle_indentation(line_start_column)` helper
   - Modify main loop to track line starts and call indentation handler

6. **Backward Compatibility:**
   - All existing token types preserved
   - Parser can ignore INDENT/DEDENT initially, then opt-in
   - Old tests should pass without modification (if parser skips new tokens)

**Files Modified/Created:**
- Created: `systemf/src/systemf/surface/types.py` - TokenType enum and type definitions
- Documented: Test contracts in work log below

**Test Contracts (What Tests Must Verify):**

```
INDENT Token Emission:
- When line has more indentation than previous non-blank line, emit INDENT
- INDENT token location points to first non-whitespace character of indented line
- INDENT token value is the indentation column number

DEDENT Token Emission:
- When line has less indentation than previous non-blank line, emit DEDENT(s)
- Number of DEDENTs equals number of indentation levels exited
- DEDENTs emitted BEFORE tokens on the dedented line
- DEDENT location points to first non-whitespace character of dedented line

Multiple DEDENT Handling:
- Indentation drop of 2+ levels emits 2+ DEDENT tokens
- DEDENTs emitted in order (innermost first)
- After DEDENTs, stack contains outer level(s)

Blank Line Handling:
- Blank lines (only whitespace/comments) don't change indentation
- Indentation tracked relative to last non-blank line
- Consecutive blank lines don't cause issues

Comment Handling:
- Line comments don't affect indentation tracking
- Comment-only lines are treated as blank
- Comments after code on same line preserve that line's indentation

EOF Handling:
- At EOF, emit DEDENTs to close all open blocks
- Then emit EOF token
- DEDENTs point to EOF location

Error Cases:
- Inconsistent indentation (indent not matching any level in stack)
- Mixed tabs and spaces on same line
- Indentation after blank line doesn't match any previous level
- First line indented (no outer level to reference)

Complex Scenarios:
- Nested blocks with multiple indent/dedent levels
- Lambda expressions with indentation
- Let bindings with multi-line values
- Data declarations with multi-line constructors
```

**Risks and Mitigations:**
- Risk: Breaking existing tests that assume no INDENT/DEDENT
  - Mitigation: Parser initially filters out INDENT/DEDENT tokens
- Risk: Parser complexity increases significantly
  - Mitigation: Design parser combinators for indentation-aware parsing
- Risk: Performance overhead of tracking stack
  - Mitigation: Minimal overhead, stack rarely exceeds depth 5-10

**Follow-up Tasks:**
- Task 10: Implement indentation-aware lexer
- Task 11: Design parser combinators for indentation tokens
