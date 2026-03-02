---
assignee: Architect
expertise: ['Type Theory', 'System F', 'Python']
skills: ['code-reading']
type: design
priority: medium
state: done
dependencies: []
refers: ['tasks/101-kanban-implicit-instantiation-for-system-f.md']
kanban: tasks/101-kanban-implicit-instantiation-for-system-f.md
created: 2026-03-03T00:48:31.955326
---

# Task: Design Implicit Instantiation Implementation

## Context
<!-- Background information and relevant context -->

## Files
<!-- List of files to modify or reference -->

## Description
Analyze the implicit instantiation requirements from the kanban and create detailed work items. Review the current elaborator implementation, TYPE_INFERENCE_BUGS.md, and IMPLICIT_INSTANTIATION.md to determine the exact changes needed. Focus on: 1) Nested forall instantiation, 2) Application site implicit instantiation, 3) Pattern matching with polymorphic constructors, 4) Constructor elaboration fixes.

## Work Items
<!-- Structured, script-validated work items for Manager -->
<!-- start workitems -->
work_items:
  - description: Fix nested forall instantiation in _instantiate() method
    files:
      - systemf/src/systemf/surface/inference/elaborator.py
    related_domains: ["Type Theory", "System F"]
    expertise_required: ["Type Theory", "Python"]
    dependencies: []
    priority: high
    estimated_effort: medium
    notes: |
      Current _instantiate() at lines 810-827 only handles single-level forall.
      Must recursively handle nested ∀a.∀b.T → T[α/a][β/b] where α,β are fresh meta-variables.
      Fix TYPE_INFERENCE_BUGS.md Fix 2 (Polymorphic instantiation).
      
  - description: Add implicit instantiation at application sites in infer() for SurfaceApp
    files:
      - systemf/src/systemf/surface/inference/elaborator.py
    related_domains: ["Type Theory", "System F"]
    expertise_required: ["Type Theory", "Python"]
    dependencies: [0]
    priority: high
    estimated_effort: medium
    notes: |
      In SurfaceApp case (lines 269-304), when func has TypeForall type, 
      instantiate before application. When elaborating f arg where f has 
      polymorphic type (e.g., id : ∀a. a → a), detect TypeForall and 
      instantiate to match argument type.
      
  - description: Fix pattern matching with polymorphic constructors in _check_branch()
    files:
      - systemf/src/systemf/surface/inference/elaborator.py
    related_domains: ["Type Theory", "System F"]
    expertise_required: ["Type Theory", "Python"]
    dependencies: [0]
    priority: high
    estimated_effort: large
    notes: |
      CRITICAL: Fixes prelude.sf line 103 error. _check_branch() at lines 774-808 must:
      1. Look up constructor type from ctx.constructors
      2. Instantiate polymorphic constructor type (e.g., Left : ∀a.∀b. a → Either a b)
      3. Unify constructor result type with scrutinee type
      4. Extract argument types for pattern variables from instantiated constructor
      Currently creates fresh meta-vars without validation against constructor type.
      
  - description: Update constructor elaboration for polymorphic type instantiation
    files:
      - systemf/src/systemf/surface/inference/elaborator.py
    related_domains: ["Type Theory", "System F"]
    expertise_required: ["Type Theory", "Python"]
    dependencies: [0]
    priority: medium
    estimated_effort: small
    notes: |
      SurfaceConstructor case (lines 395-436) has partial instantiation.
      Ensure constructor expressions used as values get properly instantiated
      with fresh meta-variables for all type parameters.
      
  - description: Test fixes and verify all 182 tests pass
    files:
      - systemf/tests/test_surface/test_inference.py
      - systemf/tests/test_pipeline.py
      - systemf/prelude.sf
    related_domains: ["Testing", "System F"]
    expertise_required: ["Python", "Testing"]
    dependencies: [1, 2, 3, 4]
    priority: high
    estimated_effort: small
    notes: |
      Verify prelude loads successfully (currently fails at line 103).
      Run full test suite and ensure all 182 tests pass.
      Focus on previously failing tests:
      - test_application_with_inference
      - test_deeply_nested_application  
      - test_case_with_pattern_bindings
      - test_flip_function
      - test_nested_lambda_application
<!-- end workitems -->

## Work Log
<!-- Work logs will be appended here -->

### [2026-03-03 00:50:20] Implicit Instantiation Design Analysis

**Facts:**
<!-- What was actually done (files modified, code written, tests run, etc.) -->

