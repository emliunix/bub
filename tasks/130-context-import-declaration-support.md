# Context: Add Import Declaration Support to Surface Parser

**Created:** 2026-03-30  
**Kanban:** `tasks/130-kanban-add-import-declaration-support-to-surface-parser.md`

## Goal
Add `import` declaration support to the systemf surface parser, following existing codebase style and the `elab3` `ImportSpec` design.

## Design Decisions (Locked)

### AST Representation
- **Node name:** `SurfaceImportDeclaration` (inherits from `SurfaceDeclaration`)
- **Style:** `@dataclass(frozen=True, kw_only=True)` with `location` inherited from `SurfaceNode`
- **Fields:**
  - `module: str = ""` — module name, dots allowed (e.g. `"Data.Maybe"`)
  - `qualified: bool = False`
  - `alias: str | None = None`
  - `items: list[str] | None = None` — `None` = import all, list = explicit items or hiding list
  - `hiding: bool = False` — when `True`, `items` is a hiding list
- **Rationale:** Surface AST stays simpler than `elab3` AST. No `ImportItems`/`HidingItems` wrapper types needed.

### Surface Syntax
```systemf
import List                          -- plain
import qualified List                -- qualified
import List as L                     -- aliased
import qualified List as L           -- qualified + aliased
import List (map, filter)            -- explicit items
import List hiding (internal)        -- hiding list
```

### Parser Function
- **Name:** `import_decl_parser()` — follows existing convention (`data_parser()`, `term_parser()`, etc.)
- **Location:** `systemf/src/systemf/surface/parser/declarations.py`
- **Dispatch:** Wired into `_try_parse_declaration()` via `KeywordToken(keyword="import")`
- **Re-export:** Added to `systemf/src/systemf/surface/parser/__init__.py`

## Tasks

| # | File | Assignee | Type | State | Description |
|---|------|----------|------|-------|-------------|
| 131 | `tasks/131-define-surfaceimportdeclaration-ast-type.md` | Architect | design | todo | Add `SurfaceImportDeclaration` to `surface/types.py`, update `SurfaceDeclarationRepr` |
| 132 | `tasks/132-write-parser-tests-for-import-declarations.md` | Architect | design | todo | TDD: write `TestImportDeclaration` in `test_declarations.py` (tests fail until parser exists) |
| 133 | `tasks/133-implement-import-declaration-parser.md` | Implementor | implement | todo | Implement `import_decl_parser()`, wire dispatch, re-export, make tests pass |

**Dependencies:** 131 → 132 → 133

## Key Reference Files
- `systemf/docs/module-design.md` — elab3 module/import design
- `systemf/docs/reference/syntax.md` — surface syntax spec
- `systemf/src/systemf/elab3/ast.py` — `ImportDecl`, `ImportItems`, `HidingItems`
- `systemf/src/systemf/elab3/reader_env.py` — `ImportSpec`
- `systemf/src/systemf/surface/types.py` — surface AST types
- `systemf/src/systemf/surface/parser/declarations.py` — declaration parsers
- `systemf/src/systemf/surface/parser/__init__.py` — parser exports
- `tests/test_surface/test_parser/test_declarations.py` — existing declaration tests

## Next Step
Execute task 131: add `SurfaceImportDeclaration` to `systemf/src/systemf/surface/types.py`.
