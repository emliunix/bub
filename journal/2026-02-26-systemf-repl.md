# 2026-02-26: System F REPL Implementation

## Summary

Implemented a fully functional REPL (Read-Eval-Print Loop) for System F with Unicode support, persistent global state, and automatic expression/declaration detection.

---

## Critical Bug: Empty Dict with `or {}`

**Problem:** Using `global_env or {}` creates a NEW dict when `global_env` is empty `{}`.

**Why it matters:** Empty dicts are falsy in Python, so `or` returns the RHS, breaking reference sharing.

**Fix:** Use `global_env if global_env is not None else {}`

**Files affected:**
- `src/systemf/core/checker.py`
- `src/systemf/eval/machine.py`

---

## Two-Tiered Variable System

**Challenge:** De Bruijn indices don't work across REPL inputs because each input is elaborated separately.

**Solution:**
- **Local scope** (lambda parameters): De Bruijn indices via `Var`
- **Global scope** (REPL definitions): Named references via new `Global` term type

**Implementation:**
- Added `Global` dataclass to `ast.py` with `name: str`
- Elaborator tracks `global_terms: set[str]` separately from `term_env`
- Type checker and evaluator handle `Global` lookups

---

## REPL Features

### Unicode Support
Added to lexer (`src/systemf/surface/lexer.py`):
- `→` (ARROW) for `->`
- `∀` (FORALL) for `forall`
- `λ` (LAMBDA) for `\`
- `Λ` (TYPELAMBDA) for `/\`

### Expression Auto-Detection
- Try parsing as declaration first
- On `ParseError`, fall back to expression parsing
- No special syntax needed

### Multiline Input
- `:{` starts multiline mode
- `:}` ends multiline mode
- Allows formatting declarations across multiple lines

### Persistent State
- `global_types`: Type signatures of globals
- `global_values`: Evaluated values of globals  
- `global_terms`: Names of global terms for elaborator
- `constructor_types`: Data constructor types
- `term_env` is cleared between inputs (local scope only)

### Synthetic `it` Binding
- Expression results automatically bound to `it`
- Can reference previous results in subsequent expressions

---

## Example REPL Session

```systemf
> data Bool = True | False

> id : ∀a. a → a = Λa. λx → x
id : ∀a.a -> a = <type-function>

> id [Bool] True
it : Bool = True

> :{
| not : Bool → Bool = λb →
|   case b of
|     True → False
|     False → True
| :}

> not (id [Bool] True)
it : Bool = False

> id [Bool] it
it : Bool = False
```

---

## Files Modified

- `src/systemf/surface/lexer.py` - Unicode regex patterns
- `src/systemf/core/ast.py` - Added `Global` term type
- `src/systemf/core/checker.py` - Global lookups + `or {}` fix
- `src/systemf/core/__init__.py` - Export `Global`
- `src/systemf/surface/elaborator.py` - Two-tiered variable resolution
- `src/systemf/eval/machine.py` - Global evaluation + `or {}` fix
- `src/systemf/eval/repl.py` - Complete REPL implementation

## Test Results

All 336 tests passing.

## Usage

```bash
cd systemf && uv run python -m systemf.eval.repl
```

---

## Update: Prelude and Constructor Fixes

### Prelude Standard Library

Created `prelude.sf` with 21 definitions:

**Types Defined:**
- `Bool` (True, False)
- `Maybe a` (Nothing, Just a)
- `Either a b` (Left a, Right b)
- `List a` (Nil, Cons a (List a))
- `Nat` (Zero, Succ Nat)
- `Pair a b` (MkPair a b)

**Functions:**
- `not`, `and`, `or` - Boolean operations
- `id`, `const` - Polymorphic combinators
- `fromMaybe`, `isJust` - Maybe operations
- `isLeft`, `isRight` - Either operations
- `fst`, `snd` - Pair projections

**Demo Values:**
- `zero`, `one`, `two`, `three` - Natural numbers
- `justTwo`, `nothingNat` - Maybe examples
- `leftBool`, `rightNat` - Either examples

### Constructor Application Bug Fix

**Problem:** Parser treated `Succ Zero` as `App(Constructor("Succ", []), Constructor("Zero", []))` instead of `Constructor("Succ", [Constructor("Zero", [])])`.

**Root Cause:** In the full prelude, constructor names like `Zero` and `Succ` are added to `global_terms`, causing the elaborator to look them up as `Global` references instead of treating them as constructors.

**Fix in elaborator.py:**
```python
case SurfaceApp(func, arg, location):
    core_func = self.elaborate_term(func)
    core_arg = self.elaborate_term(arg)
    # If func is a constructor, convert App to Constructor with args
    if isinstance(core_func, core.Constructor):
        return core.Constructor(core_func.name, core_func.args + [core_arg])
    return core.App(core_func, core_arg)
```

### Type Application Bug Fix

**Problem:** Type applications like `Just [Nat]` were creating `TApp(Constructor("Just"), Nat)` which the evaluator couldn't handle (constructors aren't type abstractions).

**Fix:** Skip TApp for constructors - the type checker handles the typing:
```python
case SurfaceTypeApp(func, type_arg, location):
    core_func = self.elaborate_term(func)
    core_type_arg = self._elaborate_type(type_arg)
    if isinstance(core_func, core.Constructor):
        return core_func  # Constructors don't need type applications at runtime
    return core.TApp(core_func, core_type_arg)
```

### Type Checker Fix for Constructor Type Applications

**Problem:** When type-checking `Just [Nat]`, the checker was instantiating the constructor type twice.

**Fix in checker.py:** Special case for TApp with Constructor func to look up constructor type directly:
```python
case TApp(func, type_arg):
    from systemf.core.ast import Constructor as AstConstructor
    if isinstance(func, AstConstructor):
        # Look up constructor type directly to avoid premature instantiation
        ctor_type = self.constructors[func.name]
        # ... instantiate with type_arg
```

### Readline Integration

Added to REPL:
- History persistence in `~/.systemf_history`
- Tab completion for commands (`:quit`, `:help`) and global identifiers
- Cross-platform support (GNU readline / macOS libedit)

### Test Results

All 336 tests passing. Prelude loads successfully with all 21 definitions.

### Example Session

```systemf
$ cd systemf && uv run python -m systemf.eval.repl
System F REPL v0.1.0
Loaded prelude: 21 definitions

> id [Bool] True
it : Bool = True

> not True
it : Bool = False

> justTwo
it : Maybe Nat = (Just (Succ (Succ Zero)))

> :quit
Goodbye!
```
