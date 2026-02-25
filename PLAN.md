# System F with Data Types: Implementation Plan

**Project**: System F λ-calculus with algebraic data types  
**Language**: Python 3.11+  
**Scope**: Type checker + Reference interpreter  
**Architecture**: Modular PL compiler pipeline

---

## Executive Summary

This project implements a complete System F (polymorphic lambda calculus) with algebraic data types, featuring:
- Bidirectional type inference with higher-rank polymorphism
- Sum and product types via data declarations
- Complete operational semantics reference interpreter
- Property-based testing using Python's Hypothesis

The implementation follows standard PL compiler architecture: Surface Syntax → Parser → Elaborator → Core AST → Type Checker → Interpreter.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      SURFACE LANGUAGE                        │
│  (Haskell-like syntax with type inference annotations)       │
└────────────────────┬────────────────────────────────────────┘
                     │ Parse
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                         PARSER                               │
│  - LL(1) recursive descent with Pratt parsing for operators  │
│  - Error recovery and precise error locations                │
└────────────────────┬────────────────────────────────────────┘
                     │ Elaborate
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                       CORE LANGUAGE                          │
│  - Explicitly typed System F                                 │
│  - Type abstractions (Λ) and applications ([τ])              │
│  - Data constructors and pattern matching                    │
└────────────────────┬────────────────────────────────────────┘
                     │ Type Check
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                     TYPE CHECKER                             │
│  - Bidirectional type checking                               │
│  - Unification with occurs check                             │
│  - Constraint generation and solving                         │
└────────────────────┬────────────────────────────────────────┘
                     │ Evaluate
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    INTERPRETER                               │
│  - Call-by-value operational semantics                       │
│  - Environment-based evaluation                              │
│  - Pattern matching compilation                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase Structure

### Phase 1: Core Language Foundation
**Owner**: Subagent A - AST & Type System Design  
**Duration**: 1 sprint  
**Dependencies**: None

**Deliverables**:
1. Core AST definitions (types + terms)
2. Type representation and operations
3. Substitution and alpha-equivalence
4. Variable binding and de Bruijn indices

**Key Decisions**:
- Use de Bruijn indices for bound variables (avoid alpha-conversion)
- Use names for type variables (easier debugging)
- Immutable AST nodes (dataclasses)
- Separate core language from surface syntax

### Phase 2: Type System Implementation  
**Owner**: Subagent B - Type Checker  
**Duration**: 2 sprints  
**Dependencies**: Phase 1

**Deliverables**:
1. Unification algorithm with occurs check
2. Type context (Γ) and operations
3. Bidirectional type checking algorithm
4. Data type elaboration
5. Error reporting infrastructure

**Key Decisions**:
- Robinson-style unification
- Bidirectional checking (synthesis vs checking modes)
- Separate constraint generation and solving phases
- Rich error types with source locations

### Phase 3: Surface Language & Parser
**Owner**: Subagent C - Parser & Elaborator  
**Duration**: 1.5 sprints  
**Dependencies**: Phase 1

**Deliverables**:
1. Surface syntax AST
2. Recursive descent parser
3. Elaboration (surface → core)
4. Type annotation recovery
5. Desugaring (let, if-then-else, etc.)

**Key Decisions**:
- Hand-written parser (better error messages)
- Elaboration produces fully-annotated core terms
- Minimal surface syntax, desugar everything

### Phase 4: Reference Interpreter
**Owner**: Subagent D - Interpreter  
**Duration**: 1.5 sprints  
**Dependencies**: Phase 1, Phase 2 (for type-erased evaluation)

**Deliverables**:
1. Environment-based evaluator
2. Pattern matching implementation
3. Call-by-value semantics
4. Value representation
5. REPL

**Key Decisions**:
- Type-erased evaluation (types erased after checking)
- Environment-based (not substitution-based) for efficiency
- Strict evaluation

### Phase 5: Testing Infrastructure
**Owner**: Subagent E - Testing  
**Duration**: 1 sprint (parallel with others)  
**Dependencies**: All phases

**Deliverables**:
1. Unit tests for each component
2. Property-based tests (Hypothesis)
3. Golden tests for error messages
4. Integration tests (end-to-end)
5. Test fixtures and utilities

**Key Decisions**:
- pytest with Hypothesis for property testing
- Separate tests/ submodule
- No __init__.py in test directories
- Test both valid and invalid programs

### Phase 6: Integration & Documentation
**Owner**: Parent Agent  
**Duration**: 0.5 sprint  
**Dependencies**: All phases

**Deliverables**:
1. Main entry point (CLI)
2. Integration tests
3. Documentation
4. Example programs

---

## Module Structure

```
systemf/
├── pyproject.toml              # UV project configuration
├── README.md                   # Project documentation
├── src/
│   └── systemf/
│       ├── __init__.py
│       ├── core/               # Core language (Phases 1-2)
│       │   ├── __init__.py
│       │   ├── ast.py          # Core AST definitions
│       │   ├── types.py        # Type representations
│       │   ├── context.py      # Typing contexts
│       │   ├── unify.py        # Unification algorithm
│       │   ├── checker.py      # Type checker
│       │   └── errors.py       # Error types
│       ├── surface/            # Surface language (Phase 3)
│       │   ├── __init__.py
│       │   ├── ast.py          # Surface AST
│       │   ├── parser.py       # Recursive descent parser
│       │   ├── lexer.py        # Tokenizer
│       │   ├── elaborator.py   # Surface → Core
│       │   └── desugar.py      # Desugaring passes
│       ├── eval/               # Interpreter (Phase 4)
│       │   ├── __init__.py
│       │   ├── machine.py      # Abstract machine
│       │   ├── pattern.py      # Pattern matching
│       │   ├── value.py        # Value representations
│       │   └── repl.py         # Interactive REPL
│       └── utils/              # Utilities
│           ├── __init__.py
│           ├── location.py     # Source locations
│           └── pretty.py       # Pretty printing
└── tests/                      # Testing (Phase 5)
    ├── conftest.py             # Shared fixtures
    ├── test_core/              # Core language tests
    ├── test_surface/           # Parser/elaborator tests
    ├── test_eval/              # Interpreter tests
    └── test_integration/       # End-to-end tests
```

