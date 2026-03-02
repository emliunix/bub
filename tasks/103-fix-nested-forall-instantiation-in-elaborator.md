---
assignee: Implementor
expertise: ['Type Theory', 'Python']
skills: ['python-project', 'testing']
type: implement
priority: high
state: done
dependencies: []
refers: ['tasks/101-kanban-implicit-instantiation-for-system-f.md']
kanban: tasks/101-kanban-implicit-instantiation-for-system-f.md
created: 2026-03-03T00:50:46.485614
---

# Task: Fix nested forall instantiation in elaborator

## Context
<!-- Background information and relevant context -->

## Files
<!-- List of files to modify or reference -->

## Description
Make _instantiate() method recursive to handle nested ∀a.∀b.T → T[α/a][β/b]. Current implementation at lines 810-827 only handles single-level forall. This is the foundational fix that enables all other implicit instantiation features.

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-03 00:52:56] Implementation Complete

**Facts:**
Modified _instantiate() in systemf/src/systemf/surface/inference/elaborator.py to recursively handle nested foralls. Changed line 825 from returning substituted body directly to recursively calling _instantiate() on the substituted result. All 59 inference tests pass, all 18 forall/instantiate tests pass.

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-03-03 00:54:50] Architect Review - Nested Forall Instantiation Implementation

**Facts:**

**Code Review:**
- Reviewed git diff in `systemf/src/systemf/surface/inference/elaborator.py`
- Change at lines 819-826: `_instantiate()` method now recursively calls itself after substituting the outer forall variable
- Before: `return self._subst_type_var(body, var, meta)` (single-level only)
- After: `return self._instantiate(self._subst_type_var(body, var, meta))` (recursive)
- Comment updated to explain recursive handling of nested foralls

**Test Results:**
- All 59 inference tests pass (`tests/test_surface/test_inference.py`)
- All 23 pipeline tests pass (`tests/test_pipeline.py`)
- 3 polymorphism tests pass
- 1 expected failure (forward reference - marked xfail)
- Total: 82 passed, 1 xfailed

**Verification:**
- Change is minimal: 1 line modified, 1 comment updated
- Logic correctly handles nested ∀a.∀b.T → T[α/a][β/b] where α,β are fresh meta-variables
- No breaking changes to existing functionality
- Follows existing code patterns in elaborator.py

**Analysis:**

**Correctness Analysis:**
The recursive implementation is correct for handling nested polymorphism:
1. TypeForall(var, body) extracts the bound variable
2. Fresh meta-variable created for instantiation
3. Substitution applied to body
4. **Key fix**: Recursive call ensures nested TypeForall in the body is also processed

**Example:**
```
∀a.∀b. a → b → Pair a b
  → _instantiate(∀b. a → b → Pair a b)[α/a]
  → _instantiate((a → b → Pair a b)[α/a])[β/b]
  → α → β → Pair α β
```

**Edge Cases Considered:**
- Single forall: Handled correctly (recursion base case returns ty)
- Deeply nested (∀a.∀b.∀c.T): Works via repeated recursive calls
- Mixed arrows and foralls: Substitution happens before recursion, so order is correct
- No infinite recursion risk: Each recursive call peels one TypeForall layer

**Code Quality:**
- Minimal change reduces risk of introducing bugs
- Clear updated comment explains the recursive strategy
- Consistent with existing _instantiate_free_vars() pattern in same file
- Follows functional style (returns new type rather than mutating)

**Conclusion:**
Status: ok

**Review Decision: PASS**

The implementation correctly addresses the stated problem:
- ✅ Nested forall instantiation now works (Fixes TYPE_INFERENCE_BUGS.md Fix 2)
- ✅ Change is minimal and focused (1 line modified)
- ✅ No regressions introduced (82 tests pass)
- ✅ Code follows project conventions
- ✅ Logic handles edge cases correctly

**Approval Rationale:**
This is a textbook recursive fix for a structural recursion problem. The original implementation stopped after one level; the fix continues until all TypeForall layers are processed. The change is safe because:
1. It only affects polymorphic type instantiation path
2. All existing tests pass
3. The recursion is well-founded (progresses toward base case)
4. No side effects or state mutations

**Next Steps:**
Implementation approved. Task ready for closure. The fix enables subsequent work on implicit instantiation at application sites and pattern matching (work items 2-4 from design task).

---

