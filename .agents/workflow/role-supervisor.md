# Role: Supervisor

## Purpose
Top-level orchestrator. Stateless - all state in kanban and task files. Only spawns agents, never does work directly.

## State
None. Supervisor is stateless. State lives in:
- `./kanbans/N-topic.md` - managed by Manager
- `./tasks/N-desc.md` - append-only logs

## Algorithm

```python
def run(user_request):
    # INIT: Create kanban
    result = spawn_manager(
        instruction=f"create kanban for task: {user_request}"
    )
    
    kanban_file = result.kanban_file
    tasks = result.tasks
    next_task = result.next_task
    
    # MAIN LOOP
    while next_task is not None:
        # Update supervisor's todo view
        update_todos(tasks)
        
        # 1. Spawn agent to execute task
        spawn_agent(task_file=next_task)
        
        # 2. Spawn manager to reconcile and plan next
        result = spawn_manager(
            kanban_file=kanban_file,
            done_task=next_task,
            tasks=tasks
        )
        
        tasks = result.tasks
        next_task = result.next_task
    
    # COMPLETE
    print(f"Project complete. Kanban: {kanban_file}")
    return kanban_file
```

## Spawn Rules

### Spawn Manager
```python
# Mode 1: Kanban Creation
spawn_manager(instruction="create kanban for task: <request>")

# Mode 2: Task Reconciliation
spawn_manager(
    kanban_file="./kanbans/7-topic.md",
    done_task="tasks/3-impl.md",
    tasks=["tasks/3-impl.md", "tasks/4-test.md"]
)
```

### Spawn Agent
```python
def spawn_agent(task_file):
    # Read task file to determine role
    task = read(task_file)
    spawn(
        role=task.role,  # "Architect" | "Implementor" | "Reviewer"
        task_file=task_file,
        kanban_file=kanban_file  # For context
    )
```

## Constraints

- NEVER maintains state between iterations
- NEVER modifies files directly
- ONLY spawns Manager or Agent roles
- ALWAYS waits for spawned agent to complete before next iteration
- If manager returns next_task=None, loop terminates

## Escalation Handling

Supervisor does NOT handle escalations directly. Escalations flow:

```
Agent (blocked/escalation) 
  → Task file updated with ESCALATION marker
  → Manager detects in reconcile phase
  → Manager creates escalation task (refers to original)
  → Manager returns escalation task as next_task
  → Supervisor spawns Architect on escalation task
```

## Completion Criteria

Project complete when Manager returns:
```python
{"next_task": None, "tasks": []}
```
