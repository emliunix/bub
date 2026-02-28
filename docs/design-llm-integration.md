# System F LLM Integration Design Document

**Status:** Design Complete  
**Date:** 2026-02-28  
**Scope:** LLM Function Syntax & Multi-Pass Architecture

---

## Part 1: Conversation Summary

### Topics Explored

1. **Pragma & Docstring Handling Strategy**
   - Multi-pass vs inline attachment
   - Research of Idris2 and Lean4 approaches
   - AST-embedded vs environment extensions

2. **LLM Function Syntax Design**
   - Old syntax (`extern` body) vs new `prim_op` syntax
   - Parameter docstring placement (`-- ^`)
   - Function docstring placement (`-- |`)

3. **AST Architecture**
   - Global vs lexical declarations
   - Type-embedded parameter docs
   - Extraction timing (after type checking)

4. **REPL Query Architecture**
   - Performance considerations (O(1) vs O(log n))
   - Idris2-style (AST-embedded) vs Lean4-style (environment extensions)

### Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Docstring Storage** | AST-embedded (Idris2-style) | O(1) lookups, simpler, sufficient for REPL |
| **Multi-pass** | Single-pass inline attachment | Simpler parser, no orphan comment issues |
| **LLM Syntax** | `prim_op` keyword | Aligns with primitive system, no `extern` body |
| **Param Docs** | Type-embedded (`-- ^` on types) | Universal across all type constructs |
| **Extraction Timing** | After type checking | Validated types, single extraction point |
| **Global vs Local** | Asymmetry accepted | LLM functions must be global, locals for closures |

### Rejected Options

| Option | Why Rejected |
|--------|--------------|
| **Lean4-style environment extensions** | Overkill for REPL-only, adds complexity |
| **Multi-pass comment attachment** | Unnecessary complexity for current scope |
| **Old `extern` body syntax** | Awkward, doesn't align with primitives |
| **Separate attachment pass** | Current inline attachment is sufficient |
| **Lambda parameter docs** | Not needed for LLM use case (type docs sufficient) |

### Key Rationales

1. **Idris2 vs Lean4**: Both advisors confirmed Idris2-style O(1) dict lookups are better for REPL-only tools without LSP/async needs.

2. **`prim_op` syntax**: Cleaner, aligns with `prim_type` and `prim_op` for regular primitives. No artificial `extern` marker.

3. **Type-embedded docs**: Docstrings attach to type positions, not just declarations. Works for: `String --^ doc`, `(Int -> Int) --^ doc`, etc.

4. **Post-typecheck extraction**: Ensures types are validated before building LLM metadata. Single extraction point to `Module.docstrings`.

---

## Part 2: Final Design

### 2.1 Component Overview

```
Source File
    ↓
Lexer (tokens with comments preserved)
    ↓
Parser (Surface AST with inline docs)
    ↓
Elaborator (Core AST, name resolution)
    ↓
Type Checker (validation)
    ↓
Doc Extraction (Module.docstrings)
    ↓
LLM Metadata Extraction (Module.llm_functions)
    ↓
REPL (queries via dict lookup)
```

### 2.2 Surface AST

#### Type Annotations with Docs

```python
@dataclass(frozen=True)
class SurfaceTypeArrow:
    """Function type: arg -> ret with optional param doc."""
    arg: SurfaceType
    ret: SurfaceType
    param_doc: Optional[str] = None  # -- ^ docstring
    location: Location
```

#### Declarations

```python
@dataclass(frozen=True)
class SurfaceTermDeclaration:
    """Term declaration with mandatory type annotation."""
    name: str
    type_annotation: SurfaceType  # Required! (was Optional)
    body: SurfaceTerm
    location: Location
    docstring: Optional[str] = None  # -- | function doc
    pragma: dict[str, str] | None = None

@dataclass(frozen=True)
class SurfacePrimOpDecl:
    """Primitive operation: prim_op name : type."""
    name: str
    type_annotation: SurfaceType  # Has param_doc embedded
    location: Location
    docstring: Optional[str] = None

@dataclass(frozen=True)
class SurfaceLet:
    """Local let binding with optional type annotation."""
    var: str
    var_type: Optional[SurfaceType]  # NEW: explicit annotation support
    value: SurfaceTerm
    body: SurfaceTerm
    location: Location
```

