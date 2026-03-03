# Surface AST Refactoring - Context Closure for Subagents

## 🎯 Goal
Fix all code to use the new Surface AST conventions with SurfaceNode base class.

## 📋 Surface AST Type System (New Conventions)

### Base Class
```python
@dataclass(frozen=True)
class SurfaceNode:
    location: Optional[Location] = None  # FIRST field, inherited by ALL
```

### SurfaceType Hierarchy
```python
class SurfaceType(SurfaceNode): pass

@dataclass(frozen=True)
class SurfaceTypeVar(SurfaceType):
    name: str = ""  # After location

@dataclass(frozen=True)  
class SurfaceTypeArrow(SurfaceType):
    arg: Optional[SurfaceType] = None
    ret: Optional[SurfaceType] = None
    param_doc: Optional[str] = None

@dataclass(frozen=True)
class SurfaceTypeConstructor(SurfaceType):
    name: str = ""  # After location
    args: list[SurfaceType] = field(default_factory=list)
```

### SurfaceTerm Hierarchy
```python
class SurfaceTerm(SurfaceNode): pass

@dataclass(frozen=True)
class SurfaceLit(SurfaceTerm):
    prim_type: str = ""      # After location
    value: object = None     # After location

@dataclass(frozen=True)
class GlobalVar(SurfaceTerm):
    name: str = ""  # After location

@dataclass(frozen=True)
class SurfaceTypeApp(SurfaceTerm):
    func: Optional[SurfaceTerm] = None
    type_arg: Optional[SurfaceType] = None

@dataclass(frozen=True)
class SurfaceAnn(SurfaceTerm):
    term: Optional[SurfaceTerm] = None
    type_: Optional[SurfaceType] = None

# ... all other Surface* classes follow same pattern
```

## 🔄 Transformation Rules

### Rule 1: ALWAYS Use Keyword Arguments
**BROKEN:**
```python
SurfaceTypeVar("a", DUMMY_LOC)  # "a" → location, DUMMY_LOC → name
SurfaceTypeConstructor("Int", [], DUMMY_LOC)  # "Int" → location, [] → name, DUMMY_LOC → args
SurfaceLit(42, DUMMY_LOC)  # 42 → location, DUMMY_LOC → prim_type
```

**CORRECT:**
```python
SurfaceTypeVar(name="a", location=DUMMY_LOC)
SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
SurfaceLit(prim_type="Int", value=42, location=DUMMY_LOC)
```

### Rule 2: OLD Classes → NEW Classes
| Old Class | New Class | Usage |
|-----------|-----------|-------|
| `SurfaceIntLit(value, loc)` | `SurfaceLit(prim_type="Int", value=value, location=loc)` | Integer literals |
| `SurfaceStringLit(value, loc)` | `SurfaceLit(prim_type="String", value=value, location=loc)` | String literals |
| `IntLit(loc, value)` | `Lit(prim_type="Int", value=value, source_loc=loc)` | Core integer literals |
| `StringLit(loc, value)` | `Lit(prim_type="String", value=value, source_loc=loc)` | Core string literals |

### Rule 3: Pattern Matching → Keyword Patterns
**BROKEN:**
```python
case SurfaceTypeVar(name, loc):
case SurfaceLit(prim_type, value, loc):
```

**CORRECT:**
```python
case SurfaceTypeVar(name=name, location=loc):
case SurfaceLit(prim_type=prim_type, value=value, location=loc):
```

## 📁 Impacted Files to Fix

### Priority 1: Test Files (47 failing tests)
1. `tests/test_pipeline.py` - ~50 SurfaceType* constructor calls
2. `tests/test_surface/test_inference.py` - Core.IntLit references
3. `tests/test_surface/test_scope.py` - SurfaceType* calls
4. `tests/test_surface/test_parser/test_declarations.py` - Type parser tests
5. `tests/test_surface/test_operator_desugar.py` - Operator desugaring tests

### Priority 2: Production Code
6. `src/systemf/surface/inference/elaborator.py` - Pattern matching, imports
7. `src/systemf/surface/scoped/checker.py` - Pattern matching
8. `src/systemf/core/checker.py` - IntLit/StringLit references

## 🔧 Fixing Checklist per File

For each file:
- [ ] Update imports (remove IntLit/StringLit, add Lit if needed)
- [ ] Fix SurfaceType* constructor calls → keyword args
- [ ] Fix SurfaceLit constructor calls → keyword args  
- [ ] Fix pattern matching → keyword patterns
- [ ] Fix core.IntLit/core.StringLit → core.Lit with prim_type

## ⚠️ Common Gotchas

1. **Field order matters**: location is ALWAYS first (inherited), then class-specific fields
2. **Pattern matching**: Must use `name=var` syntax, not positional
3. **Core vs Surface**: Core uses `Lit`, Surface uses `SurfaceLit`
4. **Imports**: Remove `IntLit`, `StringLit` from imports

## 📖 Examples

### Example 1: Type Parser Test
```python
# BEFORE (broken):
int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)

# AFTER (correct):
int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
```

### Example 2: Inference Test with IntLit
```python
# BEFORE (broken):
from systemf.core.ast import IntLit
assert isinstance(core_term, IntLit)

# AFTER (correct):
from systemf.core.ast import Lit
assert isinstance(core_term, Lit)
assert core_term.prim_type == "Int"
```

### Example 3: Elaborator Pattern Matching
```python
# BEFORE (broken):
case SurfaceTypeVar(name, location):
    return TypeVar(name)

# AFTER (correct):
case SurfaceTypeVar(name=name, location=_):
    return TypeVar(name)
```

## ✅ Verification

After fixing a file:
1. Check no `IntLit` or `StringLit` references remain
2. Check all Surface* constructors use keyword args
3. Check pattern matching uses keyword patterns
4. Run mypy: `uv run mypy <filepath>`

## 🎯 Success Criteria

- All SurfaceType* constructors use keyword arguments
- All SurfaceLit uses `prim_type` + `value` + `location`
- No references to deleted IntLit/StringLit classes
- All pattern matching uses keyword syntax
- Files pass mypy without errors
