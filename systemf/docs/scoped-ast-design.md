# Scoped AST Design: De Bruijn Indices with Name Preservation

## The Problem

When we convert names to de Bruijn indices during scope checking:
```
Surface:  \x -> \y -> x y
Scoped:   λ. λ. x1 x0   (de Bruijn indices)
```

**Question**: How do we report "Undefined variable 'z'" instead of "Undefined variable at index 5"?

## Solution: Store Names Alongside Indices

### Idris 2 Approach (TTImp)

Idris 2 stores **both** the de Bruijn index AND the original name:

```idris
-- In TTImp (Scoped AST)
data Term = 
  | Local Int String  -- index AND original name
  | ...
```

**Why both?**
- **Index (Int)**: For substitution, comparison, lookup
- **Name (String)**: For error messages only

### Our Implementation

```python
@dataclass(frozen=True)
class ScopedVar(ScopedTerm):
    """Variable reference with de Bruijn index and original name."""
    
    index: int           # De Bruijn index (0 = nearest binder)
    original_name: str   # Original name for error reporting
    
    def __str__(self) -> str:
        # Show original name in error messages
        return self.original_name

@dataclass(frozen=True)
class ScopedAbs(ScopedTerm):
    """Lambda abstraction with original parameter name."""
    
    var_name: str        # Original parameter name
    body: ScopedTerm
    
    def __str__(self) -> str:
        return f"λ{self.var_name}. {self.body}"
```

**Example**:
```python
# Surface:  \x -> \y -> x y
# Scoped:
ScopedAbs(
    var_name="x",
    body=ScopedAbs(
        var_name="y", 
        body=ScopedApp(
            ScopedVar(index=1, original_name="x"),  # x is index 1
            ScopedVar(index=0, original_name="y")   # y is index 0
        )
    )
)
```

## The Context: Tracking Names to Indices

During scope checking, we maintain a **name → index mapping**:

```python
@dataclass
class ScopeContext:
    """Mapping from names to de Bruijn indices."""
    
    # List of names in scope, index 0 = most recent
    term_names: list[str]
    type_names: set[str]
    
    def lookup_term(self, name: str) -> int:
        """Get de Bruijn index for a name.
        
        Returns:
            Index where 0 = most recent binding
            
        Raises:
            ScopeError: Name not in scope
        """
        for i, n in enumerate(self.term_names):
            if n == name:
                return i
        raise ScopeError(f"Undefined variable: '{name}'")
    
    def extend_term(self, name: str) -> "ScopeContext":
        """Add new binding, becomes index 0."""
        return ScopeContext([name] + self.term_names, self.type_names)
```

**Scope checking a variable**:
```python
def check_var(name: str, location: Location, ctx: ScopeContext) -> ScopedVar:
    try:
        index = ctx.lookup_term(name)
        return ScopedVar(
            source_loc=location,
            index=index,
            original_name=name  # Keep name for errors!
        )
    except ScopeError as e:
        raise ScopeError(f"Undefined variable '{name}'", location) from e
```

## Type Variables: Same Pattern

Type variables also use de Bruijn indices in the Scoped AST:

```python
@dataclass(frozen=True)
class ScopedTypeVar(ScopedType):
    """Type variable with index and original name."""
    
    index: int           # De Bruijn index for type variables
    original_name: str   # Original name for error reporting

@dataclass(frozen=True)
class ScopedTypeAbs(ScopedTerm):
    """Type abstraction with original type variable name."""
    
    var_name: str        # "a", "b", etc.
    body: ScopedTerm
```

**Context for type variables**:
```python
@dataclass
class ScopeContext:
    term_names: list[str]
    type_names: list[str]  # Now a list to track order
    
    def lookup_type(self, name: str) -> int:
        for i, n in enumerate(self.type_names):
            if n == name:
                return i
        raise ScopeError(f"Undefined type variable: '{name}'")
```

## Why Not Store Names in Core AST?

