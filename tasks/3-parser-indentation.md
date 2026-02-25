---
role: Implementor
expertise: ['Parser Design', 'Python', 'Grammar Design']
skills: ['python-uv']
type: implementation
priority: high
dependencies: [2-lexer-indentation.md]
refers: [1-kanban-systemf-parser-indentation.md]
kanban: tasks/1-kanban-systemf-parser-indentation.md
created: 2026-02-25T14:40:00.000000
---

# Task: Update Parser for Indentation-Aware Grammar

## Context
After the lexer emits INDENT/DEDENT tokens, the parser must be updated to use these tokens for structure. This will enable robust parsing without relying on declaration boundary heuristics.

Current parser is in: `systemf/src/systemf/surface/parser.py`

## Requirements

1. **Update token matchers**
   - Add matchers for INDENT and DEDENT tokens
   - Update existing token patterns

2. **Update grammar rules to use indentation**
   - `let` bindings: body should be indented
   - `case` expressions: branches should be indented
   - Data declarations: constructors should be indented
   - Top-level declarations: should handle indentation

3. **Remove or simplify declaration boundary logic**
   - Current `is_decl_boundary` and `decl_*` parsers are workarounds
   - With indentation, these may become unnecessary
   - Evaluate and simplify if possible

4. **Grammar changes needed**
   - Let expressions: `let x = expr in indented_body`
   - Case expressions: `case scrutinee of indented_branches`
   - Data declarations: `data Type = indented_constructors`

## Files to Modify
- `systemf/src/systemf/surface/parser.py`

## Success Criteria
- [ ] Parser recognizes INDENT/DEDENT tokens
- [ ] Let expressions parse with indented bodies
- [ ] Case expressions parse with indented branches
- [ ] Data declarations parse with indented constructors
- [ ] Declaration boundary heuristics simplified or removed
- [ ] All existing parser tests still pass (before test syntax changes)

## Work Log

