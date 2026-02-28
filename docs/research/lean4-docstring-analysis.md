# Lean4 Docstring System Analysis

## Overview

Lean4 has a sophisticated docstring system with support for multiple formats (Markdown and Verso), inheritance, module-level documentation, and rich metadata. This analysis examines the implementation to inform System F's design decisions.

---

## 1. Storage System

### Core Extensions

Lean4 uses **three main environment extensions** for docstring storage:

```lean
-- From Extension.lean:78-101
builtin_initialize docStringExt : MapDeclarationExtension String ←
  mkMapDeclarationExtension
    (asyncMode := .async .asyncEnv)
    (exportEntriesFn := fun _ s level =>
      if level < .server then {} else s.toArray)

private builtin_initialize inheritDocStringExt : MapDeclarationExtension Name ←
  mkMapDeclarationExtension (exportEntriesFn := fun _ s level =>
    if level < .server then {} else s.toArray)

builtin_initialize versoDocStringExt : MapDeclarationExtension VersoDocString ←
  mkMapDeclarationExtension
    (asyncMode := .async .asyncEnv)
    (exportEntriesFn := fun _ s level =>
      if level < .server then {} else s.toArray)
```

**Plus two builtin refs for compiler internals:**

```lean
private builtin_initialize builtinDocStrings : IO.Ref (NameMap String) ← IO.mkRef {}
private builtin_initialize builtinVersoDocStrings : IO.Ref (NameMap VersoDocString) ← IO.mkRef {}
```

### What is `MapDeclarationExtension`?

From `EnvExtension.lean:126-130`:

```lean
/-- Environment extension for mapping declarations to values.
    Declarations must only be inserted into the mapping in the module where they were declared. -/
structure MapDeclarationExtension (α : Type) extends PersistentEnvExtension (Name × α) (Name × α) (NameMap α)
```

**Key characteristics:**
- A typed wrapper around `PersistentEnvExtension` 
- Maps `Name` (declaration names) to values of type `α`
- **Enforces module boundary**: Can only add entries for declarations defined in the current module
- Entries are stored as sorted arrays for efficient binary search
- Supports async/parallel elaboration modes

### How Associations Work

**Insertion** (`EnvExtension.lean:154-159`):

```lean
def insert (ext : MapDeclarationExtension α) (env : Environment) (declName : Name) (val : α) : Environment :=
  if let some modIdx := env.getModuleIdxFor? declName then
    panic! s!"cannot insert `{declName}` into `{ext.name}`, it is not defined in the current module"
  else
    ext.addEntry (asyncDecl := declName) env (declName, val)
```

**Lookup** (`EnvExtension.lean:161-168`):

```leanndef find? [Inhabited α] (ext : MapDeclarationExtension α) (env : Environment) (declName : Name) : Option α :=
  match env.getModuleIdxFor? declName with
  | some modIdx =>  -- Declaration is imported
    match (ext.getModuleEntries (level := level) env modIdx).binSearch (declName, default) ...
  | none =>  -- Declaration is in current module
    (ext.getState (asyncMode := asyncMode) (asyncDecl := declName) env).find? declName
```

**The system distinguishes between:**
- **Current module**: Look in mutable state
- **Imported modules**: Look in module entries (binary search)

---

## 2. Processing Pipeline

### When Docstrings Are Added

From `Extension.lean:124-127`:

```lean
def addDocStringCore [Monad m] [MonadError m] [MonadEnv m] [MonadLiftT BaseIO m] 
    (declName : Name) (docString : String) : m Unit := do
  unless (← getEnv).getModuleIdxFor? declName |>.isNone do
    throwError m!"invalid doc string, declaration `{.ofConstName declName}` is in an imported module"
  modifyEnv fun env => docStringExt.insert env declName docString.removeLeadingSpaces
```

**Key validation**: The declaration must be defined in the current module (`getModuleIdxFor?` returns `none`).

### Flow: Parser → Elaborator → Storage

```
Source Code
     │
     ▼
Parser (Term.lean:91-92)
├── docComment: "/--" >> Doc.Parser.ifVerso versoCommentBody commentBody
│   ├── If doc.verso option is true: parse as Verso markup
│   └── Otherwise: treat as plain text/Markdown
│
     ▼
Declaration Elaboration (Add.lean)
├── addMarkdownDocString (line 257-269)
│   ├── Validates the declaration is in current module
│   ├── Validates documentation links
│   └── Inserts into docStringExt
│
├── addVersoDocString (line 306-312)
│   ├── Parses Verso syntax
│   ├── Elaborates into structured doc
│   └── Inserts into versoDocStringExt
│
     ▼
Environment Extensions
├── docStringExt: Map Name → String (Markdown)
├── versoDocStringExt: Map Name → VersoDocString
└── inheritDocStringExt: Map Name → Name (inheritance targets)
```

