---
assignee: Implementor
expertise: ['System Design', 'DSL Implementation', 'Type Theory']
skills: []
type: implement
priority: high
state: cancelled
dependencies: []
refers: []
kanban: tasks/16-kanban-systemf-language-implementation.md
created: 2026-02-26T12:47:40.609210
---

# Task: Implement Module System for SystemF

## Context
Task 30 explored DSL features architecture and identified Module System as the foundational feature that all other DSL features depend on. The Module System will provide code organization, imports, and namespace management for SystemF.

From the architecture exploration:
- Current SystemF pipeline: Surface Syntax → Lexer → Parser → Surface AST → Elaborator → Core AST → TypeChecker → Evaluator
- Module System is Phase 1 priority (required for all other features)
- Will add `SurfaceModule` and `SurfaceImport` declarations
- Needs module-aware context building in TypeChecker

## Files
- `systemf/src/systemf/surface/ast.py` - Add SurfaceModule and SurfaceImport AST nodes
- `systemf/src/systemf/surface/parser.py` - Parse `module Name where` and `import Module (names)` syntax
- `systemf/src/systemf/core/ast.py` - Add module metadata to core terms
- `systemf/src/systemf/core/types.py` - Module-aware type contexts
- `systemf/src/systemf/core/checker.py` - Extend context building for modules
- `systemf/src/systemf/surface/elaborator.py` - Handle module declarations during elaboration

## Description
Implement the Module System for SystemF DSL:

1. **Surface AST Extensions:**
   - Add `SurfaceModule` declaration node with module name and body
   - Add `SurfaceImport` declaration node for importing modules
   - Support syntax: `module Name where` and `import Module (names)`

2. **Parser Updates:**
   - Parse module declarations at file level
   - Parse import statements
   - Support selective imports: `import Module (func1, func2)`

3. **Core AST Integration:**
   - Add module metadata to core terms (qualified names)
   - Track module boundaries during elaboration

4. **TypeChecker Extensions:**
   - Module-aware context building
   - Resolve qualified names (Module.name)
   - Handle import visibility rules

5. **Tests:**
   - Module declaration parsing
   - Import resolution
   - Qualified name access
   - Circular import detection (if applicable)

**Design Decision:** Module System must be completed first as it provides the namespace foundation for all other DSL features (tape context, parallel execution, etc.).

## Work Log

### [2026-02-26] TASK_CANCELLED

**Details:**
Task cancelled - superseded by new REPL design approach.

**Reason:**
User is designing a better REPL where modules are handled simply as "load a file and evaluate it". This eliminates the need for a complex module system with imports, namespace management, and qualified names. The REPL becomes the primary interface for code organization.

**New Direction:**
- Focus on REPL implementation
- Module = load file + evaluate
- Simpler, more flexible approach

**Status:** Cancelled

<!-- Work logs will be appended here -->
