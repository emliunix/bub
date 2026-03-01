# Parser Docstring & Pragma Implementation - Technical Debt Report

**Generated:** After Tasks 75-78 completion  
**Last Updated:** 2026-03-01  
**Purpose:** Document workarounds, hacks, and non-obvious implementation details for future maintainers

---

## Current Status

### Recently Fixed
- ✅ **Removed dead pragma token patterns** - `PRAGMA_START`, `PRAGMA_END`, `PRAGMA_CONTENT` removed from `parser.py` (lines 147-151), verified not in lexer
- ✅ **Refactored docstring processing** - `process_comments()` now uses nested while loop with Idris2-style whitespace stripping
- ✅ **Pragma parsing** - `top_decl_parser()` now properly accumulates pragmas before declarations
- ✅ **Multiple declarations** - Parser now handles multiple declarations in one file correctly
- ✅ **Constructor termination** - Fixed data parser to stop at `|` separator and `ident :` patterns
- ✅ **Nested forall types** - `forall a. forall b. type` now parses correctly
- ✅ **Token location access** - Fixed `.column` -> `.location.column` in 5 locations

### Still Broken / Needs Work (Feature Goals, Not Bugs)
- 🔵 **Type abstraction syntax** - `Λa. expr` not yet supported (feature goal)
- 🔵 **Multi-argument forall** - `forall a b.` space-separated syntax (feature goal)

### Remaining Technical Debt (Priority Order)

#### Medium Priority
1. **Extract mapping dictionaries** - `op_map`/`delim_map` recreated fresh every call to `_create_token()` in lexer.py
2. **Simplify Parser class** - "Old API" compatibility wrapper in `__init__.py` needs review
3. **Add bounds checking** - Relies on `hasattr(e, "index")` parsy internals for error location extraction

