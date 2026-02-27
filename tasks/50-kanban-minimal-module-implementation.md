---
type: kanban
title: Minimal Module Implementation
created: 2026-02-27T17:28:24.016223
phase: done
current: null
tasks:
  - file: tasks/50-task-design-module.md
    status: done
    assignee: Architect
  - file: tasks/50-task-implement-elaborator.md
    status: done
    assignee: Implementor
---

# Kanban: Minimal Module Implementation

## Request
Create Module dataclass and update elaborator to return Module instead of tuple. This is Phase 1 of the refactoring to support LLM integration with proper separation between compile-time metadata and runtime execution.

## Goal
Enable the elaborator to return a structured Module object containing:
- Core declarations (AST)
- Type registries (constructor_types, global_types, primitive_types)
- Documentation metadata (docstrings)
- LLM function metadata (for future use)
- Diagnostics/errors

This allows single-pass refactoring (24 call sites updated once) rather than tuple→tuple→Module.

## Technical Design

### Module Dataclass Structure

```python
@dataclass(frozen=True)
class Module:
    """A compiled SystemF module containing all compile-time artifacts."""
    
    # Core Artifacts
    name: str  # Module name (e.g., "prelude", "main")
    declarations: list[Declaration]  # Core AST declarations
    
    # Type Registries (moved from tuple return)
    constructor_types: dict[str, Type]  # Data constructor signatures
    global_types: dict[str, Type]       # Top-level term signatures
    primitive_types: dict[str, PrimitiveType]  # Primitive type definitions
    
    # Documentation Metadata
    docstrings: dict[str, str]  # name -> docstring for declarations
    
    # LLM Function Metadata (populated by elaborator for LLM-annotated functions)
    llm_functions: dict[str, LLMMetadata]
    
    # Diagnostics
    errors: list[ElaborationError]
    warnings: list[str]

@dataclass(frozen=True)  
class LLMMetadata:
    """Compile-time metadata for LLM-derived primitives."""
    function_name: str
    function_docstring: str | None      # From -- | comment
    arg_names: list[str]                # Extracted from lambda patterns
    arg_types: list[Type]               # From type annotation
    arg_docstrings: list[str | None]    # From -- ^ comments
    model: str | None                   # From pragma
    temperature: float | None           # From pragma
    # Note: fallback_body is NOT stored here - it's the original lambda
    # which remains as the PrimOp implementation body
```

### Design Decisions

**1. Module as Pure Data (Compile-Time Only)**
- No runtime values in Module - those live in EvalContext/ModuleInst
- Module can be serialized, cached, moved between machines
- Clean separation: Module = compile-time, ModuleInst = runtime

**2. Reuse Existing Pattern**
- Current elaborator returns: `(core_decls, constructor_types)`
- New return: `Module` containing both + additional metadata
- Follows established Python pattern (dataclass vs tuple)

**3. LLMMetadata Scope**
- Stored in Module.llm_functions for tooling/documentation
- Actual LLM primitive implementation uses closures capturing this metadata
- Elaborator creates closure + registers in evaluator

**4. Backward Compatibility Strategy**
- No compatibility shim - update all 24 call sites in single pass
- Cleaner codebase, no technical debt
- Tests will catch any missed updates

### Integration Points

**Elaborator Changes:**
- `elaborate()` returns `Module` instead of `tuple[list[Declaration], dict[str, Type]]`
- Type registries moved from instance variables to Module fields
- Add docstring collection during elaboration

**TypeChecker Changes:**
- Constructor: accept `Module` instead of individual registries
- Or keep current signature (Module provides properties for backward compat during transition)

**REPL Changes:**
- `elaborate()` result now `Module` object
- Access: `module.declarations`, `module.constructor_types`

### Relevant Files

**Core Implementation:**
- `systemf/src/systemf/core/module.py` (NEW) - Module and LLMMetadata dataclasses
- `systemf/src/systemf/surface/elaborator.py` - Update elaborate() return type
- `systemf/src/systemf/core/checker.py` - Optional: Module-aware constructor

**Integration:**
- `systemf/src/systemf/eval/repl.py` - Update elaborate() usage
- `systemf/demo.py` - Update if uses elaborate()

**Tests to Update (24 call sites):**
- `systemf/tests/test_surface/test_integration.py` (12 calls)
- `systemf/tests/test_string.py` (6 calls)
- `systemf/tests/test_eval/test_tool_calls.py` (1 call)
- `systemf/tests/test_eval/test_integration.py` (1 call)

### References

**Current Elaborator Signature:**
```python
def elaborate(
    decls: list[SurfaceDeclaration]
) -> tuple[list[core.Declaration], dict[str, CoreType]]:
    elab = Elaborator()
    core_decls = elab.elaborate(decls)
    return core_decls, elab.constructor_types
```

**Current REPL Usage:**
```python
core_decls = self.elaborator.elaborate(surface_decls)
# OR
core_decls, constr_types = elaborate(surface_decls)
```

**Comparison with Other Languages:**
- GHC: Interface files (.hi) separate from Core
- Idris2: Elaboration context accumulates metadata
- Lean4: Environment tracks docs separately
- Our approach: Module as self-contained unit (cleaner for our scale)

## Plan Adjustment Log

### [2026-02-27 18:10:00] Workflow Complete
- Phase 1 (Design): Created Module and LLMMetadata dataclasses in `systemf/src/systemf/core/module.py`
- Phase 2 (Implementation): Updated elaborator to return Module, updated 22/24 call sites
- Phase 3 (Review): Architect reviewed and APPROVED implementation
- All 435 tests pass
- Workflow successfully completed
