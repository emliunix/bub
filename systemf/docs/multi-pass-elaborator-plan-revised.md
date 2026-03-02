# Multi-Pass Elaborator Plan (Revised)

## Philosophy

**No gradual migration.** We implement the correct architecture directly. The system won't work until all pieces are in place, then it works correctly.

## Pipeline Overview

```
Surface AST  →  Scoped AST  →  Core AST
  (names)       (de Bruijn)    (typed)
```

**Three passes only**:
1. **Scope** - Name resolution
2. **Inference** - Type checking + elaboration  
3. **LLM** - Pragma extraction and processing

---

## Why Scope Checking?

**Purpose**: Separate name resolution from type checking.

**Without scope checking**:
```python
# Type checker has to do name lookup
if name in term_env:
    return Var(term_env[name])  # Mixed concerns!
else:
    raise TypeError("Undefined variable")  # Wrong error type
```

**With scope checking**:
```python
# Scope checker: pure name resolution
if name in scope:
    return ScopedVar(index=scope.lookup(name))
else:
    raise ScopeError("Undefined variable")  # Correct error type

# Type checker: assumes names are resolved
def infer(scoped_term):
    match scoped_term:
        case ScopedVar(index):  # Index already computed
            return context.lookup(index)  # Just type lookup
```

**Benefits**:
1. **Better errors**: "Undefined variable 'x'" vs "Type error: None is not a type"
2. **Clear separation**: Scope errors ≠ Type errors
3. **Easier testing**: Can test name resolution without type checker
4. **Foundation for implicits**: Need clean scope before type inference can add implicit args

---

## Pass 1: Scope Checking

**Input**: `SurfaceTerm` (names)
**Output**: `ScopedTerm` (de Bruijn indices, no types)

**What it does**:
- Name → de Bruijn index conversion
- Import resolution
- Detect undefined variables
- Handle shadowing

**What it DOESN'T do**:
- Type checking
- Unification
- Any type-related work

**ScopedTerm structure**:
```python
@dataclass
class ScopedVar:
    source_loc: Location
    index: int           # de Bruijn index (0 = nearest)
    original_name: str   # For error messages

@dataclass
class ScopedAbs:
    source_loc: Location
    var_name: str        # Original name
    body: ScopedTerm

@dataclass
class ScopedApp:
    source_loc: Location
    func: ScopedTerm
    arg: ScopedTerm

# No type annotations anywhere!
```

**Result**: A well-scoped AST where all names are resolved but no types exist.

---

## Pass 2: Type Elaboration (Inference)

**Input**: `ScopedTerm` (de Bruijn, untyped)
**Output**: `Core.Term` (de Bruijn, **fully typed**)

**What it does**:
- Bidirectional type checking
- Unification (constraint solving)
- Translation to Core

**Key question**: Do we elaborate untyped Core then infer, or infer during elaboration?

**Answer**: **Infer during elaboration to typed Core.**

```python
# DON'T: Create untyped Core, then infer
def elaborate(scoped_term) -> UntypedCore:
    ...

def infer_types(untyped_core) -> TypedCore:
    ...

# DO: Elaborate directly to typed Core
def elaborate(scoped_term) -> tuple[Core.Term, Type]:
    """Returns fully typed Core term and its type."""
    match scoped_term:
        case ScopedAbs(var_name, body):
            # Create fresh type variable
            arg_ty = fresh_meta()
            # Check body with arg_ty in context
            core_body, body_ty = elaborate(body, context.extend(arg_ty))
            # Return typed lambda
            return (
                Core.Abs(arg_ty, core_body, location),  # Fully typed!
                TypeArrow(arg_ty, body_ty)
            )
```

**Why typed Core directly?**
- Core AST requires types (Abs needs `var_type`)
- No intermediate "untyped Core" representation needed
- Cleaner architecture
- Matches Idris 2's approach

---

## Pass 3: LLM Pragma Processing

**Input**: `SurfaceDeclaration` with pragma
**Output**: `Core.TermDeclaration` with processed body

**What it does**:
- Extract pragma parameters
- Replace function body with PrimOp
- Build LLM metadata
- Handle special case: LLM functions don't have executable bodies

```python
class LLMPragmaPass:
    def process_term_decl(self, decl: SurfaceTermDeclaration) -> Core.TermDeclaration:
        if decl.pragma:
            # Extract pragma parameters
            params = parse_pragma(decl.pragma)
            
            # Replace body with PrimOp
            body = Core.PrimOp(f"llm.{decl.name}", location=decl.location)
            
            return Core.TermDeclaration(
                name=decl.name,
                type_annotation=core_type,
                body=body,
                pragma=decl.pragma,
                docstring=decl.docstring,
                param_docstrings=decl.param_docstrings
            )
        else:
            # Normal function - pass through
            return elaborated_decl
```

**Why separate pass?**
- LLM functions are special (no real body)
- Keeps main elaborator clean
- Easy to disable LLM support
- Can add more pragma types later

---

## Pipeline Orchestration

