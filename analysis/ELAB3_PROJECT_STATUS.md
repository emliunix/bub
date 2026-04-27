# SystemF Elab3 - Project Status Summary

**Last Updated:** 2026-04-27
**Location:** `systemf/src/systemf/elab3/`
**Total Lines of Code:** ~5,200 lines (Python: ~3,600 elab3 + ~1,600 types)
**Test Count:** 170 tests (test_elab3)

## Overview

Elab3 is a module system elaborator for SystemF - a functional language implementation heavily inspired by GHC's architecture. It features bidirectional type inference (Putting Jones 2007), a Surface-to-Core compilation pipeline, and a CEK evaluator. The unique design goal is to support **scripting with pluggable primitives**, externalizing computation and data to the hosting environment.

## Design Philosophy: GHC Heritage + Primitive Extensibility

### GHC-Inspired Foundation
- Read and adapted GHC source code structure
- Surface syntax + Core IR organization
- Bidirectional type inference with ExpType (Check/Infer modes)
- Pattern matching compilation and desugaring
- Module system with imports/exports
- Name resolution and scoping

### Unique Focus: Pluggable Primitive System
The language is designed to have a polymorphic type checker as its core, while **computation and data are externalized** to the host environment via a tiered primitive operation system:

#### Primitive Types & Operations
- `prim_ty` declarations for declaring primitive types
- `prim_op` declarations for declaring primitive operations (must accompany `prim_ty`)
- Primitive ops are implemented as Python functions: `Callable[[list[Val]], Val]`
- Type inference handles the types; execution delegates to the host

#### Tiered `get_primop` Architecture
The `REPLContext` exposes `get_primop(name: Name, thing: AnId, session: REPLSessionProto) -> Val | None`:

1. **Base Layer (`builtins_rts`)**: Pure function implementations for basic primitives (int arithmetic, string concat, comparisons, `error`)
2. **Per-Module Registration**: Libraries register primitives under their module namespace via `Synthesizer`
3. **Factory Pattern**: Libraries get freedom to synthesize primitives dynamically

#### Synthesizer Protocol (IMPLEMENTED)
The `Synthesizer` protocol enables dynamic primitive generation:

```python
class Synthesizer(Protocol):
    def get_primop(self, name: Name, thing: AnId, session: REPLSessionProto) -> Val | None: ...
```

A synthesizer can:
- Create a sub-`REPLSession` (via `fork()`)
- Inject argument bindings via `cmd_add_args()`
- Inject a return setter via `cmd_add_return()`
- Evaluate expressions within the forked session
- Return the computed value

This enables complex runtime code generation and execution. See `bub_sf` demo below.

#### Extension Protocol (IMPLEMENTED)
The `Ext` protocol allows external libraries to plug into the REPL:

```python
class Ext(Protocol):
    @property
    def name(self) -> str: ...
    def search_paths(self) -> list[str]: ...
    def synthesizer(self) -> dict[str, Synthesizer] | None: ...
```

Extensions register search paths and module-specific synthesizers that are composed into the `SyntRouter`.

#### LLM Agent Integration (Vision)
This primitive extensibility enables declaring functions that:
1. Spawn an LLM agent with a prompt
2. The agent generates code/data
3. The result is fed back through a synthesizer sub-session
4. Evaluation completes with the agent's output

This makes the language a **host for AI-augmented computation**.

## Architecture Components

### 1. Pipeline (`pipeline.py` - 46 lines)
Main compilation pipeline:
- **Parse** → surface AST from source code
- **Rename** → resolve names and imports
- **Typecheck** → infer types and produce Core

### 2. Type System (`types/` - 11 modules + `core_extra.py`)
Core type system infrastructure:
- `core.py` / `core_pp.py` - Core AST and pretty printing
- `core_extra.py` - Extended core term builders (`CoreBuilderExtra`) for polymorphic data constructor construction
- `ty.py` - Type representation and substitution
- `tything.py` - Type environment (TyThing, ATyCon, ACon, AnId, etc.)
- `ast.py` - AST nodes for renamed declarations
- `val.py` - Runtime values (VClosure, VData, VLit, VPartial, etc.)
- `mod.py` - Module representation
- `tc.py` - Type-checking specific types (NonRecGroup, RecGroup)
- `wrapper.py` / `xpat.py` - Wrapper and pattern extensions
- `protocols.py` - Type protocols (REPLContext, REPLSessionProto, NameCache, NameGenerator, TyLookup, **Synthesizer**, **Ext**, **PrimOpsSynth**)

