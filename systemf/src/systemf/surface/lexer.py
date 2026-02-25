"""Lexer for surface language.

Simple regex-based tokenizer for System F surface syntax.
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
    """Tokenizer for System F surface language.

    Tokenizes input into a stream of tokens for the parser.
    """

    # Token specifications as regex patterns
    TOKEN_PATTERNS = [
        # Whitespace and comments
        ("WHITESPACE", r"[ \t\n\r]+"),
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

        # Compile regex for efficiency
        self._pattern = re.compile(
            "|".join(f"(?P<{name}>{pattern})" for name, pattern in self.TOKEN_PATTERNS)
        )

    def tokenize(self) -> list[Token]:
        """Convert source code to token stream.

        Returns:
            List of tokens (excluding whitespace and comments)

        Raises:
            LexerError: If unexpected character encountered
        """
        self.tokens = []

        while self.pos < len(self.source):
            # Skip whitespace and comments
            match = self._pattern.match(self.source, self.pos)

            if not match:
                # Unknown character
                char = self.source[self.pos]
                loc = Location(self.line, self.column, self.filename)
                raise LexerError(f"Unexpected character: {char!r}", loc)

            token_type = match.lastgroup
            value = match.group()
            start_loc = Location(self.line, self.column, self.filename)

            # Update position
            self._advance(value)

            # Skip whitespace and comments
            if token_type in ("WHITESPACE", "COMMENT"):
                continue

            self.tokens.append(Token(token_type, value, start_loc))

        # Add EOF token
        self.tokens.append(Token("EOF", "", Location(self.line, self.column, self.filename)))

        return self.tokens

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
