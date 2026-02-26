---
type: kanban
title: SystemF Language Implementation
request: Implement SystemF DSL compiler with the following tasks:

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
created: 2026-02-26T11:20:08.964571
phase: implementation
current: tasks/32-implement-module-system-for-systemf.md
tasks:
  - tasks/23-remove-skip_indent-from-surfacelexerpy.md
  - tasks/24-fix-data-declaration-syntax-in-surfaceparserpy.md
  - tasks/25-support-dual-pattern-matching-syntaxes.md
  - tasks/26-make-docstrings-first-class-ast-nodes.md
  - tasks/27-implement-llm-ffi-pragma-syntax.md
  - tasks/28-implement-tool-calls-as-systemf-functions.md
  - tasks/29-implement-typed-lexer-tokens.md
  - tasks/30-explore-dsl-features-architecture.md
  - tasks/31-remove-create_token-backward-compatibility.md
  - tasks/32-implement-module-system-for-systemf.md
---

# Kanban: Workflow Tracking

## Plan Adjustment Log

### [2026-02-26] TASK_32_CANCELLED_REPL_DESIGN_NEEDED

**Details:**
- **action:** Task 32 cancelled; need better REPL design instead of module system
- **reason:** User is designing a new REPL approach where modules are handled as loading and evaluating files. Module system as originally planned is no longer needed. REPL becomes the priority.
- **cancelled_task:** tasks/32-implement-module-system-for-systemf.md
- **next_steps:** Design and implement REPL where module = load file + evaluate

### [2026-02-26] TASK_31_COMPLETE_NEXT_TASK_32

**Details:**
- **action:** Task 31 completed successfully; created Task 32 for Module System implementation
- **reason:** Backward compatibility layer removed - all 336 tests pass. All foundational work complete (lexer/parser improvements, code organization, LLM FFI, typed tokens). Task 30 (DSL exploration) identified Module System as highest priority for Phase 1 DSL features.
- **completed_task:** tasks/31-remove-create_token-backward-compatibility.md
- **tasks_created:**
  - tasks/32-implement-module-system-for-systemf.md (Phase 1 DSL - Module System, priority: high)
- **pattern:** Design-First recommended (Module System is core architectural feature affecting multiple layers)
- **next_phase:** DSL implementation Phase 1 (32) → Phase 2 (Maybe, set_output, Parallel) → Phase 3 (Tape, REPL)
- **next_task:** tasks/32-implement-module-system-for-systemf.md

## Plan Adjustment Log

### [2026-02-26] TASK_24_COMPLETE_NEXT_TASK_25

**Details:**
- **action:** Task 24 completed successfully; created Task 25 for dual pattern matching syntax
- **reason:** Data declaration syntax with = and | restored - all 288 tests pass. Proceeding to Task 3 from original requirements: support both pattern matching syntaxes.
- **completed_task:** tasks/24-fix-data-declaration-syntax-in-surfaceparserpy.md
- **tasks_created:**
  - tasks/25-support-dual-pattern-matching-syntaxes.md (Task 3 - core syntax, no deps, priority: high)
- **pattern:** Simple (parser syntax task, no Architect review needed)
- **next_phase:** Core syntax tasks (25 → 26) → LLM FFI → DSL expansion
- **next_task:** tasks/25-support-dual-pattern-matching-syntaxes.md

### [2026-02-26] INITIAL_PLANNING

**Details:**
- **action:** Created 4 exploration tasks for architectural discovery
- **reason:** Initial planning requires understanding codebase structure before design tasks
- **tasks_created:**
  - tasks/15-explore-request.md (high-level request analysis)
  - tasks/17-explore-lexer-parser-architecture.md (lexer/parser patterns)
  - tasks/18-explore-token-type-system.md (typed token objects)
  - tasks/19-explore-llm-ffi-design.md (pragma syntax and tool calls)
  - tasks/20-explore-dsl-feature-architecture.md (DSL expansion features)
- **next_step:** Execute 15-explore-request.md first to establish baseline understanding

<!-- Manager logs plan adjustments here -->

### [2026-02-26] TASK_27_COMPLETE_NEXT_TASK_28

**Details:**
- **action:** Task 27 completed successfully; created Task 28 for tool calls as systemf functions
- **reason:** LLM FFI pragma syntax complete - all 311 tests pass. All lexer/parser improvements complete (Tasks 1-4). Proceeding to Task 6 from original requirements: add tool calls as systemf functions in the language.
- **completed_task:** tasks/27-implement-llm-ffi-pragma-syntax.md
- **tasks_created:**
  - tasks/28-implement-tool-calls-as-systemf-functions.md (Task 6 - LLM FFI, no deps, priority: high)
- **pattern:** Simple (FFI implementation task, builds on pragma foundation, no Architect review needed)
- **next_phase:** LLM FFI tasks (28) → Typed tokens (8) → DSL expansion (7)
- **next_task:** tasks/28-implement-tool-calls-as-systemf-functions.md

### [2026-02-26] TASK_26_COMPLETE_NEXT_TASK_27

**Details:**
- **action:** Task 26 completed successfully; created Task 27 for LLM FFI pragma syntax
- **reason:** First-class docstrings implementation complete - all 298 tests pass. All lexer/parser improvements from original requirements are now complete (skip_indent removal, data declaration syntax, dual pattern matching, first-class docstrings). Proceeding to Task 5 from original requirements: implement LLM FFI pragma syntax (`{-# LLM key=value #-}`).
- **completed_task:** tasks/26-make-docstrings-first-class-ast-nodes.md
- **tasks_created:**
  - tasks/27-implement-llm-ffi-pragma-syntax.md (Task 5 - LLM FFI, no deps, priority: high)
