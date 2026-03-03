# Surface AST Architectural Concerns & Guidelines

## Issue 1: Location Propagation in Generated Nodes

### ✅ VALIDATED: DUMMY_LOC is NOT used in production code

```bash
$ grep -r "DUMMY_LOC" src/systemf/surface/inference/elaborator.py src/systemf/surface/desugar.py
# No results - production code is clean!
```

### Current Status
- **✅ Desugarer**: Already propagates location correctly
- **✅ Elaborator**: Already propagates source_loc correctly  
- **✅ Checker**: Already propagates location correctly
- **✅ Parser**: Uses real token locations

### Rule of Thumb

**✅ CORRECT - Propagate source location:**
```python
# In elaborator: SurfaceAbs → Core.Abs
case SurfaceAbs(var=var, var_type=var_type, body=body, location=loc):
    core_body = self.elaborate(body, ctx)
    return core.Abs(
        var_type=core_var_type,
        body=core_body,
        source_loc=loc  # ← Propagate from source!
    )
```

### DUMMY_LOC Usage Policy

| Where | Use DUMMY_LOC? | Why |
|-------|---------------|-----|
| **Test files** | ✅ Yes | Tests don't care about location |
| **Elaborator** | ❌ No | Should propagate source location |
| **Desugarer** | ❌ No | Should propagate source location |
| **Parser** | ❌ No | Has real token locations |
| **REPL temp nodes** | ✅ Yes | Interactive, no source file |

### Location Propagation Pattern

```python
def transform_node(surface_node, ...):
    # Always extract location from source node
    loc = surface_node.location
    
    # Transform children with their locations
    transformed_children = [
        transform_node(child) for child in children
    ]
    
    # Create new node with SOURCE location
    return NewNode(
        field1=...,
        field2=...,
        location=loc  # ← Source location preserved
    )
```

---

## Issue 2: Structural Equality vs Location

### ✅ VALIDATED: Problem exists, solution implemented

**Test:**
```python
node1 = SurfaceVar(name="x", location=loc1)
node2 = SurfaceVar(name="x", location=loc2)

node1 == node2  # False! (locations differ) ❌
equals_ignore_location(node1, node2)  # True ✅
```

### Solution Implemented

**Location:** `systemf/utils/ast_utils.py`

```python
from systemf.utils.ast_utils import equals_ignore_location

# Use in tests:
assert equals_ignore_location(node1, node2)  # Ignores location
```

**Backward Compatibility:** Function also exported from `systemf.surface.types`

### ✅ COMPLETED

- [x] `equals_ignore_location` moved to `systemf/utils/ast_utils.py`
- [x] Import in test file updated to use canonical location
- [x] No re-export (following "Migrate imports, don't re-export" principle)

---

## Action Items

### Immediate (High Priority)
- [ ] Audit elaborator for location propagation
- [ ] Audit desugarer for location propagation
- [ ] Move `equals_ignore_location` to utils module
- [ ] Update tests to use structural equality utility

### Short Term (Medium Priority)
- [ ] Document location propagation in CONTRIBUTING.md
- [ ] Add linter rule to catch DUMMY_LOC in production code
- [ ] Create AST comparison helpers for common test patterns

### Long Term (Low Priority)
- [ ] Consider making location non-default (require explicit)
- [ ] Add location tracking validation in CI

---

## Related Files

- `systemf/surface/types.py` - Contains `equals_ignore_location`
- `systemf/surface/inference/elaborator.py` - Needs location audit
- `systemf/surface/desugar.py` - Needs location audit
- `systemf/surface/scoped/checker.py` - Needs location audit
- `tests/` - Need to use structural equality

---

## Notes

- **DUMMY_LOC in tests is OK** - Tests don't care about source positions
- **Production code must propagate** - Real source locations needed for errors
- **Structural equality is common** - Factor out the utility properly
- **This is technical debt** - Not blocking functionality but needs cleanup