**Question**: Should Core AST store names too?

**Answer**: No, Core AST should be minimal. But...

**However**: We already added `source_loc` to Core AST, which gives us file/line/column. We could optionally keep names in Core for debugging.

**Idris 2's approach**:
- TT (Core): Minimal, only indices
- TTImp (Scoped): Indices + names
- Info trees: Separate mapping for IDE features

**Our approach**:
- Core: Keep `source_loc` (already done), optionally add `debug_name`
- Scoped: Indices + names (for scope checking phase)

```python
@dataclass(frozen=True)
class Var(CoreTerm):
    """Variable in Core AST."""
    
    index: int
    # source_loc inherited from CoreTerm (for error reporting)
    # Could add: debug_name: Optional[str] = None
```

## Error Reporting Flow

**Scenario**: Type checking finds a type mismatch with variable `x`

```python
# 1. Scope checking converts name to index + preserves name
surface = SurfaceVar("x", location)
scoped = ScopedVar(index=1, original_name="x", source_loc=location)

# 2. Type elaboration produces Core (loses name, keeps location)
core = Var(index=1, source_loc=location)

# 3. Type checking finds error
#    - Uses index to look up type in context
#    - Uses source_loc for error location
#    - Could use debug_name if we added it

def report_error(term: Core.Term, expected: Type, actual: Type):
    location = term.source_loc  # line 5, column 10
    raise TypeMismatch(
        expected=expected,
        actual=actual,
        location=location,
        term=term  # Var(1) - could include debug_name here
    )
```

**Error message**:
```
error: Type mismatch
  --> test.sf:5:10
  |
5 |   x + "hello"
  |   ^
  |
  = expected: Int
  = actual: String
```

The source location points to the exact position. If we want to show the variable name, we have options:

1. **Keep name in Core** (add `debug_name` field)
2. **Source location is enough** (editor shows context)
3. **Separate mapping** (info trees like Lean/Idris)

## Complete Scoped AST Example

```python
@dataclass(frozen=True)
class ScopedTerm:
    """Base class for scoped terms."""
    source_loc: Location

@dataclass(frozen=True)
class ScopedVar(ScopedTerm):
    """Variable: de Bruijn index + original name."""
    index: int
    original_name: str

@dataclass(frozen=True)
class ScopedAbs(ScopedTerm):
    """Lambda: original name + body."""
    var_name: str
    body: ScopedTerm

@dataclass(frozen=True)
class ScopedApp(ScopedTerm):
    """Application."""
    func: ScopedTerm
    arg: ScopedTerm

@dataclass(frozen=True)
class ScopedTypeAbs(ScopedTerm):
    """Type abstraction: original type var name + body."""
    var_name: str
    body: ScopedTerm

@dataclass(frozen=True)
class ScopedTypeApp(ScopedTerm):
    """Type application."""
    func: ScopedTerm
    type_arg: ScopedType

# Types also have indices + names
@dataclass(frozen=True)
class ScopedTypeVar(ScopedType):
    """Type variable."""
    index: int
    original_name: str

@dataclass(frozen=True)
class ScopedTypeArrow(ScopedType):
    """Function type."""
    arg: ScopedType
    ret: ScopedType

@dataclass(frozen=True)
class ScopedTypeForall(ScopedType):
    """Polymorphic type."""
    var_name: str
    body: ScopedType
```

## Summary

**How to keep names with de Bruijn indices:**

1. **Scoped AST stores both**: `index: int` + `original_name: str`
2. **Names are for error messages only**: Type checking uses indices
3. **Context tracks name → index**: `ScopeContext.term_names: list[str]`
4. **Core AST minimal**: Only indices + source_loc (no names)
5. **Error reporting**: Source location is primary, names secondary

**This is the standard approach** used by:
- Idris 2 (TTImp)
- GHC (renamed AST)
- Agda (abstract syntax)
- Most dependently-typed languages
