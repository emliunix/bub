---
assignee: Implementor
expertise: ['Code Quality', 'Refactoring']
skills: []
type: implement
priority: medium
state: done
dependencies: []
refers: []
kanban: tasks/16-kanban-systemf-language-implementation.md
created: 2026-02-26T12:43:02.818156
---

# Task: Remove create_token backward compatibility

## Context
Task 29 (typed lexer tokens) added a `create_token()` factory function and `_GenericToken` class for backward compatibility. This is not allowed - any affected code must be changed directly to use the new typed token classes.

## Files
- `systemf/src/systemf/surface/types.py` - Remove create_token() and _GenericToken
- Any files using create_token() - Update to use specific token constructors

## Description
Remove the backward compatibility layer from Task 29:

1. Remove `create_token()` factory function (lines 397-478)
2. Remove `_GenericToken` fallback class (lines 481-505)
3. Find all code using `create_token()` and update to use specific token classes:
   - `IdentifierToken(name=value, location=location)`
   - `ConstructorToken(name=value, location=location)`
   - `NumberToken(number=value, location=location)`
   - `KeywordToken(keyword=value, location=location)`
   - `OperatorToken(operator=value, location=location, op_type=TokenType.XXX)`
   - `DelimiterToken(delimiter=value, location=location, delim_type=TokenType.XXX)`
   - `IndentationToken(indent_type=TokenType.INDENT/DEDENT, level=value, location=location)`
   - `PragmaToken(pragma_type=TokenType.XXX, content=value, location=location)`
   - `DocstringToken(docstring_type=TokenType.XXX, content=value, location=location)`
   - `EOFToken(location=location)`

4. Ensure all tests pass

## Work Log
<!-- Work logs will be appended here -->

### [2026-02-26 12:44:34] Starting implementation

**Facts:**
Reading task specification and identifying affected files

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-02-26 12:46:43] Implementation Complete

**Facts:**
Successfully removed create_token() factory function and _GenericToken fallback class. Updated lexer.py to use specific token constructors directly. All 336 systemf tests and 53 lexer tests pass. Modified files: systemf/src/systemf/surface/types.py (removed 108 lines), systemf/src/systemf/surface/lexer.py (updated imports and replaced create_token() calls with direct constructors, added _create_typed_token helper method)

**Analysis:**
-

**Conclusion:**
Status: ok

---

