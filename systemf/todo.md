surface.lexer.py, remove skip_indent entirely, whoever needs compatibility, migrate them to use the new one.

surface.parser.py, data_declaration, the said old syntax is valid. the indentation here is to only enclose the whole data declaration. the new syntax hides structural information.

example:
```haskell
data Nat
  = Zero
  | Succ Nat
-- syntax without = and | are not appropriate as they hide the structural information.
```

And also we need to support both syntax of pattern matching:
```haskell
not : Bool -> Bool = \b:Bool ->
  case b of
    True -> False
    False -> True
-- this syntax is ok, code is by nature block, the indentation make blocks standout

not : Bool -> Bool = \b:Bool ->
  case b of
    { True -> False
    | False -> True
    }
-- this syntax is more explicit, so we keep both
```

The intuition here is that the indentation serves as the last sort of boundary for a block of code and inside that piece of code, these braces bars convey strong structural information.

we need to make the docstring first class, those `-- |` and `-- ^` comments should be attached to the data type AST nodes, and be visible to the interpreter.

---

## LLM FFI Syntax Decision (2026-02-26)

**Syntax:** `{-# LLM key=value, ... #-}`

**Examples:**
```systemf
{-# LLM model="gpt-4" #-}
research_topic :: String -- ^ the topic
  -> String             -- ^ context
  -> String             -- ^ conclusion

{-# LLM model="claude-3-opus", tag="code_review", temperature=0.7 #-}
review_code :: String -> Language -> List Suggestion

-- we make all data serializable and not expose any low level operations cause
-- this is s a DSL focused on domain modeling of workflow.
{-# LLM model="gpt-4", json=true, temperature=0.0 #-}
-- parse_structured :: forall a. FromJSON a => String -> String -> IO a
```

**Key Points:**
- Uses standard Haskell pragma syntax `{-# ... #-}`
- Key-value pairs for configuration (model, tag, temperature, max_tokens, json, etc.)
- Docstrings (`-- |`) and parameter docs (`-- ^`) auto-synthesize system prompt
- No function body needed - LLM call is implicit
- Supports polymorphic types and type class constraints
- Multiple variants with same name but different configs allowed

**Rationale:** Haskell-compatible, conflict-free (avoids Rust's `#[...]` which conflicts with unboxed types), extensible

## Tool call in the language

Besides the LLM functions, we can also make those LLM tools appear in the context as systemf functions too.

## Feature set

The major concern is if the DSL has enough feature set to support being the structual thinking language.

What features we may want:
* variables, functions
* manageable context, through tape
* parallel execution
* runtime REPL context for LLM
* to support set_output() -- this actually has something to do with LLM prefix cache, we need the tool, yet it's type is opaque, add as later context what exact output schema we want
* maybe type, for optional data
* module system

## Typed lexer token

Make each token a typed object instaed of all using the token type.

## types.py

We should move token (shared by parser and lexer) to types.py, actually now it looks duplicated we have 2 set of token types in lexer and types

ast.py looks fine, it's complex, we make it having its own module

## code style

avoid isinstance, use match
