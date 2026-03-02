# Elaborator Architecture Research and Design

**Date**: 2026-03-02  
**Topic**: Multi-pass elaborator design, scope checking separation, and implementation planning

---

## What We Did

### 1. Research Phase

Researched elaboration architectures across major dependently-typed languages:
- **Lean 4**: Command/Term split, elaborator monad with info trees
- **GHC Haskell**: 5-stage pipeline (Parse→Rename→Type→Desugar→Core)
- **Agda**: Concrete→Abstract→Internal
- **Idris 2**: RawImp→TTImp→TT (clearest separation)

**Key finding**: All use multiple passes, but Idris 2 has the cleanest architecture.

### 2. Core Infrastructure Updates

**Core AST** (`systemf/src/systemf/core/ast.py`):
- Added `source_loc: Location` to all terms (mandatory for error reporting)
- Added `debug_name: str` to `Var` (preserve variable names)
- Added `var_name: str` to `Abs` (preserve parameter names)
- Updated all constructors with defaults for dataclass inheritance

**Error System** (`systemf/src/systemf/core/errors.py`):
- Created `SystemFError` abstract base class
- Added location, term, and diagnostic fields
- Unified hierarchy: ScopeError, TypeError, ElaborationError, ParseError

**Elaborator** (`systemf/src/systemf/surface/elaborator.py`):
- Propagates source locations to all Core terms
- Propagates debug names (variable names preserved)
- Updated test syntax (added missing `in` keywords to let expressions)

### 3. Design Decisions

**Multi-Pass Architecture**:
```
Surface AST → Scoped AST → Core AST → (LLM Pass)
  (names)      (dbi+names)   (typed)
```

**Key decisions** (recorded in `systemf/docs/DESIGN_DECISIONS.md`):
1. All-or-nothing implementation (no gradual migration)
2. Extend Surface AST with scoped variants (don't duplicate hierarchy)
3. Core AST keeps names (indices alone not enough)
4. Elaborate directly to typed Core (no untyped intermediate)
5. No verification pass (trust elaborator)
6. LLM pragma as separate pass

### 4. Documentation Created

- `systemf/docs/elaboration-comparison.md` - Language comparison
- `systemf/docs/elaborator-architecture-analysis.md` - Architecture analysis
- `systemf/docs/multi-pass-elaborator-plan.md` - Initial implementation plan
- `systemf/docs/multi-pass-elaborator-plan-revised.md` - Revised plan
- `systemf/docs/scoped-ast-design.md` - Scoped AST design
- `systemf/docs/scoped-extended-ast-design.md` - Extended Surface AST design
- `systemf/docs/elaborator-implementation-plan.md` - Final implementation plan
- `systemf/docs/type-architecture-review.md` - Type architecture review
- `systemf/docs/DESIGN_DECISIONS.md` - Running decision log

### 5. Development Guidelines

Updated `AGENTS.md` with three new style guidelines:
1. All-or-Nothing Implementation
2. Design Big to Small, Implement Small to Big
3. Systematic Test Failure Analysis (reverse dependency order)

---

## Current Status

**Completed**:
- ✅ Research on elaborator architectures
- ✅ Core AST with source locations and names
- ✅ Error hierarchy redesign
- ✅ All elaborator tests passing (32/32)
- ✅ All type checker tests passing (34/34)
- ✅ Comprehensive documentation

**Not Started**:
- ❌ Scope checker module
- ❌ Scoped AST extensions to Surface
- ❌ Refactored type elaborator
- ❌ Pipeline orchestration
- ❌ LLM pragma pass

---

## Test Status

```
systemf/tests/test_core/test_checker.py    34 passed
systemf/tests/test_surface/test_elaborator.py  32 passed
Overall: 486 passed, 61 failing (integration tests)
```

---

## Key Insights

1. **Scope checking is mandatory**: Separates name resolution from type checking, enables better error messages

2. **Extend don't duplicate**: Add `ScopedVar`/`ScopedAbs` to Surface AST instead of creating parallel hierarchy

3. **Names flow through**: `SurfaceVar("x")` → `ScopedVar(index=1, "x")` → `Core.Var(index=1, "x")`

4. **Top-level collection**: Collect all signatures first, then elaborate bodies (enables mutual recursion)

5. **All at once**: System works when complete (~3 weeks), not incrementally

---

## Next Steps

**Week 1**: Scope checking
- Create `ScopedVar`, `ScopedAbs` in `surface/types.py`
- Implement `ScopeChecker` class
- Handle top-level declarations

**Week 2**: Type elaboration
- Create `TypeElaborator` (refactored from current)
- Bidirectional type checking
- Unification

**Week 3**: Pipeline and cleanup
- Pipeline orchestration
- LLM pragma pass
- Delete old elaborator
- Update REPL

---

## References

All documentation in `systemf/docs/`:
- `DESIGN_DECISIONS.md` - Running log of decisions
- `elaborator-implementation-plan.md` - Implementation roadmap
- `scoped-extended-ast-design.md` - Surface AST extension design

**Last Updated**: 2026-03-02
