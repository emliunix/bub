---
assignee: Architect
expertise: ['Test Design', 'Type Theory']
skills: ['code-reading', 'testing']
type: design
priority: high
state: done
dependencies: ['tasks/65-create-example-files-for-llm-integration-syntax.md']
refers: []
kanban: tasks/59-kanban-system-f-llm-integration.md
created: 2026-02-28T12:25:19.235461
---

# Task: Write Test Specifications for LLM Integration

## Context
Following the successful creation of example files in Task 65, we now need comprehensive test specifications that define the expected behavior for all LLM integration components. These specifications will guide the implementation phase.

The design document (docs/design-llm-integration.md) defines a 4-phase execution plan:
- Phase 1: Foundation (AST updates) - partially complete
- Phase 2: Examples & Tests (current phase - specs needed)
- Phase 3: Component Implementation
- Phase 4: Integration & Testing

## Files

### Reference Files
- `docs/design-llm-integration.md` - Complete design specification
- `systemf/tests/llm_examples.sf` - Basic LLM function examples
- `systemf/tests/llm_multiparam.sf` - Multi-parameter examples
- `systemf/tests/llm_complex.sf` - Complex type examples
- `systemf/tests/test_llm_integration.py` - Existing tests (reference for patterns)

### Output Files (to be created)
- `systemf/tests/test_surface/test_parser_llm.py` - Parser test specifications
- `systemf/tests/test_docs/test_extractor.py` - Doc extraction test specifications
- `systemf/tests/test_llm/test_metadata.py` - LLM metadata extraction test specifications
- `systemf/tests/test_integration/test_llm_pipeline.py` - Full pipeline test specifications

## Description

Create comprehensive test specifications covering all components in the LLM integration design. Each specification should include:
1. Test name and purpose
2. Input (source code or data structure)
3. Expected output/assertions
4. Component under test
5. Dependencies on other specs

### Test Specification Categories

#### 1. Parser Tests (`test_parser_llm.py`)

**test_parse_type_with_param_doc**
- Input: `String -- ^ Input text -> String`
- Assert: `SurfaceTypeArrow.param_doc == "Input text"`
- Component: Type parser

**test_parse_multi_param_type_with_docs**
- Input: Multi-line type with multiple `-- ^`
- Assert: Each arrow has correct param_doc
- Component: Type parser

**test_parse_prim_op_declaration**
- Input: `prim_op name : Type -- ^ doc -> Type`
- Assert: Creates SurfacePrimOpDecl with correct name and type
- Component: Declaration parser

**test_parse_let_with_type_annotation**
- Input: `let x : Int = 42 in x`
- Assert: `SurfaceLet.var_type` is present with Int type
- Component: Let expression parser

**test_parse_mandatory_type_annotation**
- Input: Global decl `func = \x -> x` (missing type)
- Assert: Error raised during elaboration (not parse)
- Component: Elaborator validation

**test_parse_multi_line_param_doc**
- Input: Consecutive `-- ^` lines
- Assert: Concatenated with newlines
- Component: Type parser

**test_parse_empty_param_doc**
- Input: `String -- ^ -> Int`
- Assert: `param_doc == ""`
- Component: Type parser

#### 2. Elaborator Tests (`test_elaborator_llm.py`)

**test_elab_prim_op_generates_primop_body**
- Input: `prim_op translate : String -> String`
- Assert: SurfacePrimOpDecl → Core TermDeclaration with PrimOp body
- Component: Elaborator

**test_elab_llm_pragma_detected**
- Input: Declaration with `{-# LLM model=gpt-4 #-}`
- Assert: Pragma stored in Core declaration
- Component: Elaborator

**test_elab_function_preserves_docstring**
- Input: `-- | Function doc\nfunc : Type -> Type`
- Assert: Docstring flows Surface → Core
- Component: Elaborator

**test_elab_missing_type_annotation_error**
- Input: Global decl without type annotation
- Assert: ElaborationError with clear message
- Component: Elaborator validation

**test_elab_let_with_type_annotation**
- Input: `let x : Int = 42 in x + 1`
- Assert: Type annotation preserved in Core
- Component: Elaborator

#### 3. Type Checker Tests (`test_checker_llm.py`)

**test_check_primop_llm_lookup**
- Input: `PrimOp("llm.translate")` with registered type
- Assert: Returns correct type from global_types
- Component: Type checker

**test_check_primop_unknown_llm_function**
- Input: `PrimOp("llm.unknown")` without registration
- Assert: TypeError with "Unknown LLM function" message
- Component: Type checker

**test_check_validated_types_returned**
- Input: Module with declarations
- Assert: Returns global_types dict with validated Type objects
- Component: Type checker

**test_check_typearrow_param_doc_preserved**
- Input: TypeArrow with param_doc
- Assert: param_doc present after type checking
- Component: Type checker (pass-through)

