---
assignee: Implementor
type: implementation
kanban: tasks/parser-docstring-pragma-kanban.md
dependencies: [parser-task1-lexer-fixes.md]
expertise: Parser combinators, Idris2-style layout parsing
skills: [python-project]
references:
  - systemf/src/systemf/surface/parser/declarations.py
  - systemf/src/systemf/surface/parser/__init__.py
  - tests/test_surface/test_parser/test_decl_docstrings.py
  - tests/test_surface/test_parser/test_decl_pragma.py
---

# Task 2: Implement top_decl_parser for Multiple Declarations

## Objective
Create a top-level parser that handles multiple declarations, accumulating docstrings and pragmas before each declaration.

## Current State
- `decl_parser()` parses single declarations with `<< eof`
- `Parser.parse()` calls `decl_parser()` once, returns `[result]`
- No support for multiple declarations or metadata attachment

## Two-Pass Design

### Pass 1: Accumulation
Parse tokens sequentially, collecting into buckets:
```
docstrings: list[str] = []  # -- | style comments
pragma: dict[str, str] | None = None  # {-# ... #-}
```

### Pass 2: Attachment
When a declaration token (data, term, prim_type, prim_op) is encountered:
1. Parse the declaration using existing parsers
2. Attach accumulated docstrings (concatenated with space)
3. Attach accumulated pragma  
4. Reset accumulators
5. Continue for next declaration

## Requirements

### top_decl_parser() Function
```python
def top_decl_parser() -> P[list[SurfaceDeclaration]]:
    """Parse multiple declarations with docstrings and pragmas.
    
    Accumulates docstrings and pragmas before each declaration,
    attaches them to the declaration, then continues parsing.
    """
```

### Accumulation Logic
1. **Skip** regular comments (`--` without `|`)
2. **Accumulate** docstrings (`DOCSTRING_PRECEDING` tokens) → list[str]
3. **Accumulate** pragmas (`PragmaToken`) → dict[str, str]
   - Parse `{-# KEY content #-}` → `{"KEY": "content"}`
   - Multiple pragmas merge: `{"INLINE": "", "LLM": "model=gpt-4"}`
4. **On declaration**: 
   - Parse using `data_parser()`, `term_parser()`, etc.
   - Set `decl.docstring = " ".join(docstrings)` (or None if empty)
   - Set `decl.pragma = pragma` (or None if empty)
   - Reset accumulators
   - Append to results list

### EOF Handling
- EOF should only be checked at the very end
- Internal parsers should NOT check EOF
- Use `top_decl_parser << eof` pattern

### Metadata Concatenation Rules
- Multiple `-- |` lines: concatenate with single space
- Example: `[