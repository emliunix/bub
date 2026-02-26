---
role: Implementor
expertise: ['Python', 'Parser Design', 'Grammar Design']
skills: ['python-project', 'testing']
type: implement
priority: high
state: done
dependencies: []
refers: []
kanban: tasks/16-kanban-systemf-language-implementation.md
created: 2026-02-26T12:00:00.000000
---

# Task: Fix data_declaration in surface.parser.py - Keep = and | Syntax

## Context
This task is part of the SystemF Language Implementation project. The parser currently uses a data declaration syntax that needs to be updated. We want to keep the traditional syntax with `=` and `|` for structural clarity, e.g., `data Nat = Zero | Succ Nat`.

This is Task 2 from the original requirements, following the completion of Task 23 (remove skip_indent) and the foundational tasks (token consolidation and pattern matching refactor).

## Files
- systemf/src/systemf/surface/parser.py
- systemf/src/systemf/surface/grammar.py (if grammar is separate)
- Related test files in systemf/tests/test_surface/

## Description
Update the data declaration parsing in `surface.parser.py` to support the traditional syntax with `=` and `|` for constructors.

**Current State:**
- Data declarations may exist but need to be verified
- The desired syntax is: `data Nat = Zero | Succ Nat`
- This provides clear visual separation between type name and constructors

**Requirements:**
1. Ensure data declarations use the `data TypeName = Constructor1 | Constructor2 Args` syntax
2. The `=` separates the type name from the constructor list
3. The `|` separates alternative constructors
4. Constructors can have arguments (e.g., `Succ Nat`)
5. Maintain backward compatibility if other syntaxes exist
6. All existing tests must pass
7. Add tests for the new syntax if not already present

**Acceptance Criteria:**
- Parser correctly parses `data Nat = Zero | Succ Nat` style declarations
- The `=` and `|` tokens are handled correctly in data declarations
- Constructors with arguments are parsed correctly
- All existing tests pass
- New tests added for the syntax variations
- Clear error messages for malformed data declarations

## Work Log
<!-- Work logs will be appended here -->

### [2026-02-26 11:54:02] Data Declaration Syntax Restored

**Facts:**
Modified systemf/src/systemf/surface/parser.py to use = and | syntax for data declarations. Added is_pattern_boundary helper to prevent constructor args from consuming next pattern. Updated program_parser to handle leading indentation. All 288 tests pass.

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-02-26 11:55:03] Additional Fix: = on New Line

**Facts:**
Updated data_declaration parser to handle = on a new line after INDENT. All syntax variations now work: single-line, multi-line with = on first line, and multi-line with = on second line. All 288 tests still pass.

**Analysis:**
-

**Conclusion:**
Status: ok

---

