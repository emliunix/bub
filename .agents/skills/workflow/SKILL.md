---
name: workflow
description: Multi-agent workflow system for complex software engineering tasks requiring design, planning, implementation, and review phases. Orchestrates Supervisor, Manager, Architect, and Implementor roles.
---

# Multi-Agent Workflow System

This skill defines a hierarchical multi-agent workflow for complex software engineering tasks that require separation of design from implementation.

## When to Use

Use this workflow when:
- Tasks are too large or complex for a single agent
- Architectural decisions need to be validated before implementation
- Multiple implementation passes with review cycles are needed
- Clear separation of concerns between design and implementation is required

## Workflow Architecture

The workflow consists of four specialized roles working in sequence:

```mermaid
flowchart TD
    S[Supervisor<br/>Orchestrator] --> M[Manager<br/>Planner]
    M --> A[Architect<br/>Designer/Reviewer]
    M --> I[Implementor<br/>Executor]
    A -. Work Items .-> M
    I -. Escalation .-> M
```

### Execution Model

**Sequential by Design**: The Supervisor ensures agents execute one at a time in a defined order. This prevents race conditions and ensures each agent works with consistent state.

## Roles

### Supervisor

**Purpose**: Dumb orchestrator that manages agent execution lifecycle.

**Key Constraints**:
- Only spawns agents based on kanban state
- Never makes decisions or interprets results
- Validates output format, not content
- Retries up to 3 times on format failures
- Fails workflow if retries exhausted

**Algorithm**: See `role-supervisor.md`

### Manager

**Purpose**: Orchestrate workflow phases and task sequencing. **Manager is the ONLY role that updates kanban state.** Manager does NOT perform real work - only creates tasks and manages kanban.md.

**Key Design Decisions**:

1. **Manager Never Does Real Work**: Manager MUST NOT explore, edit files, execute shell commands, or make design decisions. Manager ONLY creates task files and updates kanban.md.

2. **One Work Item at a Time**: When replanning, Manager returns only the immediate next work item rather than all future work. This allows the workflow to adapt based on implementation results before committing to downstream tasks.

3. **Exploration Tasks for Missing Info**: If information is inadequate for planning, Manager creates exploration tasks delegated to other agents (typically Architect).

4. **Plan Adjustment Logging**: All plan changes are logged to kanban.md with timestamps and reasoning.

**Algorithm**: See `role-manager.md`

### Architect

**Purpose**: Design core systems and validate implementations.

**Task Title Convention**: Tasks for Architect must have titles starting with:
- `Design - ` for design phase tasks
- `Review - ` for review phase tasks

This allows Architect to determine mode without explicit mode field.

**Modes**:
- **DESIGN**: Create types.py and define test contracts
- **REVIEW**: Validate implementation quality

**Algorithm**: See `role-architect.md`

### Implementor

**Purpose**: Execute implementation tasks according to specification.

**Escalation Strategy**: When complexity exceeds capacity, Implementor escalates rather than attempting work beyond expertise. This maintains quality and allows Manager to replan with appropriate resources.

**Algorithm**: See `role-implementor.md`

## Skills Registry

| Skill | Location | Used By | Description |
|-------|----------|---------|-------------|
| `docs` | `.agents/skills/docs/SKILL.md` | All | Documentation conventions, mermaid validation |
| `testing` | `.agents/skills/testing/SKILL.md` | Implementor | Test running and debugging |
| `deployment` | `.agents/skills/deployment/SKILL.md` | Manager | Production deployment |
| `python-project` | `/home/liu/.claude/skills/python-project/SKILL.md` | Implementor | Python project management with uv |
| `code-reading` | `.agents/skills/code-reading-assistant/SKILL.md` | All | Codebase exploration and Q&A |
| `skill-management` | `.agents/skills/skill-management/SKILL.md` | All | Skill catalog and navigation |

## Skill Loading Rules

- **Manager**: Must load `skill-management` first to discover other skills
- **Architect**: Must load `code-reading` and domain-specific skills
- **Implementor**: Must load skills specified in task file meta

In task files:
```yaml
skills: [python-project, testing]
```

## Work Logging Requirement