### 3. Renaming Phase (`rename.py`, `rename_expr.py` - 522 lines total)
Name resolution and import handling:
- `rename.py` (250 lines) - Main renaming pass, module-level resolution, prim_ty/prim_op handling
- `rename_expr.py` (272 lines) - Expression-level renaming
- `reader_env.py` (244 lines) - Import environment and reader monad
- `scc.py` (163 lines) - Strongly connected components for binding groups

### 4. Type Checking (`typecheck.py`, `typecheck_expr.py`, `tc_ctx.py` - ~1,020 lines)
Bidirectional type inference:
- `typecheck.py` (101 lines) - Top-level type checking orchestration (data types, prims, valbinds)
- `typecheck_expr.py` (583 lines) - Expression type inference engine
- `tc_ctx.py` (336 lines) - Type checking context and constraints
- Supports: data types, primitive types/ops, let-bindings (recursive and non-recursive), pattern matching

### 5. Evaluation (`eval.py` - 284 lines)
CEK (Control, Environment, Continuation) evaluator:
- Strict call-by-value semantics
- Runtime value representation in `val.py`
- Supports: lambdas, type abstractions, let-bindings, case expressions, literals
- Variable resolution: local env → `ctx.lookup_gbl` for module-level references

### 6. Pattern Matching (`matchc.py` - 356 lines)
Pattern compilation and matching:
- Constructor patterns, literal patterns, wildcards
- Pattern desugaring to case expressions

### 7. REPL (`repl.py`, `repl_session.py`, `repl_driver.py` - ~576 lines)
Interactive environment:
- `repl.py` (184 lines) - REPL context, module loading, primitive resolution via `SyntRouter`
- `repl_session.py` (254 lines) - REPL session management, evaluation, forking, arg/return injection
- `repl_driver.py` (138 lines) - Readline-based interactive REPL interface
- Features:
  - Incremental definitions
  - `:import <module>` for loading modules
  - Multi-line input with `:{ ... :}`
  - Session forking for isolation
  - Primitive operation resolution via `SyntRouter` (composable synthesizers)
  - Extension loading via `Ext` protocol

### 8. Built-ins (`builtins.py`, `builtins_rts.py` - 244 lines)
- `builtins.py` (112 lines) - Built-in type and value definitions
- `builtins_rts.py` (132 lines) - Runtime system primitive implementations (pure Python functions)
- Includes: `Maybe` type, `Ref` type with `mk_ref`/`set_ref`/`get_ref`

### 9. Utilities
- `name_gen.py` (63 lines) - Unique name generation using `Uniq` counter

## Key Features

### Implemented
- Module system with imports/exports
- Algebraic data types with constructors
- Pattern matching with case expressions
- Let and letrec bindings
- Bidirectional type inference with polymorphism
- Primitive types (`prim_ty`) and operations (`prim_op`)
- Tiered primitive resolution through `Synthesizer` protocol + `SyntRouter`
- Extension protocol (`Ext`) for pluggable libraries
- Interactive REPL with incremental compilation
- CEK-style evaluator
- Name resolution and scoping
- Session forking for isolated evaluation
- Wildcard pattern support (`_` in patterns)

### Architecture Patterns
- **Phase separation**: Parse → Rename → Typecheck → Evaluate
- **Core language**: Explicitly typed intermediate representation
- **Reader monad**: For name resolution environment
- **Bidirectional typing**: Check vs Infer modes
- **Wrapper system**: Evidence for type coercions (HsWrapper-inspired)
- **Tiered primitives**: Base RTS → per-module `Synthesizer` → `SyntRouter` composition
- **Shared lookup protocol**: `TyLookup` enables polymorphic datacon/tycon resolution across typechecker and evaluator
- **Extension protocol**: `Ext` enables external libraries to register search paths and synthesizers

## Recent Development Focus