---

## Technical Specifications

### 1. AST Design

**Types:**
```python
@dataclass(frozen=True)
class TypeVar:
    name: str  # Named for debugging

@dataclass(frozen=True)  
class TypeArrow:
    arg: Type
    ret: Type

@dataclass(frozen=True)
class TypeForall:
    var: str
    body: Type

@dataclass(frozen=True)
class TypeConstructor:
    name: str
    args: list[Type]
```

**Terms (de Bruijn indices):**
```python
@dataclass(frozen=True)
class Var:
    index: int  # de Bruijn index

@dataclass(frozen=True)
class Abs:
    var_type: Type  # Annotation
    body: Term

@dataclass(frozen=True)
class App:
    func: Term
    arg: Term

@dataclass(frozen=True)
class TAbs:
    var: str
    body: Term

@dataclass(frozen=True)
class TApp:
    func: Term
    type_arg: Type

@dataclass(frozen=True)
class Constructor:
    name: str
    args: list[Term]

@dataclass(frozen=True)
class Case:
    scrutinee: Term
    branches: list[Branch]
```

### 2. Type Checker Algorithm

**Bidirectional checking:**
```python
def infer(ctx: Context, term: Term) -> Type:
    """Synthesize type from term (bottom-up)"""
    match term:
        case Var(idx):
            return ctx.lookup_type(idx)
        case App(f, arg):
            f_type = infer(ctx, f)
            match f_type:
                case TypeArrow(arg_type, ret_type):
                    check(ctx, arg, arg_type)
                    return ret_type
                case _:
                    raise TypeError("Expected function type")
        # ... etc

def check(ctx: Context, term: Term, expected: Type) -> None:
    """Check term against expected type (top-down)"""
    match term:
        case Abs(var_type, body):
            match expected:
                case TypeArrow(arg_type, ret_type):
                    unify(var_type, arg_type)
                    check(ctx.extend(arg_type), body, ret_type)
                case _:
                    raise TypeError("Expected arrow type")
        case _:
            # Fall back to inference
            actual = infer(ctx, term)
            unify(actual, expected)
```

### 3. Unification

```python
def unify(t1: Type, t2: Type) -> Subst:
    """Most general unifier"""
    match (t1, t2):
        case (TypeVar(n1), TypeVar(n2)) if n1 == n2:
            return Subst.identity()
        case (TypeVar(n), t) if n not in t.free_vars():
            return Subst.singleton(n, t)
        case (t, TypeVar(n)) if n not in t.free_vars():
            return Subst.singleton(n, t)
        case (TypeArrow(a1, r1), TypeArrow(a2, r2)):
            s1 = unify(a1, a2)
            s2 = unify(s1.apply(r1), s1.apply(r2))
            return s2.compose(s1)
        # ... etc
```

### 4. Pattern Matching

Pattern matching compiled to decision trees:
```python
@dataclass
class DecisionTree:
    """Compiled pattern matching"""
    pass

class PatternCompiler:
    def compile(self, branches: list[Branch]) -> DecisionTree:
        """Compile patterns to efficient decision tree"""
        # Standard algorithm: pattern matching compilation
        pass
```

---

## Testing Strategy

### Unit Tests
- Each module has corresponding test file
- Test both success and failure cases
- Error message quality tests

### Property-Based Tests (Hypothesis)
```python
from hypothesis import given, strategies as st

@given(st.builds(Term))
def test_type_preservation(term):
    """If term type checks, it evaluates to correct type"""
    ty = infer(Context.empty(), term)
    value = evaluate(term)
    assert value.type == ty
```

### Integration Tests
- End-to-end programs
- Type inference examples
- Evaluation examples
- Error cases

### Golden Tests
- Error messages stored in files
- Ensures consistent, high-quality errors

---

## Dependencies

```toml
[project]
name = "systemf"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "hypothesis>=6.100.0",
    "mypy>=1.9.0",
    "ruff>=0.3.0",
]
```

---

## Success Criteria

1. **Type System**: Complete System F with data types
2. **Type Checking**: Bidirectional algorithm with good errors
3. **Interpreter**: Correct operational semantics
4. **Testing**: >90% coverage, property tests passing
5. **Documentation**: API docs + tutorial
6. **Examples**: 5+ example programs

---

## Subagent Assignment

| Phase | Subagent | Focus | Skills Needed |
|-------|----------|-------|---------------|
| 1 | A | AST & Types | PL theory, dataclasses |
| 2 | B | Type Checker | Unification, bidirectional typing |
| 3 | C | Parser | Recursive descent, parsing theory |
| 4 | D | Interpreter | Operational semantics |
| 5 | E | Testing | pytest, Hypothesis, TDD |
| 6 | Parent | Integration | Coordination, CLI design |

---

## Next Steps

1. Spawn Subagent A to begin Phase 1 (AST design)
2. Create project skeleton with UV
3. Set up testing infrastructure
4. Begin implementation following dependencies

**Immediate Action**: Spawn Phase 1 subagent to draft AST definitions and type representations.
