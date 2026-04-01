# Testing Style Guide: Structural Comparison

Testing philosophy for the System F compiler: build expected AST structures and compare with actual results using structural comparison helpers.

## Why Structural Comparison?

Instead of asserting individual properties:
```python
# ❌ Bad: Brittle, hard to maintain
assert isinstance(rn_pat, ConPat)
assert rn_pat.con == BUILTIN_LIST_CONS
assert len(rn_pat.args) == 2
```

Build and compare entire structures:
```python
# ✅ Good: Complete, self-documenting
expected_pat = ConPat(
    con=BUILTIN_LIST_CONS,
    args=[
        VarPat(name=Name(mod="Test", surface="x", unique=-1)),
        VarPat(name=Name(mod="Test", surface="xs", unique=-1)),
    ]
)
assert structural_equals(rn_pat, expected_pat)
```

## Core Principles

### 1. Build Expected AST, Don't Assert Properties

Construct the complete expected AST node and compare structurally:

```python
def test_rename_pattern_constructor_with_args():
    """Multi-item pattern becomes ConPat with arg patterns."""
    renamer = mk_rename_expr_with_builtins()
    pat = parse_pattern("Cons x xs")
    names, rn_pat = renamer.rename_pattern(pat)
    
    # Build expected pattern structure completely
    expected_pat = ConPat(
        con=BUILTIN_LIST_CONS,
        args=[
            VarPat(name=Name(mod="Test", surface="x", unique=-1)),
            VarPat(name=Name(mod="Test", surface="xs", unique=-1)),
        ]
    )
    
    # Single assertion for entire structure
    assert structural_equals(rn_pat, expected_pat)
```

### 2. Ignore Generated Identifiers

Generated fields (unique IDs, locations) differ between runs. Use `structural_equals()` which ignores:
- `location` / `source_loc` - source position info
- `unique` - generated unique IDs
- `loc` - location in Name objects

### 3. Template Function Pattern

Every test file should define reusable template functions:

```python
# Template: Create test subject with controlled environment
def mk_rename_expr_with_builtins(
    mod_name: str = "Test", 
    uniq_start: int = 1000
) -> RenameExpr:
    """Create RenameExpr with builtins imported as unqualified."""
    uniq = Uniq(uniq_start)
    spec = ImportSpec(module_name="builtins", alias=None, is_qual=False)
    builtins = [BUILTIN_TRUE, BUILTIN_FALSE, BUILTIN_LIST_CONS, ...]
    elts = [ImportRdrElt.create(name, spec) for name in builtins]
    reader_env = ReaderEnv.from_elts(elts)
    return RenameExpr(reader_env, mod_name, uniq)

# Template: Parse surface syntax to AST
def parse_pattern(source: str) -> SurfacePatternBase:
    """Parse pattern text to SurfacePatternBase."""
    tokens = list(lex(source))
    return (pattern_parser() << eof).parse(tokens)

# Template: Compare Name lists ignoring unique IDs
def names_equal_ignore_uniq(names1: list[Name], names2: list[Name]) -> bool:
    """Compare two lists of names ignoring unique IDs."""
    if len(names1) != len(names2):
        return False
    for n1, n2 in zip(names1, names2):
        if (n1.mod, n1.surface) != (n2.mod, n2.surface):
            return False
    return True
```

### 4. Test Structure Template

```python
def test_<component>_<scenario>():
    """<What is being tested>.
    
    <Why this matters / edge case notes>
    """
    # 1. Setup: Create test subject with controlled environment
    renamer = mk_rename_expr_with_builtins()
    
    # 2. Parse: Convert surface syntax to AST
    pat = parse_pattern("Cons x xs")
    
    # 3. Execute: Run the function being tested
    names, rn_pat = renamer.rename_pattern(pat)
    
    # 4. Build expected: Construct expected results
    expected_names = [
        Name(mod="Test", surface="x", unique=-1),
        Name(mod="Test", surface="xs", unique=-1),
    ]
    expected_pat = ConPat(
        con=BUILTIN_LIST_CONS,
        args=[...]
    )
    
    # 5. Assert: Compare with structural comparison
    assert names_equal_ignore_uniq(names, expected_names)
    assert structural_equals(rn_pat, expected_pat)
```

### 5. Comparison Strategy by Type

**For AST nodes (Pat, Expr, Ty, etc.):**
```python
# Use structural_equals - ignores location/unique
assert structural_equals(actual, expected)
```

**For Name lists:**
```python
# Compare (mod, surface) tuples, ignore unique
def names_equal_ignore_uniq(names1: list[Name], names2: list[Name]) -> bool:
    if len(names1) != len(names2):
        return False
    return all(
        (n1.mod, n1.surface) == (n2.mod, n2.surface)
        for n1, n2 in zip(names1, names2)
    )
```

**For simple values:**
```python
# Use direct comparison
assert len(names) == 2
assert names[0].surface == "x"
```

## Complete Example: Rename Tests

