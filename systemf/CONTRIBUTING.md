# Contributing to System F

Thank you for your interest in contributing to System F! This guide covers development workflows, documentation standards, and best practices.

## Table of Contents

- [Development Workflow](#development-workflow)
- [Documentation Standards](#documentation-standards)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)

---

## Development Workflow

### 1. Skill-First Approach

Always check relevant skills before starting work:

```bash
# List available skills
ls -la .agents/skills/

# Read the skill for your task
cat .agents/skills/skill-management/SKILL.md
```

### 2. Check Documentation First

Before implementing:

1. Read [docs/INDEX.md](docs/INDEX.md) - Check for existing docs
2. Review [docs/architecture/overview.md](docs/architecture/overview.md) - Understand the system
3. Check [docs/development/troubleshooting.md](docs/development/troubleshooting.md) - Known issues

### 3. Update Tests

Every code change must include tests:

```python
# Example test pattern
def test_new_feature():
    """Test description."""
    # Setup
    input_data = ...
    
    # Execute
    result = function_under_test(input_data)
    
    # Assert
    assert result == expected
```

### 4. Run Full Test Suite

```bash
# Before committing
uv run pytest tests/ -v

# Check specific areas
uv run pytest tests/test_surface/test_inference.py -v
uv run pytest tests/test_eval/test_evaluator.py -v
```

---

## Documentation Standards

### Directory Structure

All documentation lives in `docs/`:

```
docs/
├── README.md                    [Entry point - never move]
├── INDEX.md                     [Navigation index - keep updated]
├── getting-started/            [User onboarding]
├── reference/                  [Language reference]
├── architecture/               [System design]
├── development/                [Developer guides]
├── _reference-materials/       [Design specs]
└── _archive/                   [Deprecated docs]
```

### File Naming Convention

- Use `kebab-case.md` for all files
- Use lowercase (except `README.md`)
- Be descriptive: `type-inference-algorithm.md` not `algo.md`

**Good:**
- `multi-pass-pipeline.md`
- `troubleshooting-guide.md`
- `pattern-matching.md`

**Bad:**
- `MultiPassPipeline.md` (wrong case)
- `pipeline.MD` (wrong extension)
- `algo.md` (too vague)

### Metadata Headers

All new documentation must include YAML frontmatter:

```markdown
---
title: "Document Title"
category: "architecture"  # architecture|reference|development|meta
status: "current"         # current|draft|deprecated
last-updated: "2026-03-03"
description: "Brief description for index"
related:
  - "./related-doc.md"
  - "../reference/syntax.md"
---
```

### Cross-References

Use relative paths with `./` prefix:

```markdown
# Good
See [syntax reference](./reference/syntax.md)
For details, check [troubleshooting](./development/troubleshooting.md)

# Bad (absolute paths)
See [syntax](/docs/reference/syntax.md)

# Bad (missing ./)
See [syntax](reference/syntax.md)
```

### When to Update Documentation

| Change Type | Documentation to Update |
|-------------|------------------------|
| **New feature** | Add to getting-started/, Update INDEX.md |
| **API change** | Update architecture/, Add migration note |
| **Bug fix** | Update troubleshooting/, Add regression test |
| **Refactor** | Update architecture/, Check cross-references |
| **New primitive** | Update architecture/overview.md#pluggable-primitives |

### Deprecating Documents

When retiring documentation:

1. Update metadata: `status: deprecated`
2. Move to `_archive/`
3. Add redirect notice in original location (if moved)
4. Update INDEX.md to reflect status

Example redirect notice:
```markdown
---
status: deprecated
redirect: "./new-location.md"
---

# OLD DOCUMENT NAME

**DEPRECATED**: This document has moved to [new location](./new-location.md).

Last updated: 2026-03-03
```

---

## Code Style

### Python Style

We use Ruff for linting and formatting:

```bash
# Check style
uv run ruff check src/systemf

# Auto-fix issues
uv run ruff check --fix src/systemf

# Format code
uv run ruff format src/systemf
```

### Type Hints

Required for all new code:

```python
# Good
def elaborate(
    term: SurfaceTerm, 
    ctx: TypeContext
) -> tuple[CoreTerm, Type]:
    ...

# Bad (missing types)
def elaborate(term, ctx):
    ...
```

### Pattern Matching

Use keyword arguments for dataclass pattern matching:

```python
# Good ✓
match term:
    case Abs(var_type=var_type, body=body):
        ...
    case App(func=func, arg=arg):
        ...

# Bad ✗ (field ordering issues)
match term:
    case Abs(var_type, body):
        ...
```

---

## Testing

### Test Organization

```
tests/
├── test_core/          # Core language tests
├── test_surface/       # Surface language tests
├── test_eval/          # Evaluator tests
└── conftest.py         # Shared fixtures
```

### Writing Tests

```python
# Test file: tests/test_surface/test_inference.py

import pytest
from systemf.surface.inference import TypeElaborator

def test_new_feature():
    """Description of what this tests."""
    # Arrange
    elaborator = TypeElaborator()
    
    # Act
    result = elaborator.elaborate(...)
    
    # Assert
    assert result.success
    assert result.type == expected_type
```

### Running Tests

```bash
# All tests
uv run pytest tests/

# Specific module
uv run pytest tests/test_surface/test_inference.py -v

# With coverage
uv run pytest tests/ --cov=systemf --cov-report=html

# Failed tests only
uv run pytest tests/ --lf

# Parallel execution
uv run pytest tests/ -n auto
```

---

## Pull Request Process

### Before Creating PR

1. **Update documentation** - Match your changes
2. **Add tests** - Cover new functionality
3. **Run tests** - Ensure nothing breaks
4. **Check style** - Run ruff and mypy
5. **Update INDEX.md** - If adding/moving docs

### PR Description Template

```markdown
## Summary
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests added/updated
- [ ] All tests pass

## Documentation
- [ ] Docs updated
- [ ] INDEX.md updated (if needed)

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
```

### Review Process

1. Automated checks must pass (tests, linting)
2. Documentation updates reviewed
3. Architecture changes need broader review
4. Approved by at least one maintainer

---

## Documentation Checklist

Before submitting documentation changes:

- [ ] File uses `kebab-case.md` naming
- [ ] Metadata header included (YAML frontmatter)
- [ ] Relative links use `./` prefix
- [ ] Cross-references work (check with grep)
- [ ] Added to INDEX.md (if new)
- [ ] Status field set appropriately
- [ ] No broken internal links

---

## Questions?

- Check [docs/INDEX.md](docs/INDEX.md) for navigation
- Review [docs/development/troubleshooting.md](docs/development/troubleshooting.md)
- See [docs/architecture/overview.md](docs/architecture/overview.md) for system design

Thank you for contributing!
