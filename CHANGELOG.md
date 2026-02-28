# Changelog

All notable changes to the System F LLM Integration project.

## [Unreleased] - Phase 4 Complete

### Added

#### Phase 1: Surface AST Foundation
- **SurfaceTypeArrow.param_doc field** - Support for parameter docstrings in type annotations
- **Mandatory type annotations** - Global declarations now require explicit type annotations
- **SurfaceLet.var_type field** - Optional type annotations for local let bindings
- **SurfaceTermDeclaration.pragma field** - Dict-based pragma storage for LLM configuration

#### Phase 2: Examples and Test Specifications
- Example files demonstrating LLM syntax:
  - `tests/llm_examples.sf` - Basic LLM function examples
  - `tests/llm_multiparam.sf` - Multi-parameter functions
  - `tests/llm_complex.sf` - Complex types (Maybe, Either)
- Comprehensive test specifications (40+ tests):
  - Parser tests for `-- ^` parameter docs
  - Elaborator tests for `prim_op` declarations
  - Type checker tests for LLM functions
  - Doc extraction tests
  - LLM metadata extraction tests
  - Integration tests for full pipeline

#### Phase 3: Core Implementation
- **Core TypeArrow.param_doc field** - Parameter docs preserved in Core AST
- **Module.docstrings dict** - O(1) lookup for function and parameter documentation
- **Module.llm_functions dict** - O(1) lookup for LLM function metadata
- **Doc extraction module** (`docs/extractor.py`) - Post-typecheck doc extraction
- **LLM metadata extraction** (`llm/extractor.py`) - Extract LLMMetadata from validated types
- **LLMMetadata dataclass** - Rich metadata for LLM function execution:
  - `function_name`: Function identifier
  - `function_docstring`: Function-level documentation
  - `arg_types`: Validated argument types
  - `arg_docstrings`: Parameter documentation
  - `pragma_params`: LLM configuration (model, temperature)

#### Phase 4: REPL Integration and Documentation
- **REPL `:llm` command** - List and inspect LLM functions
- **REPL integration** - Automatic LLM metadata extraction on file load
- **Evaluator integration** - LLM function registration and prompt crafting
- **User Manual** - Complete documentation for LLM function syntax and usage
- **README updates** - LLM integration quick start and examples

### Syntax

#### LLM Function Definition
```systemf
{-# LLM model=gpt-4 temperature=0.7 #-}
-- | Function description
prim_op functionName : ArgType
  -- ^ Parameter documentation
  -> ReturnType
  -- ^ Return documentation
```

#### Key Syntax Elements
- `{#- LLM ... #-}` - Pragma for LLM configuration (optional model, temperature)
- `-- | ...` - Function-level docstring
- `-- ^ ...` - Parameter docstring (attaches to type on the left)
- `prim_op` - Keyword declaring a function with implicit LLM implementation

### Architecture

**Two-Pass Extraction:**
1. **Pass 1 (Elaboration)**: Surface AST → Core AST with docstring preservation
2. **Pass 2 (Post-Typecheck)**: Extract docs and LLM metadata from validated types

**Key Design Decisions:**
- Parameter docs embedded in type annotations (`-- ^` on types)
- Global-only LLM functions (locals use regular let bindings)
- Mandatory type annotations for globals (explicit typing philosophy)
- Dict-based pragma storage (extensible for future pragma types)
- O(1) hash map lookups for REPL queries

### Testing

- **148 total tests passing** (1 skipped)
- **56 LLM-specific tests** (1 expected failure)
- **8 LLM file tests** for example files
- Test coverage includes:
  - Parser syntax validation
  - Elaborator transformation
  - Type checking
  - Doc extraction
  - LLM metadata extraction
  - REPL integration
  - End-to-end file processing

### Breaking Changes

None. This is a new feature addition.

### Migration Guide

For existing System F code, no changes are required. To add LLM functions:

1. Define function with `prim_op` keyword
2. Add `{-# LLM #-}` pragma (optional: specify model/temperature)
3. Use `-- |` for function docs and `-- ^` for parameter docs
4. Load file in REPL and use `:llm` command to verify

Example migration from old experimental syntax:
```systemf
-- Old (removed):
translate : String -> String
translate = \text -- ^ doc -> extern

-- New:
{-# LLM model=gpt-4 #-}
-- | Translate text
prim_op translate : String
  -- ^ Input text
  -> String
```

## See Also

- `docs/design-llm-integration.md` - Complete technical design document
- `docs/user-manual.md` - User guide for LLM integration
- `systemf/tests/llm_examples.sf` - Working example files