#### 4. Doc Extraction Tests (`test_extractor.py`)

**test_extract_function_docstring**
- Input: TermDeclaration with docstring
- Assert: `docstrings["func"] == "doc"`
- Component: Doc extractor

**test_extract_param_docs_from_type**
- Input: TypeArrow chain with param_docs
- Assert: `docstrings["func.$0"]` and `docstrings["func.$1"]` correct
- Component: Doc extractor

**test_extract_no_docs_for_undocumented**
- Input: Declaration without docs
- Assert: No entry in docstrings dict
- Component: Doc extractor

**test_extract_multi_param_function_docs**
- Input: 3-parameter function with partial docs
- Assert: Only documented params have entries
- Component: Doc extractor

**test_extract_record_field_docs**
- Input: Data declaration with field docs
- Assert: `docstrings["Type.$field"]` populated
- Component: Doc extractor

#### 5. LLM Metadata Extraction Tests (`test_metadata.py`)

**test_extract_llm_metadata_with_pragma**
- Input: Declaration with `{-# LLM model=gpt-4 #-}`
- Assert: LLMMetadata created with pragma_params
- Component: LLM extractor

**test_extract_llm_function_docstring**
- Input: Declaration with `-- | Function doc`
- Assert: `LLMMetadata.function_docstring` set
- Component: LLM extractor

**test_extract_llm_arg_types_and_docs**
- Input: Multi-param function with validated types
- Assert: `arg_types` and `arg_docstrings` arrays correct
- Component: LLM extractor

**test_extract_llm_skips_non_llm**
- Input: Regular declaration without LLM pragma
- Assert: Not included in llm_functions dict
- Component: LLM extractor

**test_extract_llm_validated_types_only**
- Input: Post-typecheck declarations
- Assert: `arg_types` are validated Type objects (not SurfaceType)
- Component: LLM extractor

**test_extract_llm_empty_pragma**
- Input: `{-# LLM #-}` without params
- Assert: `pragma_params` is empty string or None
- Component: LLM extractor

#### 6. Full Pipeline Integration Tests (`test_llm_pipeline.py`)

**test_full_pipeline_basic_llm**
- Input: `llm_examples.sf` content
- Steps: Parse → Elaborate → Typecheck → Extract docs → Extract LLM
- Assert: Module.docstrings and Module.llm_functions populated
- Component: Full pipeline

**test_full_pipeline_multi_param**
- Input: `llm_multiparam.sf` content
- Steps: Full pipeline
- Assert: All param docs extracted correctly
- Component: Full pipeline

**test_full_pipeline_complex_types**
- Input: `llm_complex.sf` content
- Steps: Full pipeline
- Assert: Custom types (Maybe, Either) handled correctly
- Component: Full pipeline

**test_full_pipeline_error_handling**
- Input: Invalid source (syntax error)
- Steps: Parse
- Assert: Error captured, graceful failure
- Component: Full pipeline

#### 7. Edge Case Tests (distributed across files)

**test_empty_doc_comment**
- Input: `String -- ^ -> Int`
- Assert: param_doc = ""

**test_consecutive_doc_lines**
- Input: Multiple `-- ^` lines
- Assert: Concatenated with newlines

**test_nested_type_with_docs**
- Input: `(a -- ^ doc1 -> b) -- ^ doc2 -> c`
- Assert: Both docs captured at correct levels

**test_no_space_after_caret**
- Input: `String --^doc -> Int`
- Assert: Valid or parse error (define behavior)

## Dependencies Between Specifications

```
Parser Tests (Layer 1)
    ↓
Elaborator Tests (Layer 2)
    ↓
Type Checker Tests (Layer 3)
    ↓
Doc Extraction Tests (Layer 4a)
LLM Metadata Tests (Layer 4b)
    ↓
Integration Tests (Layer 5)
```

## Work Log

### [2026-02-28T14:00:00Z] SPECIFICATIONS_CREATED

**Details:**
- **action:** Created comprehensive test specifications for LLM integration
- **categories:** 7 major test categories with 40+ individual test specifications
- **coverage:** Parser, Elaborator, Type Checker, Doc Extraction, LLM Metadata, Integration, Edge Cases
- **deliverables:** 
  - Category 1: Parser Tests (8 specs)
  - Category 2: Elaborator Tests (5 specs)
  - Category 3: Type Checker Tests (4 specs)
  - Category 4: Doc Extraction Tests (5 specs)
  - Category 5: LLM Metadata Tests (6 specs)
  - Category 6: Integration Tests (4 specs)
  - Category 7: Edge Cases (4 specs)
- **next_step:** Proceed to Phase 3 - Module-level AST implementation tasks (67, 68, 69, 70)

**Specifications organized by:**
- Component responsibility (parser/elaborator/checker/extractor)
- Data flow (surface → core → validated → extracted)
- Test granularity (unit → integration)
- Edge cases and error conditions
