---
role: Implementor
expertise: ['Lexer Design', 'Python']
skills: ['python-uv']
type: design
phase: design
priority: high
dependencies: []
refers: [1-kanban-systemf-parser-indentation.md]
kanban: tasks/1-kanban-systemf-parser-indentation.md
created: 2026-02-25T14:40:00.000000
---

# Design - Indentation-Aware Lexer

## Overview

Design for modifying the System F lexer to track indentation levels and emit INDENT/DEDENT tokens, similar to Python's approach. This enables the parser to use indentation-based block structure instead of declaration boundary heuristics.

## Current State Analysis

**Existing Lexer Location:** `systemf/src/systemf/surface/lexer.py`

**Current Characteristics:**
- Simple regex-based tokenizer
- Token types: Keywords, operators, delimiters, identifiers, constructors, numbers
- Skips WHITESPACE and COMMENT tokens entirely
- No indentation awareness

## Design Document

### 1. Token Type Definitions

#### New Token Types

```python
# Add to Token enum/type definitions
INDENT = "INDENT"      # Enter new indentation level
DEDENT = "DEDENT"      # Exit indentation level
NEWLINE = "NEWLINE"    # Line break (needed for indentation tracking)
```

#### Token Value for Indentation Tokens

```python
@dataclass(frozen=True)
class Token:
    type: str
    value: str
    location: Location
    indent_level: int = 0  # Track indentation level (for INDENT/DEDENT)
```

**Alternative approach:** Store indent level only for INDENT/DEDENT tokens:
- `INDENT` token value = number of spaces (e.g., "4")
- `DEDENT` token value = number of dedent levels (e.g., "2" for two dedents)

### 2. Lexer State Extension

```python
class Lexer:
    def __init__(self, source: str, filename: str = "<stdin>"):
        # ... existing initialization ...
        
        # Indentation tracking state
        self.indent_stack: list[int] = [0]  # Stack of indentation levels, starts at 0
        self.indent_char: Optional[str] = None  # ' ' or '\t', must be consistent
        self.at_line_start: bool = True  # Track if we're at start of logical line
        self.pending_tokens: list[Token] = []  # Buffer for multi-token generation (DEDENTs)
```

### 3. Indentation Tracking Algorithm

#### Core Algorithm (Pseudo-code)

```
function tokenize():
    while not at end of source:
        if at_line_start:
            process_indentation()
        
        if pending_tokens not empty:
            yield pending_tokens.pop(0)
            continue
        
        match = regex_match_at_current_position()
        
        if token_type is NEWLINE:
            at_line_start = True
            yield token
        elif token_type is COMMENT:
            # Check if comment is at line start (determines if indentation follows)
            if at_line_start:
                # Still at line start after comment
                pass
            yield token
        elif token_type is WHITESPACE:
            if at_line_start:
                # This is indentation whitespace - already handled in process_indentation
                pass
            else:
                # Inline whitespace - skip or preserve based on needs
                pass
        else:
            at_line_start = False
            yield token
    
    # EOF handling - dedent to level 0
    while len(indent_stack) > 1:
        emit_dedent()
    
    yield EOF token

function process_indentation():
    # Capture leading whitespace
    indent_match = regex_match(r"^[ \t]*", current_position)
    indent_str = indent_match.group()
    
    # Calculate indentation level in spaces
    if indent_char is None and indent_str:
        indent_char = first character of indent_str
    
    if mixed_tabs_and_spaces(indent_str):
        raise LexerError("Mixed tabs and spaces in indentation")
    
    indent_level = len(indent_str)
    if indent_char == '\t':
        indent_level = len(indent_str) * 4  # Or use tab width setting
    
    current_level = top of indent_stack
    
    if indent_level > current_level:
        # Indent
        push indent_level onto indent_stack
        emit_indent_token(indent_level)
    elif indent_level < current_level:
        # Dedent - may need multiple DEDENTs
        while indent_level < top of indent_stack:
            pop from indent_stack
            emit_dedent_token()
        
        if indent_level != top of indent_stack:
            raise LexerError(f"Inconsistent dedent: expected {top of indent_stack}, got {indent_level}")
    
    # Skip the whitespace characters (they're consumed)
    advance_position(len(indent_str))
    at_line_start = False
```

