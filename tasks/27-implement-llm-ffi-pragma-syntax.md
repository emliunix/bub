---
role: Implementor
expertise: ['Python', 'Parser Design', 'AST Design']
skills: ['python-project', 'testing']
type: implement
priority: high
state: done
dependencies: []
refers: []
kanban: tasks/16-kanban-systemf-language-implementation.md
created: 2026-02-26T12:11:46.225089
---

# Task: Implement LLM FFI Pragma Syntax

## Context
Following the completion of Task 26 (first-class docstrings), all lexer/parser improvements are complete. Now proceeding with Task 5 from original requirements: implementing LLM FFI pragma syntax.

The pragma syntax should follow Haskell-style pragmas: `{-# LLM key=value #-}`

This will be used to declare LLM configurations and FFI bindings within the SystemF language, enabling the DSL to specify LLM interactions declaratively.

## Files
- `src/surface/lexer.py` - Add pragma token types and lexer rules
- `src/surface/ast.py` - Add pragma AST node types
- `src/surface/parser.py` - Add pragma parsing logic
- `src/surface/elaborator.py` - Handle pragma elaboration
- `tests/test_lexer.py` - Add pragma lexer tests
- `tests/test_parser.py` - Add pragma parser tests

## Description
Implement Haskell-style pragma syntax `{-# LLM key=value #-}` for LLM FFI declarations:

1. **Lexer changes:**
   - Add PRAGMA_START and PRAGMA_END token types for `{-#` and `#-}`
   - Add LLM keyword token
   - Handle pragma content parsing (key=value pairs)

2. **AST changes:**
   - Create `SurfacePragma` dataclass to represent pragma nodes
   - Add pragma field to appropriate AST nodes (module, declarations)
   - Support key-value storage for pragma attributes

3. **Parser changes:**
   - Add pragma parsing rule for `{-# LLM ... #-}` pattern
   - Attach pragmas to following declarations or module
   - Handle multiple key=value pairs within single pragma

4. **Tests:**
   - Test basic pragma lexing: `{-# LLM model=gpt-4 #-}`
   - Test multi-attribute pragmas: `{-# LLM model=gpt-4 temperature=0.7 #-}`
   - Test pragma attachment to declarations
   - Test error handling for malformed pragmas

The pragma syntax enables declarative LLM FFI configuration directly in SystemF source files.

## Work Log
<!-- Work logs will be appended here -->

### [2026-02-26 12:19:33] Implementation Complete

**Facts:**
<!-- What was actually done (files modified, code written, tests run, etc.) -->
- Modified `systemf/src/systemf/surface/lexer.py`:
  - Added PRAGMA_START (`{-#`) and PRAGMA_END (`#-}`) token patterns
  - Added LLM keyword token pattern
  - Implemented `_parse_pragma_content()` method to parse pragma content until closing
  - Modified `tokenize()` to handle pragma tokens specially
  
- Modified `systemf/src/systemf/surface/ast.py`:
  - Created `SurfacePragma` dataclass with directive, attributes dict, and location
  - Added `pragma: SurfacePragma | None` field to `SurfaceDataDeclaration`
  - Added `pragma: SurfacePragma | None` field to `SurfaceTermDeclaration`
  
- Modified `systemf/src/systemf/surface/parser.py`:
  - Imported `SurfacePragma` from ast module
  - Added PRAGMA_START, PRAGMA_END, PRAGMA_CONTENT, LLM token matchers
  - Created `parse_pragma_attributes()` helper to parse key=value pairs from pragma content
  - Created `pragma_parser()` to parse full pragma syntax
  - Modified `declaration_parser()` to capture optional pragma before declarations
  - Renamed `data_declaration_with_docstring_parser` to `data_declaration_with_docstring_and_pragma_parser`
  - Renamed `term_declaration_with_docstring_parser` to `term_declaration_with_docstring_and_pragma_parser`
  - Updated declaration parsers to pass pragma parameter through to AST nodes
  
- Modified `systemf/tests/test_surface/test_lexer.py`:
  - Added `TestPragmaTokens` test class with 6 new tests
  
- Modified `systemf/tests/test_surface/test_parser.py`:
  - Added `TestPragmaParsing` test class with 7 new tests
  
- All 311 tests pass (149 existing + 13 new = 162 lexer+parser tests, plus other module tests)

**Analysis:**
<!-- What problems were encountered, what approaches were tried, key decisions made -->
- **Challenge**: Pragma syntax `{-# ... #-}` could conflict with existing comment patterns
  - **Solution**: Added pragma patterns before comment patterns in TOKEN_PATTERNS list to ensure they're matched first
  
- **Challenge**: Multi-line pragmas needed special handling in lexer
  - **Solution**: Implemented `_parse_pragma_content()` method that collects all content until `#-}` is found, handling newlines and preserving the raw content for parser processing
  
- **Challenge**: Parsing key=value pairs with optional commas and quoted values
  - **Solution**: Created `parse_pragma_attributes()` helper that handles comma-separated key=value pairs and strips quotes from string values
  
- **Challenge**: Pragma attachment to declarations required modifying existing parser infrastructure
  - **Solution**: Modified declaration_parser to optionally capture pragmas before docstrings, then pass pragma through to specialized declaration parsers. This maintains backward compatibility with existing code.
  
- **Design Decision**: Pragmas are stored as a dict[str, str] in SurfacePragma, allowing flexible key-value pairs for LLM configuration
  - This supports arbitrary attributes like model, temperature, max_tokens, tag, json, etc.
  
- **Design Decision**: Pragmas appear before declarations (like in Haskell), allowing the pragma to apply to the following declaration

**Conclusion:**
<!-- Pass/fail/escalate status and why, next steps, blockers if any -->
Status: ok

The LLM FFI pragma syntax has been successfully implemented according to the task specification. The implementation:
- Parses Haskell-style pragmas `{-# LLM key=value ... #-}`
- Supports multiple key-value pairs separated by commas
- Handles quoted string values
- Works with both term and data declarations
- Can coexist with docstrings
- All 311 tests pass (existing + new)

**Example usage:**
```systemf
{-# LLM model="gpt-4" #-}
research_topic : String -> String = \x -> x

{-# LLM model="claude-3-opus", tag="code_review", temperature=0.7 #-}
review_code : String -> String = \x -> x
```

**Files Modified:**
- `systemf/src/systemf/surface/lexer.py`
- `systemf/src/systemf/surface/ast.py`
- `systemf/src/systemf/surface/parser.py`
- `systemf/tests/test_surface/test_lexer.py`
- `systemf/tests/test_surface/test_parser.py`

**No blockers or follow-up tasks required.**

---

