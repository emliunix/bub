---
name: change-plan
description: Change plan workflow for non-trivial code changes. Create, review, and track changes before implementation.
---

# Change Plan

**Before modifying any code, create a change plan.** Applies to any non-trivial change (new feature, bug fix, refactor).

## Workflow

1. **Initialize tracking**: `todowrite` with at least:
   - One item to create the change file
   - Items to track implementation progress

2. **Create the change file**: Write to `changes/1-<change-name>.md` containing:
   - **Facts**: What exists (relevant code paths, current behavior, constraints)
   - **Design**: Exact change (new types, new functions, modified logic)
   - **Why it works**: How the design integrates with existing code
   - **Files**: Concrete list of files to change, add, or delete

3. **Get review**: Spawn a subagent to review the change plan before executing code edits

4. **Implement**: After user approval, execute the plan

## Example

```
# Step 1: Create todos
todowrite([
    {"content": "1. Create change file changes/1-add-bus-retry.md", "status": "in_progress", "priority": "high"},
    {"content": "2. Review change plan with subagent", "status": "pending", "priority": "high"},
    {"content": "3. Implement retry logic in bus client", "status": "pending", "priority": "high"},
])

# Step 2: Create change file
changes/1-add-bus-retry.md with Facts, Design, Why it works, Files
```

## Rules

- **Example filename**: `changes/1-add-literal-patterns.md`
- **Append-only**: If design evolves, create a new file (e.g., `changes/2-add-literal-patterns-v2.md`). Never modify an existing change plan.
- **Mandatory review**: Reviewer subagent checks for consistency with existing architecture, missing edge cases, and incorrect assumptions. Automatic — don't wait for user approval to run it. Implementation requires explicit user approval.
