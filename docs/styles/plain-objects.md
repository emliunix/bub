# Plain Objects Style Guide

**Principle:** Objects should be plain data structures. Do not implement "magic" behavior like custom equality that violates the principle of least surprise.

## Equality by Structure, Not by Identity

**WRONG:**
```python
@dataclass(frozen=True)
class Name:
    mod: str
    surface: str  
    unique: int
    
    def __eq__(self, other):
        return isinstance(other, Name) and self.unique == other.unique
    
    def __hash__(self):
        return hash(self.unique)
```

This is surprising because:
- Two Names with same `unique` but different `surface` are equal
- `Name("x", 1, "M") == Name("y", 1, "N")` returns `True`
- This violates structural equality expectations

**RIGHT:**
```python
@dataclass(frozen=True)
class Name:
    mod: str
    surface: str
    unique: int
    # Uses default dataclass equality: all fields must match
```

If you need identity-based lookup, use a dictionary keyed by the identifying field:

```python
# Name lookup by unique
name_by_unique: dict[int, Name] = {}

# Name lookup by (module, surface)  
name_by_module_surface: dict[tuple[str, str], Name] = {}
```

## Rationale

1. **Predictability:** `a == b` means `a` and `b` have the same content
2. **Debugging:** No hidden logic when comparing objects
3. **Hash consistency:** `hash(a) == hash(b)` implies `a == b` (Python invariant)
4. **Multiple lookup keys:** Different use cases need different keys; don't bake one into __eq__

## Exception: Explicit Wrapper Types

If identity semantics are truly needed, create an explicit wrapper:

```python
@dataclass(frozen=True)
class UniqueId:
    """Explicit identity wrapper."""
    value: int
    
    def __eq__(self, other):
        return isinstance(other, UniqueId) and self.value == other.value
```

This makes the non-structural equality explicit and opt-in.

## No Quoted Forward References

**We use Python 3.12+ with PEP 695.** Forward references are resolved lazily - no need to quote them.

**WRONG:**
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .mod import Module

@dataclass
class ReaderEnv:
    modules: dict[str, "Module"]  # Quoted - unnecessary!
```

**RIGHT:**
```python
@dataclass
class ReaderEnv:
    modules: dict[str, Module]  # Unquoted - types resolved lazily
```

**Benefits:**
1. **Cleaner code:** No string quotes around types
2. **Better IDE support:** Jump-to-definition works immediately
3. **No TYPE_CHECKING blocks:** Import what you use

## Type Unions with `|` Operator

**Use the `|` operator for type unions.** This is cleaner and works with Python 3.10+.

**WRONG:**
```python
# Verbose multi-line parenthesized syntax
type SurfaceDeclarationRepr = (
    SurfaceDataDeclaration |
    SurfaceTermDeclaration |
    SurfacePrimTypeDecl |
    SurfacePrimOpDecl |
    SurfaceImportDeclaration
)

# Or even worse - Union import
type SurfaceDeclarationRepr = Union[
    SurfaceDataDeclaration,
    SurfaceTermDeclaration,
    SurfacePrimTypeDecl,
    SurfacePrimOpDecl,
    SurfaceImportDeclaration,
]
```

**RIGHT:**
```python
# Single-line with | operator
type SurfaceDeclarationRepr = SurfaceDataDeclaration | SurfaceTermDeclaration | SurfacePrimTypeDecl | SurfacePrimOpDecl | SurfaceImportDeclaration

# Or multi-line without parentheses (for very long unions)
type SurfaceDeclarationRepr = (
    SurfaceDataDeclaration
    | SurfaceTermDeclaration
    | SurfacePrimTypeDecl
    | SurfacePrimOpDecl
    | SurfaceImportDeclaration
)

# For simple binary unions
type RdrElt = LocalRdrElt | ImportRdrElt
```

**Benefits:**
1. **Concise:** Single `|` instead of multi-line blocks
2. **Modern syntax:** Python 3.10+ supports `|` everywhere
3. **Better diffs:** Adding a type is a single-line change
4. **No typing imports:** No need to import `Union` from typing

## Explicit `__init__` Without `default_factory`

**Avoid `field(default_factory=...)`** - it's magical and hides initialization logic.

**WRONG:**
```python
@dataclass
class ReaderEnv:
    table: dict[str, list[RdrElt]] = field(default_factory=dict)
    
    @staticmethod
    def empty() -> ReaderEnv:
        return ReaderEnv()
```

**RIGHT:**
```python
@dataclass
class ReaderEnv:
    table: dict[str, list[RdrElt]]
    
    @staticmethod
    def empty() -> ReaderEnv:
        return ReaderEnv({})
