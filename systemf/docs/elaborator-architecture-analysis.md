# Elaborator Architecture Analysis

## Current State

### The Problem: Test Failure

```
FAILED tests/test_surface/test_elaborator.py::TestElaborateIntLit::test_elab_int_in_let
parsy.ParseError: expected "expected keyword 'in', got IDENT" at 4
```

The test tries to parse: `"let x = 42\n  x"`

But the parser expects: `let x = 42 in x` (same line) OR multi-line layout mode

**Root Cause**: The let parser uses `block_entries(AtPos(col), let_binding)` which expects bindings at a specific column, then `must_continue(constraint, "in")` for the terminator. When parsing with `AnyIndent()`, the constraint allows anything, but the layout detection for the body doesn't handle this case properly.

### Immediate Fix Needed

The test expects single-line let syntax: `let x = 42 in x`
The current parser supports this but the test uses newline + indentation instead.

Let me check what the test actually expects...

Looking at the test (line 303):
```python
surface = parse_term("let x = 42\n  x")
```

This is the problem! The test expects `let x = 42 in x` (with explicit `in` keyword). The newline + indented `x` is trying to be the body without `in`.

**The fix**: Either:
1. Fix the test to use proper syntax: `"let x = 42 in x"`
2. OR support a layout mode where `in` can be omitted if body is at specific column

Given System F design, we should require explicit `in`. **Fix the test**.

---

## Multi-Pass Elaboration Architecture

Based on research of Idris 2, Agda, and GHC, here's the ideal architecture:

### Pass 1: Parsing
**Input**: Source text  
**Output**: Surface AST (name-based, with sugar)  
**Responsibilities**:
- Lexical analysis (tokens)
- Syntax analysis (AST)
- Layout-sensitive parsing (indentation)
- Error: Syntax errors, indentation errors

**Current Status**: ✅ Complete with new parser

### Pass 2: Scope Checking  
**Input**: Surface AST  
**Output**: Scoped AST (de Bruijn indices, well-scoped)  
**Responsibilities**:
- Name resolution (qualified names)
- Build symbol tables (imports, exports)
- Convert names to de Bruijn indices
- Check for undefined variables
- Error: Undefined variables, duplicate definitions

**Current Status**: ⚠️ Partially in elaborator.py but needs separation

### Pass 3: Type Inference & Elaboration
**Input**: Scoped AST  
**Output**: Core AST + Type Information  
**Responsibilities**:
- Type inference with unification
- Constraint solving
- Implicit argument synthesis (if we add implicits)
- Translation to core language
- Error: Type mismatches, unification failures

**Current Status**: ⚠️ Currently mixed with scope checking

### Pass 4: Type Checking / Validation
**Input**: Core AST  
**Output**: Verified Core AST  
**Responsibilities**:
- Verify core terms are well-typed
- Totality checking (termination)
- Pattern coverage checking
- Error: Remaining type errors, non-termination

**Current Status**: ❌ Not separated

