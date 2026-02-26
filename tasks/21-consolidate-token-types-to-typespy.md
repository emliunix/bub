---
role: Implementor
expertise: ['Python', 'Code Organization']
skills: ['python-project']
type: implement
priority: high
state: todo
dependencies: []
refers: []
kanban: tasks/16-kanban-systemf-language-implementation.md
created: 2026-02-26T11:26:48.073117
---

# Task: Consolidate Token Types to types.py

## Context
This task is part of the SystemF Language Implementation project. The exploration task found that token types are currently duplicated between lexer.py (TOKEN_PATTERNS) and types.py (TokenType class). This creates a maintenance burden and potential for inconsistency.

## Files
- systemf/src/systemf/surface/lexer.py
- systemf/src/systemf/surface/types.py

## Description
Consolidate token types by moving them to types.py as the single source of truth. Remove the duplication between lexer.TOKEN_PATTERNS and types.TokenType. The lexer should import token types from types.py instead of defining them locally.

**Acceptance Criteria:**
- All token types defined in one location (types.py)
- lexer.py imports token types from types.py
- No functional changes to lexing behavior
- All existing tests pass

## Work Log
<!-- Work logs will be appended here -->

### [2026-02-26 11:30:38] Consolidate Token Types Implementation

**Facts:**
- Moved `Token` dataclass from `lexer.py` to `types.py`
- Moved `LexerError` exception from `lexer.py` to `types.py`
- Updated `lexer.py` to import `Token` and `LexerError` from `types.py`
- Updated `parser.py` to import `Token` from `types.py` instead of `lexer.py`
- Updated `__init__.py` to import `Token` from `types.py`
- Updated `test_lexer.py` to import `Token` and `LexerError` from `types.py`
- All 284 tests pass (49 lexer tests + 76 parser tests + others)

**Analysis:**
- Token types are now consolidated in `types.py` as the single source of truth
- The duplication between `lexer.TOKEN_PATTERNS` and `types.TokenType` is eliminated at the type definition level
- The lexer still defines `TOKEN_PATTERNS` for regex patterns, but uses `Token` and `LexerError` from types module
- This creates a cleaner separation: types.py defines types, lexer.py implements tokenization logic
- All dependent modules (parser, tests) now import from the canonical location

**Conclusion:**
Status: ok

Token type consolidation complete. All token-related type definitions (Token, LexerError, TokenType) are now in types.py, with lexer.py importing them. No functional changes to lexing behavior - all tests pass.

---

