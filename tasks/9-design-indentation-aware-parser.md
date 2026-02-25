---
role: Architect
expertise: ['Parser Design', 'Python', 'Formal Languages']
skills: []
type: design
priority: critical
dependencies: []
refers: []
kanban: tasks/7-kanban-systemf-parser-indentation-aware-refactoring.md
created: 2026-02-25T15:00:03.704271
---

# Task: Design Indentation-Aware Parser

## Context
<!-- Background information and relevant context -->

## Files
- systemf/src/systemf/surface/parser.py
- systemf/src/systemf/surface/ast.py
- systemf/tests/test_surface/test_parser.py

## Description
Design updates to the parsy-based parser to handle INDENT/DEDENT tokens. Define how the parser should use indentation tokens for block structures (let, case, data declarations). Include grammar changes and specify which parsers need to be updated for indentation awareness.

## Work Log

### 2026-02-25: Design Indentation-Aware Parser

**Architect Analysis:**

Examined current parser implementation in `systemf/src/systemf/surface/parser.py`:
- 710 lines, parsy-based with @generate decorator
- Current parsing style: linear token consumption, ignores whitespace entirely
- Key parsers: term_parser, type_parser, declaration_parser with mutual recursion
- Block structures use delimiters: `let...in`, `case...of{...}`, `data...=...|...`
- 260+ tests in test_parser.py covering all constructs

**Design Decisions:**

1. **New Token Matchers to Add:**
   - `INDENT = match_token("INDENT")` - matches indentation increase
   - `DEDENT = match_token("DEDENT")` - matches indentation decrease
   - Used to demarcate block boundaries instead of explicit keywords/braces

2. **Grammar Changes:**

   **Before (Brace/Keyword Delimited):**
   ```
   let_expr ::= LET IDENT EQ expr IN expr
   case_expr ::= CASE expr OF LBRACE branches RBRACE
   data_decl ::= DATA CON params EQ constrs
   branches ::= branch (BAR branch)*
   constrs ::= constr (BAR constr)*
   ```

   **After (Indentation-Based):**
   ```
   let_expr ::= LET IDENT EQ expr INDENT let_body DEDENT
   let_body ::= expr
   
   case_expr ::= CASE expr OF INDENT branches DEDENT
   branches ::= branch (branch)*
   branch ::= pattern ARROW expr
   
   data_decl ::= DATA CON params EQ INDENT constrs DEDENT
   constrs ::= constr (constr)*
   ```

3. **Parser Updates Required:**

   a. **let_parser**: Remove IN keyword, use INDENT/DEDENT for body
      - Parse: `let x = value` followed by INDENT, body, DEDENT
      - No longer needs `in` keyword - indentation defines scope
   
   b. **case_parser**: Replace `{ }` with INDENT/DEDENT for branches
      - Parse: `case expr of` followed by INDENT, branches, DEDENT
      - Remove BAR separator - each branch on its own indented line
   
   c. **data_declaration**: Replace `|` separator with INDENT/DEDENT
      - Parse: `data Name params =` followed by INDENT, constructors, DEDENT
      - Each constructor on its own indented line
   
   d. **lambda_parser**: Support multi-line bodies via indentation
      - Parse: `\x ->` followed by optional INDENT, body, DEDENT
      - Single-line lambdas work without INDENT/DEDENT

4. **Indentation-Aware Combinators:**

   Create helper combinators for common indentation patterns:

   ```python
   @generate
   def indented_block(content_parser):
       """Parse INDENT content DEDENT sequence."""
       yield INDENT
       content = yield content_parser
       yield DEDENT
       return content
   
   @generate  
   def indented_many(item_parser):
       """Parse one or more indented items (no separator)."""
       yield INDENT
       items = []
       first = yield item_parser
       items.append(first)
       rest = yield item_parser.many()  # Same indentation level
       items.extend(rest)
       yield DEDENT
       return items
   ```

5. **Block Structure Changes:**

   **Let Bindings:**
   - Old: `let x = 1 in x`
   - New: 
     ```
     let x = 1
       x
     ```
   - Or with explicit braces: `let x = 1 { x }` (optional backward compat)

   **Case Expressions:**
   - Old: `case x of { True -> y | False -> z }`
   - New:
     ```
     case x of
       True -> y
       False -> z
     ```

   **Data Declarations:**
   - Old: `data Bool = True | False`
   - New:
     ```
     data Bool =
       True
       False
     ```

