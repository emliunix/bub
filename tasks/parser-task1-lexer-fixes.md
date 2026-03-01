---
assignee: Implementor
type: implementation
kanban: tasks/parser-docstring-pragma-kanban.md
dependencies: []
expertise: Parser combinators, Lexical analysis
skills: [python-project]
references:
  - systemf/src/systemf/surface/parser/lexer.py
  - systemf/src/systemf/surface/parser/types.py
  - tests/test_surface/test_parser/test_decl_docstrings.py
  - tests/test_surface/test_parser/test_decl_pragma.md
---

# Task 1: Fix Lexer to Emit Docstring and Pragma Tokens

## Objective
Modify the lexer to properly tokenize docstrings (`-- |`) and pragmas (`{-# ... #-}`) instead of filtering them out.

## Current State
- `DOCSTRING_PRECEDING` and `DOCSTRING_INLINE` are filtered in `_create_token()` line 207
- Pragmas are split into separate tokens: `{-#` (PRAGMA_START), content tokens, `#-}` (PRAGMA_END)
- Tests exist but fail because tokens are never emitted

## Requirements

### Docstring Tokenization
1. **Stop filtering docstrings** in `_skip_whitespace()` and `_create_token()`
2. **Create DocstringToken** for `-- | ...` (DOCSTRING_PRECEDING)
3. **Keep content** - extract text after `-- |` (strip leading `|` and whitespace)
4. **Location** - use token start location

### Pragma Tokenization  
1. **Group pragma content** - capture everything between `{-#` and `#-}` as single token
2. **PragmaToken structure**: `pragma_type="PRAGMA"`, `content="KEY value..."`
3. **Parse content**: Extract `KEY` and `content` from `{-# KEY content #-}`
4. **Example**: `{-# LLM model=gpt-4 #-}` → `PragmaToken(pragma_type="PRAGMA", content="LLM model=gpt-4")`

### Implementation Notes
- Modify `_skip_whitespace()` in lexer.py to NOT skip `-- |` comments
- Modify `_create_token()` to create DocstringToken for DOCSTRING_PRECEDING
- Group pragma tokens: read from PRAGMA_START to PRAGMA_END, return single PragmaToken
- Update `PragmaToken` dataclass in types.py if needed

## Expected Result
```python
from systemf.surface.parser import lex

# Docstrings
tokens = list(lex("-- | Test doc\ndata Bool = True"))
# Should include: DocstringToken(docstring_type="DOCSTRING_PRECEDING", content="Test doc")

# Pragmas  
tokens = list(lex("{-# LLM model=gpt-4 #-}\nterm x = 1"))
# Should include: PragmaToken(pragma_type="PRAGMA", content="LLM model=gpt-4")
```

## Verification
Run tests to verify tokens are emitted:
```bash
uv run pytest tests/test_surface/test_parser/test_decl_docstrings.py::TestDataDeclarationDocstrings::test_data_with_preceding_docstring -v
```

## Work Log

### Phase 1: Analysis
**Status:** Not started

Document findings about current lexer behavior and required changes.

### Phase 2: Implementation  
**Status:** Not started

Implement the lexer modifications.

### Phase 3: Verification
**Status:** Not started

Run tests to verify tokens are properly emitted.
