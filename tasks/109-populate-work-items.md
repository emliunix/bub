---
assignee: Architect
expertise: ['System Design', 'Type Theory']
skills: []
type: design
priority: medium
state: review
dependencies: []
refers: ['tasks/108-kanban-system-fc-elaborator.md']
kanban: tasks/108-kanban-system-fc-elaborator.md
created: 2026-03-07T13:00:17.850651
---

# Task: Populate Work Items

## Context
<!-- Background information and relevant context -->

## Files
<!-- List of files to modify or reference -->

## Description
Review the design document in kanban and populate the bounded Work Items block with detailed breakdown of the System FC elaborator implementation

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items:
  # Phase 1: Design
  - id: "1.1"
    title: "Design coercion type system"
    phase: "design"
    type: "design"
    target_file: "src/systemf/core/coercion.py"
    description: "Define coercion datatypes (Refl, Sym, Trans, Comp, Axiom), coercion equality rules, and coercion composition"
    dependencies: []
    estimated_effort: "medium"
    
  - id: "1.2"
    title: "Design SCC analysis module"
    phase: "design"
    type: "design"
    target_file: "src/systemf/elaborator/scc.py"
    description: "Design Tarjan's algorithm interface for detecting mutually recursive type declarations"
    dependencies: []
    estimated_effort: "medium"
    
  - id: "1.3"
    title: "Review core design"
    phase: "review"
    type: "review"
    description: "Validate coercion system and SCC analysis designs before implementation"
    dependencies: ["1.1", "1.2"]
    estimated_effort: "small"
    
  # Phase 2: Coercion System Implementation
  - id: "2.1"
    title: "Implement coercion datatypes"
    phase: "implementation"
    type: "implement"
    target_file: "src/systemf/core/coercion.py"
    description: "Create Coercion dataclass hierarchy with Refl, Sym, Trans, Comp, Axiom constructors and coercion equality checking"
    dependencies: ["1.3"]
    estimated_effort: "medium"
    
  - id: "2.2"
    title: "Extend core AST with Cast and Axiom"
    phase: "implementation"
    type: "implement"
    target_file: "src/systemf/core/ast.py"
    description: "Add Cast(expr, coercion) and Axiom(name, args) constructors to Core AST"
    dependencies: ["2.1"]
    estimated_effort: "small"
    
  - id: "2.3"
    title: "Implement Tarjan's SCC algorithm"
    phase: "implementation"
    type: "implement"
    target_file: "src/systemf/elaborator/scc.py"
    description: "Implement strongly connected components detection for type declarations"
    dependencies: ["1.3"]
    estimated_effort: "medium"
    
  - id: "2.4"
    title: "Review coercion system implementation"
    phase: "review"
    type: "review"
    description: "Validate coercion types, core AST extensions, and SCC implementation"
    dependencies: ["2.1", "2.2", "2.3"]
    estimated_effort: "small"
    
  # Phase 3: ADT Processing
  - id: "3.1"
    title: "Generate coercion axioms for ADTs"
    phase: "implementation"
    type: "implement"
    target_file: "src/systemf/elaborator/coercion_axioms.py"
    description: "Generate axiom coercions for ADT representations (e.g., ax_Nat : Nat ~ Repr(Nat))"
    dependencies: ["2.4"]
    estimated_effort: "large"
    
  - id: "3.2"
    title: "Extend elaborator context with coercion environment"
    phase: "implementation"
    type: "implement"
    target_file: "src/systemf/surface/inference/context.py"
    description: "Add coercion axiom tracking to elaboration context"
    dependencies: ["3.1"]
    estimated_effort: "medium"
    
  - id: "3.3"
    title: "Constructor elaboration with coercions"
    phase: "implementation"
    type: "implement"
    target_file: "src/systemf/surface/inference/elaborator.py"
    description: "Modify constructor application to automatically insert coercions"
    dependencies: ["3.2"]
    estimated_effort: "large"
    
  - id: "3.4"
    title: "Review ADT processing"
    phase: "review"
    type: "review"
    description: "Validate coercion axiom generation, context extension, and constructor elaboration"
    dependencies: ["3.1", "3.2", "3.3"]
    estimated_effort: "small"
    
  # Phase 4: Pattern Matching
  - id: "4.1"
    title: "Pattern matching with inverse coercions"
    phase: "implementation"
    type: "implement"
    target_file: "src/systemf/surface/inference/elaborator.py"
    description: "Modify Case expression elaboration to insert inverse coercions (sym coercion)"
    dependencies: ["3.4"]
    estimated_effort: "large"
    
  - id: "4.2"
    title: "Implement exhaustiveness checking"
    phase: "implementation"
    type: "implement"
    target_file: "src/systemf/elaborator/exhaustiveness.py"
    description: "Pattern exhaustiveness and redundancy checking for case expressions"
    dependencies: ["4.1"]
    estimated_effort: "large"
    
  - id: "4.3"
    title: "Review pattern implementation"
    phase: "review"
    type: "review"
    description: "Validate pattern matching with coercions and exhaustiveness checking"
    dependencies: ["4.1", "4.2"]
    estimated_effort: "small"
    
  # Phase 5: Integration
  - id: "5.1"
    title: "Integrate pipeline stages"
    phase: "implementation"
    type: "implement"
    target_file: "src/systemf/surface/pipeline.py"
    description: "Wire SCC analysis → Axiom generation → Elaboration stages into pipeline"
    dependencies: ["4.3"]
    estimated_effort: "medium"
    
  - id: "5.2"
    title: "Write comprehensive test suite"
    phase: "implementation"
    type: "implement"
    target_files:
      - "tests/test_elaborator/test_coercions.py"
      - "tests/test_elaborator/test_adt.py"
      - "tests/test_elaborator/test_mutual_recursion.py"
    description: "Coercion composition tests, ADT coercion axiom tests, mutual recursion tests"
    dependencies: ["5.1"]
    estimated_effort: "large"
    
  - id: "5.3"
    title: "Implement coercion erasure"
    phase: "implementation"
    type: "implement"
    target_file: "src/systemf/elaborator/erasure.py"
    description: "Zero-cost coercion erasure - remove coercions from runtime code"
    dependencies: ["5.2"]
    estimated_effort: "medium"
    
  - id: "5.4"
    title: "Final integration review"
    phase: "review"
    type: "review"
    description: "Validate complete System FC elaborator pipeline and test coverage"
    dependencies: ["5.1", "5.2", "5.3"]
    estimated_effort: "small"
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-07 13:02:25] Populate Work Items

**Facts:**
<!-- No facts recorded -->

**Analysis:**
<!-- No analysis recorded -->

**Conclusion:**
<!-- No conclusion recorded -->

---

