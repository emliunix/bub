---
role: Implementor
expertise: ['Python', 'Parser Design', 'Pattern Matching']
skills: ['python-project', 'testing']
type: implement
priority: high
state: done
dependencies: []
refers: []
kanban: tasks/16-kanban-systemf-language-implementation.md
created: 2026-02-26T12:05:00.000000
---

# Task: Support Both Pattern Matching Syntaxes

## Context
This task is part of the SystemF Language Implementation project. Following the successful completion of Task 24 (data declaration syntax with = and |), we now need to implement dual pattern matching syntax support.

The language should support both:
1. Indented style (current): Pattern matching with indentation-based structure
2. Explicit style: Pattern matching with explicit `{ | }` syntax for structural clarity

## Files
- systemf/src/systemf/surface/parser.py
- systemf/src/systemf/surface/grammar.py (if applicable)
- Related test files in systemf/tests/test_surface/

## Description
Implement support for both pattern matching syntax styles in the SystemF parser.

**Current State:**
- Pattern matching likely uses indentation-based syntax
- Need to add support for explicit `{ | }` style

**Requirements:**
1. **Indented Style** (maintain existing):
   ```
   case x of
       Zero -> ...
       Succ n -> ...
   ```

2. **Explicit Style** (add support):
   ```
   case x of {
       | Zero -> ...
       | Succ n -> ...
   }
   ```

3. Both styles should parse to the same AST representation
4. The explicit style uses:
   - Opening brace `{` after `of`
   - Each alternative prefixed with `|`
   - Closing brace `}`
   - Arrows `->` to separate pattern from result

**Acceptance Criteria:**
- Parser correctly handles both syntax styles
- Both styles produce equivalent AST
- All existing tests pass
- New tests added for explicit syntax
- Clear error messages for malformed pattern matching
- Ensure nested pattern matching works in both styles

## Work Log
<!-- Work logs will be appended here -->

### [2026-02-26 12:00:28] Implementation Complete

**Facts:**
Modified systemf/src/systemf/surface/parser.py to add explicit_branch_parser and explicit_branches_parser parsers. Updated case_parser and decl_case_parser to support both syntaxes. Modified tests/test_surface/test_parser.py with 4 new tests. All 292 tests pass.

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-02-26 12:01:09] Implementation Complete - Detailed

**Facts:**
- Modified `systemf/src/systemf/surface/parser.py` to support dual pattern matching syntaxes
- Added `explicit_branch_parser` function to parse branches with explicit `|` prefix
- Added `explicit_branches_parser` function to parse one or more explicit branches
- Added `decl_explicit_branch_parser` and `decl_explicit_branches_parser` for declaration context
- Updated `case_parser` to detect `{` after `of` and route to appropriate parser
- Updated `decl_case_parser` similarly for declaration context
- Modified `tests/test_surface/test_parser.py`:
  - Added 4 new tests for explicit syntax in `TestCaseExpressions` class
  - Renamed `test_case_bar_not_supported` to `test_case_explicit_syntax_supported` (now tests that explicit syntax works)
  - Renamed `test_case_braces_not_supported` to `test_case_braces_without_bar_fails` (tests that `{` without `|` fails)
- All 292 tests pass (4 new, 1 skipped, 2 xfailed as expected)

**Analysis:**
The implementation allows both syntaxes to coexist:
1. **Indented style**: `case x of\n  True -> y\n  False -> z` (existing)
2. **Explicit style**: `case x of { | True -> y | False -> z }` (new)

Key design decisions:
- Explicit syntax requires `|` before each branch for visual consistency and clarity
- Both syntaxes produce identical AST representations (`SurfaceCase` with `SurfaceBranch` elements)
- The parser uses `LBRACE.optional()` to detect which syntax to use
- Branch parsing logic is shared between regular and declaration contexts

The implementation follows existing patterns:
- Uses `@generate` decorator for monadic parsing
- Follows same structure as `indented_many` pattern
- Maintains separation between `term_parser` and `decl_term_parser` contexts

**Conclusion:**
Status: ok

Task completed successfully. Both pattern matching syntaxes are now supported in the SystemF parser. The explicit `{ | }` syntax provides structural clarity while the indented style maintains the clean Haskell-like appearance. All existing tests continue to pass, and new tests verify the explicit syntax functionality.

---

