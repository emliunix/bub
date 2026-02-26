---
assignee: Architect
expertise: ['System Design', 'DSL Design']
skills: ['code-reading']
type: exploration
priority: high
state: done
dependencies: []
refers: []
kanban: tasks/16-kanban-systemf-language-implementation.md
created: 2026-02-26T12:39:40.053125
---

# Task: Explore DSL Features Architecture

## Context
<!-- Background information and relevant context -->

## Files
<!-- List of files to modify or reference -->

## Description
<!-- What needs to be done -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-02-26 12:42:28] Architecture Exploration Complete

**Facts:**
## DSL Features Architecture Exploration - Work Log

### Current SystemF Architecture Analysis

**Pipeline Overview:**
```
Surface Syntax → Lexer → Parser → Surface AST → Elaborator → Core AST → TypeChecker → Evaluator
```

**Key Components:**

1. **Surface Layer** (`systemf/src/systemf/surface/`)
   - `lexer.py`: Tokenization with typed tokens (recently completed Task 29)
   - `parser.py`: Parsy-based parser supporting dual pattern matching syntax
   - `ast.py`: Surface AST with name-based binding, docstrings, pragmas
   - `elaborator.py`: Converts surface to core (names → de Bruijn indices)
   - `desugar.py`: Syntactic sugar transformations

2. **Core Layer** (`systemf/src/systemf/core/`)
   - `ast.py`: Core AST with de Bruijn indices
   - `types.py`: Type system (TypeVar, TypeArrow, TypeForall, TypeConstructor)
   - `checker.py`: Bidirectional type checker with unification
   - `context.py`: Typing contexts for term/type variables

3. **Evaluation Layer** (`systemf/src/systemf/eval/`)
   - `machine.py`: Call-by-value evaluator
   - `value.py`: Value representations (VClosure, VConstructor, VToolResult)
   - `tools.py`: Tool registry for FFI (includes LLMCallTool placeholder)
   - `repl.py`: Interactive REPL

**Existing Features:**
- Variables, functions (λ), type abstractions (Λ), type application
- Data types with pattern matching (case/of)
- Polymorphic types (forall)
- Let bindings
- Tool calls (@tool_name) - FFI foundation
- Pragmas ({-# LLM key=value #-})
- First-class docstrings attached to AST nodes

### DSL Feature Architecture Design

#### 1. Variables & Functions (EXISTING)
**Status:** Already implemented
**Location:** `core/ast.py` (Var, Abs, App)
**Integration:** Fully integrated into pipeline

#### 2. Tape Context Management
**Purpose:** Manage conversation context through tape system
**Architecture:**
- **Surface AST:** Add `SurfaceTapeContext` term
- **Evaluation:** Register context with Bub's tape service
- **Type:** `TapeContext : forall a. String -> a -> a`
- **Syntax:** `tape "label" { expr }`
- **Dependencies:** Requires Bub tape integration

#### 3. Parallel Execution
**Purpose:** Enable concurrent computation
**Architecture:**
- **Surface/Core AST:** Add `Par` term
- **Type:** `Par : forall a. List (Unit -> a) -> List a`
- **Evaluation:** Async evaluation with result collection
- **Syntax:** `par { e1 } { e2 }` or `e1 ||| e2`
- **Dependencies:** None (self-contained)

#### 4. Runtime REPL Context for LLM
**Purpose:** Interactive context for LLM code generation
**Architecture:**
- **Implementation:** Extend existing REPL in `eval/repl.py`
- **Features:** Persistent bindings, context extraction, `:context` command
- **Dependencies:** None (extends REPL)

#### 5. set_output() Support (LLM Prefix Cache)
**Purpose:** Control LLM prefix caching
**Architecture:**
- **Surface AST:** Add `SurfaceSetOutput` term (desugars to ToolCall)
- **Type:** `set_output : String -> Unit`
- **Tool:** Add `SetOutputTool` to registry
- **Syntax:** `set_output "prefix"` or `output "prefix" { expr }`
- **Dependencies:** Tool infrastructure (exists)

#### 6. Maybe Type (Optional Data)
**Purpose:** Optional/nullable values
**Architecture:**
- **Implementation:** Data type declaration (already supported!)
- **Definition:** Standard `Maybe a = Nothing | Just a`
- **Standard Lib:** Provide `maybe`, `from_maybe`, `map_maybe`
- **Dependencies:** None (standard library only)

#### 7. Module System
**Purpose:** Code organization, imports, namespaces
**Architecture:**
- **Surface:** `SurfaceModule`, `SurfaceImport` declarations
- **Core:** Qualified names in metadata
- **TypeChecker:** Module-aware context building
- **Syntax:** `module Name where`, `import Module (names)`
- **Dependencies:** All features depend on this

### Implementation Order Recommendation

**Phase 1: Foundation**
1. Module System (required for all)
2. Maybe Type (standard library)

**Phase 2: Core DSL Features**
3. set_output() (simple tool)
4. Parallel Execution (concurrency)

**Phase 3: Integration**
5. Tape Context Management (Bub integration)
6. Runtime REPL Context (LLM features)

### Integration Points Summary

| Feature | Surface AST | Core AST | TypeChecker | Evaluator | Tools |
|---------|-------------|----------|-------------|-----------|-------|
| Variables/Functions | ✓ (exists) | ✓ (exists) | ✓ (exists) | ✓ (exists) | - |
| Module System | NEW | Metadata | Extend | Extend | - |
| Tape Context | NEW | - | - | - | NEW |
| Parallel | NEW | NEW | Extend | Extend | - |
| set_output() | NEW | - | - | - | NEW |
| Maybe Type | - | - | - | - | - |
| REPL Context | - | - | - | Extend | - |

### Risk Assessment

**High Risk:**
- Module system: Complex cross-cutting changes
- Parallel execution: Concurrency correctness

**Medium Risk:**
- Tape context: External integration
- REPL context: Serialization format

**Low Risk:**
- set_output(): Simple tool addition
- Maybe type: Standard library only

### Recommended Task Breakdown

1. **31-implement-module-system.md** - Module declarations, imports
2. **32-add-maybe-type-prelude.md** - Standard library Maybe
3. **33-implement-set-output-tool.md** - set_output() tool
4. **34-implement-parallel-execution.md** - par blocks
5. **35-implement-tape-context.md** - Tape integration
6. **36-enhance-repl-llm-context.md** - REPL context

### Key Architecture Decisions

1. **Module System First:** All features need stable scoping
2. **Tool-Based I/O:** Use existing ToolCall for set_output/tape
3. **Data Types for Maybe:** Leverage existing ADT system
4. **Async for Parallel:** Python asyncio fits semantics
5. **Surface-Only Sugar:** Some features desugar to tool calls

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-02-26 12:42:32] Exploration Complete

**Facts:**
Architecture analysis complete. Documented current SystemF pipeline (Surface→Core→TypeChecker→Evaluator), designed 7 DSL features with integration points, dependencies, and implementation order. Recommended: Module System → Maybe Type → set_output() → Parallel → Tape Context → REPL Context. Ready to create implementation tasks.

**Analysis:**
-

**Conclusion:**
Status: ok

---

