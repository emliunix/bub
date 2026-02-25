"""Lexer for surface language.

Indentation-aware tokenizer for System F surface syntax.
Uses stack-based indentation tracking to emit INDENT/DEDENT tokens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from systemf.utils.location import Location


@dataclass(frozen=True)
class Token:
    """A lexical token with type, value, and location."""

    type: str
    value: str
    location: Location

    def __str__(self) -> str:
        return f"{self.type}({self.value!r})"

    def __repr__(self) -> str:
        return f"Token({self.type!r}, {self.value!r}, {self.location})"


class LexerError(Exception):
    """Error during lexical analysis."""

    def __init__(self, message: str, location: Location):
        super().__init__(f"{location}: {message}")
        self.location = location


class Lexer:
    """Indentation-aware tokenizer for System F surface language.

    Tokenizes input into a stream of tokens for the parser.
    Tracks indentation levels and emits INDENT/DEDENT tokens.

    Indentation Algorithm:
    - Stack starts with [0] representing outermost level (column 0)
    - Track column position at start of each logical line
    - Skip blank lines (whitespace/comments only) for indentation tracking
    - Push current column on INDENT, pop on DEDENT
    - Emit multiple DEDENTs for large indentation drops
    - Error on inconsistent indentation or mixed tabs/spaces
    """

    # Token specifications as regex patterns
    TOKEN_PATTERNS = [
        # Whitespace (no newlines - handled separately for indentation tracking)
        ("WHITESPACE", r"[ \t]+"),
        ("NEWLINE", r"\n|\r\n?"),
        ("COMMENT", r"--[^\n]*"),
        # Keywords
        ("DATA", r"\bdata\b"),
        ("LET", r"\blet\b"),
        ("IN", r"\bin\b"),
        ("CASE", r"\bcase\b"),
        ("OF", r"\bof\b"),
        ("FORALL", r"\bforall\b"),
        ("TYPE", r"\btype\b"),
        # Multi-character operators
        ("ARROW", r"-\u003e"),
        ("DARROW", r"=>"),
        ("LAMBDA", r"\\"),  # Backslash for lambda
        ("TYPELAMBDA", r"/\\"),  # /\ for type lambda (Λ)
        # Single-character operators
        ("EQUALS", r"="),
        ("COLON", r":"),
        ("BAR", r"\|"),
        ("AT", r"@"),
        ("DOT", r"\."),
        # Delimiters
        ("LPAREN", r"\("),
        ("RPAREN", r"\)"),
        ("LBRACKET", r"\["),
        ("RBRACKET", r"\]"),
        ("LBRACE", r"\{"),
        ("RBRACE", r"\}"),
        ("COMMA", r","),
        # Identifiers and constructors
        ("CONSTRUCTOR", r"[A-Z][a-zA-Z0-9_]*"),  # Type/constructor names start with uppercase
        ("IDENT", r"[a-z_][a-zA-Z0-9_]*"),  # Variables start with lowercase
        # Numbers (for convenience in tests)
        ("NUMBER", r"[0-9]+"),
    ]

    def __init__(self, source: str, filename: str = "<stdin>", skip_indent: bool = True):
        """Initialize lexer with source code.

        Args:
            source: The source code to tokenize
            filename: Name of the source file (for error messages)
            skip_indent: If True, skip INDENT/DEDENT tokens for backward compatibility
        """
        self.source = source
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: list[Token] = []
        self._skip_indent = skip_indent

        # Indentation tracking
        self._indent_stack: list[int] = [0]  # Stack of indentation levels, starts at column 0
        self._at_line_start = True  # Whether we're at the start of a logical line
        self._line_start_column = 1  # Column where current logical line started

        # Compile regex for efficiency
        self._pattern = re.compile(
            "|".join(f"(?P<{name}>{pattern})" for name, pattern in self.TOKEN_PATTERNS)
        )

        # Pattern to detect leading whitespace on a line (match at current position, not start of string)
        self._leading_ws_pattern = re.compile(r"[ \t]*")

    def tokenize(self) -> list[Token]:
        """Convert source code to token stream.

        Returns:
            List of tokens including INDENT/DEDENT for indentation changes

        Raises:
            LexerError: If unexpected character encountered or indentation error
        """
        self.tokens = []
        self._indent_stack = [0]
        self._at_line_start = True
        self._line_start_column = 1

        while self.pos < len(self.source):
            # At line start: check indentation before processing tokens
            if self._at_line_start:
                is_blank = self._process_indentation()
                if is_blank:
                    # Skip blank lines (continue to next iteration)
                    continue

            match = self._pattern.match(self.source, self.pos)

            if not match:
                # Unknown character
                char = self.source[self.pos]
                loc = Location(self.line, self.column, self.filename)
                raise LexerError(f"Unexpected character: {char!r}", loc)

            token_type = match.lastgroup
            if token_type is None:
                char = self.source[self.pos]
                loc = Location(self.line, self.column, self.filename)
                raise LexerError(f"Unexpected character: {char!r}", loc)
            value = match.group()
            start_loc = Location(self.line, self.column, self.filename)

            # Update position
            self._advance(value)

            # Handle newlines: mark that next token starts a new line
            if token_type == "NEWLINE":
                self._at_line_start = True
                self._line_start_column = self.column
                continue  # Skip newline tokens

            # Skip comments and other whitespace
            if token_type in ("WHITESPACE", "COMMENT"):
                continue

            # We found a non-whitespace, non-comment token
            self._at_line_start = False
            self.tokens.append(Token(token_type, value, start_loc))

        # End of file: emit DEDENTs to close all open blocks, then EOF
        self._emit_dedents_to_level(0)
        self.tokens.append(Token("EOF", "", Location(self.line, self.column, self.filename)))

        # Filter out INDENT/DEDENT tokens if backward compatibility mode is enabled
        if self._skip_indent:
            self.tokens = [t for t in self.tokens if t.type not in ("INDENT", "DEDENT")]

        return self.tokens

    def _process_indentation(self) -> bool:
        """Process indentation at the start of a logical line.

        Measures leading whitespace and emits INDENT/DEDENT tokens as needed.
        Skips leading whitespace after processing.

        Returns:
            True if this is a blank line (should be skipped), False otherwise
        """
        # Measure leading whitespace on this line (at current position)
        ws_match = self._leading_ws_pattern.match(self.source, self.pos)
        if not ws_match:
            leading_ws = ""
        else:
            leading_ws = ws_match.group()

        # Peek ahead to see if this line is blank (only whitespace/comments)
        peek_pos = self.pos + len(leading_ws)
        is_blank = self._is_blank_line(peek_pos)

        # Check for mixed tabs and spaces (but only on non-blank lines)
        if not is_blank and "\t" in leading_ws and " " in leading_ws:
            loc = Location(self.line, self.column, self.filename)
            raise LexerError("Mixed tabs and spaces in indentation", loc)

        if is_blank:
            # Blank line - skip the entire line including newline
            self._skip_to_end_of_line()
            return True

        # Not a blank line - process indentation
        current_column = len(leading_ws) + 1  # 1-based column
        current_indent = current_column - 1  # 0-based indentation level
        last_indent = self._indent_stack[-1]

        if current_indent > last_indent:
            # Indentation increased - emit INDENT
            indent_loc = Location(self.line, current_column, self.filename)
            self.tokens.append(Token("INDENT", str(current_indent), indent_loc))
            self._indent_stack.append(current_indent)
        elif current_indent < last_indent:
            # Indentation decreased - emit DEDENTs
            self._emit_dedents_to_level(current_indent)

        # Skip the leading whitespace we just measured
        self._advance(leading_ws)

        # Mark that we've processed indentation for this line
        self._at_line_start = False
        return False

    def _skip_to_end_of_line(self) -> None:
        """Skip from current position to end of line (including newline)."""
        while self.pos < len(self.source):
            char = self.source[self.pos]
            self.pos += 1
            if char == "\n":
                self.line += 1
                self.column = 1
                break
            else:
                self.column += 1

    def _emit_dedents_to_level(self, target_level: int) -> None:
        """Emit DEDENT tokens until we reach the target indentation level.

        Args:
            target_level: Target indentation level (0-based column)

        Raises:
            LexerError: If target level doesn't match any level in stack
        """
        loc = Location(self.line, self.column, self.filename)

        while self._indent_stack[-1] > target_level:
            self._indent_stack.pop()
            self.tokens.append(Token("DEDENT", str(self._indent_stack[-1]), loc))

        # Check for inconsistent indentation
        if self._indent_stack[-1] != target_level:
            raise LexerError(
                f"Inconsistent indentation: level {target_level} doesn't match any previous level",
                loc,
            )

    def _find_line_start(self) -> int:
        """Find the position where the current line starts in the source.

        Returns:
            Position in source where current line begins
        """
        # Search backwards for newline
        pos = self.pos
        while pos > 0 and self.source[pos - 1] != "\n":
            pos -= 1
        return pos

    def _is_blank_line(self, start_pos: int) -> bool:
        """Check if line starting at position is blank (only whitespace/comments).

        Args:
            start_pos: Position to start checking from

        Returns:
            True if line is blank or contains only comments
        """
        pos = start_pos
        while pos < len(self.source):
            char = self.source[pos]

            # End of line = blank line
            if char == "\n":
                return True

            # Comment = rest of line is comment (treated as blank)
            if char == "-" and pos + 1 < len(self.source) and self.source[pos + 1] == "-":
                return True

            # Non-whitespace = not blank
            if char not in " \t\r":
                return False

            pos += 1

        # End of file = blank
        return True

    def _advance(self, text: str) -> None:
        """Update line/column counters after consuming text."""
        for char in text:
            if char == "\n":
                self.line += 1
                self.column = 1
            else:
                self.column += 1
        self.pos += len(text)


# =============================================================================
# Convenience Functions
# =============================================================================


def lex(source: str, filename: str = "<stdin>", skip_indent: bool = True) -> list[Token]:
    """Tokenize source code.

    Args:
        source: Source code string
        filename: Source filename for error messages
        skip_indent: If True (default), skip INDENT/DEDENT tokens for backward compatibility

    Returns:
        List of tokens

    Example:
        >>> tokens = lex("let x = 1")
        >>> [t.type for t in tokens]
        ['LET', 'IDENT', 'EQUALS', 'NUMBER', 'EOF']
    """
    return Lexer(source, filename, skip_indent=skip_indent).tokenize()
