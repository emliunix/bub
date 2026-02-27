---
assignee: Architect
expertise: ['Type System Design', 'System F', 'Language Implementation']
skills: ['code-reading']
type: design
priority: high
state: done
dependencies: []
refers: []
kanban: tasks/33-kanban-systemf-pluggable-primitives-system.md
created: 2026-02-26T17:17:35.149677
---

# Task: Design - Primitive Types and Operations Architecture

## Context
Design the architecture for pluggable primitive types and operations using `$prim` prefix. The system should allow primitive types like Int to be declared in prelude while keeping core language minimal. Key insight: types are declared in prelude text, evaluation only needs operation names and raw values.

## Final Design Specification

### Core Philosophy
**Clean Separation:** Types live in prelude, evaluation only needs symbol names and raw values.

```systemf
-- Prelude declares primitive types and their operations
prim_type Int
prim_op int_plus : Int -> Int -> Int
prim_op int_minus : Int -> Int -> Int
```

### AST Nodes

#### 1. IntLit (Term)
```python
@dataclass(frozen=True)
class IntLit(Term):
    """Integer literal: 42"""
    value: int
```
Parser creates this directly from NUMBER tokens.

#### 2. PrimOp (Term)
```python
@dataclass(frozen=True)
class PrimOp(Term):
    """Primitive operation: $prim.xxx"""
    name: str  # e.g., "int_plus", "int_minus"
    # Note: args handled via App wrapping, not stored here
```
Elaborator converts `$prim.xxx` names to PrimOp.

#### 3. PrimitiveType (Type)
```python
@dataclass(frozen=True)
class PrimitiveType(Type):
    """Primitive type from prelude: Int, Float, etc."""
    name: str
```
Registered when elaborating `prim_type` declarations.

#### 4. VInt (Value)
```python
@dataclass(frozen=True)
class VInt(Value):
    """Runtime integer value"""
    value: int
```
Runtime representation of integers.

### Prelude Syntax

#### `prim_type` Declaration
```systemf
prim_type Int
prim_type Float
prim_type String
```
Registers `PrimitiveType(name)` in `primitive_types` dictionary.

#### `prim_op` Declaration (single token)
```systemf
prim_op int_plus : Int -> Int -> Int
prim_op int_minus : Int -> Int -> Int
```
Registers type signature in `global_types["$prim.int_plus"]`.

### Name Resolution

```python
def resolve_name(name: str) -> Term:
    if name.startswith("$prim."):
        op_name = name[6:]  # Strip "$prim."
        return PrimOp(op_name)  # Bypass all scopes
    if name in term_env:
        return Var(term_env[name])
    if name in global_terms:
        return Global(name)
    raise UndefinedVariable(name)
```

### Type Checking Flow

**For IntLit:**
```python
case IntLit(_):
    # Lookup from prelude-populated registry
    return self.primitive_types["Int"]
```

**For PrimOp:**
```python
case PrimOp(name):
    full_name = f"$prim.{name}"
    if full_name not in self.global_types:
        raise TypeError(f"Unknown primitive: {name}")
    return self.global_types[full_name]
```

### Evaluation Flow

**Evaluator Registry:**
```python
class Evaluator:
    def __init__(self):
        self.primitive_impls = {
            "int_plus": lambda x, y: VInt(x.value + y.value),
            "int_minus": lambda x, y: VInt(x.value - y.value),
            # ...
        }
    
    def evaluate(self, term, env):
        match term:
            case IntLit(value):
                return VInt(value)
            case PrimOp(name):
                # PrimOp is the function, args come via App
                # Actually: App(App(PrimOp("int_plus"), arg1), arg2)
                pass
```

### Communication Between Components

**Type Checker ↔ Evaluator:**
- **Shared:** Operation symbol names (e.g., "int_plus")
- **Type Checker:** Knows types from prelude-declared signatures
- **Evaluator:** Knows implementations from `primitive_impls` registry

**No hardcoded type signatures in type checker!** All types come from prelude.

### Example Compilation Flow

```systemf
-- prelude.sf
prim_type Int
prim_op int_plus : Int -> Int -> Int

-- user.sf
1 + 2
```

1. **Parse prelude:**
   - `prim_type Int` → `SurfacePrimTypeDecl("Int")`
   - `prim_op int_plus : ...` → `SurfacePrimOpDecl("int_plus", ...)`

2. **Elaborate prelude:**
   - `primitive_types["Int"] = PrimitiveType("Int")`
   - `global_types["$prim.int_plus"] = Int -> Int -> Int`

3. **Parse user:**
   - `1 + 2` → `App(App(Var("+"), IntLit(1)), IntLit(2))`

4. **Desugar:**
   - `+` → `$prim.int_plus` → `PrimOp("int_plus")`
   - Result: `App(App(PrimOp("int_plus"), IntLit(1)), IntLit(2))`

5. **Type check:**
   - `IntLit(1)` → `primitive_types["Int"]` ✓
   - `PrimOp("int_plus")` → lookup `global_types["$prim.int_plus"]` → `Int -> Int -> Int` ✓

6. **Evaluate:**
   - `primitive_impls["int_plus"](VInt(1), VInt(2))` → `VInt(3)`

## Files to Design
- systemf/src/systemf/core/types.py - PrimitiveType
- systemf/src/systemf/core/ast.py - IntLit, PrimOp
- systemf/src/systemf/eval/value.py - VInt
- systemf/src/systemf/surface/ast.py - SurfacePrimTypeDecl, SurfacePrimOpDecl
- systemf/prelude.sf - Example declarations

## Key Design Decisions

1. **Single token `prim_op`:** Instead of `PRIM` + `OP`, use single `PRIM_OP` token for cleaner parsing
2. **IntLit created by parser:** Parser directly creates IntLit from NUMBER tokens
3. **Types from prelude:** Type checker looks up `primitive_types["Int"]` populated by prelude
4. **PrimOp stores only name:** Arguments handled via App wrapping (consistent with other functions)
5. **$prim bypasses scopes:** `$prim.xxx` names never lookup in local/global scopes

## Work Log
<!-- Work logs will be appended here -->

### [2026-02-26 18:04:11] Design Complete - Primitive Types and Operations

**Facts:**
Added PrimitiveType to core/types.py, IntLit and PrimOp to core/ast.py, VInt to eval/value.py, SurfacePrimTypeDecl and SurfacePrimOpDecl to surface/ast.py. Created prelude.sf with example declarations. Clean separation: types in prelude, evaluation uses operation names and raw values. IntLit created by parser. PrimOp stores only name with args via App wrapping.  bypasses scopes.

**Analysis:**
-

**Conclusion:**
Status: ok

---

