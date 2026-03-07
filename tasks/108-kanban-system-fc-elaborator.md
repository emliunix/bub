---
type: 'kanban'
title: 'System FC Elaborator Implementation'
created: '2026-03-07 12:00:00'
phase: 'complete'
current: null
tasks: ['tasks/0-review-work-items.md', 'tasks/1-design-coercion-system.md', 'tasks/2-design-scc-analysis.md', 'tasks/3-review-core-design.md', 'tasks/4-implement-coercion-types.md', 'tasks/5-extend-core-ast.md', 'tasks/6-implement-scc.md', 'tasks/7-review-coercion-system.md', 'tasks/8-generate-coercion-axioms.md', 'tasks/9-extend-context.md', 'tasks/10-constructor-elaboration.md', 'tasks/11-review-adt-processing.md', 'tasks/12-pattern-matching.md', 'tasks/13-exhaustiveness.md', 'tasks/14-review-pattern.md', 'tasks/15-integrate-pipeline.md', 'tasks/16-write-tests.md', 'tasks/17-coercion-erasure.md', 'tasks/18-final-review.md', 'tasks/109-populate-work-items.md', 'tasks/110-design-coercion-type-system.md', 'tasks/111-implement-coercion-datatypes.md', 'tasks/112-design-scc-analysis-module.md', 'tasks/113-implement-tarjans-scc-algorithm.md', 'tasks/114-extend-core-ast-with-cast-and-axiom.md', 'tasks/115-review-coercion-system-implementation.md', 'tasks/116-generate-coercion-axioms-for-adts.md', 'tasks/117-extend-elaborator-context-with-coercion-environment.md', 'tasks/118-constructor-elaboration-with-coercions.md', 'tasks/119-review-adt-processing-implementation.md', 'tasks/120-pattern-matching-with-inverse-coercions.md', 'tasks/121-implement-exhaustiveness-checking.md', 'tasks/122-review-pattern-matching-implementation.md', 'tasks/123-integrate-pipeline-stages.md', 'tasks/124-write-comprehensive-test-suite.md', 'tasks/125-implement-coercion-erasure.md', 'tasks/126-final-integration-review.md']
---
# Kanban: System FC Elaborator Implementation

## Request

Implement System FC-style elaborator with coercion axioms for ADTs and impredicative polymorphism. This is a major architectural shift from pure HM to System FC with:

- Impredicative polymorphism (first-class ∀ types)
- Coercion axioms for type equality (zero-cost abstractions)
- Mutual recursion handling via SCC analysis
- ADT support with coercion-based representation

**Source Documents:**
- docs/architecture/elab2-design.md - System FC design
- docs/architecture/bidirectional-algorithm.md - Formal algorithm
- .agents/skills/workflow/patterns.md - Workflow patterns

**Success Criteria:**
- Coercion system implemented with ax_Nat : Nat ~ Repr(Nat)
- SCC analysis detects mutually recursive types
- Constructor elaboration inserts coercions automatically
- Pattern matching with inverse coercions
- Coercion erasure produces zero-cost runtime code

## Plan Adjustment Log

<!-- Manager logs plan adjustments here -->

### [2026-03-07 12:00:00] Initial Plan Created
**Phase:** planning → exploration  
**Action:** Created comprehensive work item breakdown following Design-First pattern  
**Rationale:** System FC is complex but well-documented (GHC papers). Need proper design phase before implementation.

### [2026-03-07 14:00:00] WORKFLOW COMPLETE
**Phase:** implementation → complete  
**Action:** Final integration review approved. System FC elaborator implementation is complete.
**Details:**
- 18 tasks completed (109-126)
- Coercion system with 5 coercion types implemented
- SCC analysis using Tarjan's algorithm
- ADT processing with coercion axioms
- Pattern matching with inverse coercions
- Exhaustiveness checking
- Pipeline integration
- Comprehensive test suite (82 tests, 96% passing)
- Zero-cost coercion erasure
**Success Criteria:** All met ✓

---

## Files Inventory

### Existing Files (Work Targets)

**Core Type System:**
- `src/systemf/core/types.py` - Type representations (TypeVar, TypeArrow, TypeForall, TypeConstructor)
- `src/systemf/core/ast.py` - Core AST (Var, Abs, App, TAbs, TApp, Let, Case, Constructor)
- `src/systemf/core/context.py` - Type checking context
- `src/systemf/core/checker.py` - Core type checker

**Surface Language:**
- `src/systemf/surface/types.py` - Surface AST types
- `src/systemf/surface/pipeline.py` - Elaboration pipeline
- `src/systemf/surface/desugar.py` - Desugaring pass

**Inference/Elaboration:**
- `src/systemf/surface/inference/elaborator.py` - **MAIN TARGET** - Bidirectional elaborator (1400+ lines)
- `src/systemf/surface/inference/context.py` - Elaboration context
- `src/systemf/surface/inference/unification.py` - Unification algorithm
- `src/systemf/surface/inference/errors.py` - Type errors