### Pass 5: Desugaring & Optimization
**Input**: Core AST  
**Output**: Simplified Core AST  
**Responsibilities**:
- Remove syntactic sugar
- Case tree compilation
- Optimizations
- Error: None (shouldn't fail)

**Current Status**: ✅ In desugar.py

---

## Top-Level vs Local Declarations

### Key Differences

| Aspect | Top-Level | Local (let) |
|--------|-----------|-------------|
| **Scope** | Module-wide | Expression-bound |
| **Recursion** | Supports mutual recursion | Single recursive binding (via fix) |
| **Type Generalization** | Generalize free vars to forall | Monomorphic (no generalization) |
| **Evaluation** | Lazy shared definitions | Strict or lazy depending on semantics |
| **Ordering** | Order-independent | Sequential |
| **Visibility** | Can be exported | Private to expression |

### Why the Distinction?

1. **Nominal Recursion**: Top-level supports forward references:
   ```haskell
   even n = if n == 0 then True else odd (n - 1)
   odd n = if n == 0 then False else even (n - 1)
   ```
   Both can reference each other because declarations are collected first, then elaborated.

2. **REPL Use Case**: In a REPL, you add definitions incrementally:
   ```
   > let x = 5      -- This is 'top-level' for the session
   > let y = x + 1  -- Can reference previous 'top-level' definitions
   ```
   Top-level semantics allow referencing previous definitions.

3. **Let Generalization**: In Hindley-Milner, top-level declarations get polymorphic types:
   ```haskell
   id x = x           -- id :: forall a. a -> a
   
   let id = \x -> x   -- id :: t -> t (monomorphic in the let)
   in (id 5, id True) -- Would fail without generalization
   ```
   The `let` binding for `id` above is NOT polymorphic unless we perform let-generalization.

4. **Performance**: Top-level definitions are compiled once, while local let bindings may be instantiated multiple times.

### How Other Languages Handle This

**Haskell/GHC**:
- Top-level: `f x = ...` - Generalized polymorphic types
- Local let: `let f = ... in ...` - Monomorphic unless explicit type sig
- GHC has `-XMonoLocalBinds` to make local bindings monomorphic

**Idris 2**:
- Top-level: Type declarations + definitions, mutually recursive
- Local let: Sequential, can be recursive with `let rec`
- All declarations collected, then elaborated together

**OCaml**:
- Top-level `let`: Generalized (value restriction applies)
- Local `let`: Same generalization rules
- `let rec` for mutual recursion

**Rust**:
- Top-level `fn`: Always available module-wide
- Local bindings: Sequential, no forward references

---

## Refactoring Plan

### Phase 1: Fix Immediate Parser/Test Issues

1. Fix the let expression test - use proper syntax
2. Verify all parser tests pass
3. Update REPL to use new parser API

### Phase 2: Separate Scope Checking

Create `systemf.surface.scope` module:

```python
class ScopeChecker:
    """Pass 2: Convert Surface AST to Scoped AST."""
    
    def check_declaration(self, decl: SurfaceDeclaration) -> ScopedDeclaration:
        # Name resolution
        # Build de Bruijn indices
        # Check for undefined variables
        pass
```

### Phase 3: Separate Type Inference

Create `systemf.surface.inference` module:

```python
class TypeInference:
    """Pass 3: Infer types and elaborate to core."""
    
    def infer_term(self, term: ScopedTerm, expected_type: Optional[Type]) -> tuple[core.Term, Type]:
        # Bidirectional type checking
        # Unification
        # Constraint solving
        pass
```

### Phase 4: Separate Type Checking

Create `systemf.core.checker` module (already exists, expand it):

```python
def check_module(module: Module) -> Module:
    """Pass 4: Verify core terms are well-typed."""
    pass
```

---

## Key Design Decisions

### 1. De Bruijn Indices vs Names

**Current**: Names in surface, de Bruijn in core  
**Rationale**: 
- Surface: Easier error messages, readable AST
- Core: Alpha-equivalence for free, easier substitution

### 2. Explicit vs Implicit Arguments

**Current**: Explicit only (System F, not System F_ω with implicits)  
**Future**: Could add implicit arguments à la Idris

### 3. Top-Level Collection Strategy

**Current**: Single pass, collect globals before elaborating bodies  
**Idris Style**: Multi-pass
1. Collect all top-level names
2. Elaborate data types (need types for constructors)
3. Elaborate type signatures (for generalization)
4. Elaborate term bodies (with full environment)

### 4. Let Generalization

**Current**: No generalization (simplest)  
**Hindley-Milner**: Generalize at let-bindings  
**Trade-off**: 
- No generalization: Simpler, but `let id = \x -> x in ...` won't work polymorphically
- With generalization: More powerful, but need to track free type variables

**Recommendation**: Start without, add later if needed.

---

## Is Core Type Checking Part of Elaboration?

**Short Answer**: No, they are separate phases.

**Elaboration** = Surface → Core + Type synthesis  
**Type Checking** = Verify Core is well-typed

**Why separate?**

1. **Trust**: Core type checker is small, trusted kernel
2. **Debugging**: Can check intermediate results
3. **Extensions**: Elaborator can be complex, checker stays simple
4. **Verification**: Core checker can be formally verified independently

**In System F**:
- Our elaborator does both synthesis and produces Core
- We should have a separate pass that verifies the Core
- The checker in `core/checker.py` currently does type reconstruction
- Ideally: Elaborator produces fully-typed Core, checker verifies it

---

## Next Steps

### Immediate (Today)
1. ✅ Fix the let expression test
2. ✅ Update REPL to use new parser
3. ✅ Ensure all tests pass

### Short Term (This Week)
1. Separate scope checking from elaboration
2. Document the multi-pass pipeline
3. Add proper error reporting at each phase

### Medium Term (This Month)
1. Implement separate type inference pass
2. Add type generalization for top-level declarations
3. Support mutual recursion properly

### Long Term
1. Add implicit arguments
2. Implement termination checking
3. Case tree compilation for pattern matching

---

## Summary

The elaborator currently mixes scope checking, name resolution, and type elaboration. Following Idris 2's design, we should separate these into distinct passes:

1. **Parse** → Surface AST (✅ Done)
2. **Scope Check** → Scoped AST (de Bruijn indices)  
3. **Type Elaborate** → Core AST + Types
4. **Type Check** → Verified Core

Top-level declarations need special handling for:
- Forward references / mutual recursion
- Type generalization
- REPL incremental definitions

Local let bindings are simpler:
- Sequential evaluation
- Monomorphic (no generalization by default)
- Private scope

The key insight from Idris 2: **Collect all top-level declarations first, then elaborate them together**. This enables mutual recursion and proper generalization.
