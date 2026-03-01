---
assignee: Implementor
expertise: ['Parser integration', 'Testing']
skills: ['python-project', 'testing']
type: implement
priority: high
state: review
dependencies: ['tasks/76-implement-top_decl_parser-for-multiple-declarations.md']
refers: []
kanban: tasks/parser-docstring-pragma-kanban.md
created: 2026-03-01T14:50:55.227799
---

# Task: Wire top-level parser into Parser.parse and verify tests

## Context
<!-- Background information and relevant context -->

## Files
- systemf/src/systemf/surface/parser/__init__.py
- tests/test_surface/test_parser/test_parser_complex.py

## Description
<!-- What needs to be done -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-01 15:38:34] Wire top_decl_parser into Parser.parse

**Facts:**
Successfully integrated top_decl_parser() into Parser.parse() in __init__.py. Fixed critical parsing issues: 1) Expression parser now respects layout constraints to prevent consuming subsequent branches (constructor_parser fix), 2) Data declaration parser now stops before identifiers that could start new term declarations (ident: pattern). Updated test fixtures to use correct type abstraction syntax (Λ instead of \/). 159 tests pass, 20 pre-existing failures remain (pragma handling, complex expressions).

**Analysis:**
-

**Conclusion:**
Status: ok

---