### 4. Token Pattern Modifications

#### Updated TOKEN_PATTERNS

```python
TOKEN_PATTERNS = [
    # Line endings (NEWLINE must come before WHITESPACE)
    ("NEWLINE", r"\n"),
    
    # Comments (handle at line start)
    ("COMMENT", r"--[^\n]*"),
    
    # Inline whitespace (not at line start)
    ("WHITESPACE", r"[ \t]+"),
    
    # ... rest of patterns unchanged ...
]
```

**Key Change:** Split newline handling from general whitespace to track line boundaries.

### 5. Edge Cases

#### 5.1 Empty Lines

**Rule:** Empty lines (containing only whitespace or comments) should be ignored for indentation purposes.

```python
function is_blank_line():
    # Check if line contains only whitespace and/or comments
    match = regex_match(r"^[ \t]*(?:--[^\n]*)?$", from_current_position)
    return match is not None

function process_indentation():
    if is_blank_line():
        # Skip to end of line, keep at_line_start = True
        advance_to_next_line()
        return
```

#### 5.2 Comments at Line Start

**Rule:** Lines starting with comments should not trigger indentation processing on subsequent lines.

```
-- This is a comment
  let x = 1    -- This line has 2-space indent
```

The comment line doesn't affect indentation tracking.

#### 5.3 Mixed Tabs and Spaces

**Rule:** Each file must use consistent indentation characters (all spaces or all tabs).

```python
function validate_indent_consistency(indent_str: str):
    if indent_char is None:
        if ' ' in indent_str:
            indent_char = ' '
        elif '\t' in indent_str:
            indent_char = '\t'
    
    if indent_char == ' ' and '\t' in indent_str:
        raise LexerError("Tab character in space-indented file", location)
    if indent_char == '\t' and ' ' in indent_str:
        raise LexerError("Space character in tab-indented file", location)
```

#### 5.4 Multiple DEDENTs

**Rule:** When dedenting multiple levels, emit multiple DEDENT tokens in sequence.

```
level 0: def foo:
level 4:     x = 1
level 8:         y = 2
level 4:     z = 3   <-- Emit 1 DEDENT (8→4)
level 0: w = 4       <-- Emit 2 DEDENTs (4→0)
```

#### 5.5 EOF Handling

**Rule:** At EOF, automatically dedent to level 0, emitting DEDENT tokens as needed.

```python
# At end of tokenize():
while len(indent_stack) > 1:
    emit_dedent_token()
```

#### 5.6 Inconsistent Dedent

**Rule:** Dedent must return to a previously seen indentation level.

```
level 0: def foo:
level 4:     x = 1
level 8:         y = 2
level 6:     z = 3   <-- ERROR: level 6 was never an indent level!
```

### 6. Interface Design

#### Modified Lexer Class Interface

```python
class Lexer:
    """Indentation-aware tokenizer for System F surface language."""
    
    def __init__(self, source: str, filename: str = "<stdin>", tab_width: int = 4):
        """
        Args:
            source: The source code to tokenize
            filename: Name of the source file (for error messages)
            tab_width: Number of spaces to treat a tab as (default: 4)
        """
    
    def tokenize(self) -> list[Token]:
        """
        Convert source code to token stream with INDENT/DEDENT tokens.
        
        Returns:
            List of tokens including NEWLINE, INDENT, and DEDENT
        
        Raises:
            LexerError: On invalid indentation or unexpected characters
        """
```

#### Backward Compatibility

**Option A:** Keep existing `lex()` function signature, add new `lex_with_indent()`:

```python
def lex(source: str, filename: str = "<stdin>") -> list[Token]:
    """Legacy tokenizer without indentation awareness."""
    return Lexer(source, filename).tokenize_legacy()

def lex_with_indent(source: str, filename: str = "<stdin>") -> list[Token]:
    """New tokenizer with INDENT/DEDENT tokens."""
    return Lexer(source, filename).tokenize()
```