6. **Error Handling:**

   Add specific error messages for indentation issues:
   - "Expected indented block after 'let' binding"
   - "Indentation mismatch: expected dedent"
   - "Mixed tabs and spaces in indentation"
   - "Inconsistent indentation level"

   Error recovery strategy:
   - On DEDENT mismatch, report error at DEDENT location
   - Suggest expected indentation level
   - Allow parser to continue for error reporting

7. **Backward Compatibility:**
   
   Options for migration:
   - Option A: Flag day - update all syntax at once (chosen)
   - Option B: Support both styles temporarily (adds complexity)
   
   Decision: **Option A** - Clean break with new indentation syntax
   - Update all 260+ tests
   - Update all documentation
   - Clear error messages guide migration

8. **Interface Changes:**

   Parser class remains same:
   - `Parser(tokens)` constructor unchanged
   - `parse()`, `parse_term()`, `parse_type()` methods unchanged
   - Error handling via ParseError unchanged
   
   Only internal grammar rules change to consume INDENT/DEDENT tokens.

**Files Modified/Created:**
- Modified: `systemf/src/systemf/surface/parser.py` - Update grammar rules
- Documented: Test contracts in work log below

**Test Contracts (What Tests Must Verify):**

```
Let Expression Indentation:
- let x = value followed by INDENT body DEDENT parses correctly
- Multi-line let body with nested indentation works
- Error if missing INDENT after let binding
- Error if missing DEDENT to close let body
- Let inside let with proper nesting

Case Expression Indentation:
- case expr of followed by INDENT branches DEDENT parses correctly
- Multiple branches without BAR separator
- Each branch properly indented at same level
- Error if branch indentation inconsistent
- Nested case expressions maintain proper indentation levels

Data Declaration Indentation:
- data Name = followed by INDENT constructors DEDENT parses correctly
- Multiple constructors on separate lines
- Constructor arguments can span multiple lines with indentation
- Error if constructor indentation inconsistent

Lambda Indentation:
- Single-line lambda: \x -> expr (no INDENT/DEDENT)
- Multi-line lambda: \x -> INDENT expr DEDENT
- Nested lambdas with proper indentation stacking

Nested Block Handling:
- let inside case with correct indentation levels
- case inside let with proper nesting
- data declarations with complex constructor types
- Deeply nested structures (5+ levels)

Error Messages:
- Clear message when INDENT expected but not found
- Clear message when DEDENT expected but not found  
- Message includes line/column of indentation issue
- Message suggests correct indentation level

Edge Cases:
- Empty indented block (let x = 1 in {} style)
- Single item in indented block
- Multiple dedents at once (exiting multiple blocks)
- Mixed indentation in same file (different sections)
```

**Implementation Strategy:**

Phase 1: Add token matchers and combinators
- Add INDENT, DEDENT matchers
- Create indented_block, indented_many helpers

Phase 2: Update grammar rules one at a time
1. Update let_parser (simplest - binary structure)
2. Update case_parser (list structure)
3. Update data_declaration (list structure)
4. Update lambda_parser (optional indentation)

Phase 3: Error handling
- Add indentation-specific error messages
- Improve error locations

Phase 4: Testing
- Update existing tests to new syntax
- Add new indentation-specific tests
- Verify error messages

**Risks and Mitigations:**

- Risk: Breaking all existing code and tests
  - Mitigation: Systematic test updates with clear migration guide
  
- Risk: Parser becomes harder to debug
  - Mitigation: Good error messages, clear indentation visualization
  
- Risk: Users confused by indentation errors
  - Mitigation: Error messages show expected vs actual indentation
  
- Risk: Performance overhead of tracking indentation in parser
  - Mitigation: Minimal overhead - just token consumption changes

**Follow-up Tasks:**
- Task 11: Update parser implementation
- Task 12: Rewrite all parser tests with new indentation syntax
- Task 13: Update integration tests
- Task 14: Update documentation with new syntax examples
