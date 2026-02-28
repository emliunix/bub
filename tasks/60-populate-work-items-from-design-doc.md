---
assignee: Architect
expertise: ['System Design', 'Type Theory', 'Compiler Architecture']
skills: ['code-reading']
type: design
priority: high
state: done
dependencies: []
refers: ['docs/design-llm-integration.md']
kanban: tasks/59-kanban-system-f-llm-integration.md
created: 2026-02-28T11:30:00.991105
---

# Task: Populate Work Items from Design Doc

## Context
<!-- Background information and relevant context -->

## Files
<!-- List of files to modify or reference -->

## Description
Review the design document at docs/design-llm-integration.md and extract work items for the 4-phase execution plan. Focus on Phase 1 (Foundation) and Phase 2 (Examples & Tests) initially, as these provide the base for later phases.

## Work Log
<!-- Work logs will be appended here -->

### [2026-02-28 11:31:34] Scope Analysis Complete

**Facts:**
Phase 1 (Foundation) and Phase 2 (Examples & Tests) work items identified. Surface AST types are core dependencies. Key decisions: -- ^ param docs in SurfaceTypeArrow, mandatory type annotations for globals, prim_op keyword for LLM functions.

**Analysis:**
-

**Conclusion:**
Status: ok

---

## Suggested Work Items (for Manager)

Based on the design document analysis, the following work items should be created:

### Phase 1: Foundation (Core Types)

```yaml
work_items:
  - description: Update SurfaceTypeArrow with param_doc field for parameter documentation
    files: [src/systemf/surface/ast.py]
    related_domains: ["Type Systems", "Compiler Architecture"]
    expertise_required: ["Python", "AST Design", "Type Theory"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Add param_doc: Optional[str] = None field. Used when parser sees -- ^ after type.

  - description: Update SurfaceTermDeclaration to require type_annotation field
    files: [src/systemf/surface/ast.py]
    related_domains: ["Type Systems", "Compiler Architecture"]
    expertise_required: ["Python", "AST Design", "Type Theory"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Change type_annotation from Optional[SurfaceType] to SurfaceType. System F requires explicit typing for globals.

  - description: Update SurfaceLet with optional var_type field for type annotations
    files: [src/systemf/surface/ast.py]
    related_domains: ["Type Systems", "Compiler Architecture"]
    expertise_required: ["Python", "AST Design", "Type Theory"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Add var_type: Optional[SurfaceType] field to support 'let x : Type = value in body' syntax.

  - description: Add pragma field to SurfaceTermDeclaration for LLM configuration
    files: [src/systemf/surface/ast.py]
    related_domains: ["Type Systems", "Compiler Architecture"]
    expertise_required: ["Python", "AST Design"]
    dependencies: []
    priority: medium
    estimated_effort: small
    notes: Add pragma: dict[str, str] | None = None field. Stores {-# LLM model=gpt-4 #-} style pragmas.

  - description: Update Core TypeArrow with param_doc field for doc extraction
    files: [src/systemf/core/ast.py]
    related_domains: ["Type Systems", "Compiler Architecture"]
    expertise_required: ["Python", "AST Design", "Type Theory"]
    dependencies: [0]  # Depends on SurfaceTypeArrow design
    priority: high
    estimated_effort: small
    notes: Add param_doc: Optional[str] to Core TypeArrow for post-typecheck doc extraction.

  - description: Update Core TermDeclaration with pragma field
    files: [src/systemf/core/ast.py]
    related_domains: ["Type Systems", "Compiler Architecture"]
    expertise_required: ["Python", "AST Design"]
    dependencies: [3]  # Depends on SurfaceTermDeclaration pragma design
    priority: medium
    estimated_effort: small
    notes: Add pragma: Optional[str] field. Core AST has no docstring field (extracted to Module).

  - description: Verify Module structure has docstrings and llm_functions fields
    files: [src/systemf/core/module.py]
    related_domains: ["Type Systems", "Compiler Architecture"]
    expertise_required: ["Python", "Module Design"]
    dependencies: [5]  # Depends on Core AST changes
    priority: high
    estimated_effort: small
    notes: Ensure docstrings: dict[str, str] and llm_functions: dict[str, LLMMetadata] fields exist.

  - description: Create LLMMetadata dataclass for LLM function metadata
    files: [src/systemf/llm/types.py]
    related_domains: ["Type Systems", "LLM Integration"]
    expertise_required: ["Python", "Type Design"]
    dependencies: [5]  # Depends on Core Type design
    priority: high
    estimated_effort: small
    notes: Define LLMMetadata with function_name, function_docstring, arg_types, arg_docstrings, pragma_params fields.
```

