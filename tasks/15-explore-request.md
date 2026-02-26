---
role: Architect
expertise: ['System Design', 'Domain Analysis', 'Code Exploration']
skills: ['code-reading']
type: exploration
priority: high
state: done
dependencies: []
refers: [16-kanban-systemf-language-implementation.md]
kanban: tasks/16-kanban-systemf-language-implementation.md
created: 2026-02-26T11:20:08.959719
---

# Task: Explore Request

## Context
<!-- Background information and relevant context -->

## Files
<!-- List of files to modify or reference -->

## Description
Explore and analyze: Implement SystemF DSL compiler with the following tasks:

## Lexer & Parser Tasks
1. Remove skip_indent entirely from surface.lexer.py - migrate compatibility to new approach
2. Fix data_declaration in surface.parser.py - keep old syntax with = and | for structural clarity (e.g., data Nat = Zero | Succ Nat)
3. Support both pattern matching syntaxes: indented style and explicit { | } style
4. Make docstrings (-- |, -- ^) first-class and attach to AST nodes for interpreter visibility

## LLM FFI Tasks  
5. Implement {-# LLM key=value #-} pragma syntax for LLM declarations (Haskell-style)
6. Add tool calls as systemf functions in the language

## Feature Set Tasks
7. Expand DSL features: variables, functions, tape context management, parallel execution, runtime REPL for LLM, set_output() support, maybe type for optionals, module system

## Code Organization Tasks
8. Make lexer tokens typed objects instead of generic token type
9. Consolidate token types: move shared token types to types.py (currently duplicated between lexer and types)

## Style Tasks
10. Refactor code to avoid isinstance, use match pattern matching instead

Key Design Decisions:
- Indentation serves as block boundary; braces/bars convey structural info inside blocks
- All data serializable, no low-level operations exposed (DSL focused on domain modeling)
- Docstrings auto-synthesize system prompts for LLM FFI

## Work Log
<!-- Work logs will be appended here -->

### [2026-02-26 11:24:48] Initial Exploration Complete

**Facts:**
Explored SystemF codebase. Found: 1) Lexer has skip_indent param to remove, 2) Token types duplicated between files, 3) Parser needs dual syntax support for pattern matching, 4) No pragma syntax for LLM FFI, 5) No docstring attachment to AST. Architecture is solid with Surface→Core→Checker→Eval pipeline. All 10 tasks are clear with well-defined dependencies.

**Analysis:**

**Architecture Overview:**
- SystemF follows a clean 4-phase pipeline: Surface Language → Core Language → Type Checker → Evaluator
- Surface language uses name-based binding with indentation-aware syntax (newly implemented)
- Core language uses de Bruijn indices for efficient substitution
- Bidirectional type checking with higher-rank polymorphism
- Call-by-value interpreter with environment-based closures
- 250 tests passing (1 known parser limitation with adjacent declarations)

**Key Findings by Task:**

1. **Lexer skip_indent removal (Task 1):** The lexer.py has a `skip_indent: bool = True` parameter for backward compatibility. The parser already sets `skip_indent=False`, so this can be safely removed after checking no other code depends on it.

2. **Data declaration syntax (Task 2):** Current parser supports indentation-based constructors but removed the `=` and `|` operators. Need to restore: `data Nat = Zero | Succ Nat` syntax while keeping indentation support.

3. **Dual pattern matching syntax (Task 3):** Parser currently only supports indented style. Need to add explicit `{ | }` style as alternative: `case b of { True -> False | False -> True }`.

4. **Docstrings as first-class AST nodes (Task 4):** Comments are currently stripped by lexer. Need to capture `-- |` and `-- ^` style comments and attach them to AST nodes for interpreter visibility.

5. **LLM pragma syntax (Task 5):** No pragma syntax exists. Need to implement Haskell-style `{-# LLM key=value #-}` pragmas before declarations.

6. **Tool calls as functions (Task 6):** This builds on #5 - pragmas declare LLM functions that can be called like regular functions in the language.

7. **DSL features (Task 7):** Major feature expansion - variables/functions exist, but need: tape context management, parallel execution, runtime REPL, set_output(), Maybe type, module system.

8. **Typed lexer tokens (Task 8):** Tokens are currently generic `Token(type, value, location)`. Need specific token classes for better type safety.

9. **Consolidate token types (Task 9):** Token types defined in both lexer.py (TOKEN_PATTERNS) and types.py (TokenType class). Need single source of truth.

10. **Refactor isinstance to match (Task 10):** Code uses isinstance checks throughout (e.g., parser.py app_type). Python 3.12+ supports pattern matching which would be cleaner.

**Dependency Graph:**
```
Task 9 (consolidate types) → Task 8 (typed tokens) → Task 1 (remove skip_indent)
Task 2 (data syntax) → Task 3 (pattern matching) → Task 4 (docstrings)
Task 4 → Task 5 (LLM pragma) → Task 6 (tool calls)
Task 5 → Task 7 (DSL features - some depend on LLM)
```

