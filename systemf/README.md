# System F with Algebraic Data Types

A complete implementation of System F (polymorphic lambda calculus) with algebraic data types, featuring a bidirectional type checker and reference interpreter.

## Features

- **System F Core**: Explicitly typed polymorphic lambda calculus
- **Algebraic Data Types**: Sum and product types with pattern matching
- **Bidirectional Type Checking**: Synthesis and checking modes
- **Reference Interpreter**: Operational semantics with call-by-value evaluation
- **Property-Based Testing**: Using Hypothesis for comprehensive test coverage

## Architecture

The implementation follows a standard PL compiler pipeline:

1. **Surface Language**: Haskell-like syntax
2. **Parser**: Recursive descent with precise error messages
3. **Elaborator**: Surface → Core translation with type annotation
4. **Type Checker**: Bidirectional algorithm with unification
5. **Interpreter**: Environment-based evaluation

## Quick Start

```bash
# Run tests
uv run pytest

# Run type checker on a file
uv run python -m systemf check examples/test.sf

# Run interpreter
uv run python -m systemf run examples/test.sf

# Start REPL
uv run python -m systemf repl
```

## Project Structure

```
systemf/
├── src/systemf/
│   ├── core/          # Core language AST and types
│   ├── surface/       # Surface language and parser
│   ├── eval/          # Interpreter
│   └── utils/         # Utilities
└── tests/             # Test suite
```

## Development

```bash
# Install dependencies
uv sync --all-groups

# Run type checker
uv run mypy src/

# Run linter
uv run ruff check .
```

## License

MIT
