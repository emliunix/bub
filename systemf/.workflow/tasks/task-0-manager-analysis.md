# Task: Analyze System F Cleanup Requirements

## Metadata
- **Role**: Manager
- **Task ID**: task-0
- **Phase**: Planning
- **Status**: Ready
- **Created**: 2026-02-25

## Task Description

Analyze the systemf project to understand what cleanup is needed. Review the project structure, identify issues, and create a plan for the cleanup workflow.

## Context

The systemf project is a complete implementation of System F (polymorphic lambda calculus) with:
- 250+ passing tests
- Surface language (lexer, parser, elaborator)
- Core language (AST, type checker)
- Evaluator (interpreter, REPL)
- Project located at: /home/liu/Documents/bub/systemf/

## What to Analyze

1. Project structure and organization
2. Missing standard project files (e.g., .gitignore)
3. Cache/build artifacts that should be cleaned
4. Redundant or unnecessary files
5. Code quality issues (if any)
6. Documentation completeness

## Expected Output

1. **Update kanban.md** with:
   - Complete task breakdown for cleanup
   - Task dependencies
   - Estimated phases

2. **Create task files** in `.workflow/tasks/` for:
   - Design phase tasks (for Architect)
   - Execute phase tasks (for Implementor)

3. **Return** the immediate next task file path to execute

## Work Log

### 2026-02-25 Task Created
- Manager task created by Supervisor
- Ready for analysis phase