```python
"""Tests for elab3 rename module.

Tests rename_pattern and rename_type methods of RenameExpr class.
Uses structural comparison with structural_equals for AST nodes.
"""

import pytest
from parsy import eof

from systemf.elab3.rename import RenameExpr
from systemf.elab3.builtins import (
    BUILTIN_TRUE, BUILTIN_FALSE, BUILTIN_LIST_CONS, BUILTIN_LIST_NIL,
    BUILTIN_PAIR, BUILTIN_PAIR_MKPAIR
)
from systemf.elab3.reader_env import ReaderEnv, ImportRdrElt, ImportSpec
from systemf.elab3.types import Name, BoundTv, TyFun, TyForall, TyInt, TyString, TyConApp
from systemf.elab3.ast import VarPat, ConPat, LitPat, DefaultPat
from systemf.utils.uniq import Uniq
from systemf.utils.ast_utils import structural_equals
from systemf.surface.parser import lex, parse_type
from systemf.surface.parser.expressions import pattern_parser


# ============================================================================
# Template Functions
# ============================================================================

def mk_rename_expr_with_builtins(
    mod_name: str = "Test", 
    uniq_start: int = 1000
) -> RenameExpr:
    """Create RenameExpr with builtins imported as unqualified."""
    uniq = Uniq(uniq_start)
    spec = ImportSpec(module_name="builtins", alias=None, is_qual=False)
    builtins = [
        BUILTIN_TRUE, BUILTIN_FALSE,
        BUILTIN_LIST_CONS, BUILTIN_LIST_NIL,
        BUILTIN_PAIR, BUILTIN_PAIR_MKPAIR,
    ]
    elts = [ImportRdrElt.create(name, spec) for name in builtins]
    reader_env = ReaderEnv.from_elts(elts)
    return RenameExpr(reader_env, mod_name, uniq)


def parse_pattern(source: str) -> SurfacePatternBase:
    """Parse pattern text to SurfacePatternBase."""
    tokens = list(lex(source))
    return (pattern_parser() << eof).parse(tokens)


def names_equal_ignore_uniq(names1: list[Name], names2: list[Name]) -> bool:
    """Compare two lists of names ignoring unique IDs."""
    if len(names1) != len(names2):
        return False
    for n1, n2 in zip(names1, names2):
        if (n1.mod, n1.surface) != (n2.mod, n2.surface):
            return False
    return True


# ============================================================================
# Pattern Tests (Structural Comparison Style)
# ============================================================================

def test_rename_pattern_variable_not_in_env():
    """Variable not in reader env becomes VarPat with fresh Name."""
    renamer = mk_rename_expr_with_builtins()
    pat = parse_pattern("x")
    names, rn_pat = renamer.rename_pattern(pat)
    
    # Build expected names list (mod and surface, ignoring unique)
    expected_names = [Name(mod="Test", surface="x", unique=-1)]
    assert names_equal_ignore_uniq(names, expected_names)
    
    # Build expected pattern and compare structurally
    expected_pat = VarPat(name=Name(mod="Test", surface="x", unique=-1))
    assert structural_equals(rn_pat, expected_pat)


def test_rename_pattern_constructor_with_args():
    """Multi-item pattern becomes ConPat with arg patterns."""
    renamer = mk_rename_expr_with_builtins()
    pat = parse_pattern("Cons x xs")
    names, rn_pat = renamer.rename_pattern(pat)
    
    # Build expected names list (bound variables: x, xs)
    expected_names = [
        Name(mod="Test", surface="x", unique=-1),
        Name(mod="Test", surface="xs", unique=-1),
    ]
    assert names_equal_ignore_uniq(names, expected_names)
    
    # Build expected pattern structure completely
    expected_pat = ConPat(
        con=BUILTIN_LIST_CONS,
        args=[
            VarPat(name=Name(mod="Test", surface="x", unique=-1)),
            VarPat(name=Name(mod="Test", surface="xs", unique=-1)),
        ]
    )
    assert structural_equals(rn_pat, expected_pat)
```

## Anti-Patterns to Avoid

❌ **Don't use isinstance chains:**
```python
assert isinstance(rn_pat, ConPat)
assert rn_pat.con == BUILTIN_LIST_CONS
assert len(rn_pat.args) == 2
assert isinstance(rn_pat.args[0], VarPat)
```

❌ **Don't assert individual field values:**
```python
assert rn_pat.con.mod == "builtins"
assert rn_pat.con.surface == "Cons"
```

❌ **Don't compare unique IDs:**
```python
assert names[0].unique == 1000  # Will break on different runs
```

## Summary

1. **Build complete expected AST** - Construct the full expected structure
2. **Use structural comparison** - `structural_equals()` ignores generated fields
3. **Define template functions** - Reusable setup, parsing, and comparison
4. **Single assertions per structure** - One comparison per AST node
5. **Ignore unique IDs** - Compare (mod, surface) for Names
6. **Document with docstrings** - Explain what and why, not how
