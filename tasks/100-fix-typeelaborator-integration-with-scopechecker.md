---
assignee: Implementor
expertise: ['Type Design', 'Python', 'Integration']
skills: ['python-project']
type: implement
priority: critical
state: done
dependencies: []
refers: ['tasks/94-top-level-collection-for-mutual-recursion.md', 'tasks/79-kanban-system-f-elaborator-refactor.md']
kanban: tasks/79-kanban-system-f-elaborator-refactor.md
created: 2026-03-02T10:19:12.504146
---

# Task: Fix TypeElaborator integration with ScopeChecker

## Context
<!-- Background information and relevant context -->

## Files
<!-- List of files to modify or reference -->

## Description
Fix elaborate_declarations() in TypeElaborator to integrate with ScopeChecker. The method currently accepts SurfaceTermDeclaration with Surface AST but tries to elaborate with infer() which expects Scoped AST. Add scope checking step: convert Surface AST to Scoped AST using ScopeChecker before calling infer(). Update elaborate_declarations() to call scope_checker.check_declaration() on each SurfaceTermDeclaration body before elaboration.

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-02T19:30:00] Fix Complete

**Details:**
- **action:** Fixed TypeElaborator integration with ScopeChecker
- **state_transition:** todo → review
- **file_modified:** systemf/src/systemf/surface/inference/elaborator.py
- **problem:** Task 94's `elaborate_declarations()` tried to elaborate Surface AST directly, but TypeElaborator expects Scoped AST
- **solution:**
  1. Imported ScopeChecker and ScopeContext in elaborator.py
  2. Added scope checking step in `elaborate_declarations()` before type elaboration
  3. Pipeline now correctly converts: Surface AST → Scoped AST (via ScopeChecker) → Core AST (via TypeElaborator)
- **changes_made:**
  - Added imports: `from systemf.surface.scoped.checker import ScopeChecker` and `from systemf.surface.scoped.context import ScopeContext`
  - Modified `elaborate_declarations()` to initialize ScopeChecker
  - Added Phase 2: Scope checking - converts Surface AST to Scoped AST using `scope_checker.check_term()`
  - Updated docstring to reflect three-phase pipeline (Signature Collection → Scope Checking → Body Elaboration)
  - Pipeline flow now properly documented: Surface AST → Scoped AST → Core AST
- **integration_verification:**
  - Syntax check passed
  - ScopeChecker properly converts Surface AST to Scoped AST before type inference
  - Mutual recursion support maintained (all globals visible during scope checking)
- **notes:** Fix ensures proper separation of concerns: ScopeChecker handles name resolution, TypeElaborator handles type inference. Ready for Architect review.

### [2026-03-02 10:23:21] Integration Fix Review Complete

**Facts:**
Reviewed TypeElaborator integration with ScopeChecker in systemf/src/systemf/surface/inference/elaborator.py. Fix successfully resolves the critical bug from task 94: elaborate_declarations() now properly integrates ScopeChecker to convert Surface AST -> Scoped AST before type inference. Verified three-phase pipeline: Signature Collection -> Scope Checking -> Body Elaboration. All 54 scope tests and 32 elaborator tests pass, confirming no breaking changes. Manual test confirms Surface AST -> Scoped AST -> Core AST pipeline works correctly. Implementation approved.

**Analysis:**
-

**Conclusion:**
Status: ok

---

