---
assignee: Architect
type: design
title: "Design ScopedTypeVariables and Visible Type Application Architecture"
dependencies: []
skills: [code-reading, workflow]
expertise: ["Type System Design", "Bidirectional Type Checking", "System F"]
state: done
---

# Task: Design ScopedTypeVariables and Visible Type Application Architecture

## Context

System F currently has partial support for visible type application (`@`) but lacks full ScopedTypeVariables. The implementation needs to be extended to support:

1. **DECL-SCOPE**: Declaration-level forall binds type variables for the body
2. **ANN-SCOPE**: Type annotations bind forall variables for the annotated term
3. **LAM-ANN-SCOPE**: Lambda parameter annotations bind forall variables for the body
4. **PAT-POLY**: Pattern matching preserves polymorphic types for field bindings

## Current State

From `visible-type-application.md`:
- ✅ B_TApp works on globals (special case keeps forall)
- ❌ Context not extended with forall-bound vars before body checking
- ❌ Scoped type variables in annotations don't work
- ❌ Lambda param annotations don't bind type variables
- ❌ Pattern variables eagerly instantiated

## Files to Analyze

1. `src/systemf/surface/inference/bidi_inference.py` - Main type inference (1000+ lines)
2. `src/systemf/surface/inference/elab_bodies_pass.py` - Declaration body elaboration
3. `src/systemf/surface/inference/context.py` - Type context management
4. `systemf/docs/notes/visible-type-application.md` - Design notes

## Work Items
<!-- start workitems -->
work_items:
  - description: Add helper function collect_forall_vars() to extract forall-bound type variables from a type
    files: [systemf/src/systemf/surface/inference/bidi_inference.py]
    related_domains: ["Type Systems", "Functional Programming"]
    expertise_required: ["Type System Design", "Python"]
    dependencies: []
    priority: high
    estimated_effort: small
    notes: |
      Add a static method or module-level function to recursively extract all forall-bound 
      variable names from a TypeForall chain. Should handle nested foralls.
      
      Signature: collect_forall_vars(ty: Type) -> list[str]
      Example: forall a. forall b. a -> b -> (a, b) returns ['a', 'b']

  - description: Implement DECL-SCOPE - extend context with forall-bound vars in elab_bodies_pass
    files: [systemf/src/systemf/surface/inference/elab_bodies_pass.py]
    related_domains: ["Type Systems", "Functional Programming"]
    expertise_required: ["Type System Design", "Bidirectional Type Checking"]
    dependencies: [0]
    priority: high
    estimated_effort: small
    notes: |
      Before checking a declaration body, extend the type context with all forall-bound 
      variables from the declaration's expected type signature.
      
      Location: In elab_bodies_pass(), before calling bidi.check() or bidi.infer()
      
      Pattern:
        expected_type = signatures.get(decl.name)
        if expected_type:
            scoped_ctx = extend_with_forall_vars(type_ctx, expected_type)
        else:
            scoped_ctx = type_ctx
        core_body = bidi.check(decl.body, expected_type, scoped_ctx)

  - description: Implement ANN-SCOPE - extend context with annotation forall vars in type annotations
    files: [systemf/src/systemf/surface/inference/bidi_inference.py]
    related_domains: ["Type Systems", "Functional Programming"]
    expertise_required: ["Type System Design", "Bidirectional Type Checking"]
    dependencies: [0]
    priority: high
    estimated_effort: medium
    notes: |
      In SurfaceAnn case of infer(), extract forall-bound vars from the annotation type
      and extend the context before checking the annotated term.
      
      Location: infer() method, case SurfaceAnn
      
      Current code (lines 461-466):
        case SurfaceAnn(location=location, term=term_inner, type=type_ann):
            ann_type = self._surface_to_core_type(type_ann, ctx)
            core_term = self.check(term_inner, ann_type, ctx)
            final_type = self._apply_subst(ann_type)
            return (core_term, final_type)
      
      New code should:
        1. Extract forall vars from type_ann using collect_forall_vars()
        2. Extend ctx with those vars to create ann_ctx
        3. Convert type_ann with ann_ctx
        4. Check term_inner with ann_ctx

  - description: Implement LAM-ANN-SCOPE - extend context with lambda param forall vars
    files: [systemf/src/systemf/surface/inference/bidi_inference.py]
    related_domains: ["Type Systems", "Functional Programming"]
    expertise_required: ["Type System Design", "Bidirectional Type Checking"]
    dependencies: [0]
    priority: high
    estimated_effort: medium
    notes: |
      In ScopedAbs case of check(), when the lambda parameter has a polymorphic type 
      annotation, extend the context with forall-bound vars from that annotation for 
      checking the lambda body.
      
      Location: check() method, case ScopedAbs (lines 687-733)
      
      When var_type is not None and contains foralls:
        1. Extract forall vars from var_type
        2. Create body_ctx by extending ctx with those vars
        3. Convert var_type with original ctx (for parameter position)
        4. Check body with body_ctx (so forall vars are in scope)

  - description: Implement PAT-POLY - preserve polymorphic types in pattern matching
    files: [systemf/src/systemf/surface/inference/bidi_inference.py]
    related_domains: ["Type Systems", "Functional Programming"]
    expertise_required: ["Type System Design", "Bidirectional Type Checking"]
    dependencies: [0]
    priority: medium
    estimated_effort: medium
    notes: |
      In _check_branch() and _check_branch_check_mode(), don't eagerly instantiate 
      polymorphic constructor argument types when binding pattern variables.
      
      Current issue (lines 867-868):
        constr_type = self._instantiate(constr_type)  # This loses polymorphism!
      
      Instead:
        1. Get the constructor type
        2. Extract argument types WITHOUT instantiating polymorphic types
        3. When a pattern variable is bound to a polymorphic type (contains forall),
           keep it as-is instead of instantiating
        4. This allows the pattern variable to be used polymorphically in the branch body

  - description: Write integration tests for ScopedTypeVariables feature
    files: [systemf/tests/test_scoped_type_vars.py]
    related_domains: ["Type Systems", "Testing"]
    expertise_required: ["Type System Design", "Testing"]
    dependencies: [1, 2, 3, 4]
    priority: high
    estimated_effort: medium
    notes: |
      Create comprehensive tests covering:
      
      1. DECL-SCOPE:
         id :: forall a. a -> a = \\x -> (x :: a)  -- 'a' recognized in annotation
      
      2. ANN-SCOPE:
         let f = (\\x -> (x :: a)) :: forall a. a -> a
      
      3. LAM-ANN-SCOPE:
         usePoly :: (forall a. a -> a) -> Int
         usePoly = \\(f :: forall a. a -> a) -> f @a 42  -- 'a' bound for body
      
      4. PAT-POLY:
         data PolyBox = PolyBox (forall a. a -> a)
         unbox (PolyBox f) = f 42  -- f should be polymorphic
      
      5. Integration:
         -- All features combined
         test :: forall a b. (forall c. c -> c) -> a -> b -> (a, b)
         test = \\(f :: forall c. c -> c) x y -> (f x, f y)
