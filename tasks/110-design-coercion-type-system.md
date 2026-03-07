---
assignee: Architect
expertise: ['System Design', 'Type Theory']
skills: []
type: design
priority: high
state: done
dependencies: []
refers: ['tasks/109-populate-work-items.md', 'tasks/108-kanban-system-fc-elaborator.md']
kanban: tasks/108-kanban-system-fc-elaborator.md
created: 2026-03-07T13:05:07.591225
---

# Task: Design coercion type system

## Context
<!-- Background information and relevant context -->

## Files
- src/systemf/core/coercion.py
- src/systemf/core/types.py

## Description
Define coercion datatypes (Refl, Sym, Trans, Comp, Axiom), coercion equality rules, and coercion composition

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items:
  - description: "Implement Coercion base class with left/right type properties"
    files: [systemf/src/systemf/core/coercion.py]
    related_domains: ["Type Theory", "Type Systems"]
    expertise_required: ["System Design", "Type Theory"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: "Base class with abstract left/right properties, free_vars(), substitute() methods"
    
  - description: "Implement CoercionRefl - reflexivity coercion"
    files: [systemf/src/systemf/core/coercion.py]
    related_domains: ["Type Theory", "Type Systems"]
    expertise_required: ["System Design", "Type Theory"]
    dependencies: [0]
    priority: high
    estimated_effort: small
    notes: "Identity coercion: τ ~ τ"
    
  - description: "Implement CoercionSym - symmetry coercion"
    files: [systemf/src/systemf/core/coercion.py]
    related_domains: ["Type Theory", "Type Systems"]
    expertise_required: ["System Design", "Type Theory"]
    dependencies: [1]
    priority: high
    estimated_effort: small
    notes: "Inverse coercion: if γ : τ₁ ~ τ₂, then Sym(γ) : τ₂ ~ τ₁"
    
  - description: "Implement CoercionTrans - transitivity coercion"
    files: [systemf/src/systemf/core/coercion.py]
    related_domains: ["Type Theory", "Type Systems"]
    expertise_required: ["System Design", "Type Theory"]
    dependencies: [2]
    priority: high
    estimated_effort: small
    notes: "Chain coercions: if γ₁ : τ₁ ~ τ₂ and γ₂ : τ₂ ~ τ₃, then Trans(γ₁, γ₂) : τ₁ ~ τ₃"
    
  - description: "Implement CoercionComp - composition coercion"
    files: [systemf/src/systemf/core/coercion.py]
    related_domains: ["Type Theory", "Type Systems"]
    expertise_required: ["System Design", "Type Theory"]
    dependencies: [3]
    priority: medium
    estimated_effort: small
    notes: "Sequential composition: Comp(γ₁, γ₂) semantically equivalent to Trans"
    
  - description: "Implement CoercionAxiom - axiom coercion for ADTs"
    files: [systemf/src/systemf/core/coercion.py]
    related_domains: ["Type Theory", "Type Systems"]
    expertise_required: ["System Design", "Type Theory"]
    dependencies: [4]
    priority: high
    estimated_effort: medium
    notes: "Named coercion axioms with type arguments: ax_Nat : Nat ~ Repr(Nat)"
    
  - description: "Implement coercion equality checking"
    files: [systemf/src/systemf/core/coercion.py]
    related_domains: ["Type Theory", "Type Systems"]
    expertise_required: ["System Design", "Type Theory"]
    dependencies: [5]
    priority: medium
    estimated_effort: small
    notes: "Structural equality for coercions, checks constructor, types, and recursive equality"
    
  - description: "Implement coercion composition with normalization"
    files: [systemf/src/systemf/core/coercion.py]
    related_domains: ["Type Theory", "Type Systems"]
    expertise_required: ["System Design", "Type Theory"]
    dependencies: [6]
    priority: medium
    estimated_effort: small
    notes: "compose_coercions() with Refl optimizations"
    
  - description: "Implement coercion inversion"
    files: [systemf/src/systemf/core/coercion.py]
    related_domains: ["Type Theory", "Type Systems"]
    expertise_required: ["System Design", "Type Theory"]
    dependencies: [7]
    priority: medium
    estimated_effort: small
    notes: "invert_coercion() with double-negation elimination"
    
  - description: "Implement coercion normalization"
    files: [systemf/src/systemf/core/coercion.py]
    related_domains: ["Type Theory", "Type Systems"]
    expertise_required: ["System Design", "Type Theory"]
    dependencies: [8]
    priority: low
    estimated_effort: small
    notes: "normalize_coercion() for canonical form and equality checking"
    
  - description: "Write unit tests for coercion types"
    files: [systemf/tests/test_core/test_coercion.py]
    related_domains: ["Software Engineering", "Testing"]
    expertise_required: ["Code Implementation", "Testing"]
    dependencies: [9]
    priority: high
    estimated_effort: medium
    notes: "Test all coercion constructors, composition, equality, and normalization"
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-07 13:07:52] Design coercion type system

**Facts:**
<!-- No facts recorded -->

**Analysis:**
<!-- No analysis recorded -->

**Conclusion:**
<!-- No conclusion recorded -->

---

### [2026-03-07 13:09:33] Design Review

**Facts:**
<!-- No facts recorded -->

**Analysis:**
<!-- No analysis recorded -->

**Conclusion:**
<!-- No conclusion recorded -->

---