**Option B:** Add parameter to control behavior:

```python
def lex(source: str, filename: str = "<stdin>", track_indent: bool = True) -> list[Token]:
    """Tokenizer with optional indentation tracking."""
    lexer = Lexer(source, filename)
    if track_indent:
        return lexer.tokenize()
    return lexer.tokenize_legacy()
```

**Recommendation:** Option B for gradual migration.

### 7. Token Stream Examples

#### Example 1: Simple Indentation

**Input:**
```
let x = 1
    y = 2
```

**Token Stream:**
```
LET, IDENT("x"), EQUALS, NUMBER("1"), NEWLINE,
INDENT(4), IDENT("y"), EQUALS, NUMBER("2"), NEWLINE,
DEDENT, EOF
```

#### Example 2: Nested Indentation

**Input:**
```
data Option a
    = Some a
    | None
```

**Token Stream:**
```
DATA, CONSTRUCTOR("Option"), IDENT("a"), NEWLINE,
INDENT(4), BAR, CONSTRUCTOR("Some"), IDENT("a"), NEWLINE,
BAR, CONSTRUCTOR("None"), NEWLINE,
DEDENT, EOF
```

#### Example 3: Multiple DEDENTs

**Input:**
```
let x = 1
    y = 2
        z = 3
    w = 4
```

**Token Stream:**
```
LET, IDENT("x"), EQUALS, NUMBER("1"), NEWLINE,
INDENT(4), IDENT("y"), EQUALS, NUMBER("2"), NEWLINE,
INDENT(8), IDENT("z"), EQUALS, NUMBER("3"), NEWLINE,
DEDENT, IDENT("w"), EQUALS, NUMBER("4"), NEWLINE,
DEDENT, EOF
```

## Test Contracts

### Required Test Cases

#### TC-01: Basic Indentation Increase
**Input:** `let x = 1\n    y = 2`
**Expected:** Contains INDENT token after NEWLINE
**Verify:** `assert any(t.type == 'INDENT' for t in tokens)`

#### TC-02: Basic Indentation Decrease
**Input:** `let x = 1\n    y = 2\nz = 3`
**Expected:** Contains DEDENT token before `z`
**Verify:** Token sequence shows DEDENT between `NUMBER("2")` and `IDENT("z")`

#### TC-03: Multiple DEDENTs
**Input:** 
```
let x = 1
    y = 2
        z = 3
w = 4
```
**Expected:** Two consecutive DEDENT tokens before `w`
**Verify:** `dedents = [t for t in tokens if t.type == 'DEDENT']; assert len(dedents) == 2`

#### TC-04: EOF DEDENT
**Input:** `let x = 1\n    y = 2` (no trailing newline)
**Expected:** DEDENT emitted before EOF
**Verify:** Last two tokens are DEDENT, EOF

#### TC-05: Empty Lines Ignored
**Input:**
```
let x = 1

    y = 2
```
**Expected:** No extra INDENT/DEDENT for empty line
**Verify:** Only one INDENT token in output

#### TC-06: Comment Lines Ignored
**Input:**
```
let x = 1
-- comment
    y = 2
```
**Expected:** Comment doesn't affect indentation
**Verify:** Single INDENT before `y`

#### TC-07: Mixed Tabs and Spaces Error
**Input:** `let x = 1\n  \t y = 2`
**Expected:** LexerError raised
**Verify:** `with pytest.raises(LexerError): lex_with_indent(input)`

#### TC-08: Inconsistent Dedent Error
**Input:**
```
let x = 1
    y = 2
      z = 3
```
**Expected:** LexerError (level 6 was never established)
**Verify:** Error message mentions "inconsistent dedent"

#### TC-09: No Indentation (Backward Compatibility)
**Input:** `let x = 1`
**Expected:** Works without any INDENT/DEDENT tokens
**Verify:** No INDENT or DEDENT in token list