<!-- end workitems -->

## Work Log

### [2026-03-09 22:51:54] Design Session

**Facts:**
- Analyzed codebase architecture in systemf/src/systemf/surface/inference/
- Read visible-type-application.md design document with 4 scope rules
- Reviewed bidi_inference.py (1309 lines) - bidirectional inference engine
- Reviewed elab_bodies_pass.py (106 lines) - declaration body elaboration
- Reviewed context.py (491 lines) - TypeContext with extend_type() method
- Identified exact insertion points for each scope rule
- Created 6 work items in bounded Work Items block

**Analysis:**
**Architecture Decisions:**

1. **Helper Function**: collect_forall_vars(ty: Type) -> list[str]
   - Recursively extracts vars from TypeForall chain
   - Handles nested foralls properly
   - Can be module-level or static method

2. **Context Extension Strategy:**
   - DECL-SCOPE: elab_bodies_pass.py line ~81 (before bidi.check)
   - ANN-SCOPE: bidi_inference.py infer() SurfaceAnn case (lines 461-466)
   - LAM-ANN-SCOPE: bidi_inference.py check() ScopedAbs case (lines 687-733)
   - PAT-POLY: bidi_inference.py _check_branch() lines 867-868
   - All use ctx.extend_type() which returns new immutable context

3. **Backward Compatibility:**
   - Changes are purely additive
   - No forall = empty var list = no-op extension
   - Existing tests should continue to pass

4. **Tradeoffs:**
   - Alternative (modify _surface_to_core_type): Rejected - too invasive
   - Alternative (pass vars separately): Rejected - complicates interface
   - Chosen: Explicit extension at scope boundaries - matches paper exactly

**Conclusion:**
Status: ok
Design complete with 6 work items created following core-first dependency order. Ready for implementation phase.

---

### [2026-03-09 22:53:32] Design Review

**Facts:**
- Reviewed 6 work items in bounded Work Items block
- Work items cover all 4 required scope rules: DECL-SCOPE, ANN-SCOPE, LAM-ANN-SCOPE, PAT-POLY
- Helper function collect_forall_vars() specified as work item 0 (core, no dependencies)
- Scope implementation work items (1-4) depend on helper function
- Integration tests (work item 5) depend on scope implementations
- All work items include: description, files, domains, expertise, dependencies, priority, effort, notes
- File paths reference correct locations in systemf/src/systemf/surface/inference/
- Code patterns include specific line numbers from bidi_inference.py and elab_bodies_pass.py

**Analysis:**
**Pattern Compliance Validation:**

1. **Core-First Dependency Order**: ✓ PASSED
   - Work item 0 (helper) has dependencies: [] - correctly designed first
   - Work items 1-4 depend on [0] - correctly reference core helper
   - Work item 5 depends on [1, 2, 3, 4] - tests depend on implementations
   - No circular dependencies detected

2. **Complexity Decomposition**: ✓ PASSED
   - All work items appropriately sized: small (2) or medium (4)
   - Maximum files per work item: 1 (appropriately focused)
   - Each work item has clear, single responsibility

3. **Pattern Selection Appropriateness**: ✓ PASSED
   - Design-First pattern correctly applied (new feature with core types)
   - Work items structured for Implementation-With-Review pattern
   - No core types being implemented without prior design

4. **Expertise Specification**: ✓ PASSED
   - All work items specify required expertise
   - Domain knowledge appropriate: Type System Design, Bidirectional Type Checking
   - Technical skills specified: Python, Testing

5. **Design Completeness**: ✓ PASSED
   - All 4 scope rules from requirements covered
   - Helper function signature specified: collect_forall_vars(ty: Type) -> list[str]
   - File locations exact with line numbers
   - Code patterns show before/after with clear implementation guidance
   - Test cases specified with concrete System F syntax examples

**No Issues Found:**
- No high-severity pattern violations
- No medium-severity issues requiring redesign
- Design follows architecture principles from role-architect.md

**Conclusion:**
Status: APPROVED

Design work items are valid and ready for implementation. The design correctly follows:
- Core-First dependency ordering
- Appropriate complexity decomposition
- Design-First pattern for new features
- Clear specifications for Implementor

Next Steps: Manager should create implementation tasks from these work items, respecting dependency order (helper first, then parallel scope implementations, then tests).

---

