---
assignee: Implementor
expertise: ['Python', 'AST Design']
skills: ['code-reading', 'testing']
type: implement
priority: high
state: done
dependencies: ['tasks/68-update-core-ast-for-llm-integration.md']
refers: []
kanban: tasks/59-kanban-system-f-llm-integration.md
created: 2026-02-28T12:25:27.229282
completed: 2026-02-28
---

# Task: Update Module Structure for LLM Integration

## Context
Update the Module structure and LLM metadata extractor to use the correct architecture where docstrings are stored in Module.docstrings (extracted during elaboration) and parameter docs are extracted from TypeArrow.param_doc fields.

## Files
- `systemf/src/systemf/llm/extractor.py` - Updated extractor to use Module.docstrings
- `systemf/src/systemf/core/module.py` - Module structure already complete

## Description
Update the LLM metadata extractor to follow the two-pass extraction architecture:
1. Pass 1 (Elaboration): Extract docstrings to Module.docstrings
2. Pass 2 (Post-Typecheck): Extract LLMMetadata using validated types and TypeArrow.param_doc

## Work Log

### [2026-02-28] Implementation Complete

**Changes Made:**
1. Updated `extract_llm_metadata()` in `extractor.py`:
   - Changed to use `module.docstrings.get(decl.name)` instead of `decl.docstring`
   - Changed to use `_extract_arg_docstrings(validated_type)` which extracts from `TypeArrow.param_doc`
   - Removed dependency on `decl.param_docstrings` field
   - Updated docstring to document the extraction timing (post-typecheck)

2. Verified Module structure:
   - Module already has `docstrings: dict[str, str]` field
   - Module already has `llm_functions: dict[str, LLMMetadata]` field
   - All fields properly documented

**Test Results:**
- All 12 core LLM integration tests passing (1 xfailed as expected)
- Extractor correctly pulls function docstrings from Module.docstrings
- Extractor correctly pulls parameter docstrings from TypeArrow.param_doc

**Architecture Verification:**
The implementation now correctly follows the design:
- Core AST is clean (no docstrings in TermDeclaration)
- TypeArrow.param_doc stores parameter docs from type annotations
- Module.docstrings stores function-level docs (extracted during elaboration)
- Extractor pulls from correct sources after type checking

**State Change:** todo → done
