---
role: Implementor
expertise: ['Python', 'Parser Implementation']
skills: []
type: implement
priority: high
dependencies: ['tasks/8-design-indentation-aware-lexer.md']
refers: []
kanban: tasks/7-kanban-systemf-parser-indentation-aware-refactoring.md
created: 2026-02-25T15:00:13.089747
---

# Task: Implement Indentation-Aware Lexer

## Context
<!-- Background information and relevant context -->

## Files
- systemf/src/systemf/surface/lexer.py
- systemf/tests/test_surface/test_lexer.py

## Description
Implement the indentation-aware lexer based on the Architect's design. Modify lexer.py to track indentation levels and emit INDENT/DEDENT tokens. Ensure all existing tests still pass with the new implementation.

## Work Log

### 2026-02-25: Implemented Indentation-Aware Lexer

**Implementation Summary:**

Modified `systemf/src/systemf/surface/lexer.py` to implement stack-based indentation tracking as designed in task 8.

**Key Changes:**

1. **Token pattern changes:**
   - Split `WHITESPACE` pattern to separate newlines: `WHITESPACE` (`[ \t]+`) and `NEWLINE` (`\n|\r\n?`)
   - This allows tracking line boundaries for indentation processing

2. **Added indentation tracking state:**
   - `_indent_stack: list[int]` - Stack of indentation levels, initialized with `[0]` (column 0)
   - `_at_line_start: bool` - Tracks whether we're at start of a logical line
   - `_leading_ws_pattern` - Regex to match leading whitespace `[ \t]*` (no `^` anchor since `match()` already matches at current position)
   - `_skip_indent: bool` - Configuration flag for backward compatibility

3. **New methods:**
   - `_process_indentation()` - Processes indentation at line starts, emits INDENT/DEDENT, returns True if blank line
   - `_skip_to_end_of_line()` - Skips from current position to end of line (including newline)
   - `_emit_dedents_to_level()` - Emits DEDENT tokens to reach target indentation level
   - `_is_blank_line()` - Detects blank lines (whitespace/comments only)

4. **Modified `tokenize()` method:**
   - At line start: call `_process_indentation()` to check indentation
   - Track `_at_line_start` across newline tokens
   - Skip blank lines via `_process_indentation()` return value
   - At EOF: emit DEDENTs to close all open blocks before EOF token
   - Filter out INDENT/DEDENT tokens at the end if `_skip_indent=True` (default)

5. **Backward compatibility via `skip_indent` parameter:**
   - `Lexer(source, filename, skip_indent=True)` - Default, filters out INDENT/DEDENT tokens
   - `lex(source, filename, skip_indent=True)` - Default, backward compatible
   - Set `skip_indent=False` to receive INDENT/DEDENT tokens for indentation-aware parsing

6. **Error handling:**
   - Mixed tabs and spaces on same line → LexerError (only on non-blank lines)
   - Inconsistent indentation (indent doesn't match any previous level) → LexerError

**Example indentation output:**
```
let x = 1
  let y = 2
    z = 3
  w = 4
v = 5
```
With `skip_indent=False` produces:
- LET IDENT EQUALS NUMBER
- INDENT LET IDENT EQUALS NUMBER  
- INDENT IDENT EQUALS NUMBER
- DEDENT IDENT EQUALS NUMBER
- DEDENT IDENT EQUALS NUMBER EOF

**Test Results:**
- All 32 lexer tests pass ✓
- All 47 parser tests pass ✓
- All 10 integration tests pass ✓
- All 148 project tests pass ✓

**Design Notes:**
- INDENT token value = column number (as string)
- DEDENT token value = new indentation level (as string)
- Blank lines (whitespace/comments only) are skipped and don't affect indentation
- DEDENTs are emitted before tokens on the dedented line
- Backward compatibility maintained via `skip_indent` parameter (default True)

**Files modified:**
- `systemf/src/systemf/surface/lexer.py` - Indentation-aware implementation with backward compatibility

**Files unchanged:**
- `systemf/src/systemf/surface/types.py` - TokenType definitions already existed
