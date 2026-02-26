---
role: Implementor
expertise: ['Python', 'Parser Design', 'AST Design', 'FFI Implementation']
skills: ['python-project', 'testing']
type: implement
priority: high
state: todo
dependencies: []
refers: []
kanban: tasks/16-kanban-systemf-language-implementation.md
created: 2026-02-26T12:20:00.000000
---

# Task: Implement Tool Calls as SystemF Functions

## Context
Following the completion of Task 27 (LLM FFI pragma syntax), the foundation for LLM FFI is in place. Now implementing Task 6 from original requirements: add tool calls as systemf functions in the language.

Tool calls will allow SystemF code to invoke external tools (like LLM APIs, file operations, etc.) as native functions within the language. The pragma syntax from Task 27 (`{-# LLM key=value #-}`) provides the configuration mechanism for these tool calls.

## Files
- `src/surface/ast.py` - Add tool call AST node types
- `src/surface/parser.py` - Add tool call parsing logic
- `src/surface/elaborator.py` - Handle tool call elaboration to core
- `src/core/ast.py` - Add core representation for tool calls
- `src/interpreter/` - Add tool call execution logic
- `tests/test_surface/test_parser.py` - Add tool call parsing tests
- `tests/test_interpreter/` - Add tool call execution tests

## Description
Implement tool calls as first-class functions in SystemF:

1. **Surface AST changes:**
   - Create `SurfaceToolCall` dataclass to represent tool invocations
   - Support tool name, arguments, and pragma configuration
   - Allow tool calls in expression contexts

2. **Parser changes:**
   - Add syntax for tool calls (e.g., `tool_name(arg1, arg2)` or `@tool_name arg`)
   - Parse tool calls within expressions
   - Associate pragmas with tool call declarations

3. **Elaborator changes:**
   - Transform surface tool calls to core representation
   - Validate tool signatures against declarations
   - Handle pragma-configured tool parameters

4. **Interpreter changes:**
   - Execute tool calls at runtime
   - Support built-in tools (llm_call, file_read, etc.)
   - Handle tool results and errors

5. **Tests:**
   - Test basic tool call parsing
   - Test tool calls with arguments
   - Test pragma-configured tool calls
   - Test tool call execution in interpreter
   - Test error handling for undefined tools

## Work Log
<!-- Work logs will be appended here -->

### [2026-02-26 12:27:35] Implementation Complete

**Facts:**
Tool calls implemented as SystemF functions with pragma integration

**Analysis:**
-

**Conclusion:**
Status: ok

---

### [2026-02-26 12:28:07] Implementation Complete

**Facts:**
**F:**
- Added TOOL token to lexer (`systemf/src/systemf/surface/lexer.py`)
- Created `SurfaceToolCall` AST node in surface language (`systemf/src/systemf/surface/ast.py`)
- Created `ToolCall` AST node in core language (`systemf/src/systemf/core/ast.py`)
- Implemented tool call parser supporting `@tool_name arg1 arg2 ...` syntax (`systemf/src/systemf/surface/parser.py`)
- Added tool call elaboration from surface to core (`systemf/src/systemf/surface/elaborator.py`)
- Created tool registry infrastructure (`systemf/src/systemf/eval/tools.py`):
  - `Tool` abstract base class for defining tools
  - `ToolRegistry` for managing tool registration and lookup
  - Built-in tools: `IdentityTool`, `EchoTool`, `LLMCallTool`
  - Global registry with `get_tool_registry()` and `reset_tool_registry()`
- Added `VToolResult` value type for representing tool results (`systemf/src/systemf/eval/value.py`)
- Implemented tool call evaluation in interpreter (`systemf/src/systemf/eval/machine.py`)
- Updated eval module exports (`systemf/src/systemf/eval/__init__.py`)
- Created comprehensive test suite (`systemf/tests/test_eval/test_tool_calls.py`):
  - 25 tests covering parsing, elaboration, registry, execution, and integration
  - Tests for built-in tools and custom tool registration
  - Tests for error handling (undefined tools, wrong arguments)

**Files Modified:**
- `systemf/src/systemf/surface/lexer.py` - Added TOOL token
- `systemf/src/systemf/surface/ast.py` - Added SurfaceToolCall node
- `systemf/src/systemf/surface/parser.py` - Added tool call parsing
- `systemf/src/systemf/surface/elaborator.py` - Added tool call elaboration
- `systemf/src/systemf/core/ast.py` - Added ToolCall node and updated TermRepr
- `systemf/src/systemf/eval/value.py` - Added VToolResult value type
- `systemf/src/systemf/eval/machine.py` - Added tool call evaluation
- `systemf/src/systemf/eval/__init__.py` - Exported new modules

**Files Created:**
- `systemf/src/systemf/eval/tools.py` - Tool registry infrastructure
- `systemf/tests/test_eval/test_tool_calls.py` - Test suite (25 tests)

**Test Results:**
- All 336 tests pass (311 original + 25 new)

**Analysis:**
**A:**
- **Design Decision**: Tool calls use `@tool_name` syntax, building on the existing pragma infrastructure
  - The `@` symbol was already used for type application, but in expression context it's unambiguous
  - Parentheses can be used to disambiguate: `(@tool_name)` vs `@Type`
  
- **Design Decision**: Tool registry is global but resettable for testing
  - Global registry ensures tools are available throughout the program
  - `reset_tool_registry()` allows clean test isolation
  
- **Design Decision**: Tool results are represented as `VToolResult` values
  - Contains success/failure status for error handling
  - Tool-specific result data is stored generically
  - Allows for future extension with metadata (execution time, tool version, etc.)

- **Integration**: Tool calls integrate seamlessly with existing FFI infrastructure
  - Can be used with pragma declarations: `{-# TOOL name="llm_call" #-}`
  - Work in any expression context: let bindings, lambda bodies, function arguments
  - Follow same elaboration pattern as other surface constructs

**Conclusion:**
**C:**
Status: ok

The implementation successfully adds tool calls as first-class SystemF functions:

1. **Syntax**: `@tool_name arg1 arg2 ...` for invoking tools
2. **Registry**: Extensible tool registration system with built-in tools
3. **Execution**: Tools execute at evaluation time through the interpreter
4. **Integration**: Works with existing pragma syntax and FFI infrastructure

**Example Usage:**
```systemf
-- Simple tool call
@identity 42

-- Tool call in let binding
let result = @echo Hello World
  result

-- Tool call in lambda
\prompt -> @llm_call prompt

-- Pragma-configured tool (for future LLM integration)
{-# TOOL name="search", api_key="..." #-}
search_query : String -> String = \q -> @search q
```

**No blockers or follow-up tasks required.** All requirements from the task specification have been implemented and tested.

---

