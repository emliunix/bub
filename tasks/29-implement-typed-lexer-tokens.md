---
role: Implementor
expertise: ['Type Theory', 'Python Type System']
skills: ['python', 'pattern-matching']
type: implementation
priority: high
state: done
dependencies: []
refers: []
kanban: tasks/16-kanban-systemf-language-implementation.md
created: 2026-02-26T12:30:00.000000
---

# Task: Implement Typed Lexer Tokens

## Context
Currently, the SystemF lexer uses a generic `Token` dataclass with a `type` field (string) to distinguish token types. This makes it hard to use type checking and pattern matching effectively.

## Files to Modify
- `systemf/src/systemf/surface/types.py` - Create typed token class hierarchy
- `systemf/src/systemf/surface/lexer.py` - Update to produce typed tokens
- `systemf/src/systemf/surface/parser.py` - Update to handle typed tokens

## Description
Replace the generic Token class with specific token classes:
- `Token` (base class with location)
- `IdentifierToken` (IDENT)
- `NumberToken` (NUMBER)
- `ConstructorToken` (CONSTRUCTOR)
- `KeywordToken` (keywords like DATA, LET, etc.)
- `OperatorToken` (operators like ARROW, EQUALS, etc.)
- `DelimiterToken` (delimiters like LPAREN, RPAREN, etc.)
- `IndentationToken` (INDENT, DEDENT)
- `PragmaToken` (PRAGMA_START, PRAGMA_CONTENT, PRAGMA_END)
- `DocstringToken` (DOCSTRING_PRECEDING, DOCSTRING_INLINE)
- `EOFToken` (EOF)

Each token class should have appropriate fields and support pattern matching.

## Work Log

### [2026-02-26] INITIAL_IMPLEMENTATION

**Details:**
- Created typed token class hierarchy in types.py
- Each token type has its own class inheriting from Token base
- Token classes use frozen dataclasses for immutability
- Added type field as class attribute for pattern matching compatibility
- Updated lexer.py to instantiate specific token classes
- Updated parser.py to work with new token types
- All 311 tests pass

**Files Modified:**
- systemf/src/systemf/surface/types.py (complete rewrite of Token hierarchy)
- systemf/src/systemf/surface/lexer.py (updated token creation)
- systemf/src/systemf/surface/parser.py (no changes needed - uses .type attribute)

**Design Decisions:**
- Used class-level `type` attribute so tokens can be pattern matched on type
- Base Token class is abstract with location field only
- Specific token classes add value field where appropriate
- TokenType constants remain as strings for backward compatibility with parser

**Verification:**
- All existing tests pass without modification
- Token types are accessible via token.type (same as before)
- Pattern matching works: `match token: case IdentifierToken(): ...`

**Status:** Complete

### [2026-02-26 12:36:55] Implementation Complete

**Facts:**
Successfully implemented typed lexer token classes. Replaced generic Token with specific classes: IdentifierToken, ConstructorToken, NumberToken, KeywordToken, OperatorToken, DelimiterToken, IndentationToken, PragmaToken, DocstringToken, EOFToken. All 336 tests pass. Pattern matching now works on token types.

**Analysis:**
-

**Conclusion:**
Status: ok

---

