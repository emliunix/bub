---
assignee: Implementor
expertise: ['Python', 'Type Theory', 'ADT Processing']
skills: []
type: implement
priority: high
state: done
dependencies: ['tasks/115-review-coercion-system-implementation.md']
refers: ['tasks/110-design-coercion-type-system.md', 'tasks/108-kanban-system-fc-elaborator.md']
kanban: tasks/108-kanban-system-fc-elaborator.md
created: 2026-03-07T13:24:21.848082
---

# Task: Generate coercion axioms for ADTs

## Context
<!-- Background information and relevant context -->

## Files
- src/systemf/elaborator/coercion_axioms.py

## Description
Generate axiom coercions for ADT representations (e.g., ax_Nat : Nat ~ Repr(Nat)) including data type to representation mappings

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-07 13:26:24] Implementation Complete

**Facts:**
Created systemf/src/systemf/elaborator/coercion_axioms.py with ADTAxiom dataclass linking declarations to coercions, CoercionAxiomGenerator class with generate_axiom() creating ax_Name : T ~ Repr(T) coercions, helper methods for building abstract/repr types and type args, storage and retrieval of generated axioms, convenience functions generate_adt_axiom() and generate_axioms_for_declarations(). Verified working with simple types (Nat), polymorphic types (List a), and batch generation.

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-03-07 13:27:45] Implementation Review

**Facts:**
<!-- No facts recorded -->

**Analysis:**
<!-- No analysis recorded -->

**Conclusion:**
<!-- No conclusion recorded -->

---

