---
assignee: Architect
expertise: ['Type System Implementation', 'Python']
skills: ['code-reading']
type: design
priority: high
state: done
dependencies: []
refers: []
kanban: tasks/40-kanban-systemf-string-types.md
created: 2026-02-26T19:02:07.046528
---

# Task: Design - String Core Types (VString, StringLit)

## Context
<!-- Background information and relevant context -->

## Files
<!-- List of files to modify or reference -->

## Description
<!-- What needs to be done -->

## Work Log

### [2026-02-26T20:15:00] Design Session - String Core Types

**Facts:**
- Analyzed SystemF codebase: 4-layer architecture (declaration → core types → AST → runtime)
- String type already declared in prelude.sf but lacks implementation
- IntLit/Int pattern exists and serves as template for StringLit/VString
- Identified 5 work items for full String type implementation

**Analysis:**

Following the Core-First Dependency Order principle, I identified the type hierarchy:

1. **Core Types Layer** (`systemf/core/types.py`): Already has `PrimitiveType`, no changes needed
2. **Core AST Layer** (`systemf/core/ast.py`): Missing `StringLit` term for string literals
3. **Runtime Value Layer** (`systemf/eval/value.py`): Missing `VString` value type
4. **Surface AST Layer** (`systemf/surface/ast.py`): Missing `SurfaceStringLit` surface term
5. **Surface Elaborator** (`systemf/surface/elaborator.py`): Missing string literal elaboration
6. **Lexer** (`systemf/surface/lexer.py`): Missing `STRING` token pattern
7. **Parser** (`systemf/surface/parser.py`): Missing string literal parsing

**Design Decisions:**

**VString (Runtime Value):**
- Mirrors `VInt` exactly - frozen dataclass wrapping a Python str
- Simplest implementation appropriate for SystemF's design philosophy

**StringLit (Core AST):**
- Mirrors `IntLit` - frozen dataclass with `value: str`
- Evaluates to `VString` in machine.py

**SurfaceStringLit (Surface AST):**
- Mirrors `SurfaceIntLit` - frozen dataclass with location tracking
- Elaborates to `StringLit` in elaborator.py

**String Token:**
- Add STRING pattern to lexer matching `"..."` with escape support
- Parse in atom_base() following NUMBER pattern

**Conclusion:**
- Design complete, core types defined
- Work items logged for Manager to create implementation tasks

## Suggested Work Items (for Manager)

```yaml
work_items:
  - description: Implement VString runtime value type in systemf/eval/value.py
    files: [systemf/src/systemf/eval/value.py]
    related_domains: ["Software Engineering", "Type Systems"]
    expertise_required: ["Python", "SystemF"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Add VString dataclass mirroring VInt, update Value union type

  - description: Implement StringLit core AST term in systemf/core/ast.py
    files: [systemf/src/systemf/core/ast.py]
    related_domains: ["Software Engineering", "Type Systems"]
    expertise_required: ["Python", "SystemF"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Add StringLit dataclass mirroring IntLit, update TermRepr union

  - description: Implement StringLit evaluation in systemf/eval/machine.py
    files: [systemf/src/systemf/eval/machine.py]
    related_domains: ["Software Engineering", "Type Systems"]
    expertise_required: ["Python", "SystemF"]
    dependencies: [0, 1]  # Depends on VString and StringLit
    priority: high
    estimated_effort: small
    notes: Add StringLit case to evaluate() method, returns VString

  - description: Implement StringLit type checking in systemf/core/checker.py
    files: [systemf/src/systemf/core/checker.py]
    related_domains: ["Software Engineering", "Type Systems"]
    expertise_required: ["Python", "SystemF"]
    dependencies: [1]  # Depends on StringLit
    priority: high
    estimated_effort: small
    notes: Add StringLit case to infer() method, returns PrimitiveType("String")

  - description: Implement SurfaceStringLit surface AST term in systemf/surface/ast.py
    files: [systemf/src/systemf/surface/ast.py]
    related_domains: ["Software Engineering", "Type Systems"]
    expertise_required: ["Python", "SystemF"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Add SurfaceStringLit dataclass mirroring SurfaceIntLit, update SurfaceTermRepr

  - description: Implement STRING token in systemf/surface/lexer.py
    files: [systemf/src/systemf/surface/lexer.py]
    related_domains: ["Software Engineering", "Compiler Design"]
    expertise_required: ["Python", "Regex", "SystemF"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Add STRING token pattern for "..." with escape sequences, add to TOKEN_PATTERNS before NUMBER

  - description: Implement string literal parsing in systemf/surface/parser.py
    files: [systemf/src/systemf/surface/parser.py]
    related_domains: ["Software Engineering", "Parser Combinators"]
    expertise_required: ["Python", "Parsy", "SystemF"]
    dependencies: [5]  # Depends on STRING token
    priority: high
    estimated_effort: small
    notes: Add STRING token matcher, parse string literal in atom_base() following NUMBER pattern

  - description: Implement string literal elaboration in systemf/surface/elaborator.py
    files: [systemf/src/systemf/surface/elaborator.py]
    related_domains: ["Software Engineering", "Type Systems"]
    expertise_required: ["Python", "SystemF"]
    dependencies: [4, 1]  # Depends on SurfaceStringLit and StringLit
    priority: high
    estimated_effort: small
    notes: Add SurfaceStringLit case to elaborate_term() method

  - description: Write integration tests for String type support
    files: [systemf/tests/test_string.py]
    related_domains: ["Software Engineering", "Testing"]
    expertise_required: ["Python", "SystemF", "Testing"]
    dependencies: [0, 1, 2, 3, 4, 5, 6, 7]  # Depends on all implementation
    priority: medium
    estimated_effort: medium
    notes: Test parsing, elaboration, type checking, evaluation of string literals
```

### [2026-02-26 19:05:02] Design Complete - String Core Types

**Facts:**
## Facts
- Analyzed SystemF 4-layer architecture (declaration → core types → AST → runtime)
- String type already declared in prelude.sf but lacks implementation
- VString mirrors VInt pattern; StringLit mirrors IntLit pattern
- Identified 9 work items for implementation

**Analysis:**
Applied Core-First Dependency Order:
1. VString (runtime value) - no dependencies
2. StringLit (core AST) - no dependencies
3. evaluate StringLit in machine.py - depends on VString
4. infer StringLit type in checker.py - depends on StringLit
5. SurfaceStringLit (surface AST) - no dependencies
6. STRING token in lexer.py - no dependencies
7. parse string in parser.py - depends on STRING token
8. elaborate SurfaceStringLit in elaborator.py - depends on SurfaceStringLit and StringLit
9. integration tests - depends on all implementation

**Conclusion:**
- Design complete, ready for implementation
- 9 work items logged with dependencies
- Following IntLit pattern ensures consistency

---

