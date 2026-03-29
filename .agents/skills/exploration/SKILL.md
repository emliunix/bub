---
name: exploration
description: Systematic codebase investigation with evidence-based claims. Use when (1) researching unknown systems, (2) tracing code paths, (3) documenting architecture discoveries.
---

# Exploration: Structured Codebase Research

Guide for systematically exploring and documenting unfamiliar codebases.

## Core Concepts

**Topic** - Investigation area with central question and scope boundaries
**Claim** - Atomic, verifiable assertion with source attribution  
**Evidence** - Exact code snippets with file paths and line numbers
**Validated Notes** - Once exploration files are marked Validated, they can be cited as sources (secondary to source code, but authoritative for derived claims)

## Document Structure

Exploration files: `{TOPIC_KEYWORD}_EXPLORATION.md`

```markdown
# [Topic Title]

**Status:** In Progress | Validated | Archived
**Last Updated:** YYYY-MM-DD
**Central Question:** [What we're investigating]

## Summary
Brief overview (2-3 paragraphs).

## Claims

### Claim N: [Title]
**Statement:** [Atomic assertion]
**Source:** `path/file:lines`
**Evidence:**
```haskell
[Exact code snippet]
```
**Status:** Draft | Validated | Needs Revision
**Notes:** [Any issues or contradictions]

## Open Questions
- [ ] Unresolved item

## Related Topics
- [LINK_TO_OTHER.md]
```

**Session files** (`{TOPIC}_{DATE}_{ID}_TEMP.md`): Same structure, add **Confidence:** field per claim.

### Using Existing Exploration Notes

When previous validated exploration exists, it can serve as a starting point:

**Evidence hierarchy:**
1. **Source code** - Primary evidence (most authoritative)
2. **Validated exploration notes** - Secondary source (claims marked "Validated" in master files)
3. **Draft exploration notes** - Reference only (not authoritative)

**When citing validated notes:**
```markdown
**Claim:** [Derived assertion]
**Source:** `analysis/TOPIC_EXPLORATION.md:Claim N` + `path/file:lines`
**Evidence:**
- From exploration: [validated finding]
- From source: [code confirming the finding]
```

**Workflow:**
- **Stage 1 (Explore):** Check existing validated notes first for relevant claims
- **Stage 2 (Validate):** Verify both the source code AND check against existing validated claims for consistency
- **Stage 3 (Merge):** Update cross-references between related topics

## Step 0: Scope Clarification

Before exploring, define clear boundaries to prevent infinite exploration.

### Entry Point Selection
Choose starting point based on investigation type:
- **Error messages** → Stack traces → Source location
- **APIs** → Interface definitions → Implementations  
- **Data flow** → Input handlers → Processing → Output
- **Architecture** → Core types → Relationships → Usage

### Termination Criteria

**Stop exploring when:**
- [ ] Central question is answered with evidence
- [ ] 3+ dead-ends encountered (scope too broad - refine question)
- [ ] Recursion depth > 5 (circular dependencies or over-tracing)
- [ ] Claims become speculative (no source evidence found)

**If stuck:** Return with partial findings + specific blockers. Don't guess or hallucinate.

### Scope Boundaries (IN/OUT)

Define what's included and excluded:

```
IN: [Specific functions, files, or concepts to cover]
OUT: [Areas to ignore, even if related]
```

## Three-Stage Workflow

### Stage 1: Explore

Create temp file with findings using subagent.

**Spawn exploration subagent:**
```
You are an exploration subagent...

**Input (READ-ONLY):**
- Master: /path/to/{TOPIC}_EXPLORATION.md

**Output (WRITE TO THIS):**
/path/to/{TOPIC}_{DATE}_{ID}_TEMP.md

**Topic:** [Specific aspect]
**Central Question:** [What to answer]
**Entry Point:** File + function + line
**Scope:** IN [list], OUT [list]

**Deliverable:** Follow claim format (statement + source + evidence)
```

**Checklist:**
- [ ] Role definition
- [ ] Input files marked (READ-ONLY)
- [ ] Output temp file marked (WRITE TO THIS)
- [ ] Topic and central question specified
- [ ] Entry point (file + function + line)
- [ ] IN scope list
- [ ] OUT scope list
- [ ] Working directory specified

