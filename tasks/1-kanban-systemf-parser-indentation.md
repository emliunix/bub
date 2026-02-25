---
type: kanban
title: Systemf Parser Indentation
request: GOAL: change systemf parser to be indentation aware for robust parsing

Implementation Changes Needed:
- Lexer - Track indentation levels, emit INDENT/DEDENT tokens
- Parser - Update all parsers to handle indentation  
- Tests - Rewrite 260+ tests with new syntax
- Documentation - Update all examples
created: 2026-02-25T14:35:13.774270
phase: implementation
current: 3-parser-indentation.md
tasks: ['tasks/0-explore-request.md', 'tasks/2-lexer-indentation.md', 'tasks/3-parser-indentation.md', 'tasks/4-rewrite-tests.md', 'tasks/5-update-documentation.md']
---

# Kanban: Workflow Tracking

## Plan Adjustment Log
<!-- Manager logs plan adjustments here -->

### 2026-02-25 - Initial Planning (Manager)

Analyzed the System F parser indentation refactoring request. Created task breakdown:

**Tasks Created:**
1. **tasks/2-lexer-indentation.md** - Modify lexer to track indentation levels and emit INDENT/DEDENT tokens
2. **tasks/3-parser-indentation.md** - Update parser grammar to use indentation tokens instead of declaration boundary heuristics  
3. **tasks/4-rewrite-tests.md** - Rewrite 260+ tests across 13 test files to use new indented syntax
4. **tasks/5-update-documentation.md** - Update README, demo.py, and REPL help with new syntax examples

**Key Findings:**
- Current lexer is simple regex-based in `systemf/src/systemf/surface/lexer.py`
- Parser uses parsy combinators in `systemf/src/systemf/surface/parser.py`
- 13 test files with ~260 tests need syntax updates
- Declaration boundary heuristics (`is_decl_boundary`) may be removable after indentation support

**Dependency Chain:**
Lexer → Parser → Tests → Documentation

**Next Task:** tasks/2-lexer-indentation.md (ready for Implementor)

### 2026-02-25 - Task 2 Completed (Manager)

**Task:** tasks/2-lexer-indentation.md
**Status:** COMPLETED
**Next Task:** tasks/3-parser-indentation.md

**Summary:**
Design document for indentation-aware lexer completed. The design covers:
- Token type definitions (INDENT, DEDENT, NEWLINE)
- Lexer state extension with indentation tracking
- Indentation tracking algorithm with pseudocode
- Edge case handling (empty lines, comments, mixed tabs/spaces, EOF)
- Backward compatibility strategy
- 10 test contracts defined

**Key Design Decisions:**
- Emit explicit NEWLINE tokens for parser visibility
- Store raw indentation level (spaces) in tokens
- Default tab width of 4, configurable
- Multiple DEDENT tokens for multi-level dedent (Python-style)
- Comments don't affect indentation tracking
- Add `track_indent` parameter for gradual migration

**Ready for:** Parser implementation (Task 3)

### 2026-02-25 - Task 3 Status Check (Manager)

**Task:** tasks/3-parser-indentation.md
**Status:** INCOMPLETE

**Findings:**
- Task file exists but only contains template/requirements
- Work Log section is empty (no design or implementation work recorded)
- No grammar design, token matchers, or rule updates documented
- Success criteria checkboxes are all unchecked

**Issue:** Task 3 has been assigned but no work has been completed. The parser indentation design is missing.

**Action Required:** Task 3 needs to be completed before proceeding to Task 4 (rewrite tests).

