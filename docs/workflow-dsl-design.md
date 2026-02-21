# Workflow DSL: Design Document

## 1. Overview

A workflow DSL for structural thinking in agent systems. The core insight: flat linear context creates distraction. We need tiered, focused context through functional abstraction.

### 1.1 Core Philosophy

- **Focus through boundaries**: Each function declares exactly what it needs and produces
- **Explicit dataflow**: No hidden state creeping between steps
- **Failure as exploration**: REPL-style edit/resume/abstract cycle
- **Meta-circular**: LLMs can generate workflows that generate workflows
- **Full serializability**: All state externalized for pause/resume/debug

## 2. Core Concepts

### 2.1 The Primitive: LLM Call

The fundamental operation is a typed LLM interaction:

```
llm: Prompt × InputType × ToolSet → OutputType
```

Key properties:
- **Declared I/O**: Explicit input and output types with documentation
- **Tool scope**: Only imported tools are visible (controlled context)
- **Interactive output**: `set_output` with validation before acceptance
- **Failure modes**: Suspend for inspection, or auto-retry with expanded context

### 2.2 Functions and Composition

Functions compose by connecting outputs to inputs:

```
step1: Input → Intermediate
step2: Intermediate → Output

workflow: Input → Output = step1 → step2
```

This creates explicit dataflow graphs where information flows through typed channels.

### 2.3 Closures as Focus

A closure captures the focused context at a point in execution:

```
closure = (function, environment)
environment = {var1: ref1, var2: ref2, ...}
```

All environment references are externalized (working memory IDs, file references), making closures fully serializable.

### 2.4 Meta-Functions

LLMs can generate workflows dynamically:

```
generate_workflow: Context × Prompt → WorkflowText

# WorkflowText is parsed and validated by DSL compiler
# The generated workflow can then be executed
```

This creates hierarchical reasoning:
1. High-level planning (generates workflow)
2. Mid-level execution (runs generated steps)
3. Low-level primitives (LLM calls, tool use)

Depth is unbounded (engineering concern, not semantic limit).

## 3. First-Class Types

### 3.1 Core Primitives

| Type | Structure | Runtime Assistance |
|------|-----------|-------------------|
| `File` | path, metadata | Existence, permissions, size |
| `TextFile : File` | + encoding | Content preview |
| `MarkdownFile : TextFile` | + structure | Auto-extract: outline, section word counts |
| `CodeFile : TextFile` | + language | AST summary, imports, function count |
| `Tape` | tape_id | Entry count, tree structure |
| `Anchor` | (tape_id, entry_id, parent_ref) | Path-to-root validation |
| `Slice` | (from: Anchor, to: Anchor) | Path-connected validation, entry range |
| `Workflow` | AST | Structural validation, type checking |

### 3.2 Type Hierarchy

```
File
├── TextFile
│   ├── MarkdownFile    → outline, sections[], word-count
│   └── CodeFile        → language, AST-summary
├── BinaryFile
│   ├── ImageFile       → dimensions, format
│   └── PDFFile         → page count, toc
└── Directory           → listing, size, depth

Tape
├── Anchor (immutable pointer into tree)
└── Slice (path-connected anchor pair)
```

### 3.3 Automatic File Type Detection

File types are detected automatically—no manual annotation required:

- **Extension-based**: `.md` → MarkdownFile, `.py` → CodeFile
- **Content sniffing**: Shebang detection, magic bytes for binary files
- **Override**: Explicit type annotation when detection is ambiguous

This enables ergonomic workflows where agents work with files without knowing types in advance.

### 3.4 Automatic Context Enhancement

When typed values are passed to LLM calls, the runtime automatically enhances context based on file type.

#### MarkdownFile Enhancement

For markdown files, the runtime extracts structured metadata:

```
Input: MarkdownFile("/docs/api.md")

Auto-provided context:
- Path: /docs/api.md
- Size: 12KB
- Outline:
  * Overview (L1-L45): 150 words
  * Authentication (L47-L89): 400 words  
  * Endpoints (L91-L250): 1200 words [may skip if budget exceeded]
- Total: 1750 words across 3 sections
- Headers: [H1: API Reference, H2: Overview, H2: Auth, H2: Endpoints, H3: GET /users, ...]
```