### 2.3 Core AST

Clean AST without docstrings (extracted separately):

```python
@dataclass(frozen=True)
class TermDeclaration:
    """Core term declaration - docs extracted to Module."""
    name: str
    type_annotation: Type
    body: Term
    pragma: Optional[str] = None  # Raw pragma string
    # Note: docstrings NOT here - extracted to Module.docstrings
```

### 2.4 Module Structure

```python
@dataclass(frozen=True)
class Module:
    name: str
    declarations: list[Declaration]
    constructor_types: dict[str, Type]
    global_types: dict[str, Type]
    primitive_types: dict[str, PrimitiveType]
    
    # Docstrings: key -> doc text
    # Keys: "name" (function), "name.$n" (param n), "name.$field" (field)
    docstrings: dict[str, str]
    
    # LLM metadata extracted after type checking
    llm_functions: dict[str, LLMMetadata]
    
    errors: list[ElaborationError]
    warnings: list[str]
```

### 2.5 LLMMetadata

```python
@dataclass(frozen=True)
class LLMMetadata:
    """Validated LLM function metadata."""
    function_name: str
    function_docstring: Optional[str]
    arg_names: list[str]  # Extracted from type
    arg_types: list[Type]  # Validated types
    arg_docstrings: list[Optional[str]]  # From type_annotation
    pragma_params: Optional[str]  # Raw pragma content
```

### 2.6 Naming Conventions for Docstring Keys

```
Function doc:        "translate"
Param 1 doc:         "translate.$1"
Param 2 doc:         "translate.$2"
Record field:        "Person.$name"
Constructor param:   "Maybe.$Just.$1"
```

### 2.7 Syntax Examples

**Single parameter LLM function:**
```systemf
{-# LLM model=gpt-4 temperature=0.7 #-}
-- | Translate English to French
prim_op translate : String
  -- ^ The English text to translate
  -> String
```

**Multi-parameter:**
```systemf
{-# LLM model=gpt-4 #-}
-- | Classify text into categories
prim_op classify : String
  -- ^ Comma-separated list of categories
  -> String
  -- ^ The text to classify
  -> String
```

**Higher-order:**
```systemf
-- | Apply function to value
prim_op apply : (a -> b)
  -- ^ Function to apply
  -> a
  -- ^ Argument
  -> b
```

**Regular function (with body):**
```systemf
-- | Identity function
identity : forall a. a -> a
identity = \x -> x
```

**Local let with annotation:**
```systemf
let x : Int = 42 in x + 1
```

---

## Part 3: Execution Plan

### Phase 1: Foundation (Boundaries & Core Types)

**Step 1.1: Update Surface AST**
- Modify `SurfaceTypeArrow` to include `param_doc: Optional[str]`
- Make `type_annotation` required in `SurfaceTermDeclaration`
- Add `var_type` to `SurfaceLet`
- Update `SurfacePrimOpDecl` to include docstring support

**Step 1.2: Update Core AST**
- Ensure `TermDeclaration` carries pragma through
- No docstring fields (extracted separately)

**Step 1.3: Update Module**
- Confirm `docstrings: dict[str, str]` field
- Confirm extraction happens post-typecheck

### Phase 2: Examples & Tests (Validation)

**Step 2.1: Update Example Files**
- `llm_examples.sf` - new syntax
- `llm_multiparam.sf` - multi-param with docs
- `llm_complex.sf` - complex types

**Step 2.2: Update Parser Tests**
- Test `-- ^` attached to types
- Test `prim_op` declarations
- Test multi-param type parsing

**Step 2.3: Update Elaborator Tests**
- Verify `PrimOp` generation for LLM functions
- Verify docstrings preserved in Core AST

**Step 2.4: Update Integration Tests**
- Test full pipeline: parse → elaborate → typecheck → extract
- Verify `Module.docstrings` populated correctly
- Verify `Module.llm_functions` has validated types

### Phase 3: Component Implementation

**Step 3.1: Parser Changes**
- Parse `-- ^` within type annotations
- Parse `prim_op` declarations
- Handle multi-line type annotations

