# Task 1: Architect Review and Cleanup Specification

## Role
**Architect**

## Objective
Review the systemf project structure and create a detailed specification for the cleanup operations. The Architect is responsible for making design decisions about entry points and specifying exact cleanup steps.

## Context Closure

**Project Location**: `/home/liu/Documents/bub/systemf/`

**Project Structure**:
```
systemf/
├── src/systemf/          # Main package
│   ├── core/            # AST, types, type checker
│   ├── surface/         # Lexer, parser, elaborator
│   ├── eval/            # Interpreter, REPL
│   └── utils/           # Location utilities
├── tests/               # Test suite (250+ tests)
├── examples/            # Example .sf files
├── demo.py              # 221-line comprehensive demo
├── main.py              # 6-line minimal placeholder
└── pyproject.toml       # Project configuration
```

**Cleanup Items to Review**:
1. Create .gitignore for Python project
2. Remove cache directories (.mypy_cache, .ruff_cache, .pytest_cache)
3. Remove __pycache__ directories (9 locations)
4. Remove build artifacts (src/systemf.egg-info/)
5. Design decision: Entry points (demo.py vs main.py)

**Entry Point Analysis**:
- `demo.py`: Comprehensive demo showing System F features (221 lines)
  - Imports: `systemf.surface.lexer`, `systemf.surface.parser`, etc.
  - Contains 8 demo sections with runnable examples
  - Has import path issues when run directly
- `main.py`: Minimal placeholder (6 lines)
  - Just prints "Hello from systemf!"
  - No actual functionality

**pyproject.toml Configuration**:
- Uses `src/` layout with `pythonpath = ["src"]` in pytest config
- No console_scripts entry points defined
- Standard Python project structure

## Your Task

1. **Review the project structure** to understand the codebase organization
2. **Design entry point strategy**:
   - Decide what to do with demo.py and main.py
   - Options to consider:
     a. Keep both (fix demo.py imports)
     b. Consolidate into one entry point
     c. Convert demo.py to a proper CLI command
     d. Move demo.py to scripts/ directory
     e. Delete main.py, fix and keep demo.py
   - Consider: demo.py has value as educational material and functional demo
3. **Specify .gitignore contents**:
   - Must cover: Python cache, build artifacts, IDE files, tool caches
   - Reference: Standard Python .gitignore patterns
4. **Specify cleanup commands**:
   - Exact commands to remove cache directories
   - Exact commands to remove __pycache__ directories
   - Exact commands to remove build artifacts

## Output Requirements

Create a specification document at `.workflow/cleanup-spec.md` with:

```markdown
# System F Cleanup Specification

## Entry Point Design Decision

**Decision**: [Your decision here]
**Rationale**: [Why you chose this approach]

**Implementation Details**:
- [Specific actions to take]

## .gitignore Specification

```
[Paste the complete .gitignore content here]
```

## Cleanup Commands Specification

### Cache Directories
```bash
# Commands to remove .mypy_cache, .ruff_cache, .pytest_cache
```

### Python Cache
```bash
# Commands to remove all __pycache__ directories
```

### Build Artifacts
```bash
# Commands to remove egg-info and other build artifacts
```

## Files to Create
1. [List of new files to create]

## Files to Modify
1. [List of files to modify]

## Files to Delete
1. [List of files to delete]
```

## Success Criteria
- [ ] Cleanup specification document created
- [ ] Entry point design decision documented with rationale
- [ ] Complete .gitignore content specified
- [ ] All cleanup commands documented
- [ ] File operations (create/modify/delete) enumerated

## Next Step
After completing this task, signal completion by updating kanban.md and returning control to the workflow system.

## Work Log

### 2026-02-25 09:00 Architecture Review

**Facts:**
- Reviewed project structure: Standard Python src/ layout with pyproject.toml
- Analyzed demo.py: 221-line comprehensive demo with 8 sections covering all System F features
- Analyzed main.py: 6-line placeholder with single print statement, zero functionality
- Verified cache directories exist: .mypy_cache (9.4M), .ruff_cache (28K), .pytest_cache (36K)
- Found 9 __pycache__ directories across src/ and tests/
- Found build artifact: src/systemf.egg-info/
- README documents proper CLI entry points: `python -m systemf check/run/repl`
- demo.py imports use absolute paths (systemf.surface.lexer, etc.) which work when package is installed

**Analysis:**
- Option A (Keep both): main.py serves no purpose, would create confusion
- Option B (Consolidate): Would lose the educational value of demo.py as a standalone script
- Option C (Convert to CLI): Over-engineering - demo is educational, not a tool
- Option D (Move to scripts/): Unnecessary - no scripts/ directory exists, root is fine
- Option E (Delete main.py, keep demo.py): Cleanest solution - removes dead code, preserves value

**Trade-offs considered:**
- Deleting main.py might surprise users expecting a simple entry point
- But: README clearly documents the proper CLI interface
- Keeping demo.py in root makes it discoverable
- demo.py import issues can be resolved with PYTHONPATH when needed

**Conclusion:**
- **Decision**: Delete main.py, keep demo.py as educational material
- **Rationale**: main.py is dead code; demo.py has significant educational value; README documents proper CLI; minimal changes needed
- **Action**: Create .gitignore, delete main.py, remove all cache/build artifacts
- **Specification created**: `.workflow/cleanup-spec.md` with complete instructions