**Context Review:**
- Analyzed kanban request: prelude.sf fails at line 103 with error "expected constructor type with 1 arguments, but got ∀b._a -> Either _a b"
- Error occurs in `mapRight` function when pattern matching with polymorphic constructors `Left` and `Right`
- Reviewed TYPE_INFERENCE_BUGS.md which documents 7 failing tests related to type inference issues

**Documentation Analysis:**
- Read IMPLICIT_INSTANTIATION.md: Explains the theory of implicit type instantiation (surface language → explicit System F core)
- Reviewed TYPE_INFERENCE_BUGS.md Fix Plan: Identified 4 key fixes needed:
  - Fix 1: Apply substitution to result types (Bug A)
  - Fix 2: Instantiate polymorphic types (Bug B) - CRITICAL for this task
  - Fix 3: Convert exception types (Bug C)
  - Fix 4: Mark forward reference test as xfail

**Code Analysis:**
- Examined `systemf/src/systemf/surface/inference/elaborator.py` (1236 lines)
- Located `_instantiate()` method at lines 810-827: Only handles single-level forall, needs recursion for nested ∀a.∀b.T
- Located `_check_branch()` method at lines 774-808: Does NOT:
  - Look up constructor types from context
  - Instantiate polymorphic constructor types (e.g., Left: ∀a.∀b. a → Either a b)
  - Unify constructor result type with scrutinee type
  - Extract argument types for pattern variables from instantiated constructor type
- Located `infer()` for SurfaceApp at lines 269-304: Does NOT check for TypeForall on function type
- Located constructor case at lines 395-436: Has partial instantiation but doesn't handle nested foralls

**Prelude Analysis:**
- Line 103 in prelude.sf: `case e of { Left x → Left x | Right y → Right (f y) }`
- Constructor `Left` has type `∀a.∀b. a → Either a b`
- When used in pattern `Left x`, the type needs to be instantiated to match scrutinee `Either a b`
- Current code creates fresh meta-variables for pattern vars but doesn't validate against constructor type

**Analysis:**
**Root Cause:**
The `_check_branch()` method creates fresh meta-variables for pattern variables (line 796) but:
1. Never looks up what type the constructor expects
2. Never instantiates the constructor's polymorphic type with the scrutinee's concrete types
3. Never validates that pattern variable types match constructor argument types
4. The `_instantiate()` method only peels off one forall level, so nested polymorphism (∀a.∀b.T) isn't fully instantiated

**Key Insight from TYPE_INFERENCE_BUGS.md:**
> "When elaborating `SurfaceConstructor("Pair", [arg1, arg2])`:
> 1. We look up constructor type: `a -> b -> Pair a b`
> 2. We need to instantiate the type variables `a` and `b` with fresh meta-variables
> 3. Then unify those meta-variables with the actual argument types"

This same logic must be applied in `_check_branch()` for pattern matching.

**Required Changes:**
1. **Fix nested forall instantiation** - Make `_instantiate()` recursive to handle `∀a.∀b.T` → `T[α/a][β/b]` where α,β are fresh meta-vars
2. **Add implicit instantiation at applications** - In SurfaceApp case, detect when func has TypeForall and instantiate before applying
3. **Fix pattern matching** - In `_check_branch()`: lookup constructor, instantiate its type, unify result with scrutinee, bind pattern vars to arg types
4. **Update constructor elaboration** - Ensure constructor expressions used as values get properly instantiated
5. **Verify fixes** - Ensure prelude loads and all 182 tests pass

**Dependencies:**
- Fix 1 is foundational (changes core instantiation logic)
- Fixes 2-4 depend on Fix 1
- Fix 5 is verification/validation

**Design Decision:**
Following Core-First Dependency Order:
- Work item 1 (instantiation fix) has no dependencies
- Work items 2-4 depend on work item 1
- Work item 5 depends on all implementation items

**Conclusion:**
Status: ok

**Summary:**
Analyzed the implicit instantiation requirements and current elaborator implementation. The core issue is that polymorphic constructor types (like `Left : ∀a.∀b. a → Either a b`) are not being properly instantiated when used in pattern matching branches. 

The `_instantiate()` method needs to handle nested foralls recursively, and `_check_branch()` needs to lookup constructor types, instantiate them against the scrutinee type, and properly bind pattern variables.

Created 5 work items following Core-First Dependency Order:
1. Fix nested forall instantiation (core)
2. Add implicit instantiation at application sites (depends on #1)
3. Fix pattern matching with polymorphic constructors (depends on #1)
4. Update constructor elaboration (depends on #1)
5. Test fixes and verification (depends on #2-4)

**Next Steps:**
- Populate work items in task file
- Transition to review state

<!-- Additional notes -->

---

