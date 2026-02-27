---
type: kanban
title: LLM Integration
created: 2026-02-27T17:28:26.091407
phase: exploration
current: null
tasks: []
---

# Kanban: LLM Integration

## Request
Integrate LLM function support with Haddock-style docstrings, compile-time primitive generation, and evaluator integration. Depends on Module implementation (kanban 50).

## Goal
Enable LLM-annotated functions in SystemF to be compiled into LLM calls with automatically crafted prompts:

```systemf
{-# LLM model=gpt-4 temperature=0.7 #-}
-- | Translate English to French
translate : String -> String
translate = \text -- ^ The English text to translate
    -> text  -- Fallback identity
```

## Technical Design

### Core Concept: Compile-Time Derived Primitives

LLM calls are **elaboration-time derived primitives**. The elaborator crafts a primitive operation based on the function signature + Haddock docstrings, and the evaluator executes it by constructing prompts and calling LLM APIs.

**Why not runtime reflection?**
- Cleaner separation: compile-time metadata vs runtime execution
- No runtime overhead for introspection
- Metadata baked into closure at elaboration time
- Reuses existing primitive infrastructure

### Syntax and Parsing

**Function-level docstring (-- | style):**
```systemf
-- | Translate English to French
translate : String -> String
```

**Parameter-level docstring (-- ^ style, Haddock):**
```systemf
translate = \text -- ^ The English text to translate
    -> text
```

**Pragma for LLM configuration:**
```systemf
{-# LLM model=gpt-4 temperature=0.7 #-}
```

### Elaboration Flow

1. **Detect Pragma**: SurfaceTermDeclaration has `pragma: SurfacePragma | None`
   - Check if `pragma.directive == "LLM"`

2. **Extract Function Doc**: From `SurfaceTermDeclaration.docstring` (-- | style)

3. **Extract Param Docs**: Parse `-- ^` comments from lambda parameters
   - Need to extend SurfaceAbs to capture param_docstrings
   - Align by position: `arg_names[i]` matches `arg_docstrings[i]`

4. **Extract Types**: From `SurfaceTermDeclaration.type_annotation`
   - Function type: `String -> String`
   - Extract arg types and return type

5. **Build LLMMetadata**:
   ```python
   LLMMetadata(
       function_name="translate",
       function_docstring="Translate English to French",
       arg_names=["text"],
       arg_types=[PrimitiveType("String")],
       arg_docstrings=["The English text to translate"],
       model="gpt-4",
       temperature=0.7
   )
   ```

6. **Create Closure with Baked Metadata**:
   ```python
   def create_llm_closure(metadata: LLMMetadata, fallback_body: Term):
       def llm_impl(arg_val: Value) -> Value:
           # Closure captures metadata!
           prompt = craft_prompt(
               metadata.function_docstring,
               metadata.arg_names,
               metadata.arg_docstrings,
               [arg_val]
           )
           result = call_llm(prompt, model=metadata.model, temperature=metadata.temperature)
           if result.success:
               return parse_llm_response(result.text)
           else:
               # Fallback to original lambda
               return evaluate(fallback_body, [arg_val])
       return llm_impl
   ```

7. **Register in Evaluator**:
   ```python
   evaluator.primitive_impls[f"$llm.{name}"] = create_llm_closure(metadata, body)
   ```

8. **Elaborate Body to PrimOp**:
   ```python
   core_body = PrimOp(f"$llm.{name}")  # Instead of elaborating the lambda
   ```

9. **Store Metadata in Module**:
   ```python
   module.llm_functions[name] = metadata
   ```

### Evaluator Integration

**Current Primitive Evaluation:**
```python
case PrimOp(name):
    return self._make_primop_closure(name)
```

**LLM Primitive Evaluation (seamless integration):**
```python
case PrimOp(name):
    if name.startswith("$llm."):
        # Already registered closure - just return it
        return VPrimOp(name, self.primitive_impls[name])
    else:
        return self._make_primop_closure(name)
```

**Type Checking:**
- Looks up `$llm.function_name` in `module.global_types`
- Type signature comes from user annotation (normal primitive lookup)
- No special handling needed in type checker

### Prompt Construction