### Verso vs Regular Docstrings

**Verso docstrings** (`Extension.lean:62-65`):

```lean
structure VersoDocString where
  text : Array (Doc.Block ElabInline ElabBlock)
  subsections : Array (Doc.Part ElabInline ElabBlock Empty)
```

- Rich structured format with blocks, inline elements, and subsections
- Parsed into an AST (not just a string)
- Supports interactive features (hover, go-to-definition)
- Can contain executable code snippets

**Regular/Markdown docstrings**:

- Stored as plain `String`
- Processed at retrieval time (link rewriting)
- Simpler, no interactive features

**Configuration** (`Extension.lean:67-75`):

```lean
register_builtin_option doc.verso : Bool := {
  defValue := false,
  descr := "whether to use Verso syntax in docstrings"
}

register_builtin_option doc.verso.module : Bool := {
  defValue := false,
  descr := "whether to use Verso syntax in module docstrings"
}
```

---

## 3. Syntax

### Declaration Docstrings

From `Term.lean:91-92`:

```lean
def docComment := leading_parser
  ppDedent $ "/--" >> ppSpace >> Doc.Parser.ifVerso versoCommentBody commentBody >> ppLine
```

**Syntax**: `/-- ... -/` (note: just one `!`)

- Starts with `/--`
- Contains body text or Verso markup
- Ends with `-/`
- Must be followed by whitespace/line break

### Module Docstrings

From `Command.lean:58-59`:

```lean
def moduleDoc := leading_parser ppDedent <|
  "/-!" >> Doc.Parser.ifVersoModuleDocs versoCommentBody commentBody >> ppLine
```

**Syntax**: `/-! ... -/` (note the `!` after `/*`)

- Module docs are separate from declaration docs
- Stored separately in `moduleDocExt` / `versoModuleDocExt`
- Tracked with `DeclarationRange` for source location

### Module Doc Storage

From `Extension.lean:191-214`:

```lean
structure ModuleDoc where
  doc : String
  declarationRange : DeclarationRange

private builtin_initialize moduleDocExt :
    SimplePersistentEnvExtension ModuleDoc (PersistentArray ModuleDoc) ← registerSimplePersistentEnvExtension {
  addImportedFn := fun _ => {}
  addEntryFn    := fun s e => s.push e
  exportEntriesFnEx? := some fun _ _ es level =>
    if level < .server then #[] else es.toArray
}
```

### Docstring Inheritance

From `Extension.lean:139-146`:

```lean
def addInheritedDocString [Monad m] [MonadError m] [MonadEnv m] (declName target : Name) : m Unit := do
  unless (← getEnv).getModuleIdxFor? declName |>.isNone do
    throwError "invalid `[inherit_doc]` attribute, declaration ... is in an imported module"
  if inheritDocStringExt.find? (level := .server) (← getEnv) declName |>.isSome then
    throwError "invalid `[inherit_doc]` attribute, declaration ... already has an `[inherit_doc]` attribute"
  if inheritDocStringExt.find? (level := .server) (← getEnv) target == some declName then
    throwError "invalid `[inherit_doc]` attribute, cycle detected"
  modifyEnv fun env => inheritDocStringExt.insert env declName target
```

**Inheritance mechanism:**
- Uses `[inherit_doc]` attribute
- Maps declaration → target declaration (whose doc to inherit)
- Cycle detection prevents infinite loops
- One level of indirection per declaration

---

## 4. Query Interface

### Main Query: `findDocString?`

From `DocString.lean:33-38`:

```lean
def findDocString? (env : Environment) (declName : Name) (includeBuiltin := true) : IO (Option String) := do
  let declName := alternativeOfTactic env declName |>.getD declName
  let exts := getTacticExtensionString env declName
  let spellings := getRecommendedSpellingString env declName
  let str := (← findSimpleDocString? env declName (includeBuiltin := includeBuiltin)).map (· ++ exts ++ spellings)
  str.mapM (rewriteManualLinks ·)
```

**Processing steps:**
1. **Tactic alternates**: Resolves alternative tactic forms (e.g., `rw` vs `rewrite`)
2. **Extensions**: Appends tactic extension documentation
3. **Spellings**: Appends recommended identifier spellings
4. **Simple lookup**: Gets the base docstring
5. **Link rewriting**: Rewrites manual links (`#foo` → proper URLs)