### Synthesizer Protocol (COMPLETED)
Implemented the full synthesizer infrastructure:
- `Synthesizer` protocol with `get_primop()` method
- `PrimOpsSynth` - dictionary-based synthesizer for static primitives
- `SyntRouter` - composable router that delegates to module-specific synthesizers
- `LLMSynth` - stub for LLM-based synthesis
- `REPLSession.cmd_add_args()` - inject argument bindings into forked session
- `REPLSession.cmd_add_return()` - inject return value setter into forked session
- `REPL` accepts `exts: list[Ext]` parameter for extension loading

### `bub_sf` Extension Demo (NEW)
New subproject at `bub_sf/` demonstrating the extension system:
- `BubExt` implements `Ext` protocol
- `PrimOps` implements `Synthesizer` for `test_prim` primitive
- Demo evaluates `test_prim "test" 2` and returns `1`
- Shows forked session with arg injection and return capture

### `core_extra.py` - Polymorphic Core Term Builders
New module providing `CoreBuilderExtra` for constructing complex typed core terms:
- **`mk_tuple(elms, elm_tys)`** — Builds nested `Pair` terms with proper type applications
- **`lookup_data_con(name)`** — Resolves datacon/tycon metadata via `TyLookup` protocol
- **`ty_con_fun(tycon, con)`** — Constructs the polymorphic type of a data constructor
- Consumes any `TyLookup` implementor, decoupling from `TcCtx` or `REPLSession`

### `test_core_extra.py` - Builder Tests
5 tests validating tuple construction, error cases, and datacon lookup.

### `elab3_demo.py` - Showcase & Test Suite
The main demo/validation script that:
- Loads modules via REPL (`builtins`, `demo`)
- Runs end-to-end assertions evaluating expressions
- Tests: arithmetic, booleans, higher-order functions, pattern matching, Maybe type, Ref operations

### `repl_driver.py` - Human Interface
Readline-based interactive REPL for manual testing:
- Expression evaluation
- `:import <module>` commands
- Multi-line input blocks
- Error reporting

## Dependencies
- `pyrsistent` - Persistent data structures
- `systemf.surface` - Surface syntax parser
- `systemf.utils` - Utilities (unique identifiers, locations)

## Analysis Documentation
The `analysis/` directory contains 70+ detailed exploration documents covering:
- Type inference algorithms and GHC correspondence
- Pattern matching and desugaring
- Module system design
- Higher-rank polymorphism
- Closure and flow analysis
- Import handling and name resolution
- REPL architecture and interactive context
- Core language translation
- Evidence wrappers (HsWrapper)
- Uniqueness management

## Current State

Elab3 is a **mature, functional implementation** with:
- Complete pipeline from source to evaluation
- Comprehensive type system with GHC-inspired inference
- Working REPL for interactive development
- **Pluggable primitive system** via `Synthesizer` + `Ext` protocols
- **Polymorphic core term builders** via `CoreBuilderExtra` (tuple construction, datacon lookup)
- **Cached O(1) type environment lookup** via `_tythings_map` in `REPLSession` and `Module`
- **Shared lookup protocol** (`TyLookup`) decoupling typechecker and evaluator contexts
- Well-documented design decisions in analysis/
- ~5,200 lines of core implementation code
- 170 tests passing

## Known Issues & Active Work

### Evaluator & Environment

