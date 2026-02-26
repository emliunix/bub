---
role: Implementor
expertise: ['Python 3.12+', 'Pattern Matching']
skills: ['python-project']
type: implement
priority: medium
state: done
dependencies: []
refers: []
kanban: tasks/16-kanban-systemf-language-implementation.md
created: 2026-02-26T11:26:49.721026
---

# Task: Refactor isinstance to match Pattern Matching

## Context
This task is part of the SystemF Language Implementation project. The codebase currently uses isinstance checks throughout (e.g., parser.py app_type, arrow_type). Python 3.12+ supports pattern matching which would be cleaner and more readable.

## Files
- systemf/src/systemf/surface/*.py
- systemf/src/systemf/core/*.py
- systemf/src/systemf/eval/*.py

## Description
Refactor isinstance checks to use Python 3.12+ match pattern matching. Focus on parser.py app_type and arrow_type first, then extend to other files. This is a code quality improvement that makes the code more idiomatic and easier to maintain.

**Acceptance Criteria:**
- Replace isinstance checks with match/case patterns where appropriate
- Focus on parser.py app_type, arrow_type first
- Maintain identical functionality
- All existing tests pass
- Code is more readable after refactoring

## Work Log
<!-- Work logs will be appended here -->

### [2026-02-26 11:36:09] Refactored isinstance to pattern matching

**Facts:**
Refactored isinstance checks in 6 files: parser.py app_type function (1 isinstance check), unify.py apply/occurs_in/unify functions (25 isinstance checks), elaborator.py elaborate_declaration function (2 isinstance checks), surface/ast.py __str__ methods (2 isinstance checks), core/types.py __str__ methods (2 isinstance checks). Pattern matching makes the code more readable and idiomatic for Python 3.12+. The match/case syntax is cleaner for type dispatch than isinstance chains. All 294 tests pass after refactoring. The unify.py changes are the most significant - converting 25 isinstance checks into clean pattern matches.

**Analysis:**
-

**Conclusion:**
Status: ok

---

