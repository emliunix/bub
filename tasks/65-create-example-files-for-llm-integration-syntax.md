---
assignee: Architect
expertise: ['AST Design', 'Type Theory', 'Documentation']
skills: ['code-reading']
type: design
priority: high
state: done
dependencies: []
refers: []
kanban: tasks/59-kanban-system-f-llm-integration.md
created: 2026-02-28T12:25:17.540514
---

# Task: Create Example Files for LLM Integration Syntax

## Context
Created comprehensive example files for the LLM integration syntax in System F. These examples demonstrate the new `prim_op` keyword, parameter docstrings (`-- ^`), function-level docstrings (`-- |`), and pragma-based configuration (`{-# LLM ... #-}`).

## Files
- `systemf/tests/llm_examples.sf` - Basic LLM function examples
- `systemf/tests/llm_multiparam.sf` - Multi-parameter LLM function examples
- `systemf/tests/llm_complex.sf` - Complex types and advanced patterns

## Description
Created three example files that comprehensively demonstrate the LLM integration syntax as specified in the design document (docs/design-llm-integration.md, Section 2.7):

1. **llm_examples.sf**: Basic examples including:
   - Single parameter LLM function with pragma
   - LLM function without pragma (using defaults)
   - Regular function for comparison
   - Two-parameter LLM function

2. **llm_multiparam.sf**: Multi-parameter examples including:
   - Two-parameter classification function
   - Code generation with language and description
   - Three-parameter text formatting function
   - Comparison with regular multi-parameter function

3. **llm_complex.sf**: Complex type examples including:
   - Custom type definitions (Maybe, Either)
   - Helper functions (extract, mapMaybe)
   - LLM with Maybe return type
   - LLM with Either for error handling
   - Higher-order function patterns
   - Data type with field documentation

## Work Log

### [2026-02-28] Example Files Created
- Updated `llm_examples.sf` with comprehensive basic examples following design doc syntax
- Updated `llm_multiparam.sf` with multiple parameter examples and comparison functions
- Updated `llm_complex.sf` with custom types, error handling, and advanced patterns
- All examples use proper syntax:
  - `{-# LLM model=gpt-4 temperature=0.7 #-}` for pragmas
  - `-- | Description` for function-level docs
  - `-- ^ Description` for parameter docs
  - `prim_op name : Type -> Type` for declarations
