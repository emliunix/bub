# Multi-Pass Elaborator Refactoring Plan

## Goal

Refactor the elaborator from a single-pass design to a **multi-pass pipeline** following Idris 2's architecture:

```
Surface AST  →  Scoped AST  →  Core AST
  (names)       (de Bruijn)    (typed)
```

This separation enables:
- **Better error messages**: Scope errors vs type errors are distinct
- **Easier debugging**: Can inspect intermediate representations
- **Clearer architecture**: Each pass has a single responsibility
- **Easier extension**: Adding new features touches one pass

---

## Current State

**Single-pass elaborator** (`surface/elaborator.py`):
- Parses surface terms
- Resolves names to de Bruijn indices
- Performs type checking
- Produces Core AST

**Problems**:
- Name resolution and type checking are interleaved
- Hard to test scope checking independently
- Type errors may be reported before all names are resolved
- Can't easily add features like implicit arguments

---

## Proposed Architecture

### Phase 1: Scope Checking (Surface → Scoped)

**Module**: `systemf.surface.scope`

**Input**: `SurfaceTerm`, `SurfaceDeclaration`
**Output**: `ScopedTerm`, `ScopedDeclaration`

**Responsibilities**:
1. **Name resolution**: Convert names to de Bruijn indices
2. **Import handling**: Resolve qualified names
3. **Operator resolution**: Fix precedences
4. **Shadowing detection**: Report shadowed variables
5. **Forward reference checking**: Ensure names exist

**Scoped AST Types**:

```python
@dataclass
class ScopedTerm:
    """Term after scope checking but before type checking.
    
    Uses de Bruijn indices like Core, but no types yet.
    """
    source_loc: Location
    
@dataclass  
class ScopedVar(ScopedTerm):
    index: int  # de Bruijn index
    
@dataclass
class ScopedAbs(ScopedTerm):
    var_name: str  # For error messages
    body: ScopedTerm
    
@dataclass
class ScopedApp(ScopedTerm):
    func: ScopedTerm
    arg: ScopedTerm

# ... similar for other term constructors
```

**Key insight**: Scoped AST has the same structure as Core but:
- No type annotations
- May have unresolved implicit arguments (holes)
- Source locations preserved

**Scope Checker Monad**:

```python
@dataclass
class ScopeState:
    term_env: list[str]  # Names in scope (index 0 = most recent)
    type_env: set[str]   # Type variables in scope
    globals: set[str]    # Top-level definitions
    imports: dict[str, Module]  # Imported modules

ScopeM = State[ScopeState, Result[T, ScopeError]]
```

---

### Phase 2: Type Elaboration (Scoped → Core)

**Module**: `systemf.surface.inference`

**Input**: `ScopedTerm`, `ScopedDeclaration`  
**Output**: `Core.Term`, `Core.Declaration`

**Responsibilities**:
1. **Type inference**: Synthesize types from terms
2. **Type checking**: Verify terms against expected types
3. **Unification**: Solve type constraints
4. **Implicit synthesis**: Fill in holes (future feature)
5. **Translation to Core**: Produce fully-typed AST

**Elaborator Monad**:

```python
@dataclass
class ElabState:
    context: Context  # Typing context
    metavariables: dict[MetaVarId, MetaVar]  # For unification
    constraints: list[Constraint]  # Deferred constraints
    source_map: dict[int, Location]  # For error reporting

ElabM = State[ElabState, Result[T, TypeError]]
```

**Bidirectional Type Checking**:

```python
def infer(term: ScopedTerm) -> ElabM[Core.Term, Type]:
    """Synthesize type from term (bottom-up)."""
    
def check(term: ScopedTerm, expected: Type) -> ElabM[Core.Term]:
    """Check term against expected type (top-down)."""
```

---

### Phase 3: Verification (Core → Verified Core)

**Module**: `systemf.core.verifier`

**Input**: `Core.Term`, `Core.Declaration`  
**Output**: Verified Core (or errors)

**Responsibilities**:
1. **Type soundness**: Verify Core is well-typed
2. **Coverage checking**: Ensure patterns are exhaustive
3. **Termination checking**: Verify recursive functions terminate
4. **Totality**: Check for partial functions

**Note**: This is like Lean 4's kernel - a small, trusted verifier.

---

## Top-Level Declaration Handling

**Challenge**: Top-level declarations need special handling for:
- Forward references (mutual recursion)
- Type generalization
- REPL incremental definitions

**Idris 2 Strategy**:

