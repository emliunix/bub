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
type: design  # Determines Architect enters DESIGN mode
title: "<Component> Design"
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

## Pattern: Design-With-Review

**Use when:** Creating complex designs that need validation before implementation begins.

**Characteristics:**
- Initial design by Architect
- Peer review (or self-review) of design before implementation
- Catches design flaws early, prevents implementation rework
- Design review validates types, contracts, and test coverage

**Task Structure:**
```yaml
# Task 1: Initial Design
role: Architect
type: design  # Architect enters DESIGN mode
title: "<Component> Design"
dependencies: []
skills: [code-reading, domain-specific]

# Task 2: Design Review (gate before implementation)
role: Architect
type: review  # Architect enters REVIEW mode
title: "<Component> Design Review"
dependencies: [design_task]
skills: [code-reading]
expertise: ["Design Review", "Architecture Validation"]

# Task 3: Implementation (only after design review passes)
role: Implementor
type: implement
dependencies: [design_review_task]
skills: [from work item]
```

**When to use this pattern:**
- Design affects multiple components
- Design introduces new architectural patterns
- High cost of design errors (hard to change later)
- Team wants design consensus before implementation
- Core types design for foundational systems

**Manager Actions:**
1. Create initial design task
2. After design completes, create design review task
3. Only after review passes (work log shows "PASS"), create implementation task
4. If review escalates:
   - Assign SAME task file to Architect for review (no new task file created)
   - Architect appends work log with `additional_work_items` to same file
   - Manager creates prerequisite tasks from work items
   - Update original task dependencies to include new prerequisite tasks
   - Original task will be retried after prerequisites complete

---

## Pattern: Implementation-With-Quality-Gates

**Use when:** Implementation touches core types, public APIs, or critical system components. Ensures type safety and conformance testing.

**Characteristics:**
- Pre-implementation: Core types reviewed and conformance tests defined
- Implementation follows established contracts
- Post-implementation: Review validates against original design
- Prevents type drift and integration issues

**Task Structure:**
```yaml
# Task 1: Core Types Review (Architect validates types)
role: Architect
type: review
title: "Review - Core Types for <Component>"
dependencies: [design_task]
skills: [code-reading]
expertise: ["Type System Design", "API Contract Review"]

# Task 2: Conformance Tests (Define test contracts)
role: Implementor
type: implement
title: "Tests - Conformance for <Component>"
dependencies: [core_types_review_task]
skills: [testing]
expertise: ["Test-Driven Development", "Contract Testing"]

# Task 3: Implementation (Build to spec)
role: Implementor
type: implement
title: "Implement - <Component>"
dependencies: [conformance_tests_task]
skills: [from work item]
expertise: [from work item]

# Task 4: Post-Implementation Review (Validate against design)
role: Architect
type: review
title: "Review - <Component> Implementation"
dependencies: [implementation_task]
skills: [code-reading]
expertise: ["Code Review", "Architecture Validation"]
```

**Apply this pattern when:**
- Work item mentions "core types", "public API", or "protocol"
- Changes affect multiple components or external interfaces
- High risk of type mismatches or API drift
- Need to ensure tests validate contracts, not just behavior

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

**Use when:** Any task escalates (Implementor blocked, design issues, implementation doesn't meet spec, etc.).

**Trigger:** Work log contains `ESCALATE` or `BLOCKED` status

**Characteristics:**
- Task escalates for review by Architect
- SAME task file continues (no new task created)
- Architect reviews and adds `additional_work_items` to same file
- Manager creates prerequisite tasks and updates dependencies
- May iterate multiple times

**Flow:**
```
Task (e.g., implementation) → ESCALATE → Architect reviews SAME file → 
Adds work items → Manager creates prerequisites → Task retries after prereqs
```

**Manager Actions:**
1. Detect escalation from work log status (`| escalate` or `| blocked`)
2. Assign SAME task file to Architect for review
3. Wait for Architect to append review with `additional_work_items`
4. Create prerequisite tasks from work items
5. Update original task dependencies to include new prerequisite tasks
6. Put original task back in queue (retries after prerequisites complete)
7. Log plan adjustment: `escalation_for_review` or `escalation_prerequisites_created`

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

**Step 2: Evaluate complexity and risk**
- Small, isolated? → **Simple**
- Core types/architecture involved? → **Design-First**
- Complex design needing peer review? → **Design-With-Review**
- Core types + needs conformance testing? → **Implementation-With-Quality-Gates**
- Must validate before continuing? → **Validate-Before-Continue**

**Step 3: Consider sequence**
- Can tasks run in parallel? → **Integration** pattern for coordination
- Must validate quality? → Insert **Validate-Before-Continue** gate
- High-risk implementation? → Use **Implementation-With-Quality-Gates**
- Previous attempt failed? → **Escalation Recovery** loop

## Pattern Constraints

**Manager MUST:**
- Read this file before creating tasks
- Select pattern based on work item characteristics and context
- Set correct `type`, `role`, and `dependencies`
- Use `type` field to route Architect tasks: `design` or `review`
- Set `state: todo` when creating tasks
- Log pattern choice in kanban plan adjustment log

**Anti-Patterns:**
- Creating Implementor task before Design for core changes → Use **Design-First**
- Complex design without peer review → Use **Design-With-Review**
- Skipping Review for architecture-critical work → Add **Validate-Before-Continue**
- Skipping type review and conformance tests for core types → Use **Implementation-With-Quality-Gates**
- Creating all tasks upfront → Use **Discovery** to inform planning
- Ignoring escalation status → Trigger **Escalation Recovery**

## Pattern Composition

Patterns can be composed:

```
Discovery → Design-First → Implementation-With-Quality-Gates
    ↓
Escalation Recovery (if validation fails)
    ↓
Validate-Before-Continue (retry)
    ↓
Integration (merge with other work)
```

Common compositions:
- **New feature with core types**: Discovery → Design-First → Implementation-With-Quality-Gates
- **API changes**: Implementation-With-Quality-Gates (types → tests → impl → review)
- **Bug fix in core**: Escalation Recovery → Implementation-With-Quality-Gates

Manager handles composition by treating pattern output as input to next pattern selection.
