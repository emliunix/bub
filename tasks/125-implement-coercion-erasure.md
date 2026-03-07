---
assignee: Implementor
expertise: ['Python', 'Code Generation']
skills: []
type: implement
priority: medium
state: done
dependencies: ['tasks/124-write-comprehensive-test-suite.md']
refers: ['tasks/111-implement-coercion-datatypes.md', 'tasks/108-kanban-system-fc-elaborator.md']
kanban: tasks/108-kanban-system-fc-elaborator.md
created: 2026-03-07T19:23:23.808062
---

# Task: Implement coercion erasure

## Context
<!-- Background information and relevant context -->

## Files
- src/systemf/elaborator/erasure.py

## Description
Zero-cost coercion erasure - remove coercions from runtime code to ensure coercions are truly zero-cost abstractions

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items: []
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-07 19:25:41] Implementation Complete

**Facts:**
Created systemf/src/systemf/elaborator/erasure.py with zero-cost coercion erasure: erase_coercions(term) recursively processes terms removing Cast nodes (just returns inner expression), raising ValueError for naked Axiom terms (should be wrapped in Cast), and recursively erasing coercions in all subterms (lambda bodies, application func/arg, constructor args, case scrutinee/branches, let value/body, tool call args, term declaration bodies). erase_module_coercions(module) erases coercions from all declarations in a module, returning a new module with erased declarations. is_erased(term) checks if a term contains no Cast or Axiom nodes. Verified Cast nodes are erased (returns inner expression), nested Casts are fully erased, naked Axioms raise errors, and all term constructors properly recursively process subterms. Ensures zero-cost abstraction guarantee for System FC coercions.

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-03-07 19:26:52] Implementation Review

**Facts:**
<!-- No facts recorded -->

**Analysis:**
<!-- No analysis recorded -->

**Conclusion:**
<!-- No conclusion recorded -->

---

