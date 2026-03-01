---
assignee: Implementor
expertise: ['Lexer design', 'Look-ahead parsing']
skills: ['python-project']
type: implement
priority: medium
state: review
dependencies: ['tasks/75-fix-lexer-to-emit-docstring-and-pragma-tokens.md']
refers: []
kanban: tasks/parser-docstring-pragma-kanban.md
created: 2026-03-01T16:48:59.889138
---

# Task: Enhance lexer to merge consecutive comments after docstrings

## Context
<!-- Background information and relevant context -->

## Files
- systemf/src/systemf/surface/parser/lexer.py
- tests/test_surface/test_parser/test_decl_docstrings.py

## Description
<!-- What needs to be done -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-01 16:57:47] Implementation Complete

**Facts:**
Enhanced lexer in systemf/src/systemf/surface/parser/lexer.py to merge consecutive -- comments after -- | docstrings (Haddock-style). Added _create_docstring_token method that looks ahead and accumulates consecutive -- lines, stopping at blank lines, new docstrings (-- | or -- ^), or pragmas ({-#). Content is concatenated with single spaces between parts. Tests added to systemf/tests/test_surface/test_parser/test_decl_docstrings.py verify: 1) Basic merging (test_multiline_docstring_concatenation) - PASSED, 2) Stops at blank lines (test_multiline_docstring_stops_at_code) - PASSED, 3) Stops at new docstrings (test_multiline_docstring_stops_at_new_docstring) - PASSED, 4) Stops at pragmas (test_multiline_docstring_stops_at_pragma) - PASSED. Pre-existing test failure test_term_multiline_docstring is unrelated to these changes.

**Analysis:**
-

**Conclusion:**
Status: ok

---

