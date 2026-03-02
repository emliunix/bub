# System F Elaborator Design

**Status**: Planning Complete, Implementation Ready  
**Last Updated**: 2026-03-02

---

## Overview

This document consolidates the design, architecture, and implementation plan for the System F elaborator refactor. The goal is to move from a single-pass elaborator to a **multi-pass pipeline** following Idris 2's architecture.

---

## Philosophy

### 1. All-or-Nothing Implementation

Do not implement features gradually or maintain backward compatibility during major refactors. The system works when complete, not before.

**Why**:
- Gradual migration adds complexity and technical debt
- Maintaining compatibility layers obscures the correct architecture
- "All at once" is often simpler than incremental changes
- Forces clear design decisions upfront

**Practice**:
```python
# DON'T: Keep old code working
class Elaborator:
    def elaborate(self, term, mode="new"):  # Compatibility parameter
        if mode == "old":
            return self._old_elaborate(term)
        else:
            return self._new_elaborate(term)

# DO: Replace entirely
class Elaborator:
    def elaborate(self, term):  # Only new implementation
        return self._elaborate(term)
```

### 2. Design Big to Small, Implement Small to Big

**Design Phase** (Big → Small):
1. System architecture and boundaries
2. Module interfaces and contracts
3. Data flow and transformations
4. Individual function signatures

**Implementation Phase** (Small → Big):
1. Core data structures and utilities
2. Leaf functions (no dependencies)
3. Internal modules (depend on leaves)
4. Public API (depends on everything)

**Example**:
```
Design:      Parser → AST → Elaborator → Type Checker → Evaluator
Implement:   AST → Parser → Type Checker → Elaborator → Evaluator
```

### 3. Systematic Test Failure Analysis

When tests fail, analyze by component in **reverse dependency order**.

**Method**:
```
Lexer → Parser → Elaborator → Type Checker → Integration Tests
   ↑         ↑          ↑              ↑
Check in this order (leaf to root)
```

**Rule**: Never fix Level N+1 when Level N is broken.

---

## Architecture

### Pipeline Overview

```
Surface AST ──► Scoped AST ──► Core AST ──► (LLM Pass)
  (names)        (dbi+names)   (typed)
```

**Three Passes**:

1. **Scope Checking** - Name resolution, de Bruijn indices, preserve names
2. **Type Elaboration** - Type inference, unification, produce typed Core
3. **LLM Pragma** - Extract pragmas, replace bodies with PrimOp

### Why Multi-Pass?

**Single-pass problems**:
- Name resolution mixed with type checking
- Hard to test scope checking independently
- Type errors may occur before all names resolved
- Can't add features (implicits) cleanly

**Multi-pass benefits**:
- Clear separation of concerns
- Better error messages (scope errors ≠ type errors)
- Can inspect intermediate representations
- Foundation for future features

---

## Extended Surface AST Design

### Core Insight

Instead of creating a separate `ScopedTerm` hierarchy, **extend Surface AST** with scoped variants:

```python
# Before scope checking (names)
SurfaceVar(name="x")
SurfaceAbs(var="x", body=...)

# After scope checking (indices + names)
ScopedVar(index=1, debug_name="x")
ScopedAbs(var_name="x", body=...)

# Unchanged (works for both)
SurfaceApp(func, arg)
SurfaceConstructor(name, args)
```

### Benefits

1. **No code duplication** - Reuse SurfaceApp, SurfaceConstructor, etc.
2. **Can mix during transformation** - Gradually convert names to indices
3. **Pattern matching reuse** - Type elaborator handles both
4. **Less maintenance** - ~15 fewer AST types to maintain

### Implementation

```python
# systemf/surface/types.py

@dataclass(frozen=True)
class SurfaceVar(SurfaceTerm):
    """Variable reference by name (before scope checking)."""
    name: str

@dataclass(frozen=True)
class ScopedVar(SurfaceTerm):
    """Variable reference by de Bruijn index (after scope checking)."""
    index: int           # De Bruijn index (0 = nearest binder)
    debug_name: str      # Original name for error messages

@dataclass(frozen=True)
class SurfaceAbs(SurfaceTerm):
    """Lambda with parameter name (before scope checking)."""
    var: str
    var_type: Optional[SurfaceType]
    body: SurfaceTerm

@dataclass(frozen=True)
class ScopedAbs(SurfaceTerm):
    """Lambda with parameter name preserved (after scope checking)."""
    var_name: str        # Original parameter name
    var_type: Optional[SurfaceType]
    body: SurfaceTerm
```

### Scope Checking as Transformation

