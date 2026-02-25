---
role: Implementor
expertise: ['Technical Writing', 'Documentation']
skills: ['markdown']
type: implementation
priority: medium
dependencies: [4-rewrite-tests.md]
refers: [1-kanban-systemf-parser-indentation.md]
kanban: tasks/1-kanban-systemf-parser-indentation.md
created: 2026-02-25T14:40:00.000000
---

# Task: Update Documentation and Examples

## Context
All documentation and examples need to be updated to show the new indentation-aware syntax.

## Files to Check and Update
1. `systemf/README.md` - Main README with examples
2. `systemf/demo.py` - Demo script examples
3. `systemf/src/systemf/eval/repl.py` - REPL examples/help
4. Any other documentation files

## Requirements

1. **Update all code examples**
   - Convert flat syntax to indented syntax
   - Ensure examples are syntactically correct
   - Use consistent 4-space indentation

2. **Update README**
   - Syntax examples
   - Getting started guide
   - Language features descriptions

3. **Update demo.py**
   - Example programs shown in demo
   - Comments explaining syntax

4. **Update REPL help**
   - Any help text showing syntax examples

## Files to Modify
- `systemf/README.md`
- `systemf/demo.py`
- `systemf/src/systemf/eval/repl.py`
- Any other docs with examples

## Success Criteria
- [ ] All code examples use new indentation syntax
- [ ] README updated with new examples
- [ ] Demo script runs successfully
- [ ] REPL help text updated
- [ ] All examples verified to parse correctly

## Work Log

