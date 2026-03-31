---
assignee: Implementor
expertise: ['Parser Implementation', 'Python']
skills: [skill-management, testing, code-reading-assistant]
type: implement
priority: high
state: done
dependencies: ['tasks/132-write-parser-tests-for-import-declarations.md']
refers: ['tasks/130-kanban-add-import-declaration-support-to-surface-parser.md', 'systemf/docs/module-design.md', 'systemf/docs/reference/syntax.md', 'systemf/src/systemf/surface/parser/declarations.py', 'systemf/src/systemf/surface/parser/__init__.py', 'systemf/src/systemf/elab3/ast.py']
kanban: tasks/130-kanban-add-import-declaration-support-to-surface-parser.md
created: 2026-03-30T05:38:04.087512
---

# Task: Implement Import Declaration Parser

## Context
The surface parser uses `parsy` with a token-based approach. Key patterns from `systemf/surface/parser/declarations.py`:
- Token matching: `match_keyword("data")`, `match_ident()`
- Sequential parsing: `@generate` decorator with `yield`
- Layout is NOT sensitive for declarations (unlike expressions)
- `top_decl_parser()` uses `_try_parse_declaration()` to dispatch on the first token
- New declaration types must be added to `_try_parse_declaration()` and handled by `decl_parser()`

The `elab3` design (`systemf/docs/module-design.md`) specifies `ImportSpec` with fields: `module`, `qualified`, `alias`, `items`/`hiding`. The parser must produce `SurfaceImportDeclaration` (defined in task #131) which maps 1:1 to these concepts.

## Parser Grammar

```
import_decl   ::= "import" ["qualified"] module_name ["as" alias] [import_spec]
module_name   ::= IDENT ("." IDENT)*
import_spec   ::= "(" ident_list ")"
               |  "hiding" "(" ident_list ")"
ident_list    ::= ident ("," ident)*
```

## Files
- `systemf/src/systemf/surface/parser/declarations.py` — implement `import_decl_parser()`, wire into dispatch
- `systemf/src/systemf/surface/parser/__init__.py` — re-export `import_decl_parser`
- `systemf/docs/module-design.md` — elab3 module/import design reference
- `systemf/docs/reference/syntax.md` — surface syntax specification
- `systemf/src/systemf/elab3/ast.py` — elab3 ImportDecl reference for downstream mapping

## Description

### Step 1: Implement `import_decl_parser()`
In `declarations.py`, add:

```python
def import_decl_parser() -> P[SurfaceImportDeclaration]:
    @generate
    def parser():
        import_token = yield match_keyword("import")
        loc = import_token.location
        
        qualified = yield (match_keyword("qualified")).optional()
        
        # Module name: IDENT ("." IDENT)*
        first_part = yield match_ident()
        module_parts = [first_part.value]
        while True:
            dot = yield (match_symbol(".")).optional()
            if dot is None:
                break
            part = yield match_ident()
            module_parts.append(part.value)
        module_name = ".".join(module_parts)
        
        alias = None
        as_kw = yield (match_keyword("as")).optional()
        if as_kw is not None:
            alias_token = yield match_ident()
            alias = alias_token.value
        
        items = None
        hiding = False
        
        # Check for "hiding" or "("
        hiding_kw = yield (match_keyword("hiding")).optional()
        if hiding_kw is not None:
            hiding = True
        
        open_paren = yield (match_symbol("(")).optional()
        if open_paren is not None:
            # Parse ident list
            first_item = yield match_ident()
            item_names = [first_item.value]
            while True:
                comma = yield (match_symbol(",")).optional()
                if comma is None:
                    break
                item_token = yield match_ident()
                item_names.append(item_token.value)
            yield match_symbol(")")
            items = item_names
        
        return SurfaceImportDeclaration(
            module=module_name,
            qualified=qualified is not None,
            alias=alias,
            items=items,
            hiding=hiding,
            location=loc,
        )
    
    return parser
```

**Style notes:**
- Use `.optional()` for optional parts (existing pattern in `data_parser()`)
- Use `match_keyword()`, `match_ident()`, `match_symbol()` (existing helpers)
- Return `SurfaceImportDeclaration` with `location=loc`

### Step 2: Wire into dispatch
In `_try_parse_declaration()`, add a case for `KeywordToken(keyword="import")`:

```python
case KeywordToken(keyword="import"):
    result = import_p(tokens, i)
    if result.status:
        return (True, result.value, "import", result.index)
    return (True, None, None, i)
```

Update the function signature of `_try_parse_declaration()` to accept `import_p` as a new parameter, and update the call site in `top_decl_parser()` to pass it.

### Step 3: Update `decl_parser()`
Ensure `decl_parser()` can parse import declarations. Since it delegates to `top_decl_parser()` and returns the first declaration, the dispatch wiring should be sufficient.

### Step 4: Re-export from `__init__.py`
In `systemf/src/systemf/surface/parser/__init__.py`, add `import_decl_parser` to the re-export list from `declarations.py`.

### Step 5: Run tests
Run `uv run pytest tests/test_surface/test_parser/test_declarations.py -v` and ensure all tests pass, including the new import declaration tests from task #132.

## Edge Cases to Handle
- `import qualified Data.Maybe as Maybe` — both qualified and aliased
- `import List (map, filter, length)` — multiple items with commas
- `import List hiding ()` — empty hiding list (should parse as `items=[]`, `hiding=True`)
- Module names with dots like `Data.Maybe` — must parse as a single module string

## Work Items
<!-- start workitems -->
work_items:
  - description: Implement import_decl_parser() in declarations.py using @generate
    files: [systemf/src/systemf/surface/parser/declarations.py]
    related_domains: ["Software Engineering", "Parsing"]
    expertise_required: ["Python", "parsy", "Parser Combinators"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Follow existing parser style exactly. Use match_keyword, match_ident, match_symbol.
  
  - description: Wire import keyword into _try_parse_declaration() and top_decl_parser()
    files: [systemf/src/systemf/surface/parser/declarations.py]
    related_domains: ["Software Engineering", "Parsing"]
    expertise_required: ["Python", "parsy"]
    dependencies: [0]
    priority: high
    estimated_effort: small
    notes: Add import_p parameter to _try_parse_declaration and match KeywordToken(keyword="import").
  
  - description: Re-export import_decl_parser from parser/__init__.py
    files: [systemf/src/systemf/surface/parser/__init__.py]
    related_domains: ["Software Engineering"]
    expertise_required: ["Python"]
    dependencies: [0]
    priority: medium
    estimated_effort: small
    notes: Add to the re-export list from declarations module.
  
  - description: Run tests and ensure all pass
    files: [tests/test_surface/test_parser/test_declarations.py]
    related_domains: ["Software Engineering", "Testing"]
    expertise_required: ["Python", "pytest"]
    dependencies: [0, 1, 2]
    priority: high
    estimated_effort: small
    notes: Run uv run pytest tests/test_surface/test_parser/test_declarations.py -v
<!-- end workitems -->

## Work Log

### [2026-03-30 05:48:22] Implementation

**Facts:**
Implemented import_decl_parser() in systemf/src/systemf/surface/parser/declarations.py using @generate with support for qualified, as alias, module names with dots, explicit item lists, and hiding lists. Wired import keyword into _try_parse_declaration() and top_decl_parser(). Re-exported import_decl_parser from parser/__init__.py. All 52 declaration tests pass.

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-03-30 05:51:10] Approval

**Facts:**
Parser implementation is correct, all review findings fixed, all tests pass. Approved.

**Analysis:**
-

**Conclusion:**
Status: ok

---

