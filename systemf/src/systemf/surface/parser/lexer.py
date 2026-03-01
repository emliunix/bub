"""Lexer for surface language.

Simple tokenizer for System F surface syntax.
No virtual indentation tokens - stateful parser will handle layout.
"""

from __future__ import annotations

import re

from systemf.surface.parser.types import (
    ConstructorToken,
    DelimiterToken,
    DocstringToken,
    EOFToken,
    IdentifierToken,
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
    """Tokenizer for System F surface language.

    Tokenizes input into a stream of tokens for the parser.
    No indentation tracking - raw tokens only with location info.
    """

    # Token specifications as regex patterns
    TOKEN_PATTERNS = [
        # Pragma syntax (must come before other patterns to catch {-# before comments)
        ("PRAGMA_START", r"\{-#"),
        ("PRAGMA_END", r"#-\}"),
        # Whitespace
        ("WHITESPACE", r"[ \t]+"),
        ("NEWLINE", r"\n|\r\n?"),
        # Docstrings
        ("DOCSTRING_PRECEDING", r"--\s*\|[^\n]*"),
        ("DOCSTRING_INLINE", r"--\s*\^\s*(.*?)(?=\s*-\u003e|\s*\||\n|$)"),
        ("COMMENT", r"--[^\n]*"),
        # Keywords
        ("DATA", r"\bdata\b"),
        ("LET", r"\blet\b"),
        ("IN", r"\bin\b"),
        ("CASE", r"\bcase\b"),
        ("OF", r"\bof\b"),
        ("FORALL", r"\bforall\b|∀"),
        ("TYPE", r"\btype\b"),
        ("IF", r"\bif\b"),
        ("THEN", r"\bthen\b"),
        ("ELSE", r"\belse\b"),
        ("PRIM_TYPE", r"\bprim_type\b"),
        ("PRIM_OP", r"\bprim_op\b"),
        # Multi-character operators
        ("ARROW", r"-\u003e|\u2192"),
        ("DARROW", r"=\u003e"),
        ("NEQ", r"/="),
        ("LE", r"\u003c="),
        ("GE", r"\u003e="),
        ("AND", r"\u0026\u0026"),
        ("OR", r"\|\|"),
        ("APPEND", r"\+\+"),
        ("LAMBDA", r"\\|\u03bb"),
        ("TYPELAMBDA", r"/\\|\u039b"),
        # Single-character operators (after multi-char)
        ("EQ", r"=="),
        ("PLUS", r"\+"),
        ("MINUS", r"-"),
        ("STAR", r"\*"),
        ("SLASH", r"/"),
        ("LT", r"\u003c"),
        ("GT", r"\u003e"),
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
        # Literals
        ("STRING", r'"([^"\\]|\\.)*"'),
        ("NUMBER", r"\d+"),
        # Identifiers and constructors (order matters!)
        ("CONSTRUCTOR", r"[A-Z][a-zA-Z0-9_]*"),
        ("IDENT", r"[a-z_][a-zA-Z0-9_]*"),
    ]

    def __init__(self, source: str, filename: str | None = None) -> None:
        """Initialize lexer with source code.

        Args:
            source: Source code to tokenize
            filename: Optional filename for error reporting
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
            List of tokens with location information

        Raises:
            LexerError: If unexpected character encountered
        """
        self.tokens = []

        while self.pos < len(self.source):
            # Skip whitespace and comments (but not newlines)
            if self._skip_whitespace():
                continue

            # Try to match a token
            match = self._pattern.match(self.source, self.pos)

            if match:
                token = self._create_token(match)
                if token:
                    self.tokens.append(token)
                self._advance(match.group())
            else:
                # Unknown character
                loc = Location(self.line, self.column, self.filename)
                raise LexerError(f"Unexpected character: {self.source[self.pos]!r}", loc)

        # Return tokens without explicit EOF - parsy expects stream to end naturally
        return self.tokens

    def _skip_whitespace(self) -> bool:
        """Skip whitespace and comments (except newlines).

        Returns:
            True if skipped anything, False otherwise
        """
        skipped = False
        while self.pos < len(self.source):
            char = self.source[self.pos]

            # Skip spaces and tabs
            if char in " \t":
                self._advance(char)
                skipped = True
            # Skip comments
            elif self.source.startswith("--", self.pos):
                # Skip to end of line
                while self.pos < len(self.source) and self.source[self.pos] != "\n":
                    self.pos += 1
                skipped = True
            else:
                break

        return skipped

    def _advance(self, text: str) -> None:
        """Advance position by text length, updating line/column."""
        for char in text:
            if char == "\n":
                self.line += 1
                self.column = 1
            else:
                self.column += 1
        self.pos += len(text)

    def _create_token(self, match: re.Match) -> Token | None:
        """Create appropriate token from regex match."""
        token_type = match.lastgroup
        value = match.group()
        loc = Location(self.line, self.column, self.filename)

        if token_type in ("WHITESPACE", "COMMENT", "DOCSTRING_PRECEDING", "DOCSTRING_INLINE"):
            # Skip these (but we already skipped them in _skip_whitespace)
            return None
        elif token_type == "NEWLINE":
            # Track newlines for location, but don't emit token
            return None
        elif token_type == "IDENT":
            return IdentifierToken(name=value, location=loc)
        elif token_type == "CONSTRUCTOR":
            return ConstructorToken(name=value, location=loc)
        elif token_type == "NUMBER":
            return NumberToken(number=value, location=loc)
        elif token_type == "STRING":
            # Remove quotes from string value
            string_value = value[1:-1]
            return StringToken(string=string_value, location=loc)
        elif token_type in (
            "DATA",
            "LET",
            "IN",
            "CASE",
            "OF",
            "FORALL",
            "TYPE",
            "IF",
            "THEN",
            "ELSE",
            "PRIM_TYPE",
            "PRIM_OP",
        ):
            return KeywordToken(keyword=value, location=loc)
        elif token_type in (
            "ARROW",
            "DARROW",
            "LAMBDA",
            "TYPELAMBDA",
            "EQ",
            "NEQ",
            "PLUS",
            "MINUS",
            "STAR",
            "SLASH",
            "LT",
            "GT",
            "LE",
            "GE",
            "AND",
            "OR",
            "APPEND",
            "EQUALS",
            "COLON",
            "BAR",
            "AT",
            "DOT",
        ):
            # Determine operator type
            op_map = {
                "ARROW": TokenType.ARROW,
                "DARROW": TokenType.DARROW,
                "LAMBDA": TokenType.LAMBDA,
                "TYPELAMBDA": TokenType.TYPELAMBDA,
                "EQ": TokenType.EQ,
                "NEQ": TokenType.NEQ,
                "PLUS": TokenType.PLUS,
                "MINUS": TokenType.MINUS,
                "STAR": TokenType.STAR,
                "SLASH": TokenType.SLASH,
                "LT": TokenType.LT,
                "GT": TokenType.GT,
                "LE": TokenType.LE,
                "GE": TokenType.GE,
                "AND": TokenType.AND,
                "OR": TokenType.OR,
                "APPEND": TokenType.APPEND,
                "EQUALS": TokenType.EQUALS,
                "COLON": TokenType.COLON,
                "BAR": TokenType.BAR,
                "AT": TokenType.AT,
                "DOT": TokenType.DOT,
            }
            return OperatorToken(operator=value, op_type=op_map[token_type], location=loc)
        elif token_type in ("LPAREN", "RPAREN", "LBRACKET", "RBRACKET", "LBRACE", "RBRACE"):
            delim_map = {
                "LPAREN": TokenType.LPAREN,
                "RPAREN": TokenType.RPAREN,
                "LBRACKET": TokenType.LBRACKET,
                "RBRACKET": TokenType.RBRACKET,
                "LBRACE": TokenType.LBRACE,
                "RBRACE": TokenType.RBRACE,
            }
            return DelimiterToken(delimiter=value, delim_type=delim_map[token_type], location=loc)
        elif token_type in ("PRAGMA_START", "PRAGMA_END"):
            return PragmaToken(
                pragma_type=getattr(TokenType, token_type), content=value, location=loc
            )
        else:
            # Unknown token type - skip
            return None


def lex(source: str, filename: str | None = None) -> list[Token]:
    """Tokenize source code.

    Convenience function that creates a Lexer and tokenizes the source.

    Args:
        source: Source code to tokenize
        filename: Optional filename for error reporting

    Returns:
        List of tokens
    """
    return Lexer(source, filename).tokenize()