**Extracted for each section:**
- Line number range (start-end)
- Word count
- Header level and title
- Nesting hierarchy

This enables budget-aware LLM interactions—LLM can decide to read specific sections based on word counts without loading full content.

#### Other File Types

- **CodeFile**: AST summary, imports, function signatures, complexity metrics
- **ImageFile**: Dimensions, format, color depth
- **PDFFile**: Page count, TOC extraction, text layer summary

### 3.4 Slice Path Semantics

Slices require anchors on the same path in the tape tree:

```
Tape Tree:
anchor:0 ──┬── anchor:1 ──┬── anchor:2
           │              └── anchor:3 (fork)
           └── anchor:4

Valid:   Slice(anchor:1, anchor:3)   # Same path: 1→2→3
Invalid: Slice(anchor:2, anchor:4)   # Different branches
```

Storage optimization: Each anchor stores `parent_ref`, enabling O(log n) path checks with skip lists.

## 4. Failure Model

### 4.1 REPL-Style Development

Traditional: Run → Fail → Abort  
REPL-style: Run → Check → Adjust → Capture

When LLM fails:
1. **Suspend**: Pause execution, preserve full state
2. **Inspect**: Examine context, intermediate results
3. **Adjust**: Add context, change tools, decompose step
4. **Resume**: Continue from suspension point
5. **Abstract**: If successful, capture as reusable pattern

### 4.2 Pattern Library

Successful recoveries are captured:
- **Micro**: Specific prompts that worked
- **Meso**: Recovery strategies ("needs more context" → expand scope)
- **Macro**: Common workflow templates

### 4.3 Granularity

Resumption can happen at any level:
- Single step (retry with different prompt)
- Sub-workflow (replace generated workflow)
- Parent workflow (change composition)

### 4.4 Context Boundary Crossing (Suspension with Continuation)

**Problem**: In nested structures (`llm → eval_workflow → llm`), sub-workflows can become context-starved while parent workflows retain broader context. Two approaches exist:

**Option A: Direct Parent Query (Rejected)**
```
sub_llm → "I need X" → parent_llm → "Here's X" → sub_llm continues
```
**Why rejected**: Breaks encapsulation, creates hidden dependencies, makes tracing/debugging difficult, violates tiered context principles, risks circular dependencies.

**Option B: Suspension with Continuation (Adopted)**
```
sub_llm → set_output(ContextRequest(
    need="API schema for /users endpoint",
    reason="Validating against OpenAPI spec",
    current_scope={...}  # Serialized checkpoint
))

# Parent receives as regular output, decides:
# - Provide context → resume with additional input
# - Delegate → resume with specialist result
# - Escalate → resume with broader context
# - Abort → workflow terminates

# Sub-workflow resumes via continuation
```

**Key Properties**:
- **Observable**: Context request is in tape trace, not hidden IPC
- **Interruptible**: Parent can introspect, modify, redirect
- **Serializable**: Exact continuation point captured via `set_output`
- **Composable**: Same pattern for human-in-the-loop, LLM-to-LLM, tool calls
- **CPS-style**: `set_output` is continuation-passing—the workflow doesn't die, it yields

**DSL Support**:
```python
workflow analyze_section:
    input: section_ref  # Reference, not content
    
    if section_ref.ambiguous:
        suspend ContextRequest(
            need="Which section?",
            options=outline.headers,
            checkpoint=partial_analysis
        )
    # Execution continues here after parent provides context
```

This extends REPL-style failure model: **any boundary crossing** (not just failures) triggers suspension/continuation pattern.

## 5. Syntax Design

### 5.1 Indentation-Based

Line-friendly syntax without delimiter matching:

