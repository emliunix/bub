# 2026-02-28 - Workflow Skill: Design Review Pattern

## Summary
Added **Design Review** phase to the workflow skill to validate design work items before implementation begins. This addresses the issue where large implementation tasks weren't being properly validated at the design stage.

## Problem
Previously, when Architect created a design with work items, there was no review phase to validate:
- Whether work items followed correct patterns (Design-First vs direct implementation)
- Whether complex work items were appropriately decomposed
- Whether dependencies followed Core-First principle
- Whether pattern selection matched complexity

This led to large, unmanageable implementation tasks being created without validation.

## Solution

### 1. New Pattern: Design Review

**Location:** `patterns.md`

Added new pattern between **Design-First** and **Implementation-With-Review**:

```
Design task (state: review - design complete)
    ↓
Architect runs design_review_mode() algorithm:
  - validate_work_items_against_patterns()
  - check_complexity_decomposition()
  - verify_core_first_ordering()
    ↓
IF approved → State: done → Manager creates implementation tasks
IF escalated → State: escalated → Architect redesigns
```

### 2. Architect Algorithm: design_review_mode()

**Location:** `role-architect.md`

New mode for validating design work items:

```python
def design_review_mode(task_file):
    """Review design work items against workflow patterns."""
    # Step 1: Load context
    context = load_design_review_context(task_file)
    
    # Step 2: Validate against patterns
    pattern_issues = validate_work_items_against_patterns(...)
    
    # Step 3: Check complexity decomposition
    complexity_issues = check_complexity_decomposition(...)
    
    # Step 4: Verify Core-First dependencies
    dependency_issues = verify_core_first_ordering(...)
    
    # Step 5: Make decision
    decision, reasoning = make_design_review_decision(all_issues)
    
    # State transitions:
    # approved -> done (ready for implementation)
    # escalate -> escalated (needs redesign)
```

**Validation checks:**
- Pattern selection appropriateness
- Work item decomposition (large items flagged)
- Core-First dependency ordering
- No circular dependencies

### 3. Manager Algorithm Updates

**Location:** `role-manager.md`

Updated `reconcile_tasks()` to:
1. Detect design tasks with work items (type: design)
2. Route to design review (state: review) instead of marking done
3. Handle design review completion:
   - approved (state: done) → create implementation tasks
   - escalated → create redesign task

New event types added:
- `design_ready_for_review` - Design task complete, needs review
- `design_review_approved` - Review passed, creating implementation tasks
- `design_review_escalated` - Review found issues, redesign required

### 4. State Transitions

**Architect now controls state transitions via `new_state` parameter:**

| Mode | Completion State | Meaning |
|------|------------------|---------|
| Design | `review` | Ready for design review |
| Design Review (approved) | `done` | Approved, ready for implementation |
| Design Review (escalated) | `escalated` | Needs redesign |
| Review (approved) | `done` | Implementation approved |
| Review (escalated) | `escalated` | Needs fixes |

**Universal constraint maintained:** `todo → review → done` (no direct `todo → done`)

### 5. Pattern Documentation

**Location:** `patterns.md`, `SKILL.md`

- Updated Pattern Selection Decision Tree
- Added Design Review to Quick Reference
- Updated Pattern Selection Guide (algorithm-based selection)
- Updated Pattern Constraints (follow algorithm, not manual checks)
- Updated Pattern Composition diagram

## Files Changed

| File | Changes |
|------|---------|
| `patterns.md` | +100 lines - Added Design Review pattern, updated selection guide |
| `role-architect.md` | +250 lines - Added design_review_mode(), state transitions, constraints |
| `role-manager.md` | +60 lines - Updated reconcile_tasks() for design review routing, new event types |
| `SKILL.md` | +10 lines - Updated pattern reference, added Design Review to table |

## Validation

### Syntax & Style: ✓
- All code blocks balanced (verified with script)
- Heading levels consistent
- Function definitions follow docstring convention
- State transition comments follow pattern

### State Flow: ✓
```
Design Mode → state: review (ready for design review)
Design Review → state: done (approved) OR state: escalated (redesign)
Implementation → state: review (ready for review)
Review → state: done (approved) OR state: escalated (fixes)
```

### Pattern Conformance: ✓
- Single-file continuity maintained (same task file for design + review)
- Universal review constraint enforced (ALL work reviewed)
- Core-First principle encoded in validation algorithm
- One work item at a time principle preserved

## Impact

### Before
```
Design-First → Implementation-With-Review
```
Design work items created implementation tasks without validation.

### After
```
Design-First → Design Review → Implementation-With-Review
```
Design work items validated before implementation tasks created.

## Status
- ✅ Design Review pattern documented
- ✅ Architect algorithm implemented
- ✅ Manager routing updated
- ✅ State transitions defined
- ✅ All files syntax validated
- ✅ Pattern consistency verified

## Future Work

Potential enhancements:
- Add complexity heuristics to automatically flag large work items
- Add pattern selection guidance based on file count/scope
- Consider adding integration pattern validation for multi-component features

## Commits

TBD - Workflow skill: Add Design Review pattern for design validation before implementation
