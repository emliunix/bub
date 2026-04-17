# Development Style Guidelines

## 1. All-or-Nothing Implementation

**Principle**: Do not implement features gradually or maintain backward compatibility during major refactors. The system works when complete, not before.

**Why**:
- Gradual migration adds complexity and technical debt
- Maintaining compatibility layers obscures the correct architecture
- "All at once" is often simpler than incremental changes
- Forces clear design decisions upfront

**Practice**:
- Use feature branches for major changes
- Delete old code immediately when replacing
- Don't keep compatibility shims "just in case"
- System may be broken during refactor - that's OK

**Example**:
```python
# DON'T: Keep old code working
class Elaborator:
    def elaborate(self, term, mode="new"):  # Compatibility parameter
        if mode == "old":
            return self._old_elaborate(term)
        else:
            return self._new_elaborate(term)

# DO: Replace entirely
class Elaborator:
    def elaborate(self, term):  # Only new implementation
        return self._elaborate(term)
```

## 2. Design Big to Small, Implement Small to Big

**Principle**: Architecture flows top-down; implementation flows bottom-up.

**Design Phase** (Big → Small):
1. System architecture and boundaries
2. Module interfaces and contracts
3. Data flow and transformations
4. Individual function signatures

**Implementation Phase** (Small → Big):
1. Core data structures and utilities
2. Leaf functions (no dependencies)
3. Internal modules (depend on leaves)
4. Public API (depends on everything)

**Why**:
- Prevents building on unstable foundations
- Tests can verify small units before integration
- Easier to debug when components are verified independently
- Natural dependency order respects the architecture

**Example**:
```
Design order:    Parser → AST → Elaborator → Type Checker → Evaluator
Implementation:  AST → Parser → Type Checker → Elaborator → Evaluator
```

## 3. Systematic Test Failure Analysis

**Principle**: When tests fail, analyze by component in reverse dependency order.

**Method**:
1. **Identify components** in the dependency tree:
   ```
   Lexer → Parser → Elaborator → Type Checker → Integration Tests
   ```

2. **Check in reverse order** (leaf to root):
   - Level 1: Lexer (foundational)
   - Level 2: Parser (depends on Lexer)
   - Level 3: Elaborator (depends on Parser)
   - Level 4: Type Checker (depends on Elaborator)
   - Level 5: Integration Tests (depends on all)

3. **Never fix Level N+1 when Level N is broken**
   - If Lexer fails, don't debug Parser
   - If Parser fails, don't debug Elaborator
   - Fix foundational issues first

**Why**:
- Higher-level failures often cascade from lower-level bugs
- Fixing leaves first prevents wasted debugging effort
- Clear priority: foundation before superstructure

**Example**:
```python
# Integration test fails with TypeError in elaborator
# 1. Check Lexer tests first - PASS
# 2. Check Parser tests - PASS  
# 3. Check Elaborator tests - FAIL (found the issue!)
# 4. Fix elaborator, then re-run integration tests
```

## 4. Overwrite Style Editing

For files requiring substantial changes (>20% of lines or complex refactoring):

1. **Architecture design first** - Document the new structure.
2. **Read entire file** - Understand all components.
3. **Create outline** - List all classes, methods, and their purposes.
4. **Use LSP** - Let language server help identify references.
5. **Draft new outline** - According to the new architecture.
6. **Generate complete new file** - Write from scratch using the outline.
7. **Review with diff** - Compare old vs new (`diff -u old.py new.py`).
8. **Fix type/lint errors** - Before replacing.
9. **Overwrite** - Replace the old file with the new file.

Anti-pattern: Incremental small edits on complex files (creates inconsistent state).
