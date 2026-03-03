# Battle Test Documentation and Binding Semantics Design

## Date: 2026-03-03

## Summary

Extended battle test documentation with comprehensive design decisions for early binding and isorecursive types. The work bridges the gap between current implementation status and future architectural direction.

## Changes Made

### 1. BATTLE_TEST_SUMMARY.md Updates

**Status Update:**
- Updated to reflect 100% test pass rate (641 passing, 0 failing)
- Documented latest achievements: kw_only dataclasses, escape sequences, elaborator tests

**New Sections Added:**

#### Unsolved Architectural Questions
Documented the binding semantics question that's been pending:
- Current late binding approach (Global terms resolve at runtime)
- Early binding alternative (capture values at elaboration)
- Research direction: isorecursive types with pack/unpack

#### Design Decision: Early Binding for REPL
Comprehensive rationale for choosing early binding:

1. **LLM Fork Isolation**
   - LLM functions require type-safe return values
   - Types used in return types must be frozen (no redefinition)
   - Context snapshots needed for forked REPL sessions

2. **REPL Context Snapshot Model**
   - Snapshot current context before LLM call
   - Fresh REPL environment for LLM computation
   - Return values type-checked against original context

3. **Isorecursive Types Elaboration**
   ```
   Surface (Nominal):    data List a = Nil | Cons a (List a)
   Core (Isorecursive):  List a = μX. Unit + (a × X)
   Elaboration:          fold/unfold at constructor boundaries
   ```

**Implementation Path:**
1. Core AST: Add `Fold`, `Unfold`, `Rec` terms
2. Elaborator: Transform nominal → isorecursive
3. Type Checker: Adapt bidirectional inference for `μX.T`
4. REPL: Context snapshot support for LLM isolation

### 2. Code Changes

#### Global __str__ Simplification
Removed `@` prefix from Global terms:
```python
# Before
def __str__(self) -> str:
    return f"@{self.name}"

# After  
def __str__(self) -> str:
    return self.name
```

**Rationale:** The `@` prefix was unnecessary visual noise. The distinction between globals and locals is handled at the AST level, not in string representation.

## Commits

- `9d41e3d` docs: Update battle test summary with latest 100% pass rate status
- `f6c7d08` refactor(systemf): Clean up syntax desugaring, parser, and type system  
- `a05e18a` docs: Document unsolved binding semantics question with isorecursive types research
- `aa5e4c2` docs: Extend binding semantics decision with LLM isolation and isorecursive elaboration

## Discussion Summary

### Why Early Binding?

The key insight came from LLM integration requirements:

1. **Type Safety Across Forks**: When an LLM function is called, we fork the REPL. The return value must be well-typed in the *original* context, not the forked one.

2. **Type Freezing**: Any type used in an LLM function's return type must be immutable. If `List` is redefined after an LLM function uses it, the return value's type becomes invalid.

3. **Context Snapshots**: Each LLM call requires:
   - Snapshot of current types, values, constructors
   - Fresh environment for the LLM computation
   - Return value validated against snapshot context

### Isorecursive vs Nominal

**Nominal recursion** (current surface syntax):
- `data List a = Nil | Cons a (List a)`
- Intuitive for programmers
- Requires special handling in type checker

**Isorecursive types** (proposed core):
- `List a = μX. Unit + (a × X)`
- Explicit fold/unfold operations
- Uniform treatment of all types
- Cleaner meta-theory

**The Plan:**
Surface language keeps nominal syntax for ergonomics, but elaborator transforms to isorecursive core. This gives us:
- User-friendly surface syntax
- Uniform core language
- Simpler type checking
- Easier to reason about semantics

## Next Steps

1. **Implement isorecursive types in core AST**
   - Add `Rec` type constructor (μX.T)
   - Add `Fold` and `Unfold` term constructors
   - Update type equality/unification

2. **Extend elaborator**
   - Transform data declarations to isorecursive types
   - Insert fold at constructor applications
   - Insert unfold in pattern matching

3. **Adapt type checker**
   - Bidirectional rules for fold/unfold
   - μX.T unification
   - Occurs check for recursive types

4. **REPL context snapshots**
   - Implement context serialization
   - Fork with isolated environment
   - Type-safe value marshaling

## References

- `BATTLE_TEST_SUMMARY.md` - Complete design rationale
- `src/systemf/core/ast.py` - Global term updated
- `journal/2026-03-03-type-system-fixes.md` - Previous type system work
