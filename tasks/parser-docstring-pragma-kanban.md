# Parser Docstring & Pragma Support

## Request
Implement parser support for declaration-level docstrings (-- |) and pragmas ({-# ... #-}), enabling multiple declarations per file.

## Current State
✅ COMPLETE - All tasks finished

## Goal
- Parse `-- | comment` as declaration docstrings ✅
- Parse `{-# KEY content #-}` as pragmas (dict[str, str]) ✅
- Support multiple declarations in one file ✅
- Maintain backward compatibility ✅

## Status

### Backlog
(None)

### In Progress
(None)

### Review
(None)

### Done
- [x] Task 1: Fix lexer to emit docstring and pragma tokens (Task 75)
- [x] Task 2: Implement top_decl_parser for multiple declarations (Task 76)
- [x] Task 3: Wire top-level parser into Parser.parse() (Task 77)
- [x] Task 4: Showcase tests in test_parser_complex.py

## Summary

**Task 75** (Lexer):
- Modified lexer to emit DocstringToken for `-- | ...`
- Group pragma content into single PragmaToken
- Content parsed as `"KEY content"` for `{#- KEY content #-}`

**Task 76** (Parser):
- Implemented `top_decl_parser()` with two-pass design
- Accumulates docstrings/pragmas before each declaration
- Attaches metadata: docstrings concatenated with spaces
- Created `_raw()` parser variants for internal use

**Task 77** (Integration):
- Fixed critical bug: constr_parser now stops before term declarations
- Fixed expression parser layout constraints
- Added TestMultipleDeclarations and TestDeclarationMetadata to test_parser_complex.py
- 159 tests passing (20 pre-existing failures unrelated to this work)

## Test Results
```bash
# Showcase tests passing:
- test_bool_with_tostring
- test_rank2_const_function
- test_maybe_with_frommaybe
- test_natural_numbers_with_conversion
- test_list_with_length
- test_mixed_declarations
- test_pragma_with_declaration

# All basic functionality working:
- Docstring attachment (-- | style)
- Pragma parsing (dict[str, str])
- Multiple declarations per file
- Metadata preserved in AST
```

## Update: Task 78 Complete

**Task 78**: Enhance lexer to merge consecutive comments after docstrings
- **Status**: ✅ DONE

**Behavior**:
```systemf
-- | First line
-- Second line (merged)
-- Third line (merged)
data Bool = True | False
```
→ Single DocstringToken: "First line Second line (merged) Third line (merged)"

**Implementation**:
- Modified `lexer.py` with `_create_docstring_token()` method
- Look-ahead logic accumulates consecutive `--` lines
- Stops at: blank lines, new docstrings (`-- |`, `-- ^`), pragmas (`{-#`)
- Concatenates with single spaces

**Tests added**:
- test_multiline_docstring_concatenation
- test_multiline_docstring_stops_at_new_docstring
- test_multiline_docstring_stops_at_pragma
- test_multiline_docstring_stops_at_code
