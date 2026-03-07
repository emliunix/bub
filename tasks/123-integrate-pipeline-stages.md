---
assignee: Implementor
expertise: ['Python', 'Pipeline Integration']
skills: []
type: implement
priority: high
state: done
dependencies: ['tasks/122-review-pattern-matching-implementation.md']
refers: ['tasks/113-implement-tarjans-scc-algorithm.md', 'tasks/116-generate-coercion-axioms-for-adts.md', 'tasks/108-kanban-system-fc-elaborator.md']
kanban: tasks/108-kanban-system-fc-elaborator.md
created: 2026-03-07T19:09:43.212156
---

# Task: Integrate pipeline stages

## Context
<!-- Background information and relevant context -->

## Files
- src/systemf/surface/pipeline.py

## Description
Wire SCC analysis → Axiom generation → Elaboration stages into the pipeline to create the complete System FC elaboration flow

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-07 19:13:28] Implementation Complete

**Facts:**
Modified systemf/src/systemf/surface/inference/elaborator.py to integrate pipeline stages: Added SCC analysis and coercion axiom generation imports (SCCAnalyzer, CoercionAxiomGenerator, etc.), Added Phase 3.5 call in elaborate_declarations() to run _generate_coercion_axioms() after data declaration processing and before term elaboration, Implemented _generate_coercion_axioms() method that extracts data declarations, builds SCC nodes from constructor dependencies, runs Tarjan's SCC algorithm for mutual recursion detection, generates coercion axioms (ax_Name : Name ~ Repr(Name)) for each data type, and adds axioms to TypeContext for use during elaboration, Added _collect_type_dependencies() helper to extract type names from surface types, Added _convert_surface_to_core_data_decl() to convert surface data declarations to core format for axiom generation. Verified integration works - axioms generated and added to context for ADT declarations.

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-03-07 19:14:50] Implementation Review

**Facts:**
<!-- No facts recorded -->

**Analysis:**
<!-- No analysis recorded -->

**Conclusion:**
<!-- No conclusion recorded -->

---

