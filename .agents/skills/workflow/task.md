# Task File Specification

This document defines the complete structure and format of task files in the workflow system.

## Overview

Task files are the primary unit of work in the workflow system. They contain:
- **Metadata** (YAML frontmatter): Role, type, priority, state, dependencies
- **Context**: Background information and requirements
- **Work Log**: Record of work performed with Facts/Analysis/Conclusion structure

## File Structure

```yaml
---
role: Architect                    # Agent role (Architect, Implementor, Manager)
skills: [code-reading]             # Skills to load (auto-loaded by agent tool)
expertise: ["System Design"]       # Required expertise domains
dependencies: []                   # Prerequisite task file paths
refers: []                         # Related task file paths for reference
type: design                       # Task type (see Type field below)
priority: high                     # critical | high | medium | low
state: todo                        # todo | done | escalated | cancelled
kanban: tasks/0-kanban.md          # Associated kanban file
created: 2026-02-25T11:38:30      # ISO timestamp
---

# Task: <Descriptive Title>

## Context
Background information, requirements, and relevant context for the task.

## Files
- src/example.py                   # Files to modify or reference
- tests/test_example.py

## Description
Detailed description of what needs to be done.

## Work Log

### [2026-02-25 14:30:00] Work Session Title | status

**F:** Facts - What was actually done
- Files modified: [list]
- Code written: [summary]
- Tests run: [results]

**A:** Analysis - Problems and decisions
- Issues encountered: [description]
- Approaches tried: [what worked/didn't]
- Decisions made: [with rationale]

**C:** Conclusion - Status and next steps
- Status: ok | blocked | escalate
- Outcome: [summary]
- Next steps: [if any]
```

## Metadata Fields

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `role` | string | Agent role: `Architect`, `Implementor`, or `Manager` |
| `type` | string | Task type (see Type field below) |
| `priority` | string | `critical`, `high`, `medium`, or `low` |
| `state` | string | `todo`, `done`, `escalated`, or `cancelled` |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `skills` | list | Skills to load (auto-loaded by agent tool) |
| `expertise` | list | Required expertise domains |
| `dependencies` | list | Prerequisite task file paths |
| `refers` | list | Related tasks for reference |
| `kanban` | string | Associated kanban file path |
| `created` | string | ISO timestamp of creation |

### Type Field

The `type` field determines task behavior and routing:

| Type | Role | Description |
|------|------|-------------|
| `exploration` | Architect | Explore codebase or problem space |
| `design` | Architect | Design core types and interfaces |
| `review` | Architect | Review implementation against spec |
| `implement` | Implementor | Implement features or fixes |
| `redesign` | Architect | Redesign after escalation |

### State Field

The `state` field tracks task lifecycle:

| State | Description |
|-------|-------------|
| `todo` | Ready to be worked on (default when created) |
| `done` | Completed successfully |
| `escalated` | Escalated for review or blocked |
| `cancelled` | Cancelled (no longer needed) |

**State Transitions:**
- `todo` → `done`: Task completed with work items
- `todo` → `escalated`: Task escalated for review
- `escalated` → `done`: Escalation resolved, task completed
- Any → `cancelled`: Task cancelled by Manager

## Work Log Specification

Work logs are the primary communication mechanism between agents.

### Required Structure

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

### Optional Sections

Add these when relevant:

#### Suggested Work Items (Architect only)

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

#### Blockers (if status = blocked)

```markdown
## Blockers

- **Issue**: Description
  - Impact: What's blocked
  - Solutions: Ideas for resolution
```

#### References

```markdown
## References

- Design doc: docs/arch.md
- Related: tasks/0-design.md
```

### Per-Role Examples

#### Architect - Design Task

```markdown
### [14:30] API Design | ok

**F:** Defined User/Role/Permission types in types.py. Created test contracts.

**A:** Chose RBAC over ABAC (simpler). Existing User class needs deprecation path.

**C:** Design complete. 2 work items ready for Manager.

## Suggested Work Items

```yaml
work_items:
  - description: Implement User model
    files: [src/models/user.py]
    expertise_required: ["Python", "SQLAlchemy"]
    priority: high
```
```

#### Implementor - Implementation Task

```markdown
### [16:45] Auth Implementation | ok

**F:** Implemented UserSchema, updated login endpoint. Tests 12/12 pass.

**A:** Added email regex validation (not in original spec) to minimize deps.

**C:** Complete. Email regex may need RFC 5322 refinement later.
```

#### Architect - Review Task (Escalation)

```markdown
### [15:20] Implementation Review | escalate

**F:** Reviewed implementation in src/auth.py. Found 3 critical issues.
- Issue 1: Password hashing doesn't use salt
- Issue 2: Session tokens not invalidated on logout
- Issue 3: Rate limiting missing on login endpoint

**A:** Security vulnerabilities detected. Implementation doesn't meet security requirements.
All issues are blockers for production deployment.

**C:** **ESCALATE** - Implementation requires security fixes before approval.

## Additional Work Items

```yaml
additional_work_items:
  - description: Fix password hashing to use salt
    files: [src/auth/password.py]
    expertise_required: ["Security", "Cryptography"]
    priority: critical
    notes: Use bcrypt or Argon2
```
```

## Creating Task Files

**Manager MUST use the create-task.py script** to create task files:

```bash
.agents/skills/workflow/scripts/create-task.py \
    --role Architect \
    --expertise "System Design,Python" \
    --skills "code-reading" \
    --title "Design API Layer" \
    --type design \
    --priority high \
    --kanban tasks/0-kanban.md \
    --creator-role manager
```

The script automatically:
1. Validates required fields
2. Generates next sequential ID
3. Sets `state: todo`
4. Creates file with proper YAML header

## Logging Work

**You MUST use log-task.py to write work logs.** No manual editing.

```bash
# Generate temp file for writing
TEMP=$(.agents/skills/workflow/scripts/log-task.py generate tasks/0-task.md "Analysis")

# Edit temp file, then commit
.agents/skills/workflow/scripts/log-task.py commit tasks/0-task.md "Analysis" "$TEMP"

# Or quick log for simple updates
.agents/skills/workflow/scripts/log-task.py quick tasks/0-task.md "Update" "Fixed bug"
```

## Constraint

**You MUST write a work log before completing.** No exceptions. Even failures must be documented.
