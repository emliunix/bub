---
role: Implementor
expertise: ['Documentation', 'Technical Writing']
skills: []
type: implement
priority: medium
dependencies: ['tasks/8-design-indentation-aware-lexer.md', 'tasks/9-design-indentation-aware-parser.md']
refers: []
kanban: tasks/7-kanban-systemf-parser-indentation-aware-refactoring.md
created: 2026-02-25T15:00:32.687622
---

# Task: Update Documentation and Examples

## Context
<!-- Background information and relevant context -->

## Files
- systemf/README.md
- systemf/demo.py
- systemf/src/systemf/eval/repl.py

## Description
Update all documentation and examples to use the new indentation-aware syntax. This includes README.md with code examples, demo.py demo script, and REPL help text in repl.py.

## Work Log

### 2026-02-25 - Documentation Update Complete

**Files Updated:**

1. **systemf/demo.py**
   - Updated all demo examples to use indentation-aware syntax:
     - Data declarations: `data Bool =\n  True\n  False` (multi-line)
     - Case expressions: `case b of\n  True -> False\n  False -> True` (no braces/bars)
     - Let expressions: `let x = 1\n  x + 1` (no `in` keyword, indented body)
   - Updated summary section with new syntax examples

2. **systemf/src/systemf/eval/repl.py**
   - Added syntax examples to `:help` command:
     - Data declaration example with multi-line constructors
     - Function with case expression example
     - Let binding example with indented body

3. **systemf/README.md**
   - Verified no code examples need updating (contains only bash commands)

**Syntax Changes Applied:**

| Feature | Old Syntax | New Syntax |
|---------|------------|------------|
| Data declarations | `data Bool = True \| False` | `data Bool =\n  True\n  False` |
| Case expressions | `case x of { A -> b \| C -> d }` | `case x of\n  A -> b\n  C -> d` |
| Let expressions | `let x = 1 in x` | `let x = 1\n  x` |

**Verification:**
- New syntax aligns with updated parser implementation
- Examples match test cases in test_parser.py and test_integration.py
- Documentation phase complete for indentation-aware refactoring
