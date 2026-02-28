---
assignee: Implementor
expertise: ['Python', 'AST Design', 'Type Theory']
skills: ['code-reading', 'testing']
type: implement
priority: medium
state: cancelled
dependencies: []
refers: []
kanban: tasks/59-kanban-system-f-llm-integration.md
created: 2026-02-28T11:54:59.419409
---

# Task: Add pragma field to SurfaceTermDeclaration for LLM configuration

## Context
<!-- Background information and relevant context -->

## Files
<!-- List of files to modify or reference -->

## Description
<!-- What needs to be done -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-02-28 12:15:59] Implementation Complete

**Facts:**
Added pragma field to SurfaceTermDeclaration and SurfacePrimOpDecl in ast.py; Updated parser to handle pragma for prim_op declarations; Updated elaborator to pass pragma through; Fixed one test file (test_tool_calls.py) for mandatory type annotations; All core parser, elaborator, and type tests passing (327 tests). Parser has pre-existing bug with consuming declaration names as type variables affecting LLM integration tests.

**Analysis:**
Task lacks proper specification - Context, Files, and Description sections are empty. Tests were written without clear examples of expected syntax/behavior.

**C:**
Status: REPLAN - Task cancelled. Requires Phase 2 (examples and specifications) before implementation.

---

