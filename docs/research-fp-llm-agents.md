# Functional Programming Researchers in LLM Agents

*Research notes on FP/PL researchers working on LLM agent systems, compiled 2026-02-22*

---

## Overview

This document catalogs functional programming and programming language researchers who have entered the LLM agent space. Their work shows converging architectural patterns with our Workflow DSL design.

**Key convergence:** Functional abstractions + explicit control flow = better agent systems

---

## Primary Researchers

### Erik Meijer — Neural Computers

**Key Papers:**
- **"Virtual Machinations: Using Large Language Models as Neural Computers"** (ACM Queue, July 2024)
- **"From Function Frustrations to Framework Flexibility"** (ACM Queue, Feb 2025)

**Core Concepts:**
- **Neural Computer**: LLMs are not just databases but "dynamic, end-user programmable neural computers"
- **Linguistic Bytecode**: Natural language as the instruction set for these neural VMs
- **Prolog-style programming**: Logic programming paradigms for controlling LLMs
- **Big-step semantics**: Uses formal semantics concepts to tame AI with lambda calculus
- **Function calling critique**: Current LLM tool calls are "brittle and inconsistent" — proposes indirection mechanisms

**Key Insight:**
> "Prompt once, run anywhere" — Paralleling Java's "Write once, run anywhere"

**Relevance to Our DSL:**
- Treats LLMs as computational substrate (like our meta-functions)
- Emphasizes formal semantics for reliability
- Proposes declarative control flow (Prolog-style)

---

### EnCompass / PAN — Probabilistic Angelic Nondeterminism

**Authors:** Zhening Li, Armando Solar-Lezama, Yisong Yue, Stephan Zheng

**Paper:** "EnCompass: Enhancing Agent Programming with Search Over Program Execution Paths" (NeurIPS 2025)

**Core Innovation:**
- **Probabilistic Angelic Nondeterminism (PAN)**: Separates agent workflow logic from inference-time search strategies
- **Disentanglement**: Current frameworks mix "what should the agent try" with "how should it search"
- **Python decorator**: `@encompass.compile` transforms agent workflows into searchable execution spaces

**Key Primitives:**
```python
@encompass.compile
def agent_workflow(...):
    branchpoint()        # Non-deterministic choice point
    record_score(...)    # Scoring for search guidance
    optional_return(...) # Early successful paths
    early_stop_search()  # Terminate search branch
```

**Relevance to Our DSL:**
- Direct parallel to our tiered context / closure approach
- Separates control flow (DSL) from execution strategy
- Uses explicit branching points (similar to our `suspend` with continuation)
- Separates workflow definition from search implementation

---

### Paul Chiusano — Unison as Agent Sandbox

**Background:** Creator of Unison language (content-addressed, immutable ASTs)

**Key Interests:**
- **Unison as "agent sandbox"**: Perfect for agent manipulation due to content-addressed code
- **LLM vs Code Control Flow**: When to use LLM reasoning vs deterministic code
- **Functional approach to agents**: Structured editing, type-safe code manipulation

**Key Statements:**
- "I think Unison has amazing potential as an agent sandbox!"
- "LLM vs Code Control Flow in AI Apps: Which to Choose?"

**Relevance to Our DSL:**
- Code-as-data philosophy aligns with our closure externalization
- Immutable ASTs enable safe agent code manipulation
- Type-safe structured editing matches our typed I/O boundaries

---

### Andrej Karpathy — Practical Agent Workflows

**Background:** Ex-OpenAI, ex-Tesla, founder of Eureka Labs

**Key Concepts:**
- **"Vibe Coding"** (Feb 2025): AI-native development paradigm
- **"Agentic Engineering"**: Humans as orchestrators, not coders
- **13-step workflow** for agent-driven coding
- **Backpropagation into harness**: Reflect on bugs → update CLAUDE.md files, hooks, SKILLs

**Workflow Steps (Simplified):**
1. Task decomposition
2. Context gathering
3. Implementation via agent
4. Deep code review
5. Reflect on bugs → backprop learnings into harness

**Impressive Claim:**
> Shipped ~200,000 lines of code with agents in 20 working days (80% agent, 20% manual)

**Relevance to Our DSL:**
- **REPL-style failure recovery**: Our suspension + inspect + adjust + resume pattern
- **Harness evolution**: Meta-functions generating improved workflows based on failures
- **Tiered context**: Different agents for different tasks (planner, executor, checker)

---

## Other Researchers (Less Relevant)

| Researcher | Focus Area | LLM/Agent Work? |
|------------|-----------|-----------------|
| **Edward Kmett** | Haskell internals, lenses, type systems | ❌ None found |
| **Simon Peyton Jones** | Excel/spreadsheet programming | ❌ Moved away from FP research |
| **Philip Wadler** | Monads, linear logic | ⚠️ Credited in EnCompass but not primary author |
| **Conor McBride** | Dependent types (Epigram, Agda) | ❌ No LLM crossover |
| **John Hughes** | QuickCheck, property-based testing | ❌ No agent-specific work |
| **Bartosz Milewski** | Category theory education | ❌ No LLM/agent work |
| **Oleg Kiselyov** | Effects systems, extensible effects | ⚠️ "Effects as Protocols" blog post touches on agents conceptually |

---

## Architectural Convergences

All active researchers share core principles with our Workflow DSL:

### 1. **Separation of Concerns**
- **Meijer**: Neural computer vs control logic
- **EnCompass**: Workflow logic vs search strategy
- **Our DSL**: Functions/closures vs execution engine

### 2. **Explicit Control Flow**
- **Meijer**: Big-step semantics, formal operational semantics
- **EnCompass**: Explicit `branchpoint()` markers
- **Our DSL**: Suspension with continuation, `set_output` as CPS

### 3. **Code-as-Data**
- **Chiusano**: Unison's content-addressed ASTs
- **EnCompass**: Workflows compiled to search spaces
- **Our DSL**: Closures as serializable, externalized objects

### 4. **Failure Recovery as First-Class**
- **Karpathy**: Backprop into harness, iterative refinement
- **Meijer**: Search space traversal with backtracking
- **Our DSL**: REPL-style suspend → inspect → adjust → resume

---

## Open Questions from Research

1. **How does Meijer's "linguistic bytecode" map to our type system?**
   - Natural language as universal interface vs our structured types

2. **Can we incorporate PAN-style angelic nondeterminism?**
   - `@encompass.compile` decorator equivalent in our DSL?
   - Integration with our meta-functions?

3. **Chiusano's Unison insights**
   - Content-addressing for workflow deduplication?
   - Structured editing for workflow manipulation?

4. **Karpathy's practical workflow patterns**
   - Which of his 13 steps map to DSL primitives?
   - How to formalize "backprop into harness"?

---

## References

**Meijer:**
- ACM Queue: "Virtual Machinations" (2024)
- ACM Queue: "From Function Frustrations" (2025)
- KotlinConf 2024 PDF: "Leveraging Linguistic Bytecode"

**EnCompass/PAN:**
- arXiv:2512.03571 (NeurIPS 2025)
- OpenReview: EnCompass forum

**Chiusano:**
- LinkedIn posts on Unison agent sandbox
- Unison language documentation

**Karpathy:**
- X/Twitter threads on agentic coding (Jan 2026)
- LinkedIn posts on workflow methodology

---

*Last updated: 2026-02-22*
