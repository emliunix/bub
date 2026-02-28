---
assignee: Architect
expertise: ['Type System Design', 'AST Design']
skills: ['code-reading']
type: design
priority: high
state: done
dependencies: []
refers: []
kanban: tasks/52-kanban-system-f-llm-integration.md
created: 2026-02-28T11:17:27.473629
---

# Task: Design Surface AST Changes

## Context
<!-- Background information and relevant context -->

## Files
<!-- List of files to modify or reference -->

## Description
Design and update Surface AST types for LLM function support:

1. Add param_doc: Optional[str] to SurfaceTypeArrow
2. Make type_annotation required in SurfaceTermDeclaration (change from Optional)
3. Add var_type: Optional[SurfaceType] to SurfaceLet
4. Verify SurfacePrimOpDecl supports docstring

Reference: docs/design-llm-integration.md Section 2.2 and Part 3 Phase 1 Step 1.1

## Work Log
<!-- Work logs will be appended here -->

### [2026-02-28 11:22:15] Surface AST Design Complete

**Facts:**
## Work Log

### [2026-02-28T11:22:15] Design Session | ok

**Facts:**
- Updated SurfaceTypeArrow with param_doc: Optional[str] field
- Made type_annotation required in SurfaceTermDeclaration (removed Optional)
- Added var_type: Optional[SurfaceType] to SurfaceLet for optional type annotations
- Verified SurfacePrimOpDecl already supports docstring field
- All changes tested and verified working

**Analysis:**
- Changes align with design document Section 2.2 and Phase 1 Step 1.1
- param_doc field enables parameter documentation via -- ^ syntax
- Required type annotations enforce System F's explicit typing philosophy
- var_type in SurfaceLet supports bidirectional type checking for local bindings
- SurfacePrimOpDecl docstring support enables function-level documentation

**Conclusion:**
Design complete. Surface AST types are ready for implementation phase.

**Analysis:**
-

**Conclusion:**
Status: ok

## Suggested Work Items (for Manager)

The following work items should be turned into task files by Manager:

```yaml
work_items:
  - description: Update SurfaceTypeArrow to include param_doc field
    files: [src/systemf/surface/ast.py]
    related_domains: ["Type Systems", "AST Design"]
    expertise_required: ["Python", "Type System Design"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: param_doc is Optional[str], defaults to None. Already designed, needs parser support.

  - description: Update parser to handle -- ^ param docs in types
    files: [src/systemf/surface/parser.py]
    related_domains: ["Parsing", "Type Systems"]
    expertise_required: ["Parser Combinators", "Python"]
    dependencies: []
    priority: high
    estimated_effort: medium
    notes: Parser needs to capture -- ^ comments after type expressions and populate param_doc

  - description: Update SurfaceTermDeclaration validation in elaborator
    files: [src/systemf/surface/elaborator.py]
    related_domains: ["Type Systems", "Elaboration"]
    expertise_required: ["Type Theory", "Python"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: type_annotation is now required (not Optional). Remove checks for missing annotation.

  - description: Update parser for let with optional type annotation
    files: [src/systemf/surface/parser.py]
    related_domains: ["Parsing", "Type Systems"]
    expertise_required: ["Parser Combinators", "Python"]
    dependencies: []
    priority: medium
    estimated_effort: small
    notes: Parse 'let x : Type = value in body' syntax with optional ': Type' part

  - description: Update elaborator for SurfaceLet with var_type
    files: [src/systemf/surface/elaborator.py]
    related_domains: ["Type Systems", "Elaboration"]
    expertise_required: ["Type Theory", "Python"]
    dependencies: [3]
    priority: medium
    estimated_effort: small
    notes: Handle optional var_type annotation during elaboration for bidirectional checking
```

---

