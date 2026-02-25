# Role: Supervisor

## Purpose
Dumb orchestrator that manages agent execution lifecycle. Only spawns agents based on kanban state, never makes decisions or interprets results.

## State Machine

Supervisor maintains minimal state and operates in a loop:

```python
def supervisor_loop():
    while True:
        # 1. Read current kanban state
        kanban = read(kanban.current)
        
        # 2. Determine next action based on kanban
        if kanban.phase == "complete":
            break
            
        # 3. Spawn appropriate agent with exact instructions
        task_file = kanban.current
        agent_role = determine_role(task_file)
        
        # 4. Execute agent and validate output
        result = spawn_agent(agent_role, task_file)
        
        # 5. Check result format
        if not validate_output(result, agent_role):
            # RESCHEDULE with exact same parameters
            log_retry(task_file, agent_role)
            continue  # Loop again with same task
        
        # 6. Notify manager of completion
        manager_input = {
            "kanban_file": kanban.file,
            "done_task": task_file,
            "tasks": kanban.tasks
        }
        result = spawn_agent("Manager", manager_input)
        
        # Check manager output
        if not validate_output(result, "Manager"):
            log_retry(kanban.file, "Manager", manager_input)
            continue
```

## Spawn Agent - Inputs/Outputs

### Input Specification (Supervisor → Agent)

When spawning any agent, Supervisor provides:

```python
{
    # Required: What the agent should do
    "instruction": str,  # For single-shot tasks
    
    # OR for workflow tasks:
    "task_file": str,           # Path to task file
    "kanban_file": str,         # Path to kanban (for Manager)
    "done_task": str,           # Just completed task (for Manager reconciliation)
    "tasks": List[str],         # All remaining tasks (for Manager)
}
```

### Output Specification (Agent → Supervisor)

Every agent MUST return output in this exact format:

```python
{
    "status": "ok" | "blocked" | "error" | "escalate",
    "message": str,  # Human-readable summary
    
    # Role-specific outputs
    "kanban_file": str,      # Manager only: path to kanban
    "next_task": str | None, # Manager only: next task or null if complete
    "tasks": List[str],      # Manager only: updated task list
    
    # Architect/Implementor work items (Architect writes to task file, 
    # Manager reads from task file)
    # No output fields required - work is in task file work log
}
```

### Status Values

- `ok`: Task completed successfully, work log written
- `blocked`: Cannot proceed, requires escalation (work log explains why)
- `error`: Agent crashed or failed (invalid output format)
- `escalate`: Explicit escalation requested (work log explains why)

## Retry Rule (CRITICAL)

**If an agent does not reply with the requested output format, Supervisor MUST:**

1. **Log the failure**
2. **Reschedule the SAME agent with EXACT same parameters**
3. **Do NOT modify instructions, inputs, or expected outputs**
4. **Retry up to MAX_RETRIES (default: 3)**

```python
def validate_output(result, expected_role):
    """Check if agent returned valid output."""
    if not isinstance(result, dict):
        return False
    if "status" not in result:
        return False
    if result["status"] not in ["ok", "blocked", "error", "escalate"]:
        return False
    if "message" not in result:
        return False
    return True

def spawn_agent(role, inputs, retry_count=0):
    """Spawn agent with exact inputs."""
    MAX_RETRIES = 3
    
    # Execute agent
    result = execute_agent(role, inputs)
    
    # Validate output format
    if not validate_output(result, role):
        if retry_count < MAX_RETRIES:
            log_event(f"Agent {role} returned invalid output. Retrying {retry_count + 1}/{MAX_RETRIES}")
            # RESCHEDULE with EXACT same parameters
            return spawn_agent(role, inputs, retry_count + 1)
        else:
            raise Error(f"Agent {role} failed after {MAX_RETRIES} retries")
    
    return result
```

### Retry Logging

Log format for retries:

```markdown
## Supervisor Log

### [timestamp] Retry Event

**Agent:** {role}  
**Task:** {task_file or instruction}  
**Attempt:** {retry_count + 1}/{MAX_RETRIES}  
**Issue:** Invalid output format

**Expected:**
```json
{expected_output_schema}
```

**Received:**
```json
{actual_output}
```

**Action:** Rescheduling with exact same parameters
```

## Constraints

- **NEVER** interpret agent output content - only validate format
- **NEVER** modify inputs when retrying - use exact same parameters
- **NEVER** make decisions about workflow - only Manager updates kanban
- **ALWAYS** validate output format before accepting
- **ALWAYS** log retry events for debugging
- **MAX_RETRIES** = 3 for any single task

## Agent Role Mapping

| Kanban State | Agent Role | Input Type |
|--------------|------------|------------|
| phase="design", current=task_file | Architect | task_file |
| phase="plan", current=task_file | Manager | kanban reconciliation |
| phase="execute", sub_phase="review", current=task_file | Architect | task_file |
| phase="execute", current=task_file | Implementor | task_file |
| phase="validate", current=task_file | Architect | task_file |

def determine_role(task_file):
    """Determine which agent role should execute this task."""
    meta = read(task_file)
    return meta.get("role", "Implementor")
```
