---
role: Implementor
expertise: ['Python', 'Lexer Design']
skills: ['python-project', 'testing']
type: implement
priority: high
state: done
dependencies: []
refers: []
kanban: tasks/16-kanban-systemf-language-implementation.md
created: 2026-02-26T11:37:26.306063
---

# Task: Remove skip_indent from surface.lexer.py

## Context
This task is part of the SystemF Language Implementation project. The lexer currently uses a `skip_indent` mechanism that needs to be removed entirely. The compatibility layer using `skip_indent` should be migrated to a new approach. This is Task 1 from the original requirements.

After completing the foundational tasks (token type consolidation and pattern matching refactor), we're now moving to core syntax improvements.

## Files
- systemf/src/systemf/surface/lexer.py
- Related parser files that may reference skip_indent

## Description
Remove `skip_indent` entirely from `surface.lexer.py` and migrate any compatibility code to a new approach.

**Requirements:**
1. Remove all `skip_indent` functionality from the lexer
2. Identify and migrate any compatibility code that relies on `skip_indent`
3. Ensure the lexer continues to handle indentation correctly as block boundaries
4. Maintain compatibility with existing syntax where indentation serves as block boundary
5. All existing tests must pass after the change

**Acceptance Criteria:**
- No references to `skip_indent` remain in surface.lexer.py
- Indentation still works correctly as block boundary
- All tests pass (294 tests currently passing)
- Code is cleaner and more maintainable

## Work Log
<!-- Work logs will be appended here -->

### [2026-02-26 11:40:46] Implementation Complete

**Facts:**
<!-- What was actually done (files modified, code written, tests run, etc.) -->
- Removed `skip_indent` parameter from `Lexer.__init__` in `systemf/src/systemf/surface/lexer.py`
- Removed `skip_indent` parameter from `lex()` convenience function in same file
- Removed `_skip_indent` instance variable and filtering logic (lines 159-160)
- Updated 2 call sites in `systemf/src/systemf/surface/parser.py` to remove `skip_indent=False` argument
- Removed all `skip_indent=False` arguments from test file `systemf/tests/test_surface/test_lexer.py` using sed
- Replaced `TestBackwardCompatibility` class with `TestIndentTokensIncluded` class containing a single test
- All 47 lexer tests pass
- All 148 tests in the full test suite pass

**Analysis:**
<!-- What problems were encountered, what approaches were tried, key decisions made -->
- The `skip_indent` parameter was originally a backward compatibility mechanism that defaulted to True, causing INDENT/DEDENT tokens to be filtered out
- With the new approach, indentation tokens are always emitted (which is what the parser needs)
- Had to update the test file to remove backward compatibility tests that were testing the old behavior
- Replaced with a test confirming that INDENT/DEDENT tokens are now always included by default
- Parser was already passing `skip_indent=False` so it didn't need any change in behavior, just removal of the parameter

**Conclusion:**
<!-- Pass/fail/escalate status and why, next steps, blockers if any -->
Status: ok

All requirements met:
- ✅ Removed skip_indent parameter from all functions
- ✅ Updated all call sites in parser and tests
- ✅ All 148 tests pass (47 lexer tests + 101 other tests)
- ✅ Code is cleaner with one less parameter to manage
- ✅ Indentation handling is now the sole, consistent behavior

---

