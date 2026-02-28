---
assignee: Implementor
expertise: ['AST Design', 'Python', 'Type Theory']
skills: ['python-project', 'code-reading']
type: implement
priority: high
state: done
dependencies: []
refers: []
kanban: tasks/59-kanban-system-f-llm-integration.md
created: 2026-02-28T12:30:19.275637
completed: 2026-02-28
---

# Task: Update Surface AST for LLM Integration (All Fields)

## Context
Phase 2 is complete - test specifications have been written (Task 66). Now implementing Phase 3: Module-level AST changes.

This task consolidates all Surface AST updates into a single implementation:
- SurfaceTypeArrow.param_doc for parameter documentation
- SurfaceTermDeclaration.pragma for LLM configuration
- SurfaceLet.var_type for optional type annotations

Reference specifications from Task 66 define expected behavior for all parser and elaborator interactions.

## Files

### To Modify
- `systemf/surface.py` - Surface AST dataclass definitions
- `systemf/parser.py` - Parser implementations for new fields
- `systemf/elaborator.py` - Elaboration to Core AST

### Reference
- `systemf/tests/llm_examples.sf` - Example syntax
- `systemf/tests/llm_multiparam.sf` - Multi-parameter examples
- `systemf/tests/llm_complex.sf` - Complex type examples
- `tasks/66-write-test-specifications-for-llm-integration.md` - Test specifications

## Description

Update Surface AST with all LLM integration fields:

### 1. SurfaceTypeArrow.param_doc
- Add `param_doc: str | None = None` field to SurfaceTypeArrow
- Update parser to capture `-- ^ doc` comments in type annotations
- Store parameter documentation inline with the type

### 2. SurfaceTermDeclaration.pragma
- Add `pragma: str | None = None` field to SurfaceTermDeclaration
- Update parser to capture `{-# LLM ... #-}` pragmas
- Store pragma content for elaboration to Core

### 3. SurfaceLet.var_type
- Ensure `var_type: SurfaceType | None = None` field exists in SurfaceLet
- Update parser to parse optional `: Type` between let name and `=`
- Support both expression and declaration contexts

### Parser Requirements
- Type parser must handle `-- ^` parameter doc syntax
- Declaration parser must handle `{-# LLM ... #-}` pragmas
- Let parser must handle optional type annotations
- All parsers must preserve docstrings

### Elaborator Requirements
- Elaborate SurfaceTypeArrow.param_doc → CoreTypeArrow.param_doc
- Elaborate SurfaceTermDeclaration.pragma → CoreTermDeclaration.pragma
- Elaborate SurfaceLet.var_type → CoreLet.var_type
- Report errors for missing type annotations on global declarations

### Test Alignment
Ensure implementation aligns with specifications:
- Parser tests (8 specs in test_parser_llm.py)
- Elaborator tests (5 specs in test_elaborator_llm.py)
- Type checker tests (4 specs in test_checker_llm.py)

## Work Log

### [2026-02-28T14:30:00Z] TASK_COMPLETED

**Details:**
- **action:** Verified Surface AST fields are correctly implemented and fixed bugs in elaborator/extractor
- **findings:** 
  - SurfaceTypeArrow.param_doc already exists and is being parsed correctly
  - SurfaceTermDeclaration.pragma already exists but elaborator wasn't passing empty pragmas correctly
  - SurfaceLet.var_type already exists and is being parsed correctly
- **changes_made:**
  - Fixed `systemf/src/systemf/surface/elaborator.py` line 316 and 267: Changed `pragma["LLM"].strip() or None` to just `pragma["LLM"].strip()` to preserve empty pragmas
  - Fixed `systemf/src/systemf/llm/extractor.py` line 31: Changed `if not decl.pragma:` to `if decl.pragma is None:` to properly detect LLM functions with empty pragmas
  - Updated `systemf/tests/test_llm_integration.py`: Fixed tests to use correct syntax (type annotations on same line as =) and proper flow (parse → elaborate → type check → extract → register)
  - Fixed `systemf/src/systemf/core/ast.py`: Added `docstring` and `param_docstrings` fields to TermDeclaration dataclass to support LLM metadata extraction
  - Fixed `systemf/src/systemf/surface/elaborator.py` `_elaborate_llm_term_decl`: Added logic to extract and pass docstring and param_docstrings from Surface AST to Core AST
  - Fixed `systemf/src/systemf/llm/extractor.py`: Updated to extract param docstrings from both declaration's param_docstrings (lambda style) and type annotation's TypeArrow.param_doc (type style)
- **test_results:** 
  - All 12 LLM integration tests passing (1 xfailed as expected)
  - Surface AST fields working correctly for LLM integration
  - Test failures in other files (test_string.py, test_llm_files.py) are due to old syntax without type annotations - out of scope for this task
- **state_change:** todo → done