```python
def elaborate_module(decls: list[SurfaceDeclaration]) -> Result[Module, list[SystemFError]]:
    # Pass 1: Scope check all declarations
    scoped_decls = []
    for decl in decls:
        match scope_check_declaration(decl):
            case Ok(scoped):
                scoped_decls.append(scoped)
            case Err(errors):
                return Err(errors)
    
    # Pass 2: Collect signatures
    signatures = collect_signatures(scoped_decls)
    
    # Pass 3: Elaborate type signatures
    type_signatures = {}
    for name, sig in signatures.items():
        match elaborate_type_sig(sig):
            case Ok(ty):
                type_signatures[name] = ty
            case Err(error):
                return Err([error])
    
    # Pass 4: Elaborate bodies (with all signatures in scope)
    declarations = []
    for decl in scoped_decls:
        match elaborate_declaration(decl, type_signatures):
            case Ok(core_decl):
                declarations.append(core_decl)
            case Err(error):
                return Err([error])
    
    # Pass 5: Verify
    for decl in declarations:
        match verify_declaration(decl):
            case Err(error):
                return Err([error])
    
    return Ok(Module(declarations=declarations, ...))
```

**Why this order?**
1. All names must be resolved before type checking
2. Type signatures must be elaborated before bodies (for generalization)
3. Bodies can reference any top-level definition (mutual recursion)
4. Verification happens last (kernel check)

---

## Data Structures

### 1. Surface AST (existing)

Already exists in `surface/types.py`:
- Names (strings)
- Optional type annotations
- Syntactic sugar
- Source locations

### 2. Scoped AST (new)

New module: `surface/scoped/types.py`

```python
@dataclass(frozen=True)
class ScopedTerm:
    """Base class for scoped terms."""
    source_loc: Location

@dataclass(frozen=True)
class ScopedVar(ScopedTerm):
    index: int  # de Bruijn index
    original_name: str  # For error messages

@dataclass(frozen=True)
class ScopedAbs(ScopedTerm):
    var_name: str  # Original name for error messages
    body: ScopedTerm

@dataclass(frozen=True)
class ScopedApp(ScopedTerm):
    func: ScopedTerm
    arg: ScopedTerm

@dataclass(frozen=True)
class ScopedTypeAbs(ScopedTerm):
    var: str
    body: ScopedTerm

@dataclass(frozen=True)
class ScopedTypeApp(ScopedTerm):
    func: ScopedTerm
    type_arg: ScopedType

# ... etc

ScopedType = ScopedTypeVar | ScopedTypeArrow | ScopedTypeForall | ...
```

**Key differences from Surface**:
- Variables use de Bruijn indices
- All names are resolved
- No type annotations yet

### 3. Core AST (existing, updated)

Already has `source_loc`. No changes needed.

---

## Implementation Plan

### Step 1: Create Scoped AST (Week 1)

**Tasks**:
1. Create `surface/scoped/` package
2. Define `ScopedTerm`, `ScopedType`, `ScopedDeclaration`
3. Add conversion helpers: `Surface → Scoped`
4. Write tests for Scoped AST

**Files**:
```
src/systemf/surface/scoped/
├── __init__.py
├── types.py          # Scoped AST definitions
└── test_types.py     # Unit tests
```

### Step 2: Implement Scope Checker (Week 1-2)

**Tasks**:
1. Create `ScopeChecker` class
2. Implement `check_term()` for each term type
3. Implement `check_declaration()`
4. Handle imports and modules
5. Write comprehensive tests

**Key algorithms**:
- Name resolution: lookup in `term_env` (list of names)
- Index calculation: position in `term_env`
- Import resolution: qualified name lookup

**Files**:
```
src/systemf/surface/scoped/
├── checker.py        # Scope checking logic
├── errors.py         # ScopeError types
├── context.py        # Scope checking context
└── test_checker.py   # Tests
```

### Step 3: Refactor Elaborator (Week 2-3)

**Tasks**:
1. Split current elaborator:
   - Move name resolution to scope checker
   - Keep type elaboration in elaborator
2. Update `Elaborator` to take `ScopedTerm` instead of `SurfaceTerm`
3. Update all tests to use new pipeline
4. Remove name resolution code from elaborator

**Files to modify**:
```
src/systemf/surface/
├── elaborator.py     # Simplified - only type elaboration
└── __init__.py       # Update public API
```

### Step 4: Pipeline Integration (Week 3)

**Tasks**:
1. Create `elaborate_module()` that orchestrates all passes
2. Implement top-level declaration handling
3. Add mutual recursion support
4. Update REPL to use new pipeline

**Files**:
```
src/systemf/surface/
├── pipeline.py       # Multi-pass orchestration
└── module.py         # Module-level elaboration
```