### Phase 2: Examples & Test Specifications

```yaml
work_items:
  - description: Create example files with new LLM function syntax
    files: [tests/llm_examples.sf, tests/llm_multiparam.sf, tests/llm_complex.sf]
    related_domains: ["Testing", "Language Design"]
    expertise_required: ["System F", "Language Syntax"]
    dependencies: [0, 1, 2]  # Depends on all Surface AST types
    priority: high
    estimated_effort: medium
    notes: Create example files showing prim_op syntax, -- ^ param docs, and LLM pragmas.

  - description: Create parser test specifications for type annotations with docs
    files: [tests/test_surface/test_parser_docs.py]
    related_domains: ["Testing", "Parser Design"]
    expertise_required: ["Python", "Testing", "Parser Combinators"]
    dependencies: [0, 8]  # Depends on SurfaceTypeArrow and examples
    priority: high
    estimated_effort: medium
    notes: Test parse_type_with_param_doc, parse_multi_param_type, parse_doc_comment_caret.

  - description: Create parser test specifications for prim_op declarations
    files: [tests/test_surface/test_parser_docs.py]
    related_domains: ["Testing", "Parser Design"]
    expertise_required: ["Python", "Testing", "Parser Combinators"]
    dependencies: [1, 3, 8]  # Depends on SurfaceTermDeclaration, pragma, and examples
    priority: high
    estimated_effort: medium
    notes: Test parse_prim_op_declaration, parse_let_with_type_annotation, parse_mandatory_type_annotation.

  - description: Create elaborator test specifications for prim_op handling
    files: [tests/test_surface/test_elaborator.py]
    related_domains: ["Testing", "Compiler Architecture"]
    expertise_required: ["Python", "Testing", "Type Elaboration"]
    dependencies: [4, 5, 6, 9]  # Depends on Core AST and parser tests
    priority: medium
    estimated_effort: medium
    notes: Test elab_prim_op_generates_primop_body, elab_function_preserves_docstring, elab_passes_pragma_to_core.

  - description: Create integration test specifications for full pipeline
    files: [tests/test_integration/test_llm_pipeline.py]
    related_domains: ["Testing", "Integration Testing"]
    expertise_required: ["Python", "Testing", "System Integration"]
    dependencies: [6, 7, 10, 11]  # Depends on Module, LLMMetadata, and component tests
    priority: medium
    estimated_effort: large
    notes: Test full_pipeline_basic_llm, full_pipeline_multi_param, llm_metadata_has_validated_types.
```

### Dependency Graph Summary

**Phase 1 Dependencies:**
- Items 0-3 (Surface AST) have no dependencies - can be done in parallel
- Item 4 (Core TypeArrow) depends on item 0
- Item 5 (Core TermDeclaration) depends on item 3
- Item 6 (Module) depends on item 5
- Item 7 (LLMMetadata) depends on item 5

**Phase 2 Dependencies:**
- Item 8 (Examples) depends on Surface AST items (0-2)
- Items 9-10 (Parser tests) depend on examples (8) and relevant Surface types
- Item 11 (Elaborator tests) depends on Core AST (4-5), Module (6), and parser tests
- Item 12 (Integration tests) depends on Module (6), LLMMetadata (7), and all component tests

**Recommended Execution Order:**
1. Parallel: Items 0-3 (Surface AST types)
2. Parallel: Items 4-5 (Core AST types)
3. Parallel: Items 6-7 (Module and LLMMetadata)
4. Item 8 (Examples)
5. Parallel: Items 9-10 (Parser tests)
6. Item 11 (Elaborator tests)
7. Item 12 (Integration tests)

### [2026-02-28 11:34:35] Design Review

**Facts:**
<!-- No facts recorded -->

**Analysis:**
<!-- No analysis recorded -->

**Conclusion:**
<!-- No conclusion recorded -->

---