### Simple Query: `findSimpleDocString?`

From `Extension.lean:176-189`:

```lean
def findSimpleDocString? (env : Environment) (declName : Name) (includeBuiltin := true) : IO (Option String) := do
  match (← findInternalDocString? env declName (includeBuiltin := includeBuiltin)) with
  | some (.inl str) => return some str
  | some (.inr verso) => return some (toMarkdown verso)
  | none => return none
```

### Internal Query with Inheritance Resolution

From `Extension.lean:154-168`:

```lean
partial def findInternalDocString? (env : Environment) (declName : Name) (includeBuiltin := true) : IO (Option (String ⊕ VersoDocString)) := do
  if let some target := inheritDocStringExt.find? (level := .server) env declName then
    return (← findInternalDocString? env target includeBuiltin)  -- Follow inheritance chain
  match docStringExt.find? (level := .server) env declName with
  | some md => return some (.inl md)
  | none => pure ()
  match versoDocStringExt.find? (level := .server) env declName with
  | some v => return some (.inr v)
  | none => pure ()
  if includeBuiltin then
    if let some docStr := (← builtinDocStrings.get).find? declName then
      return some (.inl docStr)
    else if let some doc := (← builtinVersoDocStrings.get).find? declName then
      return some (.inr doc)
  return none
```

**Lookup order:**
1. Check inheritance chain (follow until concrete doc found)
2. Check user-defined Markdown doc
3. Check user-defined Verso doc
4. Check builtin Markdown doc
5. Check builtin Verso doc

---

## 5. Assessment for System F Implementation

### Should We Store Docstrings in Environment?

**Lean4's approach:**
- ✅ Docstrings are in environment extensions (persistent, module-scoped)
- ✅ Lookups work across module boundaries (binary search in imported entries)
- ✅ Async-safe for parallel elaboration
- ✅ Validation prevents modifying imported declarations

**Current System F approach (likely):**
- Docstrings in Module dataclass
- Simpler, but lookups require accessing module objects
- Module-level scoping is explicit

### Pros/Cons Comparison

| Aspect | Environment Extensions (Lean4) | Module Dataclass (Simple) |
|--------|-------------------------------|---------------------------|
| **Lookup speed** | O(log n) via binary search | O(1) dict access |
| **Cross-module** | Automatic via env | Manual module resolution |
| **Persistence** | Built into env serialization | Need custom serialization |
| **Validation** | Automatic (cannot modify imports) | Manual validation needed |
| **Complexity** | Higher (async modes, levels) | Lower |
| **Memory** | Shared across threads | Per-module |
| **Tooling** | Works with env-based tools | Need doc-specific tools |

### Recommendation for System F

**Keep docstrings in Module dataclass** for now because:

1. **Simplicity**: System F is simpler than Lean4 (no async elaboration)
2. **Explicitness**: Module-level scoping is clearer
3. **Sufficient**: For a research/educational compiler, module-level storage is adequate
4. **Migration path**: Can move to environment later if needed

**However, consider environment storage if:**
- Need cross-module doc lookups without loading modules
- Building IDE features that need fast doc access
- Implementing incremental compilation with async processing
- Want automatic persistence with .olean equivalents

### Key Design Decisions to Consider

1. **Format support**: Start with simple strings, can add structured format later
2. **Module docs**: Separate storage for module-level documentation
3. **Inheritance**: Optional feature, can be added later
4. **Builtin docs**: Separate storage for compiler-internal documentation
5. **Link validation**: Process at add-time vs retrieve-time

### Implementation Sketch for System F

```python
@dataclass
class DocString:
    text: str
    # Future: format, source_location, etc.

@dataclass  
class Module:
    name: str
    docstrings: dict[str, DocString]  # decl_name -> doc
    module_doc: Optional[DocString]
    # ... other fields

def add_docstring(module: Module, decl_name: str, text: str) -> None:
    """Add docstring to current module."""
    # Validate: decl_name must be defined in this module
    if decl_name not in module.declarations:
        raise ValueError(f"Cannot add docstring to {decl_name}: not in current module")
    module.docstrings[decl_name] = DocString(text)

def find_docstring(env: Environment, decl_name: str) -> Optional[str]:
    """Find docstring across all loaded modules."""
    # Find which module defines decl_name
    module = env.find_decl_module(decl_name)
    if module and decl_name in module.docstrings:
        return module.docstrings[decl_name].text
    return None
```

This is simpler than Lean4 but sufficient for System F's current scope.

---

