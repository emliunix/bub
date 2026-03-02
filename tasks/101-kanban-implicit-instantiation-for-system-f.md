---
type: 'kanban'
title: 'Implicit Instantiation for System F'
created: '2026-03-03 00:48:20.168029'
phase: 'exploration'
current: 'tasks/107-test-fixes-and-verify-all-tests-pass.md'
tasks: ['tasks/102-design-implicit-instantiation-implementation.md', 'tasks/103-fix-nested-forall-instantiation-in-elaborator.md', 'tasks/104-add-implicit-instantiation-at-application-sites.md', 'tasks/105-fix-pattern-matching-with-polymorphic-constructors.md', 'tasks/106-update-constructor-elaboration-for-polymorphic-types.md', 'tasks/107-test-fixes-and-verify-all-tests-pass.md']
---
# Kanban: Implicit Instantiation for System F

## Request
Implement implicit type instantiation in System F elaborator to fix pattern matching with polymorphic constructors. The prelude currently fails to load with error at line 103: 'expected constructor type with 1 arguments, but got ∀b._a -> Either _a b'. This is because constructors like Left : ∀a.∀b. a → Either a b aren't being properly instantiated when used in pattern matching.

## Plan Adjustment Log
<!-- Manager logs plan adjustments here -->

### [2026-03-03 01:00:00] WORKFLOW_INITIALIZED

**Details:**
- **action:** Created initial Architect design task to analyze implicit instantiation requirements
- **architect_task:** tasks/102-design-implicit-instantiation-implementation.md
- **note:** Architect analyzed elaborator, TYPE_INFERENCE_BUGS.md, and created 5 detailed work items

### [2026-03-03 01:05:00] DESIGN_REVIEW_APPROVED

**Details:**
- **design_task:** tasks/102-design-implicit-instantiation-implementation.md
- **work_items_count:** 5
- **action:** Design review approved. Created implementation tasks from work items following Core-First Dependency Order.
- **tasks_created:**
  - tasks/103-fix-nested-forall-instantiation-in-elaborator.md (high priority, no deps)
  - tasks/104-add-implicit-instantiation-at-application-sites.md (high priority, depends on #1)
  - tasks/105-fix-pattern-matching-with-polymorphic-constructors.md (critical priority, depends on #1)
  - tasks/106-update-constructor-elaboration-for-polymorphic-types.md (medium priority, depends on #1)
  - tasks/107-test-fixes-and-verify-all-tests-pass.md (high priority, depends on #1-4)
- **next_step:** Start implementation with task #1 (nested forall instantiation)

### [2026-03-03 01:15:00] IMPLEMENTATION_REVIEW_APPROVED

**Details:**
- **reviewed_task:** tasks/103-fix-nested-forall-instantiation-in-elaborator.md
- **action:** Architect reviewed and approved the implementation
- **test_results:** 82 tests passed (59 inference + 23 pipeline)
- **change_scope:** 1 line modified - recursive call in _instantiate()
- **next_step:** Proceed with task #2 (implicit instantiation at application sites)


### [2026-03-03 01:45:00] WORKFLOW_COMPLETE

**Details:**
- **status:** ALL IMPLEMENTATION TASKS COMPLETE
- **tasks_completed:**
  - ✅ tasks/103-fix-nested-forall-instantiation-in-elaborator.md (DONE)
  - ✅ tasks/104-add-implicit-instantiation-at-application-sites.md (DONE)
  - ✅ tasks/105-fix-pattern-matching-with-polymorphic-constructors.md (DONE)
  - ✅ tasks/106-update-constructor-elaboration-for-polymorphic-types.md (DONE)
  - ✅ tasks/107-test-fixes-and-verify-all-tests-pass.md (DONE)
- **test_results:**
  - 59/59 inference tests PASS
  - 23/24 pipeline tests PASS (1 expected xfail)
  - 5 previously failing tests now PASS
- **prelude_status:** Original line 103 error FIXED. Progressed from line 103 → line 77 (different issue - type scoping)
- **summary:** Implicit type instantiation successfully implemented in System F elaborator. Polymorphic constructors now work correctly in pattern matching and applications.