All agents **must** write a work log before completing their task, regardless of success or failure.

### Purpose

Work logs provide:
- **Traceability**: What was actually done vs what was planned
- **Accountability**: Clear record of decisions and actions
- **Handoff context**: Essential information for the next agent in the chain
- **Learning**: Pattern recognition across similar tasks

### Content Requirements

Every work log must include:

1. **Facts**: What was actually done (files modified, code written, tests run)
2. **Analysis**: What problems were encountered, what approaches were tried
3. **Conclusion**: Pass/fail/escalate status and why

### Work Log Format by Role

#### Architect (writes to task.md)

```markdown
## Work Log

### [timestamp] Design Session

**Facts:**
- Analyzed requirements from user request
- Defined 3 new types in types.py: User, Role, Permission
- Created test cases in tests/test_auth.py

**Analysis:**
- Identified ambiguity in permission inheritance
- Considered RBAC vs ABAC models, chose RBAC for simplicity
- Noticed existing User class in models.py needs deprecation

**Conclusion:**
- Design complete, 2 work items logged for Manager
- Potential future issue: Need migration path for existing User class
```

#### Implementor (writes to task.md)

```markdown
## Work Log

### [timestamp] Implementation

**Facts:**
- Modified src/auth/models.py: added UserSchema class
- Modified src/auth/routes.py: updated login endpoint
- Tests pass: 12/12

**Analysis:**
- Had to deviate from spec: email validation requires regex not in types.py
- Alternative considered: use external library, decided against to minimize deps

**Conclusion:**
- Implementation complete, ready for review
- Note: Email validation regex may need refinement per RFC 5322
```

#### Manager (writes to kanban.md)

Manager maintains TWO logs in kanban.md:

**Work Log** (per session):
```markdown
## Work Log

### [timestamp] Planning Session

**Facts:**
- Read work items from tasks/0-design-core.md
- Created task file: tasks/1-implement-models.md
- Set dependencies: task/2 depends on task/1

**Analysis:**
- Work item requires architecture review before implementation
- Detected potential dependency chain complexity

**Conclusion:**
- Next task: tasks/1-implement-models.md
- Will create implementation task after review passes
```

**Plan Adjustment Log** (all significant decisions):
```markdown
## Plan Adjustment Log

### [timestamp] BLOCKER_DETECTED

**Details:**
- **blocked_task:** tasks/3-implementation.md
- **blocker:** Missing type information for User model
- **action:** Created exploration task to resolve blocker
- **exploration_task:** tasks/4-explore-user-model.md
```

### Work Log Placement

- **Architect/Implementor**: Append to the task file they're working on
- **Manager**: Append to kanban.md

### Escalation Work Logs

When escalating, work logs are **especially critical**:

```markdown
## Work Log - ESCALATION

**Facts:**
- Attempted implementation per spec
- Blocked at line 45: UserSchema missing required field

**Analysis:**
- Root cause: Core types incomplete for use case
- Attempted workaround: local schema extension (rejected - violates architecture)

**Conclusion:**
- **ESCALATE** to Architect
- Required: Update UserSchema in types.py to include email field
- Impact: All existing implementations need review
```

### Constraint

**You MUST write a work log before completing.** No exceptions. Even for failures, the work log documents what was attempted and why it failed.

## Rationale: Design Decisions

### Why Sequential Execution?

Sequential execution (one agent at a time) ensures:
- Consistent file system state for each agent
- Clear accountability for each step
- Predictable debugging when issues arise
- Manager has complete context for planning decisions

### Why One Work Item at a Time?

Returning one work item per planning cycle allows:
- Dynamic replanning based on implementation results
- Early discovery of architectural issues before committing to full task list
- Reduced waste from over-planning
- Adaptation to changing requirements

### Why Expertise Field?

The `expertise` field in task metadata allows:
- Self-assessment before attempting work
- Clear escalation criteria
- Appropriate agent selection by Manager
- Documentation of required domain knowledge

### Why Work Logs?

Mandatory work logging ensures:
- Handoff context for multi-agent workflows
- Audit trail for debugging
- Knowledge capture for future similar tasks
- Accountability for decisions made