```
workflow analyze-and-fix
  doc: """
    Analyze code for issues and propose fixes.
    Success: All bugs identified with line numbers.
    """
  
  import tools: read-file, semantic-search
  import llm: generate
  
  input file: CodeFile
    doc: "Python source file under 1000 lines"
  
  output result: AnalysisResult
  
  let analysis: AnalysisResult = llm
    prompt: "Analyze code for issues"
    input: file
    tools: [read-file, semantic-search]
  
  if analysis.has-issues
    let fix-plan: Workflow = generate
      prompt: "Create fix plan for: ${analysis.summary}"
      context: analysis.relevant-files
    
    let patches: PatchList = exec fix-plan
    
    return ok
      issues: analysis.issues
      patches: patches
  
  else
    return ok "No issues found"
```

### 5.2 Key Forms

| Form | Purpose |
|------|---------|
| `workflow name` | Define named workflow |
| `doc: "..."` | Attach documentation (LLM instructions) |
| `import` | Control visible tools/types |
| `input name: Type` | Declare input with type |
| `output name: Type` | Declare output with type |
| `let name: Type = expr` | Bind expression result |
| `llm prompt...` | Primitive LLM call |
| `generate prompt...` | Generate workflow dynamically |
| `exec workflow` | Execute workflow value |
| `if cond then... else...` | Conditional |
| `return ok/err...` | Return result |

### 5.3 Documentation Strategy

Documentation is **LLM instructions**, attached at multiple levels:

```
workflow level:    Overall goal, success criteria
input/output:      Type semantics, constraints  
steps:             Why this step exists
failure patterns:  Recovery hints
```

Runtime can inject relevant docs into LLM context automatically.

## 6. Integration with Bub

### 6.1 Leverages Existing Infrastructure

| Bub Feature | DSL Integration |
|-------------|-----------------|
| `handoff` | Creates workflow phase boundaries |
| `fork_session` | Spawns workflow steps as child sessions |
| `tape` | Persists execution state immutably |
| `anchors` | Typed as first-class `Anchor` type |
| `SessionGraph` | Tracks parent/child workflow relationships |
| `systemd-run` | Spawns workflow agents with proper isolation |

### 6.2 Serialization Model

All execution state externalized:

```json
{
  "workflow": "analyze-and-fix",
  "pc": 3,
  "env": {
    "file": "file://src/main.py",
    "analysis": "wm://abc123",
    "tape_anchor": "tape:xyz/pos:5"
  },
  "call_stack": [
    {"workflow": "parent", "step": 2},
    {"workflow": "analyze-and-fix", "step": 3}
  ]
}
```

### 6.3 Execution Flow

```
External Input
      ↓
Bus Router
      ↓
DSL Engine
      ↓
Workflow Graph
      ↓
AgentLoop (per step)
      ↓
ModelRunner
      ↓
Router (commands)
      ↓
Tool Execution
      ↓
State Checkpoint → Tape
```

## 7. Design Decisions

### 7.1 Made

- ✅ Syntax: Indentation-based (line-friendly)
- ✅ Depth: Unbounded (engineering concern)
- ✅ Representation: JSON for serialization
- ✅ Closures: Serializable via external references
- ✅ Dynamic: Workflows generate workflows
- ✅ Failure: REPL-style suspend/resume
- ✅ Types: Rich first-class type system
- ✅ Context Boundaries: Suspension with continuation (CPS via `set_output`)
- ✅ Parent-Child Communication: No direct queries—structured suspension messages only

### 7.2 Open Questions

1. **Sync vs Async**: Does parent wait for child workflow, or spawn-and-continue?
2. **Parallelism**: Explicit parallel blocks, or implicit dataflow?
3. **Type Checking**: Runtime validation, or compile-time?
4. **Error Propagation**: Bubble up, catch locally, or suspend globally?
5. **Context Request Patterns**: Standard library of common `suspend` reasons and parent responses?

## 8. Next Steps

1. Draft formal grammar for the DSL
2. Design type system (constraints, inheritance)
3. Specify validation rules for generated workflows
4. Prototype core execution engine
5. Define serialization format precisely

## 9. Summary

This DSL brings **functional programming discipline** to LLM workflows:
- **Explicit boundaries**: What goes in, what comes out
- **Composability**: Functions link via typed dataflow
- **Recoverability**: Full serialization enables suspend/resume
- **Evolvability**: REPL-style pattern capture
- **Meta-capability**: LLMs generate and reason about workflows

The result: structural thinking for agents, with focused context at every step.
