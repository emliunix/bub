# Workflow DSL Parser Comparison

**Date:** 2026-02-22  
**Goal:** Evaluate modern Python parsing libraries for Haskell-like, indentation-based DSL

---

## Test Results Summary

| Parser | Status | Lines of Code | Grammar Type | Works? |
|--------|--------|---------------|--------------|--------|
| **Lark** | ❌ Grammar Error | ~300 | EBNF (LALR) | No |
| **TatSu** | ❌ Grammar Error | ~900 | EBNF (PEG) | No |
| **Pratt** | ✅ Working | ~950 | Hand-rolled | Yes |

---

## Parser 1: Lark

### Approach
- **Library:** Lark (modern, popular)
- **Grammar:** EBNF with LALR parser
- **Features:** Automatic tree generation, ambiguity resolution

### Issues Encountered
```
GrammarError: Rule 'name' used but not defined (in rule function_def)
```

The grammar references `name` but defines `NAME` as a terminal. In Lark's grammar syntax, there's a distinction between rules (lowercase) and terminals (UPPERCASE). The grammar needs refinement to properly handle this distinction.

### Pros
- Clean EBNF grammar syntax
- Good error messages (when grammar is valid)
- Built-in tree generation
- Supports multiple algorithms (Earley, LALR)

### Cons
- Steep learning curve for grammar syntax
- Indentation handling requires special post-lexer
- Grammar validation errors can be cryptic

### Verdict
Promising but requires more grammar debugging. The indentation support is complex.

---

## Parser 2: TatSu

### Approach
- **Library:** TatSu (modern PEG)
- **Grammar:** EBNF-style with semantic actions
- **Features:** Left-recursion support, grammar modularity

### Issues Encountered
```
Grammar compilation error: (7:5) expecting '@' :
    program = function_def:* ;
    ^
    decorator
```

TatSu's grammar syntax uses `*` for zero-or-more, but the error suggests the grammar structure isn't being recognized correctly. There may be an issue with how rules are being defined or the grammar isn't being parsed as expected.

### Pros
- Modern PEG with good performance
- Left-recursion handling
- Clean semantic action syntax

### Cons
- Grammar syntax has learning curve
- Error messages not very helpful
- Indentation preprocessing required

### Verdict
Complex grammar syntax makes debugging difficult. The error message doesn't clearly indicate what's wrong.

---

## Parser 3: Hand-Rolled Pratt Parser

### Approach
- **Type:** Top-down operator precedence (hand-written)
- **Components:** Lexer + Parser + AST
- **Algorithm:** Recursive descent with binding powers

### Implementation Highlights

**Core Algorithm:**
```python
def expr(self, rbp: int = 0) -> Any:
    token = self.next()
    left = self.nud(token)
    while rbp < self.lbp(self.peek()):
        token = self.next()
        left = self.lef(left, token)
    return left
```

**Binding Powers:**
```
NONE(0) < ASSIGNMENT(10) < COMMA(20) < ARROW(30) 
    < WITH(40) < TYPE_ANNOT(50) < CALL(60) < PRIMARY(70)
```

### Success
✅ **Successfully parses the example DSL:**
- Indentation-based blocks
- Type annotations (`::`)
- Function definitions with params
- Let bindings
- LLM calls with context
- Docstrings

### Pros
- Full control over parsing logic
- Custom error messages
- Handles indentation naturally
- No grammar debugging
- Easy to extend

### Cons
- More code (950 lines vs 300)
- Manual AST construction
- Must handle all edge cases
- No automatic tree generation

### Verdict
**Best for experimentation** - Works immediately, easy to understand, easy to modify.

---

## Key Insights

### 1. Parser Generators vs Hand-Rolled

**Parser Generators (Lark, TatSu):**
- Require learning specific grammar syntax
- Grammar debugging can be time-consuming
- Good for stable, well-defined languages
- Harder to customize error messages

**Hand-Rolled Pratt Parser:**
- Works immediately
- Easy to debug (it's just Python code)
- Perfect for experimentation and iteration
- Can customize everything

### 2. Indentation Handling

All approaches require handling indentation:
- **Preprocessing:** Convert to explicit tokens (`INDENT`/`DEDENT`)
- **Integrated:** Track indentation level in lexer

The Pratt parser handled this naturally by tracking indent level in the lexer.

### 3. Error Messages

**Pratt parser:** Can provide custom, helpful error messages  
**Lark/TatSu:** Error messages depend on grammar quality

### 4. Extensibility

**Pratt parser:** Add new operators by defining `nud`/`led` methods  
**Parser generators:** Modify grammar, regenerate parser

---

## Recommendations

### For This DSL Project

**Use hand-rolled Pratt parser for:**
- Initial prototyping and experimentation
- When language is evolving rapidly
- When need custom error messages
- When indentation is significant

**Consider Lark later for:**
- Production use with stable grammar
- When performance matters (LALR is fast)
- When need ambiguity resolution

### Implementation Strategy

1. **Phase 1:** Use Pratt parser to validate language design
2. **Phase 2:** Stabilize grammar
3. **Phase 3:** Optionally migrate to Lark for performance

---

## LLM Call Todo Tree Idea

The user's suggestion to create a **todo item tree** for LLM calls is excellent:

```
LLM Call Path:
├── analyze_code("src/main.py")
│   ├── [TODO] Read file content
│   ├── [TODO] Summarize structure
│   └── [TODO] Identify issues
│       ├── [TODO] Check for null pointers
│       ├── [TODO] Check for resource leaks
│       └── [TODO] Check for logic errors
```

**Benefits:**
1. **Human visibility:** See what the agent is doing
2. **Agent context:** Overview of current position in workflow
3. **Progress tracking:** Which todos are done/pending
4. **Resumability:** Can pause and resume at any point

**Implementation:**
- Each LLM call creates a todo node
- Todos form a tree (parent-child relationships)
- Agent can query "where am I?" to get context
- Human can view the todo tree

---

## Next Steps

1. ✅ **Language specification** - Done (`workflow-dsl-spec.md`)
2. ✅ **Pratt parser** - Working prototype
3. 🔲 **Fix Lark grammar** - Debug grammar issues
4. 🔲 **Fix TatSu grammar** - Debug grammar issues
5. 🔲 **Performance benchmark** - Parse speed comparison
6. 🔲 **Error message quality** - Compare error helpfulness
7. 🔲 **Todo tree prototype** - Implement LLM call tracking

---

## Conclusion

**Hand-rolled Pratt parser wins for experimentation.** It works immediately, is easy to understand and modify, and handles our Haskell-like, indentation-based syntax naturally.

Parser generators (Lark, TatSu) are powerful but have a learning curve. They're better suited for production use with stable grammars.

**Recommendation:** Continue with Pratt parser for language design iteration, then consider migrating to Lark once the grammar stabilizes.