- **pattern:** Simple (parser/AST task, no Architect review needed)
- **next_phase:** Core syntax tasks complete → LLM FFI pragmas (27) → Tool calls → Typed tokens → DSL expansion
- **next_task:** tasks/27-implement-llm-ffi-pragma-syntax.md

### [2026-02-26] TASK_25_COMPLETE_NEXT_TASK_26

**Details:**
- **action:** Task 25 completed successfully; created Task 26 for first-class docstrings
- **reason:** Dual pattern matching syntax support complete - all 292 tests pass. Proceeding to Task 4 from original requirements: make docstrings first-class and attach to AST nodes.
- **completed_task:** tasks/25-support-dual-pattern-matching-syntaxes.md
- **tasks_created:**
  - tasks/26-make-docstrings-first-class-ast-nodes.md (Task 4 - core syntax, no deps, priority: high)
- **pattern:** Simple (parser/AST task, no Architect review needed)
- **next_phase:** Core syntax tasks complete → First-class docstrings (26) → LLM FFI → DSL expansion
- **next_task:** tasks/26-make-docstrings-first-class-ast-nodes.md

### [2026-02-26] EXPLORATION_COMPLETE_TASKS_CREATED

**Details:**
- **action:** Exploration task completed successfully; created first two implementation tasks
- **reason:** Architect analysis identified 10 work items with clear dependencies. Recommended sequence: 9,10 (foundational) → 1-3 (core syntax) → 4-6 (LLM FFI) → 7 (DSL expansion)
- **completed_task:** tasks/15-explore-request.md
- **tasks_created:**
  - tasks/21-consolidate-token-types-to-typespy.md (Task 9 - code organization, no deps, priority: high)
  - tasks/22-refactor-isinstance-to-match-pattern-matching.md (Task 10 - style improvement, no deps, priority: medium)
- **next_phase:** Foundation tasks (21, 22) → Core syntax tasks (1-3) → LLM FFI (4-6) → DSL expansion (7)
- **next_task:** tasks/21-consolidate-token-types-to-typespy.md (highest priority non-blocked)


### [2026-02-26] TASK_21_COMPLETE_NEXT_TASK_22

**Details:**
- **action:** Task 21 completed successfully; advancing to Task 22
- **reason:** Token type consolidation complete - all 284 tests pass. No escalations or blockers.
- **completed_task:** tasks/21-consolidate-token-types-to-typespy.md
- **next_task:** tasks/22-refactor-isinstance-to-match-pattern-matching.md
- **pattern:** Simple (isolated refactoring task, no Architect review needed)


### [2026-02-26] TASK_22_COMPLETE_NEXT_PHASE_CORE_SYNTAX

**Details:**
- **action:** Task 22 completed successfully; moving to core syntax phase
- **reason:** isinstance to pattern matching refactor complete - all 294 tests pass. Foundational tasks (21, 22) are now done. Proceeding to Task 1 from original requirements: remove skip_indent from lexer.
- **completed_task:** tasks/22-refactor-isinstance-to-match-pattern-matching.md
- **tasks_created:**
  - tasks/23-remove-skip_indent-from-surfacelexerpy.md (Task 1 - core syntax, no deps, priority: high)
- **pattern:** Simple (isolated lexer refactoring, no Architect review needed)
- **next_phase:** Core syntax tasks (23 → 24 → 25) → LLM FFI → DSL expansion
- **next_task:** tasks/23-remove-skip_indent-from-surfacelexerpy.md


### [2026-02-26] TASK_23_COMPLETE_NEXT_TASK_24

**Details:**
- **action:** Task 23 completed successfully; moving to Task 24 (core syntax phase)
- **reason:** skip_indent removal complete - all 148 tests pass. No blockers, no escalations. Proceeding to Task 2 from original requirements: fix data declaration syntax (= and |).
- **completed_task:** tasks/23-remove-skip_indent-from-surfacelexerpy.md
- **tasks_created:**
  - tasks/24-fix-data-declaration-syntax-in-surfaceparserpy.md (Task 2 - core syntax, no deps, priority: high)
- **pattern:** Simple (parser syntax task, no Architect review needed)
- **next_phase:** Core syntax tasks (24 → 25 → 26) → LLM FFI → DSL expansion
- **next_task:** tasks/24-fix-data-declaration-syntax-in-surfaceparserpy.md

### [2026-02-26] TASK_29_TYPED_TOKENS_COMPLETE

**Details:**
- **action:** Task 29 completed successfully; implemented typed lexer token classes
- **reason:** Typed tokens implementation complete - all 336 tests pass. Replaced generic Token with specific classes (IdentifierToken, ConstructorToken, NumberToken, KeywordToken, OperatorToken, DelimiterToken, IndentationToken, PragmaToken, DocstringToken, EOFToken). Pattern matching now possible on token types.
- **completed_task:** tasks/29-implement-typed-lexer-tokens.md
- **pattern:** Simple (code organization task, no Architect review needed)
- **next_phase:** DSL expansion (7) and remaining features
- **next_task:** TBD (Task 7 - DSL expansion)

### [2026-02-26] TASK_30_DSL_EXPLORATION_CREATED

**Details:**
- **action:** Created Task 30 for DSL features architecture exploration
- **reason:** Task 7 (DSL expansion) from original requirements is large and complex. Following Discovery pattern: need exploration before implementation to understand architecture, dependencies, and break down into manageable tasks. Features to explore: tape context management, parallel execution, runtime REPL, set_output(), maybe type, module system.
- **completed_task:** tasks/29-implement-typed-lexer-tokens.md
- **tasks_created:**
  - tasks/30-explore-dsl-features-architecture.md (exploration task for DSL design)
- **pattern:** Discovery (exploration before design)
- **next_phase:** Exploration (30) → Design → Implementation
- **next_task:** tasks/30-explore-dsl-features-architecture.md
