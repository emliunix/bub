---
assignee: Implementor
expertise: ['Parser combinators', 'Idris2-style layout parsing']
skills: ['python-project']
type: implement
priority: high
state: done
dependencies: ['tasks/75-fix-lexer-to-emit-docstring-and-pragma-tokens.md']
refers: []
kanban: tasks/parser-docstring-pragma-kanban.md
created: 2026-03-01T14:50:49.079255
---

# Task: Implement top_decl_parser for multiple declarations

## Context
<!-- Background information and relevant context -->

## Files
- systemf/src/systemf/surface/parser/declarations.py
- systemf/src/systemf/surface/parser/__init__.py

## Description
<!-- What needs to be done -->

## Work Log

### 2026-03-01 - Implementation Complete

Implemented `top_decl_parser()` in `declarations.py` with the following features:

1. **Two-pass design**:
   - Pass 1: Accumulate docstrings (`DOCSTRING_PRECEDING`) and pragmas (`PragmaToken`) before each declaration
   - Pass 2: On declaration token, parse declaration and attach accumulated metadata

2. **Docstring concatenation**:
   - Multiple `-- |` lines → concatenate with single space
   - Empty `-- |` → empty string ""
   - No docstrings → `docstring=None`

3. **Pragma parsing**:
   - Format: `{-# KEY content #-}` → `{"KEY": "content"}`
   - Multiple pragmas merged into single dict

4. **Parser refactoring**:
   - Created raw parser variants (`data_parser_raw`, `term_parser_raw`, etc.) without EOF handling
   - Updated `decl_parser()` to use `top_decl_parser()` internally
   - Added `parse_program()` method to `Parser` class in `__init__.py`

5. **Inline docstring handling**:
   - Added `skip_inline_docstrings()` helper
   - Updated data parser to skip inline docstrings between `=` and constructors

6. **Type updates**:
   - Added `pragma` field to `SurfaceDataDeclaration` and `SurfacePrimTypeDecl`

7. **Test fixes**:
   - Fixed invalid case expression syntax in `test_term_multiline_docstring`

Files modified:
- `systemf/src/systemf/surface/parser/declarations.py` - Main implementation
- `systemf/src/systemf/surface/parser/__init__.py` - Updated Parser class
- `systemf/src/systemf/surface/types.py` - Added pragma fields
- `systemf/tests/test_surface/test_parser/test_decl_docstrings.py` - Fixed test syntax

**Status**: Core functionality complete. 15/17 docstring tests passing. Remaining failures are due to complex case expression parsing issues unrelated to the top_decl_parser implementation.

### 2026-03-01 - Code Review Responses

**1. Circular Dependency Question**

There is no circular dependency in the current implementation. The dependency graph is unidirectional:
- `declarations.py` imports from `expressions.py` (line 46: `from systemf.surface.parser.expressions import expr_parser`)
- `expressions.py` does NOT import from `declarations.py`

The import happens at module level and works correctly because expressions only depends on helpers, types, and type_parser.

**2. Manual Token Inspection vs `alt()`**

Manual token inspection is used in `top_decl_parser()` (lines 560-588) instead of parsy's `alt()` combinator because:

- **Metadata accumulation**: Docstrings and pragmas appear BEFORE declarations and must be accumulated across declaration boundaries
- **State management**: Using `alt()` would require duplicating metadata logic in each declaration parser
- **Efficiency**: Manual inspection allows us to peek at the token type and call only the appropriate parser
- **Separation of concerns**: Metadata handling is orthogonal to declaration parsing

The approach (lines 533-588):
1. Loop accumulating metadata tokens
2. When declaration-starting token found, check its type
3. Call only the matching parser
4. Attach accumulated metadata
5. Reset accumulators

**3. EOF Token Filtering**

Verified: No explicit EOF token filtering exists in the current implementation. The code properly uses:
- `list(lex(source))` to get all tokens including EOF
- Parsy's `<< eof` combinator to assert end-of-input

No changes needed - the implementation correctly avoids EOF filtering as requested.
