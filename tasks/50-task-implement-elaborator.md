---
type: task
assignee: Implementor
expertise: Elaborator Integration
kanban: tasks/50-kanban-minimal-module-implementation.md
creator_role: manager
dependencies: [tasks/50-task-design-module.md]
skills: [python-project, testing]
type_field: implementation
---

# Implement Elaborator Module Return

## Objective
Update elaborator to return Module instead of tuple, and update all 24 call sites.

## Context
After the Module dataclass is designed, update:
1. `systemf/src/systemf/surface/elaborator.py` - Change `elaborate()` return type
2. All test files (24 call sites total)
3. REPL and demo files if needed

## Requirements

### Changes to elaborator.py:
- `elaborate()` returns `Module` instead of `tuple[list[Declaration], dict[str, Type]]`
- Move type registries from instance variables to Module fields
- Collect docstrings during elaboration

### Update Call Sites (24 total):
- `systemf/tests/test_surface/test_integration.py` (12 calls)
- `systemf/tests/test_string.py` (6 calls)
- `systemf/tests/test_eval/test_tool_calls.py` (1 call)
- `systemf/tests/test_eval/test_integration.py` (1 call)
- Plus 4 more calls elsewhere

## Acceptance Criteria
- [ ] Elaborator returns Module object
- [ ] All 24 call sites updated
- [ ] Tests pass
- [ ] No tuple unpacking remains

## Notes
- No backward compatibility shim - single pass update
- Tests will catch any missed updates


## Work Log

### [2026-02-27 17:55:03] Implementation Complete

**Facts:**
Updated elaborator to return Module instead of tuple. Fixed circular import by moving ElaborationError to core.errors. Updated all 22 call sites across test files, repl.py, and demo.py. All 435 tests pass.

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-02-27 18:05:00] Architect Review - APPROVED

**Review Checklist:**
- ✅ Elaborator returns Module object properly (elaborator.py:151, 165-175)
- ✅ All type registries included in Module (constructor_types, global_types, primitive_types)
- ✅ Call sites updated correctly (module.declarations instead of unpacking)
- ✅ No tuple unpacking remains (verified via grep)
- ✅ Code follows project conventions
- ✅ All 435 tests pass (1 skipped, 2 xfailed, 1 xpassed as expected)

**Files Reviewed:**
1. `systemf/src/systemf/surface/elaborator.py` - elaborate() returns Module with all required fields
2. `systemf/src/systemf/core/module.py` - Module dataclass properly defined with all fields
3. `systemf/tests/test_surface/test_integration.py` - 12 call sites use module.declarations
4. `systemf/tests/test_string.py` - 6 call sites updated
5. `systemf/tests/test_eval/test_tool_calls.py` - call sites updated
6. `systemf/src/systemf/eval/repl.py` - uses module.constructor_types correctly
7. `systemf/demo.py` - uses module.declarations and module.constructor_types

**Findings:**
- Implementation correctly follows the design from task 50-task-design-module.md
- ElaborationError moved to core.errors to avoid circular import (good fix)
- All type registries are properly collected and returned in Module
- Call sites consistently use `module = elaborate(...)` pattern
- No regressions introduced

**Conclusion:**
Status: APPROVED - Implementation meets all acceptance criteria.

