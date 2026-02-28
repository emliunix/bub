---
assignee: Implementor
expertise: ['Python', 'Dataclass Design']
skills: ['code-reading', 'testing']
type: implement
priority: medium
state: done
dependencies: ['tasks/66-write-test-specifications-for-llm-integration.md']
refers: []
kanban: tasks/59-kanban-system-f-llm-integration.md
created: 2026-02-28T12:25:28.758754
---

# Task: Create LLMMetadata Dataclass

## Context
<!-- Background information and relevant context -->

## Files
<!-- List of files to modify or reference -->
- `systemf/src/systemf/core/module.py` - LLMMetadata dataclass definition
- `systemf/src/systemf/llm/extractor.py` - LLM metadata extraction
- `systemf/src/systemf/eval/machine.py` - Prompt crafting using metadata
- `systemf/tests/test_llm_integration.py` - Tests
- `systemf/tests/test_llm_files.py` - File tests

## Description
<!-- What needs to be done -->
Verify and update the LLMMetadata dataclass to match the design specification from docs/design-llm-integration.md Section 2.5.

Key requirements from design spec:
- `function_name: str` - Function name
- `function_docstring: Optional[str]` - Function-level doc (-- | style)
- `arg_types: list[Type]` - Validated argument types
- `arg_docstrings: list[Optional[str]]` - Parameter docs from -- ^ syntax
- `pragma_params: Optional[str]` - Raw pragma string (e.g., "model=gpt-4")

Note: The design explicitly states in Appendix B.2 that arg_names should NOT be included since LLM functions are global declarations.

## Work Log
<!-- Work logs will be appended here -->

### 2026-02-28: Verified and Updated LLMMetadata

**Changes Made:**

1. **systemf/src/systemf/core/module.py** (lines 17-38)
   - Updated LLMMetadata docstring to match design spec
   - Removed `arg_names: list[str]` field (was extra, not in design)
   - Fields now match design exactly: function_name, function_docstring, arg_types, arg_docstrings, pragma_params

2. **systemf/src/systemf/llm/extractor.py**
   - Removed `_extract_arg_names()` function (no longer needed)
   - Updated `extract_llm_metadata()` to not populate arg_names

3. **systemf/src/systemf/eval/machine.py** (line 187-195)
   - Updated `_craft_prompt()` to generate arg0, arg1, etc. instead of using arg_names

4. **Test Updates:**
   - `tests/test_llm_integration.py`: Removed arg_names assertions (lines 88, 266)
   - `tests/test_llm_files.py`: Removed arg_names assertions (lines 90, 122)

**Test Results:**
- All 12 LLM integration tests pass
- 1 expected failure (xfail) for edge case
- No regressions in existing functionality

**Design Compliance:**
The LLMMetadata dataclass now exactly matches the design specification in docs/design-llm-integration.md Section 2.5, following the explicit decision in Appendix B.2 to not include arg_names.
