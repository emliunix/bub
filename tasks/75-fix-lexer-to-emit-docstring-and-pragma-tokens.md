---
assignee: Implementor
expertise: ['Parser combinators', 'Lexical analysis']
skills: ['python-project']
type: implement
priority: medium
state: review
dependencies: []
refers: []
kanban: tasks/parser-docstring-pragma-kanban.md
created: 2026-03-01T14:50:41.046703
---

# Task: Fix lexer to emit docstring and pragma tokens

## Context
<!-- Background information and relevant context -->

## Files
- systemf/src/systemf/surface/parser/lexer.py
- systemf/src/systemf/surface/parser/types.py
- tests/test_surface/test_parser/test_decl_docstrings.py
- tests/test_surface/test_parser/test_decl_pragma.py

## Description
<!-- What needs to be done -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-01 14:55:21] Lexer fix for docstring and pragma tokens

**Facts:**
Fixed lexer to emit DocstringToken for -- | ... comments and PragmaToken for {-# ... #-} pragmas. Modified: systemf/src/systemf/surface/parser/lexer.py (updated tokenize() to handle pragmas in _read_pragma(), modified _skip_whitespace() to preserve docstrings, updated _create_token() to emit DocstringToken), systemf/src/systemf/surface/parser/types.py (simplified PragmaToken to use content field only, removed pragma_type field). Also fixed syntax error in conftest.py. Tests now fail at parser level (parser needs to consume docstrings/pragmas), but lexer correctly emits tokens as verified by manual testing.

**Analysis:**
-

**Conclusion:**
Status: ok

---