## 6. REPL Query Architecture

### Storage and Query Mechanism

Lean4 uses `MapDeclarationExtension` for docstring storage with a **two-tier lookup system**:

```lean
-- From EnvExtension.lean:161-168
def find? [Inhabited α] (ext : MapDeclarationExtension α) (env : Environment) (declName : Name) : Option α :=
  match env.getModuleIdxFor? declName with
  | some modIdx =>
    -- Imported module: binary search in sorted array (O(log n))
    match (ext.getModuleEntries env modIdx).binSearch (declName, default) (fun a b => Name.quickLt a.1 b.1) with
    | some e => some e.2
    | none   => none
  | none =>
    -- Current module: RBTree lookup (O(log n))
    (ext.getState env).find? declName
```

**Key findings:**
- **Not O(1) hash map anywhere** - both tiers use O(log n) data structures
- Imported modules use **binary search** on sorted arrays (cache-friendly, persistent)
- Current module uses **RBTree** (persistent, efficient for <10k entries)
- Trade-off: persistent data structures over mutable hash maps for async safety

### How `#check` Command Works

The `#check` command uses the **Environment's declaration map**, not environment extensions:

```lean
-- From Elab/BuiltinCommand.lean:430-437
def elabCheckCore (ignoreStuckTC : Bool) : CommandElab
  | `(#check%$tk $term) => withoutModifyingEnv <| runTermElabM fun _ => Term.withDeclName `_check do
    if let `($id:ident) := term then
      for c in (← realizeGlobalConstWithInfos term) do
        logInfoAt tk <| .signature c  -- Lookup in env declaration map
        return
    let e ← Term.elabTerm term none  -- Elaboration uses environment
    ...
```

**Difference from docstring queries:**
- `#check` resolves constants via `realizeGlobalConstWithInfos` → Environment's constant map
- Docstrings use `MapDeclarationExtension.find?` → separate extension maps
- Both operate on the Environment, but through different mechanisms

### Inheritance Chain Resolution

Docstring inheritance is resolved during lookup, not storage:

```lean
-- From Extension.lean:154-168
partial def findInternalDocString? (env : Environment) (declName : Name) : IO (Option (String ⊕ VersoDocString)) := do
  if let some target := inheritDocStringExt.find? env declName then
    return (← findInternalDocString? env target)  -- Recursive inheritance resolution
  match docStringExt.find? env declName with
  | some md => return some (.inl md)
  | none => pure ()
  match versoDocStringExt.find? env declName with
  | some v => return some (.inr v)
  | none => pure ()
  ...
```

**Chain resolution order:**
1. Follow inheritance links (via `inheritDocStringExt`)
2. Check Markdown docs (`docStringExt`)
3. Check Verso docs (`versoDocStringExt`)
4. Check builtin docs

### Comparison: Lean4 vs Idris2 for REPL

| Aspect | Lean4 | Idris2 |
|--------|-------|--------|
| **Lookup complexity** | O(log n) | O(1) average |
| **Data structure** | RBTree + sorted arrays | Hash map |
| **Persistence** | Native (persistent DS) | Requires copying |
| **Async safety** | Built-in | Requires locks/mutable state |
| **Cross-module** | Binary search in imports | Direct lookup if loaded |
| **REPL overhead** | Higher | Lower |
| **IDE/LSP** | Excellent | Good |

**When to use which:**
- **Lean4 approach**: When you need LSP, async elaboration, or .olean-style caching
- **Idris2 approach**: For simple REPL-only tools where O(1) lookup matters more than persistence

### Updated Recommendation for System F

For a **REPL-only tool** (no LSP, no async):

**Recommended: Idris2-style AST-embedded storage**

```python
@dataclass
class Declaration:
    name: str
    docstring: Optional[str]  # Embedded, not external
    # ... other fields

@dataclass
class Module:
    declarations: dict[str, Declaration]  # O(1) lookup
```

**Why not Lean4's environment extensions:**
1. **No async needs**: REPL is sequential, persistent DS overhead unnecessary
2. **No cross-module queries**: You load what you need, no binary search needed
3. **Simpler implementation**: No environment extension machinery
4. **Better REPL performance**: O(1) hash map vs O(log n) tree

**When to switch to Lean4-style:**
- Adding LSP support (needs fast cross-module lookups)
- Implementing incremental compilation
- Needing .olean-style object file caching
- Adding async elaboration for performance

**Key insight:** Lean4's complexity is justified for their use case (full IDE support + async + persistence). For a research REPL, the simpler approach is preferable until those features are actually needed.
