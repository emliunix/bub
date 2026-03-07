---
assignee: Implementor
expertise: ['Python', 'AST Design']
skills: []
type: implement
priority: high
state: done
dependencies: ['tasks/111-implement-coercion-datatypes.md']
refers: ['tasks/110-design-coercion-type-system.md', 'tasks/108-kanban-system-fc-elaborator.md']
kanban: tasks/108-kanban-system-fc-elaborator.md
created: 2026-03-07T13:19:13.095265
---

# Task: Extend core AST with Cast and Axiom

## Context
<!-- Background information and relevant context -->

## Files
- src/systemf/core/ast.py

## Description
Add Cast(expr, coercion) and Axiom(name, args) constructors to Core AST to support coercion operations

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-07 13:20:55] Implementation Complete

**Facts:**
Added Cast and Axiom constructors to systemf/src/systemf/core/ast.py: Cast(expr, coercion) - type cast using coercion proof γ : τ₁ ~ τ₂, represented as 'expr ▷ γ', includes expr and coercion fields with proper defaults. Axiom(name, args) - axiom term for introducing coercion proofs, represented as 'axiom[name] @ [args]', includes name and type arguments list. Both extend Term base class with source_loc support, include __str__ methods for readable output. Updated TermRepr union to include both new types. Verified working with coercion datatypes from task 111.

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-03-07 13:22:00] Implementation Review

**Facts:**
<!-- No facts recorded -->

**Analysis:**
<!-- No analysis recorded -->

**Conclusion:**
<!-- No conclusion recorded -->

---

