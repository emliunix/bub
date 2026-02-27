# Idris2 Pragma System Analysis

## Overview

This document analyzes how Idris2 handles pragmas based on the source code in `Idris.Syntax.Pragmas` and the official documentation.

---

## 1. AST Representation

### 1.1 KwPragma Data Type

Idris2 defines a closed algebraic data type for pragma keywords:

```idris
public export
data KwPragma
  = KwHint
  | KwHide
  | KwUnhide
  | KwLogging
  | KwAutoLazy
  | KwUnboundImplicits
  | KwAmbiguityDepth
  | KwPair
  | KwRewrite
  | KwIntegerLit
  | KwStringLit
  | KwCharLit
  | KwDoubleLit
  | KwName
  | KwStart
  | KwAllowOverloads
  | KwLanguage
  | KwDefault
  | KwPrefixRecordProjections
  | KwAutoImplicitDepth
  | KwNfMetavarThreshold
  | KwSearchTimeOut
```

**Total pragmas defined in core:** 22

### 1.2 PragmaArg - Typed Arguments

Arguments to pragmas are typed, not just strings:

```idris
public export
data PragmaArg
  = AName String           -- Single identifier name
  | ANameList             -- List of names: "nm xs f"
  | APairArg              -- Pair type: "ty fst snd"
  | ARewriteArg           -- Rewrite arguments: "eq rew"
  | AnOnOff               -- Boolean: "on|off"
  | AnOptionalLoggingTopic -- Optional: "[topic]"
  | ANat                  -- Natural number: "nat"
  | AnExpr                -- Expression: "expr"
  | ALangExt              -- Language extension
  | ATotalityLevel        -- Totality: "partial|total|covering"
```

### 1.3 pragmaArgs - Associating Arguments with Pragmas

The `pragmaArgs` function defines the argument structure for each pragma:

```idris
export
pragmaArgs : KwPragma -> List PragmaArg
pragmaArgs KwHint = []
pragmaArgs KwHide = [AName "nm"]
pragmaArgs KwUnhide = [AName "nm"]
pragmaArgs KwLogging = [AnOptionalLoggingTopic, ANat]
pragmaArgs KwAutoLazy = [AnOnOff]
pragmaArgs KwUnboundImplicits = [AnOnOff]
pragmaArgs KwAmbiguityDepth = [ANat]
pragmaArgs KwPair = [APairArg]
pragmaArgs KwRewrite = [ARewriteArg]
pragmaArgs KwIntegerLit = [AName "nm"]
pragmaArgs KwStringLit = [AName "nm"]
pragmaArgs KwCharLit = [AName "nm"]
pragmaArgs KwDoubleLit = [AName "nm"]
pragmaArgs KwName = [ANameList]
pragmaArgs KwStart = [AnExpr]
pragmaArgs KwAllowOverloads = [AName "nm"]
pragmaArgs KwLanguage = [ALangExt]
pragmaArgs KwDefault = [ATotalityLevel]
pragmaArgs KwPrefixRecordProjections = [AnOnOff]
pragmaArgs KwAutoImplicitDepth = [ANat]
pragmaArgs KwNfMetavarThreshold = [ANat]
pragmaArgs KwSearchTimeOut = [ANat]
```

**Key insight:** This is essentially a schema definition that can be used for:
- Parser validation (knowing what arguments to expect)
- IDE support (autocompletion)
- Documentation generation

---

## 2. Syntax

### 2.1 Pragma Syntax Pattern

All Idris2 pragmas use the `%` prefix:

```idris
%hint
%deprecate
%logging "elab" 5
%name Foo foo,bar
%language ElabReflection
%default total
```

### 2.2 Attachment to Declarations

**Before declarations:**

```idris
%deprecate
foo : String -> String
foo x = x ++ "!"

||| Please use the @altFoo@ function from now on.
%deprecate
foo : String -> String
foo x = x ++ "!"
```

**Documentation can precede pragmas:** Triple vertical bar documentation appears BEFORE the pragma.

### 2.3 Standalone vs Declaration Pragmas

The documentation identifies three categories:

1. **Global pragmas** - Change compiler behavior until changed back:
   ```idris
   %language ElabReflection
   %default total
   %logging 1
   ```

2. **Declaration pragmas** - Apply to the following declaration:
   ```idris
   %hint
   myFunction : ...

   %inline
   fastFunction : ...
   ```

3. **Argument pragmas** - Apply directly to arguments (niche use case):
   ```idris
   %name Foo foo,bar
   ```

---

## 3. Processing

### 3.1 When Pragmas Are Processed

Based on the documentation analysis:

| Pragma Type | Processing Phase | Notes |
|------------|------------------|-------|
| `%language` | Parse/Load time | Enables language extensions for the module |
| `%default` | Parse time | Sets default totality requirement |
| `%hint` | Elaboration time | Used during type inference for auto implicits |
| `%logging` | Compile time | Controls logging during compilation |
| `%deprecate` | Usage time | Warning generated when deprecated function is used |
| `%transform` | Codegen time | Replaces function at runtime |
| `%macro` | Elaboration time | Run at compile time to generate code |

### 3.2 Global vs Declaration Pragmas

**Global pragmas:**
- Persist until explicitly changed
- Affect entire module or compilation unit
- Examples: `%language`, `%default`, `%logging`
- Can be changed mid-file: `%logging 5` then later `%logging 0`

**Declaration pragmas:**
- Apply only to the immediately following declaration
- Single use per declaration
- Examples: `%hint`, `%inline`, `%deprecate`
- Cannot be "undone" - each declaration is independent

### 3.3 Additional Pragma Categories Found in Docs

The docs reveal more pragmas than defined in `Pragmas.idr`:

- **Not in core AST:** `%builtin`, `%cg`, `%totality_depth`, `%transform`, `%spec`, `%foreign`, `%foreign_impl`, `%export`, `%nomangle`, `%defaulthint`, `%globalhint`, `%extern`, `%macro`, `%TTImpLit`, `%declsLit`, `%nameLit`, `%runElab`, `%search`, `%World`, `%MkWorld`, `%syntactic`, `%tcinline`, `%unsafe`, `%inline`, `%noinline`

This suggests some pragmas are handled in other modules or have different parsing strategies.

---

## 4. Assessment for System F

### 4.1 Pros of Idris2's Typed Pragma Arguments

1. **Compile-time validation:** The type system ensures pragmas receive correct arguments
2. **IDE support:** `pragmaArgs` provides metadata for autocompletion
3. **Documentation generation:** `pragmaTopics` can generate help text
4. **Refactoring safety:** Changing a pragma's signature requires updating all call sites
5. **Self-documenting:** The `Show` instances clearly indicate expected syntax

### 4.2 Cons of Idris2's Approach

1. **Verbosity:** 161 lines just to define 22 pragmas with their schemas
2. **Rigidity:** Adding a new pragma requires modifying the ADT and all related functions
3. **Code duplication:** `allPragmas` list must be manually kept in sync with the type
4. **Limited extensibility:** Users cannot define custom pragmas without modifying core

### 4.3 Syntax Comparison: `%prefix` vs `{-# ... #-}`

**`%prefix` (Idris2):**
- ✅ Shorter, less visual noise
- ✅ Easy to type
- ❌ Less visible (might be missed when skimming)
- ❌ Could conflict with user-defined operators

**`{-# ... #-}` (Haskell):**
- ✅ Very visible, clearly compiler directives
- ✅ No risk of collision with user code
- ❌ Verbose, more typing
- ❌ Requires balanced delimiters

### 4.4 Recommendation for System F

**Keep the simpler dict-based approach**, but consider these improvements inspired by Idris2:

1. **Optional schema validation:** Add a lightweight schema system (not mandatory)
   ```python
   # Optional typing hints, not enforced
   PRAGMA_SCHEMA = {
       "hint": [],  # No args
       "logging": ["optional_str", "int"],  # Topic (opt) + level
       "default": ["enum:partial,total,covering"],
   }
   ```

2. **Documentation generation:** Use a separate registry for help text

3. **Keep flexibility:** Dict-based approach allows:
   - Runtime-defined pragmas
   - Plugin-defined pragmas
   - Easier experimentation

4. **Consider prefix syntax:** If adopting Idris2-style pragmas, use `%` instead of `{-#` for brevity

**Verdict:** Idris2's approach is excellent for a mature, stable language with strong IDE support needs. For System F (experimental/research language), the flexibility of dict-based pragmas outweighs the type safety benefits. However, documenting expected argument formats (like Idris2's `PragmaArg` type) would improve usability.

---

## Summary

Idris2 demonstrates a well-structured pragma system with:
- **Closed ADT** for pragma kinds (22 core pragmas)
- **Typed arguments** via `PragmaArg` discriminated union
- **Schema function** (`pragmaArgs`) mapping pragmas to their expected arguments
- **Clear distinction** between global, declaration, and argument pragmas
- **`%` prefix syntax** for brevity

The trade-off is **rigidity for safety**. For System F, we should prioritize **flexibility** while optionally borrowing Idris2's documentation and validation patterns where appropriate.

---

*Analysis based on:*
- `src/Idris/Syntax/Pragmas.idr` (161 lines)
- `docs/source/reference/pragmas.rst` (517 lines)