```python
class ScopeChecker:
    def check_term(self, term: SurfaceTerm, ctx: ScopeContext) -> SurfaceTerm:
        match term:
            case SurfaceVar(name, location):
                try:
                    index = ctx.lookup_term(name)
                    return ScopedVar(location, index, name)
                except ScopeError:
                    raise ScopeError(f"Undefined variable '{name}'", location)
            
            case SurfaceAbs(var, var_type, body, location):
                new_ctx = ctx.extend_term(var)
                scoped_body = self.check_term(body, new_ctx)
                return ScopedAbs(location, var, var_type, scoped_body)
            
            case SurfaceApp(func, arg, location):
                # Recurse but keep SurfaceApp
                return SurfaceApp(
                    location,
                    self.check_term(func, ctx),
                    self.check_term(arg, ctx)
                )
            
            # ... other cases pass through or transform recursively
```

### Scope Context

```python
@dataclass
class ScopeContext:
    """Tracks name → de Bruijn index mapping."""
    
    term_names: list[str]  # Index 0 = most recent
    type_names: list[str]
    globals: set[str]
    
    def lookup_term(self, name: str) -> int:
        """Get de Bruijn index for name."""
        for i, n in enumerate(self.term_names):
            if n == name:
                return i
        raise ScopeError(f"Undefined variable '{name}'")
    
    def extend_term(self, name: str) -> "ScopeContext":
        """Add binding, becomes index 0."""
        return ScopeContext([name] + self.term_names, ...)
```

---

## Core AST Requirements

### Source Locations Mandatory

Every Core term must carry source location for error reporting:

```python
@dataclass(frozen=True)
class Term:
    source_loc: Optional[Location] = None
```

### Preserve Names

Core AST keeps variable names for readable errors:

```python
@dataclass(frozen=True)
class Var(Term):
    index: int
    debug_name: str = ""  # Original name

@dataclass(frozen=True)
class Abs(Term):
    var_name: str = ""  # Original parameter name
    var_type: Type
    body: Term
```

**Before**: `λ(_:_).x0`  
**After**: `λ(x:_).x`

---

## Implementation Plan

### Phase 1: Scope Checking (Week 1)

**Deliverables**:
1. Add `ScopedVar`, `ScopedAbs` to `surface/types.py`
2. Create `surface/scope/checker.py` with `ScopeChecker` class
3. Create `surface/scope/context.py` with `ScopeContext`
4. Handle top-level declarations
5. Tests in `tests/surface/test_scope.py`

**Key Algorithm**:
```python
def check_declaration(decl: SurfaceDeclaration) -> SurfaceDeclaration:
    # Transform all SurfaceVar -> ScopedVar
    # Transform all SurfaceAbs -> ScopedAbs
    # Keep other nodes unchanged (but recurse)
```

### Phase 2: Type Elaboration (Week 2)

**Deliverables**:
1. Create `surface/inference/elaborator.py` with `TypeElaborator`
2. Implement bidirectional type checking
3. Unification logic
4. Move logic from old elaborator
5. Tests in `tests/surface/test_inference.py`

**Input**: `ScopedTerm` (de Bruijn indices, no types)  
**Output**: `Core.Term` (fully typed)

**Key Algorithm**:
```python
def elaborate_term(term: ScopedTerm, ctx: TypeContext) -> tuple[Core.Term, Type]:
    match term:
        case ScopedVar(index, debug_name, location):
            ty = ctx.lookup_type(index)
            return Core.Var(location, index, debug_name), ty
        
        case ScopedAbs(var_name, body, location):
            arg_ty = fresh_meta()
            new_ctx = ctx.extend_term(arg_ty)
            core_body, body_ty = elaborate_term(body, new_ctx)
            result_ty = TypeArrow(arg_ty, body_ty)
            return Core.Abs(location, var_name, arg_ty, core_body), result_ty
```

### Phase 3: Pipeline & LLM (Week 3)

**Deliverables**:
1. Create `surface/pipeline.py` orchestrating all passes
2. Implement top-level collection strategy (mutual recursion)
3. Create `surface/llm/pass.py` for pragma processing
4. Delete old elaborator
5. Update REPL

**Top-Level Collection** (for mutual recursion):
```python
def elaborate_module(decls: list[SurfaceDeclaration]) -> Module:
    # Step 1: Scope check all
    scoped_decls = [scope_checker.check_declaration(d) for d in decls]
    
    # Step 2: Collect all type signatures
    signatures = collect_signatures(scoped_decls)
    
    # Step 3: Elaborate type signatures
    type_sigs = {name: elaborate_type(sig) for name, sig in signatures.items()}
    
    # Step 4: Elaborate bodies (with all signatures in scope)
    core_decls = []
    for decl in scoped_decls:
        core_decl = type_elaborator.elaborate_declaration(decl, type_sigs)
        core_decls.append(core_decl)
    
    # Step 5: Process LLM pragmas
    final_decls = [llm_pass.process(d) for d in core_decls]
    
    return Module(final_decls)
```

---

## Design Decisions Log

### Decision 1: Multi-Pass Architecture

**Decision**: Implement explicit multi-pass elaboration following Idris 2 design.

