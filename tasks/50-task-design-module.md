---
type: task
assignee: Architect
expertise: System Design, Type System
kanban: tasks/50-kanban-minimal-module-implementation.md
creator_role: manager
dependencies: []
skills: [code-reading, python-project]
type_field: design
---

# Design Module Dataclass

## Objective
Design the Module dataclass and LLMMetadata dataclass according to the kanban specification.

## Context
Create `systemf/src/systemf/core/module.py` with:
1. `Module` dataclass containing all compile-time artifacts
2. `LLMMetadata` dataclass for LLM function metadata

## Requirements

### Module Dataclass Fields:
- `name: str` - Module name (e.g., "prelude", "main")
- `declarations: list[Declaration]` - Core AST declarations
- `constructor_types: dict[str, Type]` - Data constructor signatures
- `global_types: dict[str, Type]` - Top-level term signatures
- `primitive_types: dict[str, PrimitiveType]` - Primitive type definitions
- `docstrings: dict[str, str]` - name -> docstring for declarations
- `llm_functions: dict[str, LLMMetadata]` - LLM function metadata
- `errors: list[ElaborationError]` - Elaboration errors
- `warnings: list[str]` - Warnings

### LLMMetadata Dataclass Fields:
- `function_name: str`
- `function_docstring: str | None`
- `arg_names: list[str]`
- `arg_types: list[Type]`
- `arg_docstrings: list[str | None]`
- `model: str | None`
- `temperature: float | None`

## Acceptance Criteria
- [ ] Module dataclass is frozen (immutable)
- [ ] All type hints are correct
- [ ] Imports are minimal and correct
- [ ] Docstrings follow project conventions
- [ ] Design is ready for elaborator integration

## Output
Create the module.py file with the dataclass definitions.


## Work Log

### [2026-02-27 17:47:40] Design Module Dataclass

**Facts:**
- Created `systemf/src/systemf/core/module.py` with two frozen dataclasses
- Designed `Module` dataclass with 9 fields as specified in requirements
- Designed `LLMMetadata` dataclass with 7 fields for LLM function metadata
- Both dataclasses use `frozen=True` for immutability
- Imports are minimal and focused on required types from existing modules

**Analysis:**
- Followed existing codebase patterns from `systemf.core.types` and `systemf.core.ast`
- Used modern Python type hints (X | None instead of Optional[X])
- Applied `from __future__ import annotations` for forward compatibility
- Included comprehensive docstrings following project conventions
- `ElaborationError` already exists in `systemf.surface.elaborator` - imported from there
- Design is ready for integration with elaborator (declarations field uses existing Declaration type)

**Conclusion:**
Status: ok

Design complete. Both dataclasses are properly frozen, type-hinted, and documented. Ready for implementation phase.

---

