---
assignee: Implementor
expertise: ['Type Theory', 'Python']
skills: ['python-project', 'testing']
type: implement
priority: high
state: done
dependencies: [tasks/103-fix-nested-forall-instantiation-in-elaborator.md]
refers: ['tasks/101-kanban-implicit-instantiation-for-system-f.md']
kanban: tasks/101-kanban-implicit-instantiation-for-system-f.md
created: 2026-03-03T00:50:52.394160
---

# Task: Add implicit instantiation at application sites

## Context
<!-- Background information and relevant context -->

## Files
<!-- List of files to modify or reference -->

## Description
In SurfaceApp case (lines 269-304), when func has TypeForall type, instantiate before application. When elaborating f arg where f has polymorphic type (e.g., id : ∀a. a → a), detect TypeForall and instantiate to match argument type using unification.

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-03 00:58:08] Implementation Complete

**Facts:**
Added implicit instantiation at application sites in systemf/src/systemf/surface/inference/elaborator.py SurfaceApp case (lines 275-279). When elaborating function application f arg, if f has TypeForall type, it's now automatically instantiated with fresh meta-variables before continuing. All 59 inference tests pass, 600 total tests pass.

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-03-03 00:59:15] Architect Review - Implicit Instantiation at Application Sites

**Facts:**
<!-- What was actually done (files modified, code written, tests run, etc.) -->

**Code Review:**
- Reviewed changes in `systemf/src/systemf/surface/inference/elaborator.py` at lines 276-281 (SurfaceApp case)
- Added implicit instantiation logic after function type inference and substitution
- Implementation:
  ```python
  # Handle implicit instantiation for polymorphic functions
  # If func has type ∀a. ..., instantiate it with fresh meta-variables
  match func_type:
      case TypeForall(_, _):
          func_type = self._instantiate(func_type)
          func_type = self._apply_subst(func_type)
  ```
- Change is positioned correctly between `_apply_subst(func_type)` and the subsequent pattern match on func_type

**Test Results:**
- All 59 inference tests pass
- All 23 pipeline tests pass (1 xfailed - expected)
- All 7 application-related tests pass:
  - test_simple_application
  - test_application_with_inference
  - test_curried_application
  - test_application_type_mismatch
  - test_type_application (polymorphism)
  - test_deeply_nested_application
  - test_self_application_fails

**Verification:**
- Change is minimal: 7 lines added (3 lines of code + 4 lines of comments/blank)
- No changes to existing logic - pure addition
- Follows existing code patterns (pattern matching, substitution application)
- Properly integrated with recursive _instantiate() from previous fix

**Analysis:**
<!-- What problems were encountered, what approaches were tried, key decisions made -->

**Correctness Analysis:**
The implementation correctly handles implicit instantiation at application sites:
1. Function type is inferred from `self.infer(func, ctx)`
2. Substitution is applied to resolve any existing meta-variables
3. **New**: If the function type is `TypeForall`, it's instantiated with fresh meta-variables
4. Substitution is reapplied to resolve any new meta-variables from instantiation
5. Normal application logic continues with the instantiated (now arrow) type

**Example Workflow:**
```
Surface:   id 42
           ↓ infer(id) returns TypeForall("a", a → a)
           ↓ _apply_subst (no change)
           ↓ detect TypeForall → _instantiate()
           ↓ returns TypeArrow(TMeta(α), TMeta(α))
           ↓ _apply_subst (no change yet)
           ↓ match TypeArrow → proceed with application
           ↓ check(42, TMeta(α)) → unifies α ~ Int
           ↓ return type: Int
```

**Edge Cases Considered:**
1. **Nested foralls**: Handled by recursive _instantiate() (depends on previous fix)
2. **Chained applications**: Each application site independently instantiates
3. **Already arrow types**: No change - passes through unchanged
4. **Meta-variables**: Substitution applied before and after instantiation ensures consistency

**Code Quality:**
- Clear comment explains the purpose
- Uses existing _instantiate() method (DRY principle)
- Consistent with codebase pattern matching style
- Minimal invasive change - doesn't modify existing branches

**Potential Considerations:**
- The implementation instantiates ALL TypeForall types at application sites, which is correct for rank-1 polymorphism
- This could be refined in future to support higher-rank polymorphism with bidirectional checking
- Current approach is HM-style (Hindley-Milner) which is appropriate for System F surface language

**Conclusion:**
<!-- Pass/fail/escalate status and why, next steps, blockers if any -->
Status: ok

**Review Decision: PASS**

The implementation correctly addresses the stated problem:
- ✅ Implicit instantiation works at application sites
- ✅ Change is minimal and focused (7 lines added)
- ✅ No regressions introduced (82 tests pass)
- ✅ Code follows project conventions (pattern matching, substitution)
- ✅ Logic handles edge cases correctly (nested foralls, chained apps)

**Approval Rationale:**
This is a clean, minimal implementation that enables implicit instantiation - the key feature that distinguishes surface System F from core System F. The change is safe because:
1. It's additive - doesn't modify existing code paths
2. It depends on the previously reviewed _instantiate() fix
3. All tests pass including polymorphic application tests
4. Follows established patterns in the elaborator

**Note on Completeness:**
While this enables implicit instantiation at application sites, the full feature (e.g., using polymorphic constructors as values without explicit type application) may require additional work in other code paths. However, this implementation correctly addresses the specified scope for SurfaceApp.

**Next Steps:**
Implementation approved. The fix enables polymorphic functions like `id 42` to work without explicit type application. Combined with the nested forall fix, this forms the foundation for the remaining work items (pattern matching with polymorphic constructors).

<!-- Additional notes -->

---