| # | Issue | Status | Details |
|---|-------|--------|---------|
| 1 | **Env dict copying inefficiency** | ✅ Fixed | Migrated `Env = dict[int, Val]` to `PMap` (persistent data structure). Previously O(n) per frame in stack depth due to `cenv \| {key: val}` on every lambda application and let binding. |
| 2 | **Rec binding re-evaluation** | ✅ Fixed | `eval_mod` for `Rec` bindings now evaluates once by constructing a tuple via `CoreBuilderExtra.mk_tuple()`, then unwraps fields. Single-binder rec still uses the old direct approach. |
| 3 | **Missing core term builders** | ✅ Fixed | Added `CoreBuilderExtra.mk_tuple()` in `core_extra.py` for polymorphic tuple construction with automatic datacon/tycon lookup. |
| 4 | **Pretty printer "duplication"** | ❌ Not an issue | Originally flagged as duplication, but the three code paths serve distinct purposes: (1) Typechecker `lookup_datacon`/`lookup_tycon` validate constructors and extract field types for unification; (2) REPL `pp_val` resolves constructors for value display (now factored into `core_extra.lookup_data_con_by_tag`); (3) `core_pp.py` simply prints `con.surface` from AST nodes without any lookup. These are not duplicates. |
| 5 | **REPLSession datacon lookup uncached** | ✅ Fixed | Added `_tythings_map: dict[Name, TyThing]` to `REPLSession` and `Module` for O(1) lookup. Updated eagerly on module import. |
| 6 | **Core term builder lacks polymorphic lookup** | ✅ Fixed | `CoreBuilderExtra.lookup_data_con()` provides generic datacon/tycon lookup via the `TyLookup` protocol. Works anywhere the protocol is implemented. |
| 7 | **Lookup mechanism fragmentation** | ✅ Fixed | Introduced `TyLookup` protocol with `lookup(name: Name) -> TyThing`. `REPLSession` implements it, providing a shared interface for `CoreBuilderExtra` and other consumers. |
| 8 | **REPL wildcard pattern compilation** | ✅ Fixed | Pattern renamer treated `_` as a regular variable, causing "duplicate param names: _" errors in constructor patterns with multiple wildcards (e.g., `Cons _ _`). Now returns `WildcardPat()` for `_` which doesn't bind any variable. |
| 9 | **Synthesizer protocol** | ✅ Implemented | Full `Synthesizer` + `Ext` protocol with `SyntRouter`, `PrimOpsSynth`, `LLMSynth`. `bub_sf` extension demo working. |

### Lookup Optimization (Completed)

**Problem:** Post-typecheck, `REPLSession` stores `tythings: list[TyThing]` and module bindings, but lookup is O(n) linear scan. Same for `Module.tythings`.

**Solution Implemented:**
1. **`_tythings_map`** — `dict[Name, TyThing]` index added to both `REPLSession` and `Module`. Names have fixed uniques, giving O(1) lookup. In `REPLSession`, updated eagerly via `self._tythings_map.update(...)` on every `add_module()`. In `Module`, populated directly from `type_env` dict in the pipeline.
2. **`TyLookup` protocol** — `protocols.py` defines `TyLookup` with `lookup(name: Name) -> TyThing`. `REPLSession` implements this, allowing `CoreBuilderExtra` to consume lookup polymorphically without coupling to specific context types.

**Removed:** `_bindings_map` was considered but removed — not needed for the current use cases.

### Related Documentation

- **`analysis/ENV_AND_CORE_BUILDERS_EXPLORATION.md`** — Tracks problems #2-5 with validated claims, evidence, and open questions
- **`systemf/docs/evaluator_env_review.md`** — Detailed review of env design, dict-copying inefficiency (#1, now fixed), and closure capture issues
- **`systemf/docs/evaluator_design.md`** — Broader evaluator architecture; target design for lazy module loading, `get_eval` as sole entry point, `EvalCtx` protocol

## Entry Points

- **Demo/Testing**: `systemf/src/systemf/elab3_demo.py`
- **Extension Demo**: `bub_sf/src/bub_sf/demo.py`
- **Interactive REPL**: `cd systemf && uv run python -m systemf.elab3.repl_driver`
- **Programmatic**: `pipeline.execute(ctx, mod_name, file_path, code)`
- **Session**: `repl.REPLSession` with evaluation and import commands

## Future Direction

The primitive system architecture positions elab3 as a host language for:
- **External library integration** via module-scoped primitives (`bub_sf` is the first example)
- **Code synthesis** via factory-registered operations
- **AI agent integration** via sub-session evaluation
- **Runtime-extensible scripting** without modifying the core type checker

### Next Steps

1. **Clean Up Codebase**: Remove experimental and legacy code
2. **Recover Pragma and Docstring Passing**: Restore pragma and docstring support in the pipeline. See `analysis/DOCSTRING_RECOVERY_BLUEPRINT.md` for the new precedence-based docstring model that attaches docs to type nodes rather than arrow nodes.
3. **LLM Agent Synthesizer**: Implement `LLMSynth.get_primop()` to call an LLM API, generate code, and evaluate it in a forked session
4. **More Built-in Types**: Add `Array`, `Map`, `IO` primitive types with corresponding operations
5. **Error Handling**: Improve error messages in the typechecker and evaluator
6. **Performance**: Profile and optimize the evaluator for larger programs
7. **Documentation**: Add user-facing documentation for the surface language syntax