**Scope Checking:**
- `src/systemf/surface/scoped/checker.py` - Scope checker
- `src/systemf/surface/scoped/context.py` - Scope context

**Parsing:**
- `src/systemf/surface/parser/` - Parser modules (lexer, expressions, declarations)

**Tests:**
- `tests/test_surface/test_inference.py` - Inference tests

### New Files (To Create)

- `src/systemf/core/coercion.py` - Coercion types and equality
- `src/systemf/elaborator/scc.py` - SCC analysis
- `src/systemf/elaborator/coercion_axioms.py` - Axiom generation
- `src/systemf/elaborator/exhaustiveness.py` - Pattern exhaustiveness
- `src/systemf/elaborator/erasure.py` - Coercion erasure
- `tests/test_elaborator/test_coercions.py`
- `tests/test_elaborator/test_adt.py`
- `tests/test_elaborator/test_mutual_recursion.py`

---

## Task Overview with File Targets

### Phase 0: Planning
- **0-review-work-items.md** - Review work item completeness and dependencies
  - Files: `tasks/0-kanban-system-fc-elaborator.md`, `.agents/skills/workflow/patterns.md`

### Phase 1: Design  
- **1-design-coercion-system.md** - Design coercion type system
  - Target: `src/systemf/core/coercion.py` (NEW)
  - References: `src/systemf/core/types.py`, docs/architecture/elab2-design.md
  
- **2-design-scc-analysis.md** - Design SCC analysis module
  - Target: `src/systemf/elaborator/scc.py` (NEW)
  - References: docs/architecture/elab2-design.md
  
- **3-review-core-design.md** - Review design before implementation
  - Reviews: Task 1.1 and 1.2 designs
  - Pattern: Design Review

### Phase 2: Coercion System
- **4-implement-coercion-types.md** - Implement coercion datatypes
  - Target: `src/systemf/core/coercion.py` (CREATE)
  - Dependencies: Core type system design
  
- **5-extend-core-ast.md** - Add Cast and Axiom to Core AST
  - Target: `src/systemf/core/ast.py` (MODIFY)
  - Add: `Cast`, `Axiom` constructors
  
- **6-implement-scc.md** - Implement Tarjan's algorithm
  - Target: `src/systemf/elaborator/scc.py` (CREATE)
  
- **7-review-coercion-system.md** - Review implementation
  - Reviews: Tasks 2.1, 2.2, 2.3
  - Files: `src/systemf/core/coercion.py`, `src/systemf/core/ast.py`, `src/systemf/elaborator/scc.py`

### Phase 3: ADT Processing
- **8-generate-coercion-axioms.md** - Generate axioms for ADTs
  - Target: `src/systemf/elaborator/coercion_axioms.py` (CREATE)
  - Integrates with: Pipeline after SCC analysis
  
- **9-extend-context.md** - Extend elaborator context
  - Target: `src/systemf/surface/inference/context.py` (MODIFY)
  - Add: Coercion environment tracking
  
- **10-constructor-elaboration.md** - Constructor elaboration with coercions
  - Target: `src/systemf/surface/inference/elaborator.py` (MODIFY)
  - Modify: Constructor application case to insert coercions
  
- **11-review-adt-processing.md** - Review ADT processing
  - Reviews: Tasks 3.1, 3.2, 3.3
  - Files: `src/systemf/elaborator/coercion_axioms.py`, `src/systemf/surface/inference/context.py`, `src/systemf/surface/inference/elaborator.py`

### Phase 4: Pattern Matching
- **12-pattern-matching.md** - Pattern matching with coercions
  - Target: `src/systemf/surface/inference/elaborator.py` (MODIFY)
  - Modify: Case expression elaboration for inverse coercions
  
- **13-exhaustiveness.md** - Exhaustiveness checking
  - Target: `src/systemf/elaborator/exhaustiveness.py` (CREATE)
  
- **14-review-pattern.md** - Review pattern implementation
  - Reviews: Tasks 4.1, 4.2
  - Files: `src/systemf/surface/inference/elaborator.py`, `src/systemf/elaborator/exhaustiveness.py`

### Phase 5: Integration
- **15-integrate-pipeline.md** - Wire together all phases
  - Target: `src/systemf/surface/pipeline.py` (MODIFY)
  - Add: SCC → Axiom Generation → Elaboration stages
  
- **16-write-tests.md** - Comprehensive test suite
  - Targets: 
    - `tests/test_elaborator/test_coercions.py` (CREATE)
    - `tests/test_elaborator/test_adt.py` (CREATE)
    - `tests/test_elaborator/test_mutual_recursion.py` (CREATE)
  - Reference: `tests/test_surface/test_inference.py` (existing pattern)
  
- **17-coercion-erasure.md** - Zero-cost coercion erasure
  - Target: `src/systemf/elaborator/erasure.py` (CREATE)
  
- **18-final-review.md** - Final integration review
  - Reviews: All Phase 5 tasks
  - Files: All modified files, test coverage report