#### TC-10: Complex Nested Structure
**Input:**
```
data Tree a
    = Node (Tree a) (Tree a)
    | Leaf a

let x = case t of
    Node l r -> 1
    Leaf a -> 2
```
**Expected:** Proper INDENT/DEDENT sequences for both data and let
**Verify:** Token count and sequence matches expected structure

### Test File Location

Tests should be added to:
- `systemf/tests/test_lexer.py` (or create `test_lexer_indentation.py`)

### Test Helper Functions

```python
def assert_token_sequence(tokens: list[Token], expected_types: list[str]):
    """Assert token types match expected sequence."""
    actual = [t.type for t in tokens]
    assert actual == expected_types, f"Expected {expected_types}, got {actual}"

def assert_indent_levels(tokens: list[Token], expected_levels: list[int]):
    """Assert INDENT/DEDENT tokens have correct levels."""
    indent_tokens = [t for t in tokens if t.type in ('INDENT', 'DEDENT')]
    actual = [t.indent_level for t in indent_tokens]
    assert actual == expected_levels
```

## Work Log

### Design Decisions

#### Decision 1: NEWLINE Token
**Choice:** Emit explicit NEWLINE tokens instead of skipping whitespace entirely.
**Rationale:** Parser needs to know when indentation changes can occur. Newlines are semantic.
**Alternative considered:** Track line starts internally, don't emit NEWLINE tokens.
**Rejected because:** Parser combinators (parsy) work better with explicit tokens.

#### Decision 2: Indentation Level Storage
**Choice:** Store raw indentation level (number of spaces) in token, not logical level.
**Rationale:** Provides more information for error messages and debugging.
**Alternative considered:** Store logical level (1, 2, 3) instead of spaces (4, 8, 12).
**Trade-off:** Logical levels are cleaner but spaces help with error reporting.

#### Decision 3: Tab Width
**Choice:** Default tab width of 4 spaces, configurable via constructor.
**Rationale:** Industry standard, but should be adjustable.
**Alternative considered:** Require spaces only, no tabs.
**Rejected because:** Some users prefer tabs, should support both (consistently).

#### Decision 4: DEDENT Value
**Choice:** Each DEDENT token represents one level, emit multiple for multi-level dedent.
**Rationale:** Matches Python's approach, simpler parser logic.
**Alternative considered:** Single DEDENT token with count of levels to dedent.
**Rejected because:** Complicates parser - must handle variable number of levels.

#### Decision 5: Comment Handling
**Choice:** Comments don't affect indentation tracking.
**Rationale:** Comments are not code, shouldn't change block structure.
**Edge case:** What about:
```
let x = 1
    -- indented comment
    y = 2
```
**Resolution:** Still ignore for indentation. The code determines structure.

#### Decision 6: Backward Compatibility
**Choice:** Add `track_indent` parameter with default behavior TBD.
**Rationale:** Allows gradual migration of existing code.
**Migration plan:**
1. Implement lexer with both modes
2. Parser starts using indentation-aware lexer
3. Eventually deprecate non-indent mode

### Open Questions for Implementor

1. **Tab width:** Should it be a global constant, lexer parameter, or source directive?
2. **Indentation in string literals:** Should we handle multi-line strings specially?
3. **Error recovery:** Should lexer try to continue after indentation errors?
4. **Token representation:** Should NEWLINE be a token type or handled specially?

### Assumptions

1. **Source encoding:** UTF-8, no special handling for other encodings.
2. **Line endings:** `\n` (Unix). `\r\n` (Windows) normalized to `\n`.
3. **Maximum indentation:** Limited by Python list size (practically unlimited).
4. **Indentation must increase:** Cannot have INDENT of 0 spaces from level 0.

## Success Criteria

- [ ] Design reviewed and approved
- [ ] All test contracts defined above are implementable
- [ ] Edge cases documented and handled in design
- [ ] Interface is clear and backward-compatible
- [ ] Implementor has all information needed to proceed

DONE
