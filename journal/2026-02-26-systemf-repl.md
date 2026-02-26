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