```

**Benefits:**
1. **Explicit initialization:** Caller provides the initial value
2. **No hidden mutable defaults:** `default_factory=dict` creates shared mutable state bug risk
3. **Clearer API:** You see exactly what's being initialized

Use static factory methods for common construction patterns.

## `__add__` for Composition

**Use `__add__` to provide natural syntax for combining values.**

For types that represent collections or environments that can be merged, implement `__add__` to proxy to the merge operation:

```python
@dataclass(frozen=True)
class ReaderEnv:
    table: dict[str, list[RdrElt]]
    
    def merge(self, other: ReaderEnv) -> ReaderEnv:
        """Merge two envs. Other shadows self."""
        ...
    
    def __add__(self, other: ReaderEnv) -> ReaderEnv:
        """env1 + env2 proxies to merge."""
        return self.merge(other)
```

**Usage:**
```python
base = ReaderEnv([LocalRdrElt.create(x)])
imports = ReaderEnv([ImportRdrElt.create(y, spec)])

# Both equivalent:
combined = base.merge(imports)
combined = base + imports  # Later shadows earlier
```

**Rationale:**
1. **Familiar syntax:** `+` is natural for "combining" operations
2. **Immutability preserved:** Returns new instance, doesn't mutate
3. **Order matters:** `a + b` means `b` shadows `a` (reads left-to-right)

**Note:** The magic method for `+` is `__add__`, not `__plus__`.

## Omit `-> None` on `__init__`

**Don't annotate `__init__` return type.** `__init__` always returns `None` by definition, so the annotation is redundant noise.

**WRONG:**
```python
def __init__(self, elts: list[RdrElt]) -> None:
    ...
```

**RIGHT:**
```python
def __init__(self, elts: list[RdrElt]):
    ...
```

**Rationale:**
1. **Every `__init__` returns `None`** - this is a Python invariant
2. **Visual noise:** The `-> None` adds 9 characters with zero information
3. **Consistency with other methods:** Regular methods need return types; `__init__` doesn't

**Exception:** If a type checker complains, you may need to add it. But modern Python type checkers (mypy, pyright) infer `None` for `__init__` automatically.

## Static Factory Methods

**Use `from_*` static methods when construction logic is complex or has multiple variants.** Keep `__init__` simple and direct.

**WRONG:**
```python
@dataclass
class ReaderEnv:
    table: dict[str, list[RdrElt]]
    
    def __init__(self, elts: list[RdrElt]):
        # Complex merging logic in __init__
        table = defaultdict(list)
        for elt in elts:
            # ... merging, deduplication, etc.
        self.table = table
```

**RIGHT:**
```python
@dataclass
class ReaderEnv:
    table: dict[str, list[RdrElt]]
    
    def __init__(self, table: dict[str, list[RdrElt]]):
        self.table = table
    
    @staticmethod
    def from_elts(elts: list[RdrElt]) -> ReaderEnv:
        """Create from list with merging logic."""
        table = defaultdict(list)
        for elt in elts:
            # ... complex logic here
        return ReaderEnv(table)
    
    @staticmethod
    def empty() -> ReaderEnv:
        """Create empty environment."""
        return ReaderEnv({})
```

**Rationale:**
1. **Clear intent:** Different construction paths have explicit names
2. **Simple __init__:** The basic constructor just stores data
3. **Flexibility:** Can construct from raw table OR from processed elements

## Avoid Variable Shadowing in Match

**Use distinct variable names in match patterns to avoid confusion.**

**WRONG:**
```python
def lookup(self, rdr_name: RdrName):
    match rdr_name:
        case UnqualName(name):
            name = name  # 'name' shadows itself - confusing!
        case QualName(_, name):
            name = name  # Same issue
    return self.table.get(name, [])
```

**RIGHT:**
```python
def lookup(self, rdr_name: RdrName):
    match rdr_name:
        case UnqualName(occ):
            occ_name = occ
        case QualName(_, occ):
            occ_name = occ
    return self.table.get(occ_name, [])
```

**Rationale:**
1. **Clarity:** Distinct names make the flow obvious
2. **Avoids bugs:** Shadowing makes it unclear which variable you're using
3. **Self-documenting:** `occ_name` tells you it's the occurrence name

## Functional Iteration

**Use `itertools` for clean functional iteration patterns.**

```python
from itertools import chain

# Flatten nested structure
all_elts = list(chain(
    self.table.values(),
    other.table.values()
))

# Or with generator expression
all_elts = [
    elt 
    for elts in chain(self.table.values(), other.table.values())
    for elt in elts
]
```

**Benefits:**
1. **Lazy evaluation:** `chain` doesn't create intermediate lists
2. **Composability:** Can chain multiple operations
3. **Readability:** Declarative style vs nested loops

## References

- GHC's `Name` type uses structural equality (all fields)
- NameCache provides identity mapping: `(Module, OccName) -> Name`
- Python 3.12 PEP 695: Lazy type resolution
