---
assignee: Architect
expertise: ['System Design', 'Type Theory', 'Python']
skills: ['code-reading']
type: design
priority: medium
state: done
dependencies: []
refers: ['tasks/79-kanban-system-f-elaborator-refactor.md']
kanban: tasks/79-kanban-system-f-elaborator-refactor.md
created: 2026-03-02T08:34:53.203772
---

# Task: Design System F Elaborator - Populate Work Items

## Context
<!-- Background information and relevant context -->

## Files
<!-- List of files to modify or reference -->

## Description
Review the design document at systemf/docs/ELABORATOR_DESIGN.md and populate the bounded Work Items block for implementing the multi-pass elaborator (Phase 1: scope checking, Phase 2: type elaboration, Phase 3: pipeline orchestration).

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items:
  # Phase 1: Scope Checking Infrastructure (Core-First)
  - description: Create Scoped AST types in surface/scoped/types.py
    files: [systemf/surface/scoped/types.py]
    related_domains: ["Type Theory", "Software Engineering"]
    expertise_required: ["Type Design", "Python"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Define ScopedTerm, ScopedVar (index+original_name), ScopedAbs, ScopedTypeVar with source locations

  - description: Create ScopeContext in surface/scoped/context.py for name-to-index mapping
    files: [systemf/surface/scoped/context.py]
    related_domains: ["Type Theory", "Software Engineering"]
    expertise_required: ["Type Design", "Python"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Data structure tracking term_names and type_names lists with lookup/extend methods

  - description: Create ScopeError exception hierarchy in surface/scoped/errors.py
    files: [systemf/surface/scoped/errors.py]
    related_domains: ["Software Engineering", "Error Handling"]
    expertise_required: ["Python"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Define ScopeError with location tracking for undefined variables

  - description: Implement ScopeChecker in surface/scoped/checker.py for Phase 1
    files: [systemf/surface/scoped/checker.py]
    related_domains: ["Type Theory", "Software Engineering"]
    expertise_required: ["Type Design", "Python", "Pattern Matching"]
    dependencies: [0, 1, 2]
    priority: high
    estimated_effort: medium
    notes: Transform SurfaceVar->ScopedVar, SurfaceAbs->ScopedAbs, recurse on other nodes

  - description: Add source location support to Core AST (core/ast.py)
    files: [systemf/core/ast.py]
    related_domains: ["Type Theory", "Software Engineering"]
    expertise_required: ["Type Design", "Python"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Every Core term must carry source_loc for error reporting; add debug_name to Var/Abs

  - description: Implement scope checking for top-level declarations
    files: [systemf/surface/scoped/checker.py]
    related_domains: ["Type Theory", "Software Engineering"]
    expertise_required: ["Type Design", "Python"]
    dependencies: [4]
    priority: medium
    estimated_effort: small
    notes: Handle SurfaceTermDeclaration with type annotation and body scope checking

  - description: Write unit tests for scope checker in tests/surface/test_scope.py
    files: [systemf/tests/surface/test_scope.py]
    related_domains: ["Testing", "Type Theory"]
    expertise_required: ["Python", "pytest", "Test Design"]
    dependencies: [3, 5]
    priority: medium
    estimated_effort: medium
    notes: Test variable lookup, scoping, error cases with location tracking

  # Phase 2: Type Elaboration Infrastructure
  - description: Create TypeContext in surface/inference/context.py for type checking state
    files: [systemf/surface/inference/context.py]
    related_domains: ["Type Theory", "Software Engineering"]
    expertise_required: ["Type Design", "Python"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Track type bindings, metas, and constraints during elaboration

  - description: Create TypeError exception hierarchy in surface/inference/errors.py
    files: [systemf/surface/inference/errors.py]
    related_domains: ["Software Engineering", "Error Handling"]
    expertise_required: ["Python"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: Define TypeError hierarchy with UnificationError, TypeMismatch subclasses

  - description: Implement unification logic in surface/inference/unification.py
    files: [systemf/surface/inference/unification.py]
    related_domains: ["Type Theory", "Computer Science"]
    expertise_required: ["Type Design", "Python", "Unification Algorithms"]
    dependencies: [8]
    priority: high
    estimated_effort: medium
    notes: Robinson-style unification with occurs check and substitution

  - description: Implement TypeElaborator in surface/inference/elaborator.py for Phase 2
    files: [systemf/surface/inference/elaborator.py]
    related_domains: ["Type Theory", "Software Engineering"]
    expertise_required: ["Type Design", "Python", "Bidirectional Type Checking"]
    dependencies: [7, 9, 10]
    priority: high
    estimated_effort: large
    notes: Move logic from old elaborator; input ScopedTerm, output typed Core.Term

  - description: Write unit tests for type elaborator in tests/surface/test_inference.py
    files: [systemf/tests/surface/test_inference.py]
    related_domains: ["Testing", "Type Theory"]
    expertise_required: ["Python", "pytest", "Test Design"]
    dependencies: [11]
    priority: medium
    estimated_effort: medium
    notes: Test type inference, unification, error cases

  # Phase 3: Pipeline Orchestration and LLM
  - description: Implement LLM pragma pass in surface/llm/pass.py for Phase 3
    files: [systemf/surface/llm/pass.py]
    related_domains: ["Software Engineering", "LLM Integration"]
    expertise_required: ["Python", "AST Transformation"]
    dependencies: [11]
    priority: medium
    estimated_effort: small
    notes: Extract pragmas from surface_decl, replace body with Core.PrimOp

  - description: Implement top-level collection for mutual recursion support
    files: [systemf/surface/inference/elaborator.py]
    related_domains: ["Type Theory", "Software Engineering"]
    expertise_required: ["Type Design", "Python"]
    dependencies: [11]
    priority: high
    estimated_effort: medium
    notes: Collect all type signatures first, then elaborate bodies with all signatures in scope

  - description: Create pipeline orchestrator in surface/pipeline.py
    files: [systemf/surface/pipeline.py]
    related_domains: ["Software Engineering", "System Design"]
    expertise_required: ["Python", "Pipeline Architecture"]
    dependencies: [12, 14]
    priority: high
    estimated_effort: medium
    notes: Orchestrate scope check -> type elaborate -> LLM pass with error handling

  - description: Update REPL integration to use new pipeline
    files: [systemf/repl.py]
    related_domains: ["Software Engineering"]
    expertise_required: ["Python", "REPL Development"]
    dependencies: [15]
    priority: medium
    estimated_effort: small
    notes: Replace old elaborator calls with new pipeline API

  - description: Delete old elaborator code and update imports
    files: [systemf/surface/elaborator.py, systemf/surface/__init__.py]
    related_domains: ["Software Engineering", "Legacy Code Removal"]
    expertise_required: ["Python"]
    dependencies: [15]
    priority: low
    estimated_effort: small
    notes: Remove old single-pass elaborator, update all imports to use new pipeline

  - description: Write integration tests in tests/test_pipeline.py
    files: [systemf/tests/test_pipeline.py]
    related_domains: ["Testing", "System Integration"]
    expertise_required: ["Python", "pytest", "Integration Testing"]
    dependencies: [15]
    priority: medium
    estimated_effort: medium
    notes: End-to-end tests covering all three phases with error message verification
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-02 08:38:46] Architecture Design Complete

**Facts:**
- Analyzed design documents: ELABORATOR_DESIGN.md and elaborator-implementation-plan.md
- Identified 3-phase implementation (Scope Check, Type Elaboration, LLM Pass)
- Created 18 work items following Core-First dependency order
- Aligned work items with implementation plan's module structure:
  - surface/scoped/ - Phase 1: Scoped AST types, ScopeContext, ScopeChecker
  - surface/inference/ - Phase 2: TypeContext, Unification, TypeElaborator
  - surface/llm/ - Phase 3: LLMPragmaPass
  - surface/pipeline.py - Orchestration layer
  - core/ast.py - Source locations and debug names

**Analysis:**
- **Core-First Principle Applied**: Core types (Scoped AST, Core AST with locations) have empty dependencies
- **Phase Dependencies**: Phase 1 work items must complete before Phase 2 (indices 0-6 before 7-12)
- **Implementation Plan Alignment**: Work items reflect the sibling impl plan doc structure (surface/scoped/ not surface/scope/)
- **Testing Strategy**: Unit tests per phase plus integration tests for full pipeline
- **All-or-Nothing**: Old elaborator deletion work item (16) depends on full pipeline completion

**Conclusion:**
Status: ok

Design complete. 18 work items populated in bounded Work Items block, ready for Manager to create implementation tasks. Dependencies ensure correct execution order following multi-pass elaborator architecture.

---

### [2026-03-02 08:41:57] Design Review Complete

**Facts:**
Verified 18 work items following Core-First principle. Phase 1 (7 items): Core types with no dependencies (0,1,2,4) built first, implementation (3,5) and tests (6) follow. Phase 2 (5 items): Type infrastructure core (7,8) first, unification (9) and elaborator (10) build on them, tests (11) validate. Phase 3 (6 items): LLM pass (12) and top-level collection (13) depend on Phase 2 core, orchestrator (14) integrates both, REPL (15), cleanup (16), and integration tests (17) complete the pipeline. All items have complete metadata (files, domains, expertise, dependencies, priority, effort, notes). Dependencies ensure correct build order: core types → implementations → tests → integration → cleanup. Minor note: Item 10 dependencies [7,9,10] appears to have a typo (self-reference), likely should be [7,8,9].

**Analysis:**
-

**Conclusion:**
Status: ok

---