### Step 5: Error Handling (Week 4)

**Tasks**:
1. Ensure errors have source locations
2. Add error context (which pass failed)
3. Implement error recovery (continue after errors)
4. Add helpful diagnostics

**Example**:
```
error: Undefined variable 'x'
  --> test.sf:5:10
  |
5 |   let y = x + 1
  |           ^
  |
  = did you mean 'xs'? (scope checking phase)
```

### Step 6: Verification (Week 4-5)

**Tasks**:
1. Create `CoreVerifier` (like Lean 4's kernel)
2. Verify all Core terms are well-typed
3. Add pattern coverage checking
4. Make verification optional for development speed

**Files**:
```
src/systemf/core/
├── verifier.py       # Core verification
└── test_verifier.py  # Tests
```

---

## Migration Strategy

**Phase 1: Parallel Implementation** (Steps 1-2)
- Create new scope checker alongside existing elaborator
- Don't break existing code
- Run both and compare results

**Phase 2: Gradual Switch** (Step 3)
- Update tests to use new pipeline
- Fix any discrepancies
- Deprecate old elaborator

**Phase 3: Full Migration** (Steps 4-6)
- Remove old single-pass elaborator
- Update all imports
- Add verification

---

## API Design

### Public API (unchanged for users)

```python
from systemf.surface import parse_program, elaborate_program

# Parse surface syntax
decls = parse_program(source_code)

# Elaborate to Core (now multi-pass internally)
result = elaborate_program(decls)

match result:
    case Ok(module):
        # Use module
    case Err(errors):
        for error in errors:
            print(error)  # Rich error with location
```

### Internal API (for advanced use)

```python
from systemf.surface.scope import ScopeChecker
from systemf.surface.inference import TypeElaborator
from systemf.core.verifier import CoreVerifier

# Access individual passes
scope_checker = ScopeChecker()
scoped = scope_checker.check_term(surface_term)

elaborator = TypeElaborator()
core_term, ty = elaborator.infer(scoped)

verifier = CoreVerifier()
verifier.verify(core_term, ty)
```

---

## Testing Strategy

### Unit Tests (each pass)

```python
# Test scope checking
class TestScopeChecker:
    def test_variable_lookup(self):
        term = SurfaceVar("x", loc)
        ctx = ScopeContext(["y", "x"])  # x is index 1
        result = check_term(term, ctx)
        assert result == ScopedVar(index=1, original_name="x", source_loc=loc)

# Test type elaboration
class TestTypeElaboration:
    def test_identity_function(self):
        scoped = ScopedAbs("x", ScopedVar(0))
        core, ty = elaborate(scoped)
        assert isinstance(core, Abs)
        assert isinstance(ty, TypeForall)
```

### Integration Tests (full pipeline)

```python
class TestPipeline:
    def test_end_to_end(self):
        source = "let id = \\x -> x in id 5"
        decls = parse_program(source)
        module = elaborate_program(decls).unwrap()
        assert "id" in module.global_types
```

### Property Tests

```python
# Well-scoped terms should always elaborate
@given(well_scoped_term())
def test_well_scoped_elaborates(term):
    result = elaborate(term)
    assert result.is_ok()
```

---

## Benefits After Refactoring

1. **Clear separation**: Each pass has one job
2. **Better errors**: Know which phase failed
3. **Testability**: Can test scope checking without type checker
4. **Debugging**: Can print Scoped AST to see name resolution
5. **Extension**: Easy to add implicits, type classes, etc.
6. **Performance**: Can cache scope-checked results
7. **Verification**: Kernel can verify Core independently

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking changes | Keep old API, implement in parallel |
| Performance regression | Benchmark each phase, optimize hotspots |
| Complex error messages | Add phase info to errors |
| Test failures | Run both pipelines, compare outputs |
| Scope creep | Focus on scope checking first, add features later |

---

## Timeline

| Week | Deliverable |
|------|-------------|
| 1 | Scoped AST + Scope Checker |
| 2 | Scope Checker complete + tests |
| 3 | Refactor Elaborator, update tests |
| 4 | Pipeline integration, error handling |
| 5 | Verification, cleanup, documentation |

**Total**: ~5 weeks for full migration

---

## Immediate Next Steps

1. **Create `surface/scoped/types.py`** with `ScopedTerm` definitions
2. **Implement basic scope checker** for variables and lambdas
3. **Write tests** comparing Surface → Scoped → Core
4. **Gradually expand** to cover all term types
5. **Update main elaborator** to use scope checker

The key is to start small: get variable lookup working end-to-end, then expand.