**Recommended Task Sequencing:**
1. Tasks 9, 10 - Code organization/style (foundational)
2. Tasks 1, 2, 3 - Lexer/parser improvements (core syntax)
3. Tasks 4, 5, 6 - Docstrings and LLM FFI (advanced features)
4. Task 7 - DSL expansion (largest scope, depends on others)
5. Task 8 - Can be done in parallel with any group

**Conclusion:**
Status: ok

## Suggested Work Items (for Manager)

The following work items should be created as task files:

```yaml
work_items:
  - description: Consolidate token types - move to types.py as single source of truth
    files: [systemf/src/systemf/surface/lexer.py, systemf/src/systemf/surface/types.py]
    related_domains: ["Software Engineering", "Refactoring"]
    expertise_required: ["Python", "Code Organization"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Remove duplication between lexer.TOKEN_PATTERNS and types.TokenType
    
  - description: Refactor isinstance checks to use match pattern matching
    files: [systemf/src/systemf/surface/*.py, systemf/src/systemf/core/*.py, systemf/src/systemf/eval/*.py]
    related_domains: ["Software Engineering", "Code Quality"]
    expertise_required: ["Python 3.12+", "Pattern Matching"]
    dependencies: []
    priority: medium
    estimated_effort: medium
    notes: Focus on parser.py app_type, arrow_type first
    
  - description: Remove skip_indent parameter from lexer
    files: [systemf/src/systemf/surface/lexer.py]
    related_domains: ["Software Engineering", "API Design"]
    expertise_required: ["Python"]
    dependencies: [0]
    priority: high
    estimated_effort: small
    notes: Check all usages first - parser already uses skip_indent=False
    
  - description: Restore = and | syntax in data declarations
    files: [systemf/src/systemf/surface/parser.py]
    related_domains: ["Programming Languages", "Parser Design"]
    expertise_required: ["Parsing", "Parser Combinators"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Support both: indented style AND `data Nat = Zero | Succ Nat` style
    
  - description: Support dual pattern matching syntax (indented and explicit { | })
    files: [systemf/src/systemf/surface/parser.py]
    related_domains: ["Programming Languages", "Parser Design"]
    expertise_required: ["Parsing", "Parser Combinators"]
    dependencies: [3]
    priority: high
    estimated_effort: medium
    notes: `case b of { True -> False | False -> True }` alternative syntax
    
  - description: Make docstrings (-- |, -- ^) first-class AST nodes
    files: [systemf/src/systemf/surface/lexer.py, systemf/src/systemf/surface/ast.py, systemf/src/systemf/surface/parser.py]
    related_domains: ["Programming Languages", "Documentation"]
    expertise_required: ["Parsing", "AST Design"]
    dependencies: [4]
    priority: high
    estimated_effort: medium
    notes: Attach docstrings to declarations, visible to interpreter
    
  - description: Implement {-# LLM key=value #-} pragma syntax
    files: [systemf/src/systemf/surface/lexer.py, systemf/src/systemf/surface/parser.py, systemf/src/systemf/surface/ast.py]
    related_domains: ["Programming Languages", "LLM Integration"]
    expertise_required: ["Parsing", "Language Design"]
    dependencies: [5]
    priority: high
    estimated_effort: medium
    notes: Haskell-style pragmas for LLM configuration
    
  - description: Add tool calls as systemf functions
    files: [systemf/src/systemf/eval/*.py]
    related_domains: ["Programming Languages", "LLM Integration"]
    expertise_required: ["Interpreter Design", "LLM Tools"]
    dependencies: [6]
    priority: medium
    estimated_effort: medium
    notes: Enable LLM tool calls to appear as regular functions in context
    
  - description: Make lexer tokens typed objects
    files: [systemf/src/systemf/surface/lexer.py, systemf/src/systemf/surface/types.py]
    related_domains: ["Software Engineering", "Type Systems"]
    expertise_required: ["Python", "Type Design"]
    dependencies: [0]
    priority: medium
    estimated_effort: medium
    notes: Replace generic Token with specific token classes
    
  - description: Expand DSL features (tape, parallel, REPL, Maybe, modules)
    files: [systemf/src/systemf/surface/*.py, systemf/src/systemf/core/*.py, systemf/src/systemf/eval/*.py]
    related_domains: ["Programming Languages", "DSL Design", "Concurrency"]
    expertise_required: ["Language Design", "Type Systems", "Interpreter Design"]
    dependencies: [6, 7]
    priority: medium
    estimated_effort: large
    notes: Largest task - break down further when ready. Includes: tape context, parallel exec, REPL, set_output(), Maybe type, module system
```

---

