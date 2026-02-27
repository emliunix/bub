"""Lexer for surface language.

Indentation-aware tokenizer for System F surface syntax.
Uses stack-based indentation tracking to emit INDENT/DEDENT tokens.
"""

from __future__ import annotations

import re

from systemf.surface.types import (
    ConstructorToken,
    DelimiterToken,
    DocstringToken,
    EOFToken,
    IdentifierToken,
    IndentationToken,
    KeywordToken,
    LexerError,
    NumberToken,
    OperatorToken,
    PragmaToken,
    StringToken,
    Token,
    TokenType,
)
from systemf.utils.location import Location


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
        # Pragma syntax (must come before other patterns to catch {-# before comments)
        # Match pragma start: {-#
        ("PRAGMA_START", r"\{-#"),
        # Match pragma end: #-}
        ("PRAGMA_END", r"#-\}"),
        # Whitespace (no newlines - handled separately for indentation tracking)
        ("WHITESPACE", r"[ \t]+"),
        ("NEWLINE", r"\n|\r\n?"),
        # Docstrings (must come before regular comments)
        # Preceding docstrings (-- |) capture until end of line
        ("DOCSTRING_PRECEDING", r"--\s*\|[^\n]*"),
        # Inline docstrings (-- ^) capture until -> or end of line
        # Must come before COMMENT pattern to be recognized
        ("DOCSTRING_INLINE", r"--\s*\^\s*(.*?)(?=\s*-\u003e|\s*\||\n|$)"),
        ("COMMENT", r"--[^\n]*"),
        # Keywords
        ("DATA", r"\bdata\b"),
        ("LET", r"\blet\b"),
        ("IN", r"\bin\b"),
        ("CASE", r"\bcase\b"),
        ("OF", r"\bof\b"),
        ("FORALL", r"\bforall\b|∀"),  # forall or ∀ (U+2200)
        ("TYPE", r"\btype\b"),
        ("LLM", r"\bLLM\b"),
        ("TOOL", r"\bTOOL\b"),
        ("PRIM_TYPE", r"\bprim_type\b"),  # Primitive type declaration
        ("PRIM_OP", r"\bprim_op\b"),  # Primitive operation declaration
        # Multi-character operators (ASCII and Unicode)
        ("ARROW", r"-\u003e|\u2192"),  # -> or → (U+2192)
        ("DARROW", r"=>"),
        ("LAMBDA", r"\\|\u03bb"),  # \ or λ (U+03bb)
        ("TYPELAMBDA", r"/\\|\u039b"),  # /\ or Λ (U+039b)
        # Multi-character comparison operators
        ("EQ", r"=="),  # Equality
        ("LE", r"<="),  # Less than or equal
        ("GE", r">="),  # Greater than or equal
        # Arithmetic operators
        ("PLUS", r"\+"),
        ("MINUS", r"-"),
        ("STAR", r"\*"),
        ("SLASH", r"/"),
        # Single-character comparison operators (must come after multi-char)
        ("LT", r"<"),
        ("GT", r">"),
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
        ("CONSTRUCTOR", r"[A-Z][a-zA-Z0-9_']*"),  # Type/constructor names start with uppercase
        ("IDENT", r"[a-z_][a-zA-Z0-9_']*"),  # Variables start with lowercase
        # String literals (double-quoted with escape sequence support)
        ("STRING", r'"(?:[^"\\]|\\.)*"'),
        # Numbers (for convenience in tests)
        ("NUMBER", r"[0-9]+"),
    ]

    def __init__(self, source: str, filename: str = "<stdin>"):
        """Initialize lexer with source code.

        Args:
            source: The source code to tokenize
            filename: Name of the source file (for error messages)
        """
        self.source = source
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: list[Token] = []

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

            # Handle pragma start specially
            if token_type == "PRAGMA_START":
                # Emit PRAGMA_START token
                self.tokens.append(
                    PragmaToken(
                        pragma_type=TokenType.PRAGMA_START, content=value, location=start_loc
                    )
                )
                self._advance(value)
                # Parse pragma content
                self._parse_pragma_content(start_loc)
                continue

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
            self.tokens.append(self._create_typed_token(token_type, value, start_loc))

        # End of file: emit DEDENTs to close all open blocks, then EOF
        self._emit_dedents_to_level(0)
        self.tokens.append(EOFToken(location=Location(self.line, self.column, self.filename)))

        return self.tokens

    def _parse_pragma_content(self, start_loc: Location) -> None:
        """Parse pragma content and emit PRAGMA_CONTENT token with key-value pairs.

        Pragma format: {-# KEY key=value ... #-}
        We capture everything between PRAGMA_START and PRAGMA_END as raw content.

        Args:
            start_loc: Location of the pragma start
        """
        content_lines = []

        while self.pos < len(self.source):
            # Check for pragma end
            if self.source[self.pos :].startswith("#-}"):
                # Join content lines (removing trailing whitespace)
                raw_content = "".join(content_lines).strip()
                self.tokens.append(
                    PragmaToken(
                        pragma_type=TokenType.PRAGMA_CONTENT,
                        content=raw_content,
                        location=start_loc,
                    )
                )
                # Emit PRAGMA_END
                end_loc = Location(self.line, self.column, self.filename)
                self._advance("#-}")
                self.tokens.append(
                    PragmaToken(pragma_type=TokenType.PRAGMA_END, content="#-}", location=end_loc)
                )
                return

            # Collect character
            char = self.source[self.pos]
            content_lines.append(char)

            if char == "\n":
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            self.pos += 1

        # Reached end of file without finding pragma end
        raise LexerError("Unclosed pragma: expected #-}", start_loc)

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
            self.tokens.append(
                IndentationToken(
                    indent_type=TokenType.INDENT, level=str(current_indent), location=indent_loc
                )
            )
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
            self.tokens.append(
                IndentationToken(
                    indent_type=TokenType.DEDENT, level=str(self._indent_stack[-1]), location=loc
                )
            )

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
            True if line is blank or contains only regular comments (not docstrings)
        """
        pos = start_pos
        while pos < len(self.source):
            char = self.source[pos]

            # End of line = blank line
            if char == "\n":
                return True

            # Check for comment start
            if char == "-" and pos + 1 < len(self.source) and self.source[pos + 1] == "-":
                # Check if this is a docstring (-- | or -- ^)
                # Skip the "--"
                comment_start = pos + 2
                # Skip whitespace after "--"
                while comment_start < len(self.source) and self.source[comment_start] in " \t":
                    comment_start += 1
                # If followed by | or ^, it's a docstring (not blank)
                if comment_start < len(self.source) and self.source[comment_start] in "|^":
                    return False
                # Regular comment = rest of line is blank
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

    def _process_escape_sequences(self, s: str) -> str:
        """Process escape sequences in a string literal.

        Handles common escape sequences: \\, \", \n, \t, \r, \b, \f.

        Args:
            s: The raw string content (without quotes)

        Returns:
            The string with escape sequences processed
        """
        result = []
        i = 0
        while i < len(s):
            if s[i] == "\\" and i + 1 < len(s):
                next_char = s[i + 1]
                if next_char == "\\":
                    result.append("\\")
                elif next_char == '"':
                    result.append('"')
                elif next_char == "n":
                    result.append("\n")
                elif next_char == "t":
                    result.append("\t")
                elif next_char == "r":
                    result.append("\r")
                elif next_char == "b":
                    result.append("\b")
                elif next_char == "f":
                    result.append("\f")
                else:
                    # Unknown escape sequence, keep as-is
                    result.append(s[i : i + 2])
                i += 2
            else:
                result.append(s[i])
                i += 1
        return "".join(result)

    def _create_typed_token(self, token_type: str, value: str, location: Location) -> Token:
        """Create a typed token based on the token type string.

        Args:
            token_type: The type of token (e.g., "IDENT", "NUMBER")
            value: The token value as a string
            location: The source location

        Returns:
            A specific Token subclass instance
        """
        match token_type:
            case TokenType.IDENT:
                return IdentifierToken(name=value, location=location)
            case TokenType.CONSTRUCTOR:
                return ConstructorToken(name=value, location=location)
            case TokenType.NUMBER:
                return NumberToken(number=value, location=location)
            case TokenType.STRING:
                # Strip quotes and process escape sequences
                string_value = value[1:-1]  # Remove surrounding quotes
                string_value = self._process_escape_sequences(string_value)
                return StringToken(string=string_value, location=location)
            case TokenType.ARROW:
                return OperatorToken(operator=value, location=location, op_type=TokenType.ARROW)
            case TokenType.DARROW:
                return OperatorToken(operator=value, location=location, op_type=TokenType.DARROW)
            case TokenType.LAMBDA:
                return OperatorToken(operator=value, location=location, op_type=TokenType.LAMBDA)
            case TokenType.TYPELAMBDA:
                return OperatorToken(
                    operator=value, location=location, op_type=TokenType.TYPELAMBDA
                )
            case TokenType.EQ:
                return OperatorToken(operator=value, location=location, op_type=TokenType.EQ)
            case TokenType.LE:
                return OperatorToken(operator=value, location=location, op_type=TokenType.LE)
            case TokenType.GE:
                return OperatorToken(operator=value, location=location, op_type=TokenType.GE)
            case TokenType.PLUS:
                return OperatorToken(operator=value, location=location, op_type=TokenType.PLUS)
            case TokenType.MINUS:
                return OperatorToken(operator=value, location=location, op_type=TokenType.MINUS)
            case TokenType.STAR:
                return OperatorToken(operator=value, location=location, op_type=TokenType.STAR)
            case TokenType.SLASH:
                return OperatorToken(operator=value, location=location, op_type=TokenType.SLASH)
            case TokenType.LT:
                return OperatorToken(operator=value, location=location, op_type=TokenType.LT)
            case TokenType.GT:
                return OperatorToken(operator=value, location=location, op_type=TokenType.GT)
            case TokenType.EQUALS:
                return OperatorToken(operator=value, location=location, op_type=TokenType.EQUALS)
            case TokenType.COLON:
                return OperatorToken(operator=value, location=location, op_type=TokenType.COLON)
            case TokenType.BAR:
                return OperatorToken(operator=value, location=location, op_type=TokenType.BAR)
            case TokenType.AT:
                return OperatorToken(operator=value, location=location, op_type=TokenType.AT)
            case TokenType.DOT:
                return OperatorToken(operator=value, location=location, op_type=TokenType.DOT)
            case TokenType.LPAREN:
                return DelimiterToken(
                    delimiter=value, location=location, delim_type=TokenType.LPAREN
                )
            case TokenType.RPAREN:
                return DelimiterToken(
                    delimiter=value, location=location, delim_type=TokenType.RPAREN
                )
            case TokenType.LBRACKET:
                return DelimiterToken(
                    delimiter=value, location=location, delim_type=TokenType.LBRACKET
                )
            case TokenType.RBRACKET:
                return DelimiterToken(
                    delimiter=value, location=location, delim_type=TokenType.RBRACKET
                )
            case TokenType.LBRACE:
                return DelimiterToken(
                    delimiter=value, location=location, delim_type=TokenType.LBRACE
                )
            case TokenType.RBRACE:
                return DelimiterToken(
                    delimiter=value, location=location, delim_type=TokenType.RBRACE
                )
            case TokenType.COMMA:
                return DelimiterToken(
                    delimiter=value, location=location, delim_type=TokenType.COMMA
                )
            case TokenType.DOCSTRING_PRECEDING:
                return DocstringToken(
                    docstring_type=TokenType.DOCSTRING_PRECEDING, content=value, location=location
                )
            case TokenType.DOCSTRING_INLINE:
                return DocstringToken(
                    docstring_type=TokenType.DOCSTRING_INLINE, content=value, location=location
                )
            case _ if token_type in TokenType.KEYWORDS:
                # Normalize Unicode forall to ASCII for consistent token type
                normalized = "forall" if value == "∀" else value
                return KeywordToken(keyword=normalized, location=location)
            case _:
                raise LexerError(f"Unknown token type: {token_type}", location)


# =============================================================================
# Convenience Functions
# =============================================================================


def lex(source: str, filename: str = "<stdin>") -> list[Token]:
    """Tokenize source code.

    Args:
        source: Source code string
        filename: Source filename for error messages

    Returns:
        List of tokens

    Example:
        >>> tokens = lex("let x = 1")
        >>> [t.type for t in tokens]
        ['LET', 'IDENT', 'EQUALS', 'NUMBER', 'EOF']
    """
    return Lexer(source, filename).tokenize()