**Template Structure:**
```
You are a function: {function_docstring}

Arguments:
- {arg_name}: {arg_docstring} (type: {arg_type})

Call with:
{text} = {arg_value}

Respond only with the result value.
```

**Example for `translate`:**
```
You are a function: Translate English to French

Arguments:
- text: The English text to translate (type: String)

Call with:
text = "Hello world"

Respond only with the result value.
```

### Design Decisions

**1. Reuse PrimOp (Not New AST Node)**
- Minimal changes to core AST
- Type checker treats it as regular primitive
- Evaluator already handles PrimOp

**2. Closure for Metadata (Not Runtime Reflection)**
- Metadata baked at elaboration time
- No runtime lookup overhead
- Clean functional style

**3. Haddock -- ^ Convention**
- Established Haskell documentation standard
- Users familiar with functional programming will recognize it
- Clear distinction: -- | for function, -- ^ for params

**4. Fallback to Lambda Body**
- Original implementation preserved
- On LLM failure: execute lambda instead
- Allows pure functional testing without API calls

**5. $llm. Namespace**
- Avoids conflicts with user-defined names
- Clear indication of LLM-derived primitive
- Consistent with $prim. namespace pattern

### Relevant Files

**Parser (Surface Layer):**
- `systemf/src/systemf/surface/lexer.py` - Add -- ^ token recognition
- `systemf/src/systemf/surface/parser.py` - Parse param docstrings in lambda
- `systemf/src/systemf/surface/ast.py` - Add param_docstrings to SurfaceAbs

**Elaborator (Compile-Time):**
- `systemf/src/systemf/surface/elaborator.py` - Detect LLM pragma, extract metadata, create closure
- `systemf/src/systemf/core/module.py` - LLMMetadata dataclass (already in Module kanban)

**Evaluator (Runtime):**
- `systemf/src/systemf/eval/machine.py` - Register and execute LLM closures
- `systemf/src/systemf/eval/value.py` - (No changes - reuse existing)

**Configuration:**
- Environment variables for API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- Pragma for model selection: `{-# LLM model=gpt-4 #-}`

### Dependencies

- **Module system (kanban 50)** must be complete first
- `Module.llm_functions` registry for metadata storage
- `Module` passed to elaborator for registration

### References

**Current Surface Declaration with Pragma:**
```python
@dataclass(frozen=True)
class SurfaceTermDeclaration:
    name: str
    type_annotation: Optional[SurfaceType]
    body: SurfaceTerm
    location: Location
    docstring: str | None = None      # -- | style
    pragma: SurfacePragma | None = None  # {-# ... #-}
```

**Current Elaboration of Term Declaration:**
```python
def _elaborate_term_decl(self, decl: SurfaceTermDeclaration):
    core_type = self._elaborate_type(decl.type_annotation)
    self._add_global_term(decl.name)
    core_body = self.elaborate_term(decl.body)  # Elaborates lambda to Abs
    return core.TermDeclaration(name, core_type, core_body)
```

**Current Lambda Parsing:**
```systemf
\x:T -> body    -- SurfaceAbs(var="x", var_type=T, body=...)
```

**Primitive Registration:**
```python
# In _elaborate_prim_op_decl
self.global_types[f"$prim.{name}"] = core_type
evaluator.primitive_impls[name] = impl_closure
```

### Trade-offs Considered

**Alternative: Runtime Reflection Object**
- ❌ Rejected: Would require new VTool runtime value type
- ❌ Runtime overhead for metadata lookup
- ✅ Current approach: Zero runtime overhead

**Alternative: Separate LLM AST Node**
- ❌ Rejected: Would require type checker changes
- ❌ More complex AST
- ✅ Current approach: Reuses PrimOp, minimal AST changes

**Alternative: No Fallback (Pure LLM)**
- ❌ Rejected: Requires API availability for testing
- ❌ No offline development
- ✅ Current approach: Lambda body as fallback enables testing

**Alternative: Different Docstring Syntax**
- ❌ Considered: `@param name description` (JavaDoc style)
- ❌ Considered: `[name]: description` (custom)
- ✅ Chose: `-- ^ description` (Haddock) - established convention in FP community

## Plan Adjustment Log
<!-- Manager logs plan adjustments here -->