---

### Stage 2: Validate

Verify evidence against actual source code.

**Spawn validation subagent:**
```
You are a validation subagent...

**Target:** /path/to/{TOPIC}_{DATE}_{ID}_TEMP.md

**Validate:**
1. Evidence verification (code exists at cited location?)
2. Cross-check against existing validated claims (consistency with prior findings)
3. Logic check (does claim follow from evidence?)
4. Assess confidence (High/Medium/Low)

**Add per claim:**
- **VALIDATED:** Yes/No/Partial
- **Source Check:** Verified/Mismatch at line X
- **Logic Check:** Sound/Questionable
- **Notes:** Any issues
```

**Checklist:**
- [ ] Role definition
- [ ] Target file specified
- [ ] Validation criteria listed
- [ ] Annotation format defined
- [ ] Working directory specified

---

### Stage 3: Merge

Integrate validated findings into master file.

**Spawn merge subagent:**
```
You are a merge subagent...

**Source:** /path/to/{TOPIC}_{DATE}_{ID}_TEMP.md (validated)
**Target:** /path/to/{TOPIC}_EXPLORATION.md (UPDATE THIS)

**Merge rules:**
- Validated claims → Add to Claims section
- Failed claims → Add to "Unconfirmed Hypotheses" section with reason
- Remove obsolete claims (mark deprecated first)
- Deduplicate existing claims
- Update cross-references

**Update metadata:** Last Updated date, Status
```

**Checklist:**
- [ ] Role definition
- [ ] Source file (validated)
- [ ] Target file (UPDATE THIS)
- [ ] Validation summary provided
- [ ] Merge rules enumerated
- [ ] Metadata updates listed

**Post-merge:** Archive or delete temp file.

## Critical: Single Channel Principle

The subagent tool call is the **only** communication channel. Once spawned, the subagent cannot ask questions or request additional context.

**Must include in initial prompt:**
- Absolute file paths
- Working directory
- Read vs write file operations
- Entry points and search patterns
- Scope boundaries
- Expected deliverable format

**Insufficient context leads to:** wasted time, incorrect assumptions, incomplete findings.

## Claim Quality Standards

**Good claim characteristics:**
- **Atomic** - One specific fact, not compound
- **Verifiable** - Can be confirmed by reading source
- **Attributed** - Linked to specific source location
- **Dated** - When it was discovered

**Example:**
```markdown
**Claim:** `runTcInteractive` copies `icReaderEnv icxt` to `tcg_rdr_env`.
**Source:** `compiler/GHC/Tc/Module.hs:2675-2685`
**Evidence:**
```haskell
runTcInteractive :: HscEnv -> InteractiveContext -> TcM a -> IO (Messages, Maybe a)
runTcInteractive hsc_env icxt thing_inside = do
    initTcWithGbl hsc_env gbl_env emptyVarEnv thing_inside
  where
    gbl_env = updInteractiveContext env (icReaderEnv icxt) env
```
**Discovered:** 2024-03-28
```

## Handling Contradictions

When evidence contradicts existing claims:

1. **Report it** - Document both old claim and contradictory evidence
2. **Flag for review** - Add "CONTRADICTS: [old claim source]" to new finding
3. **Stop** - Don't resolve contradictions at subagent level
4. **Escalate** - Parent agent (user conversation) decides how to handle

The outer scope determines whether to:
- Keep both (different contexts/versions)
- Replace old with new
- Investigate further
- Mark both as uncertain

## Common Pitfalls

- **Following too many branches** - Stay within scope boundaries
- **Interface vs implementation** - Distinguish public API from internal details
- **Similar names** - Don't assume `Foo` in file A is same as `Foo` in file B
- **Cherry-picking evidence** - Report contradictions, don't hide them
- **Over-confidence** - Mark speculative claims as Low confidence

## Maintenance Rules

1. **Atomic commits** - Each session appends new claims
2. **No deletion** - Mark deprecated, don't remove
3. **Date everything** - Every claim gets discovered/updated date
4. **Link liberally** - Cross-reference related topics
5. **Validate periodically** - Run validation when status changes to Validated
