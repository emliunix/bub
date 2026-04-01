# Style Guides

Language-specific and domain-specific coding conventions for the Bub project.

## Available Guides

| File | Topic |
|------|-------|
| [`python.md`](python.md) | General Python conventions (imports, types, naming, error handling, async, testing) |
| [`plain-objects.md`](plain-objects.md) | Data structure design patterns (equality, initialization, composition) |
| [`testing-structural.md`](testing-structural.md) | Testing with structural comparison (template functions, AST comparison) |

## Quick Reference

### New Python Code
Start with [`python.md`](python.md) for:
- Import ordering and style
- Type annotation conventions
- Naming conventions
- Error handling patterns
- Testing guidelines

### Data Structures / Classes
See [`plain-objects.md`](plain-objects.md) for:
- Equality semantics (structural vs identity)
- Dataclass initialization patterns
- Factory method patterns
- Composition with `__add__`

### Testing with Structural Comparison
See [`testing-structural.md`](testing-structural.md) for:
- Building expected AST structures
- Template functions for test setup
- Using `structural_equals()` for comparison
- Ignoring generated fields (unique IDs, locations)
- Anti-patterns to avoid
