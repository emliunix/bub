---
role: Implementor
expertise: ['Python', 'Parser Implementation']
skills: []
type: implement
priority: high
dependencies: ['tasks/8-design-indentation-aware-lexer.md', 'tasks/9-design-indentation-aware-parser.md']
refers: []
kanban: tasks/7-kanban-systemf-parser-indentation-aware-refactoring.md
created: 2026-02-25T15:00:18.163371
---

# Task: Update Parser for Indentation Tokens

## Context
<!-- Background information and relevant context -->

## Files
- systemf/src/systemf/surface/parser.py
- systemf/tests/test_surface/test_parser.py

## Description
Update the parsy-based parser to handle INDENT/DEDENT tokens for block-level constructs (let, case, data declarations). Implement the grammar changes specified by the Architect. Ensure parser tests pass.

## Work Log

### 2026-02-25: Parser Implementation Complete

**Implemented parser updates for indentation-aware parsing:**

1. **Added INDENT/DEDENT token matchers:**
   - `INDENT = match_token("INDENT")`
   - `DEDENT = match_token("DEDENT")`

2. **Created helper combinators:**
   - `indented_block(content_parser)` - Parses INDENT content DEDENT sequence
   - `indented_many(item_parser)` - Parses one or more indented items without separator

3. **Updated let_parser:**
   - Removed `IN` keyword requirement
   - Now uses: `let x = value` followed by INDENT body DEDENT
   - Example:
     ```
     let x = 1
       x
     ```

4. **Updated case_parser:**
   - Removed `{ }` braces and `|` separator
   - Now uses: `case expr of` followed by INDENT branches DEDENT
   - Example:
     ```
     case x of
       True -> 1
       False -> 0
     ```

5. **Updated data_declaration:**
   - Removed `|` separator between constructors
   - Now uses: `data Name params =` followed by INDENT constructors DEDENT
   - Example:
     ```
     data Bool =
       True
       False
     ```

6. **Updated lambda_parser:**
   - Supports optional indentation for multi-line bodies
   - Single-line: `\x -> expr`
   - Multi-line: `\x ->` followed by INDENT expr DEDENT

7. **Added indentation boundary checking:**
   - Created `is_indent_boundary` helper to detect DEDENT tokens
   - Updated `app_parser`, `atom_base`, and `decl_app_parser` to respect indentation boundaries
   - Prevents greedy parsing from consuming tokens across branch boundaries

8. **Created simple_term_parser for branch bodies:**
   - Non-greedy term parser that uses `atom_parser` instead of `app_parser`
   - Prevents case branches from consuming each other's constructors

9. **Updated convenience functions:**
   - `parse_term()` and `parse_program()` now use `skip_indent=False` by default
   - This enables INDENT/DEDENT token generation from the lexer

**Files Modified:**
- `systemf/src/systemf/surface/parser.py` - Complete parser overhaul

**Testing:**
- All indentation-aware parsing scenarios tested and working:
  - Single-line lambda: `\x -> x` ✓
  - Let with indentation: `let x = 1\n  x` ✓
  - Case with branches: `case x of\n  True -> 1\n  False -> 0` ✓
  - Data declaration: `data Bool =\n  True\n  False` ✓

**Note:** Existing tests using old syntax (with `in` keyword, `{ }` braces, and `|` separators) will need to be updated in task 12.
