---
assignee: Architect
expertise: ['Type Theory', 'SystemF']
skills: ['code-reading']
type: exploration
priority: high
state: done
dependencies: []
refers: []
kanban: tasks/40-kanban-systemf-string-types.md
created: 2026-02-26T18:59:19.643016
---

# Task: Explore SystemF codebase for String types

## Context
<!-- Background information and relevant context -->

## Files
<!-- List of files to modify or reference -->

## Description
Explore the existing SystemF implementation to understand: 1) Where primitive types are defined, 2) How prim ops are implemented, 3) What String operations would be sensible to add

## Work Log
<!-- Work logs will be appended here -->

### [2026-02-26 19:01:05] Exploration Complete

**Facts:**
**Primitive Type System Structure:**
- `PrimitiveType` class exists in `systemf/core/types.py:112-130` for declaring primitive types
- Primitive types are declared in `prelude.sf` using `prim_type` keyword
- String is already declared as `prim_type String` in prelude.sf line 7

**Primitive Operations Structure:**
- `PrimOp` class exists in `systemf/core/ast.py:172-186` for primitive operations
- Operations are implemented in `systemf/eval/machine.py:43-48` via `primitive_impls` registry
- Current implementations: `int_plus`, `int_minus`, `int_multiply`, `int_divide`
- `VInt` value type exists in `systemf/eval/value.py:57-68` for integer literals
- `IntLit` term exists in `systemf/core/ast.py:157-168` for integer literals in AST

**Current String State:**
- Two String operations declared in prelude.sf:
  - `string_concat : String -> String -> String` (line 22)
  - `string_length : String -> Int` (line 23)
- **BUT**: No implementations exist in the evaluator
- **Missing**: `VString` value type, `StringLit` term, parser support for string literals

**Type Checking:**
- Primitive types and operations are registered in elaborator (`systemf/surface/elaborator.py:94-95`)
- Type checker looks up primitive types via `primitive_types` registry
- Primitive op types come from `global_types` registry with `$prim.` prefix

**Analysis:**
**Architecture Pattern:**
The primitive system follows a clear 4-layer architecture:
1. **Declaration** (prelude.sf): Declares types and operation signatures
2. **Core Types** (core/types.py): `PrimitiveType` represents primitive types
3. **Core AST** (core/ast.py): `PrimOp` represents primitive operations, `IntLit` for literals
4. **Runtime** (eval/): `VInt` for values, `primitive_impls` for implementations

**What's Missing for String Support:**
To fully support String primitive type and operations, we need:

1. **Runtime Value** (`eval/value.py`): Add `VString` class (like `VInt`)
2. **Core AST** (`core/ast.py`): Add `StringLit` class (like `IntLit`)
3. **Evaluator** (`eval/machine.py`): Add string operations to `primitive_impls` registry
4. **Type Checker**: Handle `StringLit` type checking (like `IntLit`)
5. **Parser/Lexer**: Add string literal tokenization and parsing
6. **Elaborator**: Handle string literals in surface-to-core translation

**Sensible String Operations to Add:**
Based on common functional language patterns:
- Already declared: `string_concat`, `string_length`
- Additional useful ops: `string_eq`, `string_slice`, `string_contains`, `string_empty`, `string_char_at`

**Dependencies:**
The work follows a core-first dependency order:
- Core types/AST changes are foundational (no dependencies)
- Evaluator implementation depends on core AST
- Parser/lexer changes depend on core definitions
- Integration tests come last

**Conclusion:**
Status: **ok**

Exploration complete. The SystemF codebase has a well-structured primitive type system. String primitive type is declared but not fully implemented. The pattern is clear: follow the same 4-layer architecture used for Int primitives.

## Suggested Work Items (for Manager)

```yaml
work_items:
  - description: Add String primitive value type and literal to core
    files: 
      - systemf/src/systemf/eval/value.py (add VString)
      - systemf/src/systemf/core/ast.py (add StringLit)
    related_domains: ["Type Theory", "SystemF"]
    expertise_required: ["Type System Implementation", "Python"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Follow the same pattern as VInt and IntLit

  - description: Implement String primitive operations in evaluator
    files:
      - systemf/src/systemf/eval/machine.py (add string_concat, string_length)
    related_domains: ["Type Theory", "SystemF"]
    expertise_required: ["Interpreter Implementation", "Python"]
    dependencies: [0]
    priority: high
    estimated_effort: small
    notes: Add to primitive_impls registry following int_plus pattern

  - description: Add String literal parsing and elaboration
    files:
      - systemf/src/systemf/surface/lexer.py (string literal token)
      - systemf/src/systemf/surface/parser.py (string literal parsing)
      - systemf/src/systemf/surface/elaborator.py (StringLit elaboration)
    related_domains: ["Type Theory", "SystemF", "Parsing"]
    expertise_required: ["Parser Implementation", "Python"]
    dependencies: [0]
    priority: high
    estimated_effort: medium
    notes: Surface language support for string literals

  - description: Add String type checking support
    files:
      - systemf/src/systemf/core/checker.py (StringLit type inference)
    related_domains: ["Type Theory", "SystemF"]
    expertise_required: ["Type System Implementation", "Python"]
    dependencies: [0, 2]
    priority: high
    estimated_effort: small
    notes: Check StringLit similar to IntLit

  - description: Write tests for String primitives
    files:
      - systemf/tests/test_core/test_strings.py
      - systemf/tests/test_eval/test_strings.py
    related_domains: ["Type Theory", "SystemF", "Testing"]
    expertise_required: ["Testing", "Python"]
    dependencies: [0, 1, 2, 3]
    priority: medium
    estimated_effort: medium
    notes: Follow test_primitives.py pattern for String operations
```

---