**Step 3.2: Elaborator Changes**
- Support `prim_op` (auto-generate `PrimOp` body)
- Pass pragma through to Core AST
- Pass docstrings through (don't extract yet)

**Step 3.3: Type Checker Changes**
- Handle `PrimOp("llm.name")` type lookup
- Validate all types before extraction

**Step 3.4: Doc Extraction Module**
- Walk Core AST types
- Extract docs using naming conventions
- Populate `Module.docstrings`

**Step 3.5: LLM Metadata Extraction**
- Extract from validated types
- Build `LLMMetadata` with final types
- Populate `Module.llm_functions`

### Phase 4: Integration & Cleanup

**Step 4.1: REPL Integration**
- Call extraction passes after type checking
- Update REPL queries to use `Module.docstrings`

**Step 4.2: Test Review**
- Remove obsolete tests (old syntax)
- Add missing coverage
- Verify all tests pass

**Step 4.3: Documentation**
- Update user-facing docs with new syntax
- Document naming conventions for doc keys

---

## Part 4: Component Specifications

### Component: SurfaceTypeArrow

**Location:** `src/systemf/surface/ast.py`

**Change:** Add `param_doc` field

```python
@dataclass(frozen=True)
class SurfaceTypeArrow:
    arg: SurfaceType
    ret: SurfaceType
    param_doc: Optional[str] = None  # NEW
    location: Location
```

**Spec:**
- `param_doc` is populated when parser sees `-- ^` after a type
- Only applies to the argument position (the type before `->`)
- Can be `None` for types without documentation

### Component: SurfaceTermDeclaration

**Location:** `src/systemf/surface/ast.py`

**Change:** Make type annotation required

```python
@dataclass(frozen=True)
class SurfaceTermDeclaration:
    name: str
    type_annotation: SurfaceType  # Was Optional, now required
    body: SurfaceTerm
    location: Location
    docstring: Optional[str] = None
    pragma: dict[str, str] | None = None
```

**Spec:**
- All global declarations MUST have type annotations
- This aligns with System F's explicit typing philosophy
- Pragma is dict for extensibility (multiple pragma types possible)

### Component: SurfaceLet

**Location:** `src/systemf/surface/ast.py`

**Change:** Add `var_type` field

```python
@dataclass(frozen=True)
class SurfaceLet:
    var: str
    var_type: Optional[SurfaceType]  # NEW
    value: SurfaceTerm
    body: SurfaceTerm
    location: Location
```

**Spec:**
- Optional type annotation for bidirectional type checking
- Allows explicit annotation when inference fails
- Syntax: `let x : Type = value in body`

### Component: SurfacePrimOpDecl

**Location:** `src/systemf/surface/ast.py`

**Current:** Already exists

**Spec:**
- Represents `prim_op name : type` syntax
- No body (implicit `PrimOp`)
- Can have function-level docstring (`-- |`)
- Type can have parameter docs (`-- ^` embedded in type)

### Component: Parser (Type Annotation)

**Location:** `src/systemf/surface/parser.py`

**Spec:**

1. **Parse `-- ^` in types:**
   ```python
   # When parsing type arrow:
   arg_type = parse_type()
   doc_comment = parse_optional_doc_comment()  # -- ^ text
   expect(ARROW)
   ret_type = parse_type()
   return SurfaceTypeArrow(arg_type, ret_type, doc_comment)
   ```

2. **Parse `prim_op` declarations:**
   ```python
   # prim_op name : type
   expect(PRIM_OP)
   name = parse_ident()
   expect(COLON)
   type_ann = parse_type()  # Type has embedded param docs
   return SurfacePrimOpDecl(name, type_ann, ...)
   ```

3. **Parse multi-line types:**
   - Support `-- ^` on separate lines
   - Handle indentation correctly

### Component: Elaborator

**Location:** `src/systemf/surface/elaborator.py`

**Spec:**

1. **Handle `prim_op`:**
   - Auto-generate `PrimOp(f"llm.{name}")` body
   - Register type in `global_types`
   - Pass docstring through to Core AST

2. **Regular functions:**
   - Elaborate body normally
   - Pass docstring through

3. **Do NOT extract docs yet:**
   - Keep docstrings in Core AST
   - Extraction happens after type checking

### Component: Type Checker

**Location:** `src/systemf/core/checker.py`

**Spec:**

1. **Handle `PrimOp("llm.name")`:**
   - Look up type in `global_types`
   - Validate existence

2. **Validate all types:**
   - Ensure type constructors exist
   - Unify where needed

3. **After validation:**
   - Return `global_types` mapping
   - Used for doc extraction

### Component: Doc Extraction Pass

**Location:** NEW `src/systemf/docs/extractor.py`

**Spec:**

```python
def extract_docs(module: Module, global_types: dict[str, Type]) -> dict[str, str]:
    """Extract all docstrings from validated module.
    
    Returns: dict mapping name to docstring
        "func" -> function doc
        "func.$1" -> param 1 doc
        "func.$2" -> param 2 doc
    """
```

**Algorithm:**
1. Iterate declarations
2. For each declaration with docstring: add to dict
3. Walk type annotation, extract param docs
4. Build keys using naming convention

### Component: LLM Metadata Extraction

**Location:** `src/systemf/llm/extractor.py`

**Spec:**

```python
def extract_llm_metadata(module: Module, global_types: dict[str, Type]) -> dict[str, LLMMetadata]:
    """Extract LLM metadata after type checking.
    
    Only processes declarations with pragma containing "LLM".
    Uses validated types from global_types.
    """
```

**Algorithm:**
1. Find declarations with `pragma` containing "LLM"
2. Extract function docstring (from declaration)
3. Extract arg types from validated type (walk arrows)
4. Extract arg docstrings (from type's param_doc fields)
5. Build `LLMMetadata` with all fields
6. Return dict mapping name to metadata

### Component: REPL Integration

**Location:** `src/systemf/eval/repl.py`

**Spec:**

```python
# After type checking:
types = checker.check_program(module.declarations)

# Extract docs
module.docstrings = extract_docs(module, types)

# Extract LLM metadata
module.llm_functions = extract_llm_metadata(module, types)

# Register closures (future)
# for name, metadata in module.llm_functions.items():
#     evaluator.register_llm_closure(name, metadata)
```

---

## Appendix A: Test Plan

### Unit Tests

1. **Parser Tests**
   - `test_parse_prim_op_declaration`
   - `test_parse_type_with_param_doc`
   - `test_parse_multi_param_type_with_docs`
   - `test_parse_let_with_type_annotation`

2. **Elaborator Tests**
   - `test_elab_prim_op_generates_primop_body`
   - `test_elab_function_preserves_docstring`
   - `test_elab_mandatory_type_annotation`

3. **Doc Extraction Tests**
   - `test_extract_function_doc`
   - `test_extract_param_docs`
   - `test_extract_multi_param_docs`
   - `test_extract_record_field_docs` (future)

4. **LLM Metadata Tests**
   - `test_extract_llm_metadata_with_validated_types`
   - `test_llm_metadata_has_arg_docs`
   - `test_llm_metadata_pragma_params`

### Integration Tests

1. **End-to-End Pipeline**
   - Parse `llm_examples.sf` → elaborate → typecheck → extract
   - Verify `Module.docstrings` populated
   - Verify `Module.llm_functions` has correct types

2. **REPL Queries**
   - `:doc translate` returns function doc
   - `:t translate` shows validated type

### Obsolete Tests (to remove/update)

1. Old syntax tests using `extern` body
2. Lambda parameter docstring tests (if any)
3. Tests expecting early extraction in elaborator

---

## Appendix B: Migration Guide

### For Users

**Old syntax:**
```systemf
translate : String -> String
translate = \text -- ^ doc -> extern
```

**New syntax:**
```systemf
{-# LLM #-}
-- | Function description
prim_op translate : String
  -- ^ Parameter description
  -> String
```

### For Developers

- **Parser**: Handle `-- ^` in types, parse `prim_op`
- **Elaborator**: Generate `PrimOp` for `prim_op`, pass docs through
- **Type Checker**: Look up `llm.name` in `global_types`
- **New Pass**: Doc extraction after type checking
- **Tests**: Update to new syntax

---

*End of Design Document*
