# Work Log Specification

Work logs are the primary communication mechanism between agents. This document specifies the format and requirements.

**⚠️ IMPORTANT**: You MUST read this document before writing any work log.

## Required Structure

Every work log entry MUST include three core sections:

```markdown
### [timestamp] Title | status

**F:** Facts - What was actually done (files modified, code written, tests run)

**A:** Analysis - Problems encountered, approaches tried, decisions made

**C:** Conclusion - Status (ok/blocked/escalate), outcome summary, next steps
```

### Sections (Required)

| Section | Key | Description |
|---------|-----|-------------|
| Facts | **F:** | Concrete actions: files changed, code written, tests executed |
| Analysis | **A:** | Problems, alternatives considered, rationale for decisions |
| Conclusion | **C:** | Final status and what happens next |

### Status Values

- `ok` - Task completed successfully
- `blocked` - Cannot proceed, needs help
- `escalate` - Needs different expertise, Manager should replan

## Optional Sections

Add these when relevant:

### Suggested Work Items (Architect only)

```markdown
## Suggested Work Items

```yaml
work_items:
  - description: What needs to be done
    files: [src/file.py]
    expertise_required: ["Skill1"]
    priority: high
```
```

### Blockers (if status = blocked)

```markdown
## Blockers

- **Issue**: Description
  - Impact: What's blocked
  - Solutions: Ideas for resolution
```

### References

```markdown
## References

- Design doc: docs/arch.md
- Related: tasks/0-design.md
```

## Per-Role Requirements

### Architect

Writes to task files. Often includes Suggested Work Items for Manager.

```markdown
### [14:30] API Design | ok

**F:** Defined User/Role/Permission types in types.py. Created test contracts.

**A:** Chose RBAC over ABAC (simpler). Existing User class needs deprecation path.

**C:** Design complete. 2 work items ready for Manager.
```

### Implementor

Writes to task files. Focus on implementation details and deviations from spec.

```markdown
### [16:45] Auth Implementation | ok

**F:** Implemented UserSchema, updated login endpoint. Tests 12/12 pass.

**A:** Added email regex validation (not in original spec) to minimize deps.

**C:** Complete. Email regex may need RFC 5322 refinement later.
```

### Manager

Writes to kanban.md. Maintains both Work Log and Plan Adjustment Log.

**Work Log:**
```markdown
### [10:00] Planning Session | ok

**F:** Read work items from tasks/0-design.md. Created tasks/1-impl.md.

**A:** Dependency chain detected between auth tasks.

**C:** Next: tasks/1-impl.md. Will create review task after completion.
```

**Plan Adjustment Log** (for significant decisions):
```markdown
### [11:30] BLOCKER_DETECTED

- blocked_task: tasks/3-impl.md
- blocker: Missing User model types
- action: Created exploration task
```

## Escalation Work Logs

When escalating, be extra thorough:

```markdown
### [15:20] Implementation Blocked | escalate

**F:** Attempted per spec. Blocked at line 45: UserSchema missing email field.

**A:** Root cause: types.py incomplete. Workaround rejected (violates architecture).

**C:** **ESCALATE** to Architect. Need UserSchema update. Impact: all auth work.

## Suggested Work Items

```yaml
work_items:
  - description: Add email field to UserSchema
    files: [src/types.py]
    expertise_required: ["Type Design"]
    priority: critical
```
```

## Constraint

**You MUST write a work log before completing.** No exceptions. Even failures must be documented.

## Helper Scripts

Use the logging scripts:

```bash
# Generate temp file for writing
TEMP=$(.agents/skills/workflow/scripts/log-task.py generate tasks/0-task.md "Analysis")

# Edit temp file, then commit
.agents/skills/workflow/scripts/log-task.py commit tasks/0-task.md "Analysis" "$TEMP"

# Or quick log
.agents/skills/workflow/scripts/log-task.py quick tasks/0-task.md "Update" "Fixed bug in parser"
```
