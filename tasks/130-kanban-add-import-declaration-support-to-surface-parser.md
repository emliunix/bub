---
type: 'kanban'
title: 'Add Import Declaration Support to Surface Parser'
created: '2026-03-30 05:37:42.701156'
phase: 'exploration'
current: 'tasks/133-implement-import-declaration-parser.md'
tasks: ['tasks/131-define-surfaceimportdeclaration-ast-type.md', 'tasks/132-write-parser-tests-for-import-declarations.md', 'tasks/133-implement-import-declaration-parser.md']
---
# Kanban: Add Import Declaration Support to Surface Parser

## Request
Add import declaration support to the systemf surface parser, following existing codebase style and elab3 ImportSpec design. The surface syntax should support: plain import, qualified import, aliased import, explicit import lists, and hiding lists. The new SurfaceImportDeclaration node must conform to existing SurfaceDeclaration patterns. Work includes: defining the AST type, writing parser tests, implementing the parser, and wiring it into the declaration parser entry points.

## Plan Adjustment Log
<!-- Manager logs plan adjustments here -->

