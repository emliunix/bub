# Role: Implementor

## Getting Started (REQUIRED)

Before doing any work:

1. **Run check-task.py to get your briefing:**
   ```bash
   .agents/skills/workflow/scripts/check-task.py --task <your_task_file>
   ```

2. **Read this file completely** (`role-implementor.md`)

3. **Load required skills** listed in the briefing

## Purpose
Execute implementation tasks according to specification.

## Inputs

```python
{
    "task_file": "tasks/2-refactor-models.md"
}
```

## Algorithm

```python
def execute(task_file):
    task = read(task_file)
    
    # 0. Work log setup (REQUIRED per skills.md Work Logging Requirement)
    work_facts = ["Read specification from task file"]
    work_analysis = []
    
    # 1. Load skills and expertise
    for skill in task.skills:
        load_skill(skill)
    
    # EXPERTISE REQUIREMENT: You should be an expert in these areas
    # task.expertise: ["Software Engineering", "Code Implementation", ...]
    # If you lack expertise in any of these areas, escalate immediately.
    
    # 2. Read specification
    spec = extract_spec(task)
    
    # 3. Implement
    try:
        # Implement the specification
        modified_files = implement(spec)
        work_facts = [modified_files, "All tests pass"]
        
        # Check for issues outside current scope
        discovered = check_for_unrelated_issues()
        if discovered:
            work_facts.append("Discovered issues for future tasks")
        
        # Log work using script
        execute_script(f"{skill_path}/scripts/log-task.py", {
            "command": "quick",
            "task": task_file,
            "title": "Implementation Complete",
            "facts": work_facts,
            "analysis": work_analysis,
            "conclusion": "ok"
        })
        return "ok"
        
    except Exception as e:
        # Log escalation
        execute_script(f"{skill_path}/scripts/log-task.py", {
            "command": "quick", 
            "task": task_file,
            "title": "Blocked",
            "facts": ["Implementation blocked"],
            "analysis": ["Cannot proceed with current spec"],
            "conclusion": "escalate"
        })
        return "blocked"
```

## Constraints

- NEVER modify types.py (only read)
- NEVER spawn subagents
- ALWAYS append log to task file
- If blocked, explain what kind of help needed
- Match specification exactly; deviations require escalation

## Expertise Check

Before starting, verify you have expertise in ALL areas listed in `task.expertise`.

**Required Expertise for this task:**
- (Populated from task file)

If you lack any required expertise, escalate immediately.

## Task Analysis (Pre-Implementation)

Before implementing, analyze the task:

**1. Divisibility Check**
- Can this task be split into independent sub-tasks?
- Are there natural boundaries (different files, different concerns)?
- If YES: Escalate with suggested work items for subdivision

**2. Prerequisites Check**
- Are all dependencies satisfied?
- Are required types/interfaces already defined?
- Are test contracts established?
- If NO: Escalate with missing prerequisites information

**Example escalation for subdivision:**
```markdown
## Work Log

### [14:30] Task Analysis | escalate

**F:**
- Analyzed task requirements
- Identified 3 independent components: auth, validation, storage
- Each can be implemented separately

**A:**
- Current task bundles unrelated concerns
- Better to implement auth first, then validation, then storage
- Reduces risk and enables parallel work

**C:**
- **ESCALATE** - Task should be subdivided
- Requires: Manager to create 3 separate tasks
- Impact: Better task granularity

## Suggested Work Items

```yaml
work_items:
  - description: Implement authentication layer
    files: [src/auth.py, tests/test_auth.py]
    expertise_required: ["Security", "Authentication"]
    priority: high
  - description: Implement input validation
    files: [src/validation.py, tests/test_validation.py]
    expertise_required: ["Data Validation"]
    priority: medium
```

**Example escalation for missing prerequisites:**
```markdown
## Work Log

### [14:30] Prerequisites Check | escalate

**F:**
- Attempted to implement API endpoint
- Required User types not defined in types.py
- Database schema interface missing

**A:**
- Cannot implement without type definitions
- Need schema contract first
- Implementation would be speculative

**C:**
- **ESCALATE** - Missing required prerequisites
- Missing: User type definition, Database schema interface
- Requires: Architect to define core types first
```

## Completion Checklist

- [ ] All files in "Files" section modified
- [ ] Matches types.py specification
- [ ] No TODOs remaining
- [ ] No workarounds without escalation
- [ ] Expertise requirements met (or escalated)
- [ ] **Work log written** (REQUIRED - Facts, Analysis, Conclusion)
