---
assignee: Implementor
expertise: ['Python', 'Parsing', 'Elaboration']
skills: ['python-project', 'testing']
type: implement
priority: high
state: done
dependencies: ['tasks/35-implement-core-ast-and-type-extensions-for-primitives.md']
refers: []
kanban: tasks/33-kanban-systemf-pluggable-primitives-system.md
created: 2026-02-26T17:17:52.984594
---

# Task: Implement - Surface Syntax for Integer Literals

## Context
Update the surface language to support integer literals. The lexer already produces NUMBER tokens, but these are currently treated as constructor names. We need to convert NUMBER tokens to IntLit terms in the elaborator.

## Files
- systemf/src/systemf/surface/lexer.py
- systemf/src/systemf/surface/parser.py
- systemf/src/systemf/surface/elaborator.py
- systemf/tests/test_surface/

## Description
Update elaborator.py to convert NUMBER tokens to IntLit terms instead of treating them as constructors. The lexer produces NUMBER tokens - we need to handle these specially in the elaborator. Update parser to pass NUMBER tokens through. Add tests for integer literal parsing and elaboration.

## Work Log

### 2026-02-26 - Implementation Complete

**Changes Made:**

1. **Added `SurfaceIntLit` class to `systemf/src/systemf/surface/ast.py`:**
   - Created new dataclass `SurfaceIntLit` with `value: int` field
   - Added to `SurfaceTermRepr` union type
   - Implements `__str__` method returning the integer as string

2. **Updated `systemf/src/systemf/surface/parser.py`:**
   - Added import for `SurfaceIntLit`
   - Modified `atom_base()` function (lines 330-332) to create `SurfaceIntLit(int(num.value), num.location)` instead of `SurfaceConstructor(num.value, [], num.location)`
   - Numbers are now properly parsed as integer literals, not constructors

3. **Updated `systemf/src/systemf/surface/elaborator.py`:**
   - Added import for `SurfaceIntLit`
   - Added case handler for `SurfaceIntLit` in `elaborate_term()` method
   - Converts `SurfaceIntLit` to `core.IntLit(value)` during elaboration

4. **Updated existing tests:**
   - Modified `test_parser.py` to check for `SurfaceIntLit` instead of `SurfaceConstructor` in `test_simple_let` and `test_declaration_boundary`

5. **Added new tests for integer literals:**
   - `TestIntegerLiterals` class in `test_parser.py` with 6 tests covering:
     - Simple integer parsing
     - Zero literal
     - Large integers
     - Integers in let bindings
     - Integers as function arguments
     - Multiple integers in case branches
   - `TestElaborateIntLit` class in `test_elaborator.py` with 6 tests covering:
     - Basic integer elaboration
     - Zero elaboration
     - Large integer elaboration
     - Integer from parsed source
     - Integer in let binding
     - Integer as function argument

**Test Results:**
- All 174 surface tests pass (including 12 new tests for integer literals)
- Verified end-to-end: `parse_term("42")` → `SurfaceIntLit(42)` → `IntLit(42)`

**Status:** COMPLETE