**Consequence**: ~2-3 weeks implementation time, but cleaner architecture.

### Decision 2: All-or-Nothing Implementation

**Decision**: No gradual migration. System works when complete, not before.

**Consequence**: System will be broken during refactor. Need feature branch.

### Decision 3: Extend Surface AST

**Decision**: Add scoped variants to Surface AST instead of creating separate hierarchy.

**Consequence**: Need to be careful about pattern matching - must handle both variants.

### Decision 4: Core AST Keeps Names

**Decision**: Add `debug_name` to `Var` and `var_name` to `Abs` in Core AST.

**Consequence**: Slightly larger Core AST, better user experience.

### Decision 5: Direct to Typed Core

**Decision**: Elaborate directly to typed Core, no untyped intermediate.

**Consequence**: Elaborator must synthesize types during translation.

### Decision 6: No Verification Pass

**Decision**: Remove separate verification/kernel pass. Trust elaborator.

**Consequence**: May revisit if we add formal verification later.

### Decision 7: LLM as Separate Pass

**Decision**: Dedicated pass for LLM pragma processing.

**Consequence**: Keeps main elaborator clean, easy to disable.

### Decision 8: Top-Level Collection

**Decision**: Collect all signatures first, then elaborate bodies.

**Consequence**: Enables mutual recursion and forward references.

---

## Module Structure

```
src/systemf/surface/
├── __init__.py              # Public API
├── types.py                 # Surface AST + Scoped variants
├── parser/                  # Parser (existing)
├── scope/                   # Phase 1: Scope checking
│   ├── __init__.py
│   ├── checker.py           # ScopeChecker
│   ├── context.py           # ScopeContext
│   └── errors.py            # ScopeError
├── inference/               # Phase 2: Type elaboration
│   ├── __init__.py
│   ├── elaborator.py        # TypeElaborator
│   ├── context.py           # TypeContext
│   ├── unification.py       # Unification
│   └── errors.py            # TypeError
├── llm/                     # Phase 3: LLM pragma
│   ├── __init__.py
│   └── pass.py              # LLMPragmaPass
└── pipeline.py              # Orchestration

src/systemf/core/
├── ast.py                   # Core AST (with names + locations)
├── types.py                 # Type representations
├── context.py               # Type checking context
└── errors.py                # Error hierarchy
```

---

## Testing Strategy

### Unit Tests per Phase

```python
# tests/surface/test_scope.py
class TestScopeChecker:
    def test_variable_lookup(self):
        surface = SurfaceVar("x", loc)
        ctx = ScopeContext(term_names=["y", "x"])
        scoped = scope_checker.check_term(surface, ctx)
        assert scoped == ScopedVar(loc, index=1, debug_name="x")

# tests/surface/test_inference.py
class TestTypeElaborator:
    def test_identity_function(self):
        scoped = ScopedAbs(loc, "x", ScopedVar(loc, 0, "x"))
        core, ty = elaborator.elaborate_term(scoped, Context.empty())
        assert isinstance(core, Core.Abs)
        assert core.var_name == "x"
```

### Integration Tests

```python
# tests/test_pipeline.py
class TestFullPipeline:
    def test_end_to_end(self):
        source = "let id = \\x -> x in id 5"
        decls = parse_program(source)
        result = elaborate_program(decls)
        assert result.is_ok()
```

---

## Error Handling

### Error Hierarchy

```
SystemFError (abstract)
├── ScopeError           # Undefined variables, shadowing
├── TypeError            # Type mismatches, unification failures
│   ├── UnificationError
│   ├── TypeMismatch
│   └── ...
├── ElaborationError     # Surface to Core translation errors
└── ParseError           # Syntax errors
```

### Error Format

```python
@dataclass
class SystemFError(Exception):
    message: str
    location: Optional[Location]
    term: Optional[Term] = None
    diagnostic: Optional[str] = None
```

**Example**:
```
error: Type mismatch
  --> test.sf:5:10
   |
 5 |   x + "hello"
   |   ^
   |
   = expected: Int
   = actual: String
   = in term: x
```

---

## Success Criteria

System is complete when:
1. ✅ All surface terms can be scope-checked
2. ✅ All scoped terms can be elaborated to typed Core
3. ✅ Variable names preserved through all phases
4. ✅ Source locations attached to all errors
5. ✅ All 486+ tests pass
6. ✅ REPL works with new pipeline
7. ✅ Error messages show names and locations
8. ✅ Old elaborator deleted

**No partial functionality.** It either works correctly or it doesn't work.

---

## References

- **Journal**: `journal/2026-03-02-elaborator-design.md`
- **Comparison**: Research on Lean 4, GHC, Agda, Idris 2 architectures
- **Implementation Status**: Planning complete (~3 weeks to implement)

---

**Last Updated**: 2026-03-02  
**Status**: Ready for implementation
