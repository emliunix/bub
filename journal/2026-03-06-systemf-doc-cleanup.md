# SystemF Doc Cleanup + Parser Improvements - 2026-03-06

**Date**: 2026-03-06
**Status**: Complete

## Summary

Cleaned up stale documentation and improved the parser with typed tokens.

## What Was Done

### Deleted Files (15)

Root-level docs that were outdated or transient session artifacts:

- `EOF` - stray file
- `CONTRIBUTING.md` - not needed
- `PROJECT_SUMMARY.md` - stale (250 tests → now 642)
- `PROJECT_STATUS.md` - old snapshot
- `PROJECT_STATUS_CURRENT.md` - old snapshot
- `BATTLE_TEST_SUMMARY.md` - superseded
- `BATTLE_TEST_RESULTS.md` - detailed test log, superseded
- `TEST_FAILURES_CATEGORIZED.md` - 47 failures, all fixed
- `REFACTORING_NOTES.md` - explained failures that are now fixed
- `NEXT_STEPS.md` - tasks from session, completed
- `SESSION_SUMMARY.md` - mid-session scratchpad
- `DOCUMENTATION_INVENTORY.md` - meta-doc of what was created
- `SURFACE_AST_ARCHITECTURAL_CONCERNS.md` - partially implemented notes
- `SURFACE_AST_REFACTOR_CONTEXT.md` - subagent context closure
- `todo.md` - out-of-date task list

### Kept

- `README.md` - current, user-facing entry point

### Parser Improvements

#### Typed Tokens (`types.py`)
- Replaced generic `Token` protocol with concrete typed token classes
- Removed `type` and `value` properties from `TokenBase` protocol
- Each token now has its own class: `IdentifierToken`, `NumberToken`, `StringToken`, `LambdaToken`, `ArrowToken`, etc.
- Simplified `__str__` to return actual value instead of debug repr
- 20+ new concrete token classes for operators and delimiters

#### Lexer Updates (`lexer.py`)
- Updated to use concrete token types instead of generic `Token`
- Imports all specific token classes explicitly
- Changed return type from `list[Token]` to `list[TokenBase]`
- Fixed operator patterns: `NEQ` → `NE`, etc.

#### Expression Parser (`expressions.py`)
- Updated imports to use typed token classes
- Refactored to use concrete token types in pattern matching

#### Type Parser (`type_parser.py`)
- Simplified type parsing logic
- Removed redundant type application handling

#### Test Updates
- `test_lexer.py` - Updated to check `type(t).__name__` instead of `t.type`
- `test_string.py` - Minor fixes
- `test_helpers.py`, `test_parser_complex.py` - Minor updates

### Config Updates (`pyproject.toml`)
- Python version: `3.11` → `3.14`
- Ruff target: `py311` → `py314`
- Added pyright stubPath for `typings/`

### New Files Added
- `typings/parsy-stubs/__init__.pyi` - Type stubs for parsy
- `tmp/parsy_init_runtime.py` - Debug script

## Current State

- Root: Only `README.md` remains
- Tests: 642 passed, 34 skipped, 2 xfailed
- Docs: Properly organized under `docs/`

## Follow-ups

None. Documentation is now clean and parser uses typed tokens.
