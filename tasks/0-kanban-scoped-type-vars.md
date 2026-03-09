# Kanban: ScopedTypeVariables and Visible Type Application Implementation

---
title: "ScopedTypeVariables and Visible Type Application Implementation"
created: 2026-03-09
phase: design
request: |
  Implement ScopedTypeVariables and Visible Type Application for System F type inference.
  
  Background:
  System F currently supports basic visible type application (@) on globals but lacks full 
  ScopedTypeVariables support. The type checker needs modifications to support context extension 
  at scope boundaries and lazy instantiation for polymorphic types.
  
  Key Requirements:
  - DECL-SCOPE: Declaration signatures bind type variables for body
  - ANN-SCOPE: Type annotations bind variables for annotated term
  - LAM-ANN-SCOPE: Lambda params bind variables for body
  - PAT-POLY: Pattern bindings keep polymorphic types
  
  Target Files:
  - src/systemf/surface/inference/bidi_inference.py
  - src/systemf/surface/inference/elab_bodies_pass.py
  
  References:
  - systemf/docs/notes/visible-type-application.md
  - Eisenberg 2016 "Visible Type Application"
current: tasks/129-implement-pat-poly-pattern-matching-with-polymorphic-types.md
phase: complete
tasks:
  - tasks/0-design-scoped-type-vars.md
  - tasks/1-implement-helper-functions.md
  - tasks/2-implement-decl-scope.md
  - tasks/127-implement-ann-scope-type-annotation-context-extension.md
  - tasks/128-implement-lam-ann-scope-lambda-parameter-annotation-context-extension.md
  - tasks/129-implement-pat-poly-pattern-matching-with-polymorphic-types.md
log:
  - timestamp: 2026-03-09
    event: design_complete
    message: Design approved, created implementation task for helper functions
    task: tasks/0-design-scoped-type-vars.md
  - timestamp: 2026-03-09
    event: task_complete
    message: Helper functions implemented and reviewed successfully
    task: tasks/1-implement-helper-functions.md
  - timestamp: 2026-03-09
    event: task_complete
    message: DECL-SCOPE implementation complete and reviewed
    task: tasks/2-implement-decl-scope.md
  - timestamp: 2026-03-09
    event: task_complete
    message: ANN-SCOPE implementation complete and reviewed
    task: tasks/127-implement-ann-scope-type-annotation-context-extension.md
  - timestamp: 2026-03-09
    event: task_complete
    message: LAM-ANN-SCOPE implementation complete and reviewed
    task: tasks/128-implement-lam-ann-scope-lambda-parameter-annotation-context-extension.md
  - timestamp: 2026-03-09
    event: task_complete
    message: PAT-POLY implementation complete and reviewed
    task: tasks/129-implement-pat-poly-pattern-matching-with-polymorphic-types.md
  - timestamp: 2026-03-09
    event: workflow_complete
    message: All ScopedTypeVariables rules implemented successfully
---

## Progress Log

<!-- progress log will be appended here -->
