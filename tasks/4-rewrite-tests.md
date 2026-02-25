---
role: Implementor
expertise: ['Test Engineering', 'Python']
skills: ['python-uv', 'pytest']
type: implementation
priority: high
dependencies: [3-parser-indentation.md]
refers: [1-kanban-systemf-parser-indentation.md]
kanban: tasks/1-kanban-systemf-parser-indentation.md
created: 2026-02-25T14:40:00.000000
---

# Task: Rewrite Tests for Indentation-Aware Syntax

## Context
All existing tests use the old flat syntax. They need to be rewritten to use the new indentation-aware syntax. This is the bulk of the work with 260+ tests across 13 test files.

## Test Files to Update
1. `systemf/tests/test_surface/test_lexer.py` - Update lexer tests
2. `systemf/tests/test_surface/test_parser.py` - Update parser tests
3. `systemf/tests/test_surface/test_elaborator.py` - Update elaborator tests
4. `systemf/tests/test_surface/test_integration.py` - Update integration tests
5. `systemf/tests/test_core/test_checker.py` - Update type checker tests
6. `systemf/tests/test_core/test_context.py` - Update context tests
7. `systemf/tests/test_core/test_types.py` - Update types tests
8. `systemf/tests/test_core/test_unify.py` - Update unification tests
9. `systemf/tests/test_eval/test_evaluator.py` - Update evaluator tests
10. `systemf/tests/test_eval/test_integration.py` - Update eval integration tests
11. `systemf/tests/test_eval/test_pattern.py` - Update pattern tests
12. `systemf/tests/test_eval/test_values.py` - Update values tests

## Requirements

1. **Update test syntax**
   - Convert flat syntax to indented syntax
   - Maintain test semantics (what's being tested)
   - Use consistent 4-space indentation

2. **Example conversions**
   ```python
   # Before:
   "let x = 1 in x"
   
   # After:
   """
   let x = 1 in
       x
   """
   
   # Before:
   "case x of { Just y -> y | Nothing -> 0 }"
   
   # After:
   """
   case x of
       Just y -> y
       Nothing -> 0
   """
   
   # Before:
   "data Maybe a = Just a | Nothing"
   
   # After:
   """
   data Maybe a =
       Just a
       Nothing
   """
   ```

3. **Maintain test coverage**
   - All existing tests should still test the same functionality
   - No test logic changes, only syntax

## Files to Modify
- All files in `systemf/tests/`

## Success Criteria
- [ ] All 13 test files updated
- [ ] All 260+ tests pass with new syntax
- [ ] No test functionality changed (only syntax)
- [ ] Test coverage maintained

## Work Log