#### Low Priority
7. **Unify parsing strategies** - Consider using parsy combinators in `top_decl_parser()`
8. **Refactor _raw() pattern** - Decide if EOF handling variants are needed
9. **Unicode in regex** - Replace `\uXXXX` escapes with literal characters
10. **Functional state** - Mutable closure state in parser

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Issues](#architecture-issues)
3. [Lexer Workarounds (Task 75)](#lexer-workarounds-task-75)
4. [Parser Workarounds (Task 76)](#parser-workarounds-task-76)
5. [Integration Workarounds (Task 77)](#integration-workarounds-task-77)
6. [Comment Merging Workarounds (Task 78)](#comment-merging-workarounds-task-78)
7. [Recommendations](#recommendations)

---

## Overview

This document catalogs all workarounds, design compromises, and non-obvious implementation patterns introduced during the implementation of:
- Docstring tokenization (`-- |`)
- Pragma tokenization (`{-# ... #-}`)
- Multiple declaration support
- Haddock-style comment merging

**Why these workarounds exist:**
1. **Parsy integration complexity** - Balancing parsy combinators with manual token scanning
2. **Metadata accumulation** - Need to collect docstrings/pragmas before declarations
3. **Circular dependency avoidance** - Careful import ordering
4. **Legacy API compatibility** - Maintaining backward compatibility

---

## Architecture Issues

### 1. Mixed Parsing Strategies

**Issue:** The codebase uses three different parsing approaches:
- **Parsy combinators** for expressions and types (`expr_parser()`, `type_parser()`)
- **Manual token scanning** for top-level declarations (`top_decl_parser()`)
- **Regex-based** for lexer tokenization

**Impact:** Inconsistent error handling, different patterns for similar operations

**Files affected:** `lexer.py`, `declarations.py`, `expressions.py`

### 2. Global Mutable State

**Issue:** Expression parser accessed via global factory pattern
```python
# declarations.py line 46
from systemf.surface.parser.expressions import expr_parser as _expr_parser_factory
```

**Why:** Avoids circular imports (declarations needs expressions for term bodies)

**Risk:** Hidden dependency, harder to test

---

## Lexer Workarounds (Task 75)

### High Priority

#### 1. Dual Whitespace/Comment Handling
**Location:** `lexer.py` lines 145-146, 185-221

**Problem:** Whitespace/comments handled in TWO places:
1. `_skip_whitespace()` manually skips spaces/tabs/comments
2. Regex patterns also match `WHITESPACE`, `COMMENT`, `NEWLINE`

**Why:** Manual skipping prevents docstrings/pragmas from being consumed as regular comments before regex sees them

**Risk:** Redundant logic, changes must be made in both places

#### 2. Position Advancement Inconsistency
**Location:** `lexer.py` lines 164-176

**Problem:** Non-uniform advancement:
- Docstrings: `_create_docstring_token()` handles ALL advancement internally
- Others: `_create_token()` returns token, then `self._advance(match.group())` outside

**Why:** Docstrings merge multi-line comments requiring custom position tracking

**Risk:** Violates principle of least surprise

#### 3. Dead Token Patterns
**Location:** `lexer.py` lines 52-53, 445-447

**Problem:** `PRAGMA_START`/`PRAGMA_END` regex patterns defined but NEVER matched

**Why:** `startswith("{-#")` check (line 155) catches pragmas before regex matching

**Risk:** Misleading - suggests pragmas go through normal tokenization

### Medium Priority

#### 4. Unicode Escapes in Regex
**Location:** `lexer.py` lines 59, 75-84, 91-92

**Problem:** Unicode characters escaped as `\uXXXX`:
```python
r"--\s*\^\s*(.*?)(?=\s*-\u003e|\s*\||\n|$)"  # \u003e is >
r"-\u003e|\u2192"  # \u2192 is →
```

**Why:** Likely Python 2 compatibility or encoding safety

**Risk:** Patterns hard to read, maintain

#### 5. String Literal Token Types ✅ FIXED
**Location:** `lexer.py`, `declarations.py`, `expressions.py`

**Problem:** Token types compared as string literals:
```python
if token_type == "DOCSTRING_PRECEDING":
elif token_type == "DOCSTRING_INLINE":
```

**Fix:** Added `DocstringType` and `TokenType` constant classes in `types.py`:
```python
class DocstringType:
    PRECEDING = "DOCSTRING_PRECEDING"
    INLINE = "DOCSTRING_INLINE"

class TokenType:
    PRAGMA = "PRAGMA"
    LAMBDA = "LAMBDA"
    TYPELAMBDA = "TYPELAMBDA"
```

**Status:** All string literals replaced with constants. Type safety improved, IDE autocompletion works.

#### 6. Recreated Mapping Dictionaries
**Location:** `lexer.py` lines 409-432, 435-443

**Problem:** `op_map` and `delim_map` created fresh every call to `_create_token()`

**Impact:** Wasteful, should be class/module constants

### Low Priority

#### 7. String Quote Stripping Assumption
**Location:** `lexer.py` lines 375-378

**Problem:** Assumes `"..."` format, blindly strips:
```python
string_value = value[1:-1]  # Remove quotes
```

**Risk:** No validation, silent failure on unexpected input

---

## Parser Workarounds (Task 76)

### High Priority

#### 1. Manual Token Inspection
**Location:** `declarations.py` lines 560-588

**Problem:** `top_decl_parser()` bypasses parsy's `alt()` combinator and uses manual token scanning:
```python
while i < len(tokens):
    token = tokens[i]

    # Accumulate docstrings BEFORE knowing declaration type
    if isinstance(token, DocstringToken):
        current_docstrings.append(token.content)
        i += 1
        continue

    # Accumulate pragmas BEFORE knowing declaration type
    if isinstance(token, PragmaToken):
        current_pragmas[token.key] = token.value
        i += 1
        continue

    # Try to parse declaration based on token type
    if isinstance(token, KeywordToken):
        if token.keyword == "data": ...
        elif token.keyword == "prim_type": ...
    elif isinstance(token, IdentifierToken):
        result = term_parser()(tokens, i)
```

**Why this can't use parsy combinators:**

1. **Stateful accumulation across declarations**: Docstrings and pragmas appear BEFORE declarations but must be attached TO them. This requires maintaining state (`current_docstrings`, `current_pragmas`) across multiple parsy parser invocations, which doesn't fit parsy's pure functional model.

2. **Backtracking complexity**: If we used parsy's `optional()` or `many()` to parse leading docstrings, we'd need to backtrack on failure. But docstring accumulation is destructive - we've already consumed the tokens.

3. **Lookahead ambiguity**: We need to peek ahead to see if there's a docstring before parsing a declaration, but parsy's lookahead doesn't handle "zero or more" metadata tokens well when combined with the actual declaration parsing.

4. **Multiple declaration types with shared metadata**: We have 4 declaration parsers (data, term, prim_type, prim_op) that all need the same accumulated metadata. Using parsy combinators would require threading this state through each parser variant.

**Why the manual approach is actually better here:**
- Clear state machine logic that's easy to follow
- Explicit control over when metadata is reset
- Easier to debug (can add print statements in the loop)
- No hidden parsy magic with backtracking

**Trade-off:** Less declarative syntax, but more control and easier to understand for this specific use case.

#### 2. Parser Triplication Pattern
**Location:** `declarations.py` throughout

**Problem:** Three functions per parser:
```python
def _data_parser_impl(): ...      # Lines 257-311
def data_parser_raw(): ...        # Lines 314-316
def data_parser(): ...            # Lines 319-328
```

**Why:** `_raw()` variants avoid EOF checking for `top_decl_parser()`

**Current state:** `data_parser()` and `data_parser_raw()` do the same thing

#### 3. Constructor Termination Heuristic
**Location:** `declarations.py` lines 229-243

**Problem:** Complex while loop with manual termination:
```python
if tokens[i].type == "IDENT" and i + 1 < len(tokens) and tokens[i + 1].type == "COLON":
    break  # Could be new term declaration
```

**Why:** Type atom parser is greedy, could consume next declaration's tokens

**Risk:** Fragile - assumes term declarations always start with `ident :`

### Medium Priority

#### 4. Mutable Closure State
**Location:** `declarations.py` lines 521-523

**Problem:** Mutable state captured in parser closure:
```python
declarations: list[SurfaceDeclaration] = []
current_docstrings: list[str] = []
current_pragmas: dict[str, str] = {}
```

**Why:** Need to accumulate metadata across declarations

**Risk:** Side-effect heavy, functional approach would be cleaner

#### 5. Lenient Token Skipping
**Location:** `declarations.py` line 645

**Problem:** Unknown tokens silently skipped:
```python
else:
    i += 1  # Skip unknown token
```

**Risk:** Could hide errors

#### 6. Scattered Inline Docstring Skipping
**Location:** `declarations.py` lines 212, 278, 287, 295

**Problem:** `skip_inline_docstrings()` called in 4 different places:
- Before first constructor
- Before/after pipe separators
- Before constructor name

**Why:** Inline docstrings (`-- ^`) can appear where grammar doesn't expect tokens

**Risk:** Unclear why so many places need this

### Low Priority

#### 7. String Literal Dispatch
**Location:** `declarations.py` lines 566, 573, 580, 587, 598-632

**Problem:** Uses string literals for declaration types:
```python
decl_type = "data"  # or "term", "prim_type", "prim_op"
if decl_type == "data": ...
```

**Risk:** No type safety, could use Enum

#### 8. Unused Imports
**Location:** `declarations.py` lines 17-18, 50

**Items:**
- `import parsy` - never used directly
- `alt, fail` - never used
- `T = TypeVar("T")` - never used

---

## Integration Workarounds (Task 77)

### Medium Priority

#### 1. Parser Class Wrapper
**Location:** `__init__.py` lines 198-296

**Problem:** Compatibility wrapper for "old Parser API" that no longer exists

**Comment:** "Compatibility wrapper for old Parser API"

**Risk:** Creates confusion about what API it's wrapping

#### 2. Exception Attribute Hack
**Location:** `__init__.py` lines 233-238, 251-255, 268-272, 291-296

**Problem:** Relies on parsy internals:
```python
if hasattr(e, "index") and e.index < len(self.tokens):
    loc = getattr(self.tokens[e.index], "location", None)
```

**Risk:** If parsy changes exception format, error location breaks silently

#### 3. Result Normalization
**Location:** `__init__.py` lines 230-232, 287-290

**Problem:** Checking if result is list:
```python
if isinstance(result, list):
    return result
return [result]
```

**Why:** Defensive programming suggests parser design inconsistency

#### 4. Late Imports
**Location:** `__init__.py` lines 191, 225, 283

**Problem:** Imports inside methods/functions:
```python
def __init__(self, message, location=None):
    from systemf.utils.location import Location
```

**Why:** Avoid circular imports

**Risk:** Unclear dependencies, slight performance hit

---

## Comment Merging Workarounds (Task 78)

### High Priority

#### 1. Special-Case Advancement
**Location:** `lexer.py` lines 164-176

**Problem:** Docstrings bypass `_advance()`:
```python
if token_type == "DOCSTRING_PRECEDING":
    token = self._create_docstring_token(match)  # Own advancement
else:
    token = self._create_token(match)
    self._advance(match.group())  # Normal advancement
```

**Why:** Multi-line merging requires custom position tracking

#### 2. Duplicate Detection Logic
**Location:** `lexer.py` lines 200-217, 309-314

**Problem:** Same check in two places:
- `_skip_whitespace()`: checks for `--|`, `-- |`, `--^`, `-- ^`
- `_create_docstring_token()`: regex `re.match(r"\s*\|", after_dash)`

**Risk:** Both must be updated consistently

#### 3. Manual Pragma Position Tracking
**Location:** `lexer.py` lines 247-254

**Problem:** Position updated manually:
```python
self.pos = pragma_end + 3  # Skip #-
# Manual line/column loop
```

**Why:** `_advance()` not used because `find()` already "consumed" content

### Medium Priority

#### 4. Blank Line Detection
**Location:** `lexer.py` lines 291-303

**Problem:** Non-obvious newline counting:
```python
if newline_count > 1:  # More than 1 newline = blank line
    break
```

**Why:** Single newline OK between comments, 2+ means blank line

#### 5. Unreachable Code
**Location:** `lexer.py` lines 445-447

**Problem:** Dead code with comment:
```python
elif token_type in ("PRAGMA_START", "PRAGMA_END"):
    # Pragmas handled by _read_pragma() - shouldn't be reached
    return None
```

---

## Recommendations

### Immediate (High Priority)

1. **Consolidate position advancement** - Make all token types use uniform `_advance()` or document why docstrings are special

2. **Remove dead token patterns** - Remove `PRAGMA_START`/`PRAGMA_END` from `TOKEN_PATTERNS` if never used

3. **Document manual token inspection** - Add detailed comment explaining why `top_decl_parser()` uses manual inspection instead of `alt()`

4. **Fix constructor termination** - Make termination check more robust or document the `ident :` assumption

### Short Term (Medium Priority)

5. **Create token type constants** - Replace string literals with constants/enum

6. **Extract mapping dictionaries** - Make `op_map` and `delim_map` module-level constants

7. **Simplify Parser class** - Document or remove the "old API" compatibility wrapper

8. **Add bounds checking** - Replace `hasattr(e, "index")` with proper error handling

### Long Term (Low Priority)

9. **Unify parsing strategies** - Consider whether manual token scanning in `top_decl_parser()` could use parsy combinators

10. **Refactor _raw() pattern** - Decide if `_raw()` variants are needed or if EOF handling can be added to public parsers

11. **Unicode in regex** - Replace `\uXXXX` escapes with literal Unicode characters

12. **Functional state** - Consider refactoring mutable closure state to functional approach

---

## Appendix: Files with Most Workarounds

| File | Workaround Count | Priority |
|------|------------------|----------|
| `lexer.py` | 15 | High |
| `declarations.py` | 12 | High |
| `__init__.py` | 6 | Medium |

---

**Next Steps:**
- [ ] Create cleanup tasks for high-priority items
- [ ] Add comments explaining non-obvious workarounds
- [ ] Refactor Parser class wrapper
- [ ] Consolidate position advancement