```python
def elaborate_module(decls: list[SurfaceDeclaration]) -> Result[Module, list[SystemFError]]:
    scope_checker = ScopeChecker()
    elaborator = TypeElaborator()
    llm_pass = LLMPragmaPass()
    
    # Pass 1: Scope check all declarations
    scoped_decls = []
    for decl in decls:
        match scope_checker.check_declaration(decl):
            case Ok(scoped):
                scoped_decls.append(scoped)
            case Err(errors):
                return Err(errors)
    
    # Pass 2: Collect signatures (for mutual recursion)
    signatures = collect_signatures(scoped_decls)
    
    # Pass 3: Elaborate type signatures
    type_sigs = {}
    for name, sig in signatures.items():
        match elaborator.elaborate_type(sig):
            case Ok(ty):
                type_sigs[name] = ty
            case Err(error):
                return Err([error])
    
    # Pass 4: Elaborate bodies (with all types in scope)
    core_decls = []
    for scoped_decl in scoped_decls:
        match elaborator.elaborate_declaration(scoped_decl, type_sigs):
            case Ok(core_decl):
                core_decls.append(core_decl)
            case Err(error):
                return Err([error])
    
    # Pass 5: Process LLM pragmas
    final_decls = []
    for i, decl in enumerate(core_decls):
        surface_decl = decls[i]  # Get original surface decl for pragma
        final_decl = llm_pass.process(surface_decl, decl)
        final_decls.append(final_decl)
    
    return Ok(Module(declarations=final_decls, ...))
```

---

## Module Structure

```
src/systemf/
├── surface/
│   ├── __init__.py          # Public API
│   ├── types.py             # Surface AST (existing)
│   ├── parser/              # Parser (existing)
│   │   └── ...
│   ├── scope/               # Pass 1: Scope checking
│   │   ├── __init__.py
│   │   ├── types.py         # Scoped AST
│   │   ├── checker.py       # ScopeChecker class
│   │   ├── context.py       # ScopeContext
│   │   └── errors.py        # ScopeError
│   ├── inference/           # Pass 2: Type elaboration
│   │   ├── __init__.py
│   │   ├── elaborator.py    # TypeElaborator class
│   │   ├── context.py       # TypeContext
│   │   ├── unification.py   # Unification
│   │   └── errors.py        # TypeError
│   └── llm/                 # Pass 3: LLM pragma
│       ├── __init__.py
│       ├── pragma.py        # Pragma parsing
│       ├── pass.py          # LLMPragmaPass
│       └── metadata.py      # LLMMetadata extraction
└── core/
    ├── ast.py               # Core AST (typed)
    ├── types.py             # Type representations
    └── errors.py            # SystemFError hierarchy
```

---

## Implementation Strategy

**All or nothing.** We don't keep old code working.

### Phase 1: Scoped AST (1-2 days)
1. Create `surface/scope/types.py` with `ScopedTerm`
2. Mirror Surface AST structure but with indices
3. Write conversion tests

### Phase 2: Scope Checker (2-3 days)
1. Create `surface/scope/checker.py`
2. Implement `check_term()` for each term type
3. Start with variables and lambdas
4. Expand to all constructs
5. Handle top-level declarations

### Phase 3: Type Elaborator (3-4 days)
1. Create `surface/inference/elaborator.py`
2. Implement bidirectional type checking
3. Handle unification
4. Produce typed Core
5. Move code from old elaborator

### Phase 4: LLM Pass (1 day)
1. Create `surface/llm/pass.py`
2. Extract pragma handling from old code
3. Wire into pipeline

### Phase 5: Pipeline (1 day)
1. Create `surface/pipeline.py`
2. Wire all passes together
3. Handle top-level declaration collection
4. Update public API

### Phase 6: Cleanup (1 day)
1. Delete old elaborator
2. Update all imports
3. Fix tests
4. Update REPL

**Total: ~2 weeks**

---

## Key Decisions

1. **Scope checking is mandatory**: Separates concerns, better errors
2. **Typed Core directly**: No untyped Core representation
3. **No verification pass**: Trust the elaborator (for now)
4. **LLM is separate**: Keeps main elaborator clean
5. **All at once**: No gradual migration, system works when done

---

## Testing

Each pass tested independently:

```python
# Test scope checking
class TestScope:
    def test_variable(self):
        surface = SurfaceVar("x", loc)
        ctx = ScopeContext(["y", "x"])
        scoped = check_term(surface, ctx)
        assert scoped == ScopedVar(loc, index=1, original_name="x")

# Test elaboration  
class TestInference:
    def test_identity(self):
        scoped = ScopedAbs(loc, "x", ScopedVar(loc, 0, "x"))
        core, ty = elaborate(scoped)
        assert isinstance(core, Core.Abs)
        assert isinstance(ty, TypeArrow)

# Test full pipeline
class TestPipeline:
    def test_end_to_end(self):
        source = "let id = \\x -> x in id 5"
        result = elaborate_module(parse_program(source))
        assert result.is_ok()
```

---

## When It Works

The system works when:
1. All surface terms can be scope-checked
2. All scoped terms can be elaborated to typed Core
3. All errors have source locations
4. All tests pass
5. REPL works

**No partial functionality.** It's either correct or it doesn't work.
