---
assignee: Architect
expertise: ['AST Design', 'Type Systems']
skills: [skill-management, code-reading-assistant]
type: design
priority: high
state: done
dependencies: []
refers: ['tasks/130-kanban-add-import-declaration-support-to-surface-parser.md', 'systemf/docs/module-design.md', 'systemf/docs/reference/syntax.md', 'systemf/src/systemf/elab3/ast.py', 'systemf/src/systemf/elab3/reader_env.py']
kanban: tasks/130-kanban-add-import-declaration-support-to-surface-parser.md
created: 2026-03-30T05:37:54.391467
---

# Task: Define SurfaceImportDeclaration AST Type

## Context
The systemf surface parser currently has no import syntax. The `elab3` module system design (`systemf/docs/module-design.md`) defines `ImportSpec` and `ImportDecl` with support for: qualified imports, aliases, explicit item lists, and hiding lists. The surface AST must mirror this capability while conforming to existing `SurfaceDeclaration` patterns.

Key conventions from the surface codebase (`systemf/src/systemf/surface/types.py`):
- All surface nodes inherit from `SurfaceNode` and use `@dataclass(frozen=True, kw_only=True)`
- All declarations inherit from `SurfaceDeclaration`
- All nodes carry an optional `location` field (inherited from `SurfaceNode`)
- The codebase uses "Declaration" exclusively; "Statement" has zero presence
- `SurfaceDeclarationRepr` union type must include all declaration variants

The `elab3` `ImportDecl` fields are: `module: str`, `qualified: bool`, `alias: str|None`, `items: ImportItems|HidingItems|None`. The surface representation should be isomorphic but surface-simple.

## Design Decisions

**Problem:** How to represent import specifications in the surface AST.

**Option A:** Mirror `elab3` exactly with `ImportItems`/`HidingItems` wrapper types.
**Option B:** Use a single `SurfaceImportDeclaration` with `items: list[str]|None` and `hiding: bool`.

**Choice: B** — Appropriate because:
- Surface AST is intentionally simpler than `elab3` AST (same reason `SurfaceTypeConstructor` uses flat strings, not `Name`)
- Keeps the node self-contained without extra wrapper dataclasses
- Easy to convert to `elab3.ast.ImportDecl` in a later pass

**Tradeoff:** We lose some type safety (can't distinguish "import all" from "import nothing" at the type level), but `items=None` vs `items=[]` is sufficient and simpler.

## Files
- `systemf/src/systemf/surface/types.py` — add `SurfaceImportDeclaration` and update `SurfaceDeclarationRepr`
- `systemf/docs/module-design.md` — elab3 ImportSpec/ImportDecl design reference
- `systemf/docs/reference/syntax.md` — surface syntax specification
- `systemf/src/systemf/elab3/ast.py` — elab3 ImportDecl AST reference
- `systemf/src/systemf/elab3/reader_env.py` — elab3 ImportSpec reference

## Description
Add `SurfaceImportDeclaration` node to `systemf/surface/types.py` conforming to existing `SurfaceDeclaration` style. Exact definition:

```python
@dataclass(frozen=True, kw_only=True)
class SurfaceImportDeclaration(SurfaceDeclaration):
    """Import declaration: import [qualified] Module [as Alias] [import_spec]."""
    module: str = ""
    qualified: bool = False
    alias: str | None = None
    items: list[str] | None = None
    hiding: bool = False
```

Also update `SurfaceDeclarationRepr` to include `SurfaceImportDeclaration`:
```python
SurfaceDeclarationRepr = Union[
    SurfaceDataDeclaration,
    SurfaceTermDeclaration,
    SurfacePrimTypeDecl,
    SurfacePrimOpDecl,
    SurfaceImportDeclaration,  # NEW
]
```

Follow the exact style of `SurfaceDataDeclaration` and `SurfaceTermDeclaration` (frozen dataclass, kw_only, default values, inherit from `SurfaceDeclaration`).

## Work Items
<!-- start workitems -->
work_items:
  - description: Define SurfaceImportDeclaration dataclass in types.py and update SurfaceDeclarationRepr
    files: [systemf/src/systemf/surface/types.py]
    related_domains: ["Software Engineering", "Type Systems"]
    expertise_required: ["Python", "AST Design"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Must match existing SurfaceDeclaration style exactly. No new wrapper types.
<!-- end workitems -->

## Work Log

### [2026-03-30 05:48:20] Implementation

**Facts:**
Added SurfaceImportDeclaration dataclass to systemf/src/systemf/surface/types.py with fields module, qualified, alias, items, hiding. Updated SurfaceDeclarationRepr union to include the new type. Also added ImportToken, QualifiedToken, AsToken, HidingToken to parser/types.py and lexer.py to support keyword recognition.

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-03-30 05:51:09] Approval

**Facts:**
AST design is correct, token types properly exported. Approved.

**Analysis:**
-

**Conclusion:**
Status: ok

---

