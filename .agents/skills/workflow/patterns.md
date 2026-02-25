# Workflow Patterns

Task orchestration patterns for Manager. These patterns define how to decompose work into tasks and reconcile based on task outcomes using skill constructs.

**Manager MUST consult this document when creating tasks** to ensure correct workflow sequencing.

---

## Pattern: Simple

**Use when:** Small, isolated changes with no core type impact.

**Characteristics:**
- Single Implementor task
- No Architect involvement
- No dependencies on design tasks

**Task Structure:**
```yaml
role: Implementor
type: implement
dependencies: []
skills: [from work item]
expertise: [from work item]
```

**Use cases:** Bug fixes, documentation updates, config changes, simple refactoring

---

## Pattern: Design-First

**Use when:** Building new features, modifying core types, or architectural changes.

**Characteristics:**
- Architect creates specification first
- Implementor executes against spec
- May include review gate

**Task Structure:**
```yaml
# Task 1: Design
role: Architect
type: design
title: "Design - <Component>"
dependencies: []
skills: [code-reading, domain-specific]

# Task 2: Implementation (depends on design)
role: Implementor
type: implement
dependencies: [design_task]
skills: [from work item]
```

**When to add Review task:**
- Work item contains "core types" or "architecture"
- Complexity is high
- Risk of deviation from spec is significant

---

## Pattern: Validate-Before-Continue

**Use when:** Implementation must be validated before downstream work proceeds.

**Characteristics:**
- Review task acts as gate
- Downstream tasks depend on Review, not directly on Implementation
- Can be inserted between any two phases

**Task Structure:**
```yaml
# Task N: Implementation
role: Implementor
type: implement
dependencies: [previous_task]

# Task N+1: Review (the gate)
role: Architect
type: review
title: "Review - <Component>"
dependencies: [implementation_task]
skills: [code-reading]

# Task N+2: Downstream work
role: [Architect|Implementor]
type: [design|implement]
dependencies: [review_task]  # Depends on review, not implementation
```

**Use cases:** Core system validation, API contract verification, security review

---

## Pattern: Escalation Recovery

**Use when:** Implementation failed review or Implementor escalated.

**Trigger:** Work log contains `ESCALATE` or `BLOCKED` status

**Characteristics:**
- Root cause analysis by Architect
- Redesign task references failed task in `refers`
- May iterate multiple times

**Task Structure:**
```yaml
# Redesign task
role: Architect
type: redesign
title: "Redesign - <Component>"
dependencies: []
refers: [failed_implementation_task]  # Links to failed work
priority: critical
skills: [code-reading]

# New implementation task (after redesign completes)
role: Implementor
type: implement
dependencies: [redesign_task]
```

**Manager Actions:**
1. Read work log, extract escalation issues
2. Create redesign task with `refers` to failed task
3. Log plan adjustment: `escalation_received`
4. Set priority to `critical`

---

## Pattern: Discovery

**Use when:** Information inadequate for planning.

**Trigger:** `has_adequate_information()` returns false for work item

**Characteristics:**
- Architect explores and reports findings
- Manager waits before creating implementation tasks
- Findings logged as suggested work items

**Task Structure:**
```yaml
# Exploration task
role: Architect
type: exploration
dependencies: []
skills: [code-reading]
expertise: ["Problem Analysis", "Code Exploration"]
```

**Manager Actions:**
1. Create exploration task
2. Log plan adjustment: `inadequate_information`
3. Wait for Architect's suggested work items
4. After completion, select appropriate pattern based on findings

---

## Pattern: Integration

**Use when:** Multiple work streams converge into single deliverable.

**Characteristics:**
- Parallel implementation tasks
- Integration task depends on all parallel tasks
- Final validation step

**Task Structure:**
```yaml
# Parallel tasks (no dependencies between them)
role: Implementor
type: implement
dependencies: [shared_parent_task]
# ... multiple parallel tasks

# Integration task (convergence point)
role: Implementor
type: implement
dependencies: [parallel_task_1, parallel_task_2, ...]
expertise: ["System Integration", "Testing"]
```

**Use cases:** Multi-component features, modular system assembly, cross-module changes

---

## Pattern Selection Guide

**Step 1: Check for triggers**
- Work log has `ESCALATE`/`BLOCKED`? → **Escalation Recovery**
- Missing information? → **Discovery**
- Multiple parallel streams converging? → **Integration**

**Step 2: Evaluate complexity**
- Small, isolated? → **Simple**
- Core types/architecture involved? → **Design-First**
- Must validate before continuing? → **Validate-Before-Continue**

**Step 3: Consider sequence**
- Can tasks run in parallel? → **Integration** pattern for coordination
- Must validate quality? → Insert **Validate-Before-Continue** gate
- Previous attempt failed? → **Escalation Recovery** loop

## Pattern Constraints

**Manager MUST:**
- Read this file before creating tasks
- Select pattern based on work item characteristics and context
- Set correct `type`, `role`, and `dependencies`
- Use title conventions (`Design - `, `Review - `) for Architect tasks
- Log pattern choice in kanban plan adjustment log

**Anti-Patterns:**
- Creating Implementor task before Design for core changes → Use **Design-First**
- Skipping Review for architecture-critical work → Add **Validate-Before-Continue**
- Creating all tasks upfront → Use **Discovery** to inform planning
- Ignoring escalation status → Trigger **Escalation Recovery**

## Pattern Composition

Patterns can be composed:

```
Discovery → Design-First → Validate-Before-Continue
    ↓
Escalation Recovery (if validation fails)
    ↓
Validate-Before-Continue (retry)
    ↓
Integration (merge with other work)
```

Manager handles composition by treating pattern output as input to next pattern selection.
