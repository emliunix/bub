---
assignee: Implementor
expertise: ['Python', 'AST Transformation']
skills: ['python-project', 'testing']
type: implement
priority: medium
state: done
dependencies: ['tasks/91-implement-typeelaborator-phase-2.md']
refers: ['tasks/80-design-system-f-elaborator-populate-work-items.md', 'tasks/79-kanban-system-f-elaborator-refactor.md']
kanban: tasks/79-kanban-system-f-elaborator-refactor.md
created: 2026-03-02T08:43:44.831790
---

# Task: Implement LLM pragma pass Phase 3

## Context
<!-- Background information and relevant context -->

## Files
- systemf/surface/llm/pragma_pass.py

## Description
Implement LLM pragma pass in systemf/surface/llm/pragma_pass.py for Phase 3. Extract pragmas from surface_decl, replace body with Core.PrimOp.

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-02T18:45:00] Implementation Complete

**Details:**
- **action:** Implemented LLM pragma pass for Phase 3 pipeline orchestration
- **state_transition:** todo → review
- **files_created:**
  - systemf/src/systemf/surface/llm/pragma_pass.py (380 lines)
  - systemf/src/systemf/surface/llm/__init__.py (18 lines)
- **implementation_summary:**
  - LLMPragmaPass class for processing LLM pragma annotations
  - process_declaration() method for SurfaceTermDeclaration and SurfacePrimOpDecl
  - Extracts LLM configuration (model, temperature, max_tokens) from pragma dict
  - Replaces function body with Core.PrimOp("llm.{name}")
  - Builds LLMMetadata with function name, docstring, arg types, arg docstrings, pragma params
  - Helper functions: parse_pragma_config(), process_llm_pragmas()
  - Handles both regular functions and primitive operations with LLM pragmas
  - Preserves parameter docstrings from lambda annotations
  - Tracks processed count for diagnostics
- **key_features:**
  - Pragma extraction from dict[str, str] format
  - Type-aware metadata extraction (arg types from TypeArrow)
  - Config parsing (key=value space-separated format)
  - Non-LLM declarations pass through unchanged
  - Support for param_docstrings from type annotations
- **usage_example:**
  ```python
  llm_pass = LLMPragmaPass()
  result = llm_pass.process_declaration(decl, core_type)
  # result.declaration - Core TermDeclaration with PrimOp body
  # result.metadata - LLMMetadata for runtime
  # result.is_llm - True if LLM pragma was found
  ```
- **convenience_function:**
  - process_llm_pragmas(decls, type_map) - batch processing with metadata collection
- **notes:** Implementation complete and imports verified. Ready for Architect review.

### [2026-03-02 10:11:00] LLM Pragma Pass Review Complete

**Facts:**
Reviewed LLM pragma pass implementation in systemf/src/systemf/surface/llm/pragma_pass.py. Implementation meets all requirements: pragma parsing correctly extracts config via parse_pragma_config() and _extract_pragma_config(), function replacement properly transforms body to PrimOp, metadata building complete with LLMMetadata including function name, docstring, arg types, arg docstrings, and pragma params. Error handling is appropriate - gracefully handles non-LLM declarations and missing pragmas. 3 parser tests pass for LLM pragma support. Manual verification confirms full functionality works correctly.

**Analysis:**
-

**Conclusion:**
Status: ok

---

