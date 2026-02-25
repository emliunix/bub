"""Recursive descent parser for System F surface language.

Implements a hand-written parser with Pratt parsing for operators.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from systemf.surface.ast import (
    SurfaceAbs,
    SurfaceApp,
    SurfaceBranch,
    SurfaceCase,
    SurfaceConstructor,
    SurfaceDataDeclaration,
    SurfaceDeclaration,
    SurfaceLet,
    SurfacePattern,
    SurfaceTerm,
    SurfaceTermDeclaration,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceTypeArrow,
    SurfaceTypeConstructor,
    SurfaceTypeForall,
    SurfaceTypeVar,
    SurfaceAnn,
    SurfaceVar,
)
from systemf.surface.lexer import Lexer, Token
from systemf.utils.location import Location


class ParseError(Exception):
    """Error during parsing."""

    def __init__(self, message: str, location: Location):
        super().__init__(f"{location}: {message}")
        self.location = location


class Parser:
    """Recursive descent parser for surface language.

    Grammar:
        decl ::= "data" CON ident* "=" constr ("|" constr)*
               | ident (":" type)? "=" term

        constr ::= CON type_atom*

        term ::= "\\" ident (":" type)? "->" term
               | "let" ident "=" term "in" term
               | "case" term "of" "{" branch* "}"
               | "/\\" ident "." term
               | app

        app ::= atom+

        atom ::= ident
               | CON atom*
               | "(" term ")"
               | atom "@" type
               | atom "[" type "]"
               | atom ":" type

        type ::= forall_type

        forall_type ::= "forall" ident+ "." arrow_type
                      | arrow_type

        arrow_type ::= app_type ("->" arrow_type)?

        app_type ::= atom_type+

        atom_type ::= ident | CON | "(" type ")"

        branch ::= pattern "->" term

        pattern ::= CON ident*
    """

    def __init__(self, tokens: list[Token]):
        """Initialize parser with token stream."""
        self.tokens = tokens
        self.pos = 0

    def _current(self) -> Token:
        """Get current token."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF token

    def _peek(self, offset: int = 0) -> Token:
        """Peek at token ahead."""
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]

    def _advance(self) -> Token:
        """Consume and return current token."""
        token = self._current()
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return token

    def _expect(self, token_type: str) -> Token:
        """Expect current token to be of specific type."""
        token = self._current()
        if token.type != token_type:
            raise ParseError(f"Expected {token_type}, got {token.type}", token.location)
        return self._advance()

    def _match(self, *token_types: str) -> bool:
        """Check if current token matches any of the types."""
        return self._current().type in token_types

    def _consume(self, token_type: str) -> bool:
        """Consume token if it matches type."""
        if self._match(token_type):
            self._advance()
            return True
        return False

    def at_end(self) -> bool:
        """Check if at end of input."""
        return self._current().type == "EOF"

    # =====================================================================
    # Declaration Parsing
    # =====================================================================

    def parse(self) -> list[SurfaceDeclaration]:
        """Parse token stream into surface AST."""
        decls = []
        while not self.at_end():
            decls.append(self.parse_declaration())
        return decls

    def parse_declaration(self) -> SurfaceDeclaration:
        """Parse a declaration."""
        if self._match("DATA"):
            return self.parse_data_declaration()
        else:
            return self.parse_term_declaration()

    def parse_data_declaration(self) -> SurfaceDataDeclaration:
        """Parse: data Name params = Con1 args1 | Con2 args2 | ..."""
        data_kw = self._expect("DATA")
        name_tok = self._expect("CONSTRUCTOR")

        # Parse optional type parameters
        params = []
        while self._match("IDENT"):
            params.append(self._advance().value)

        self._expect("EQUALS")

        # Parse constructors
        constructors = []
        while True:
            con_tok = self._expect("CONSTRUCTOR")
            con_name = con_tok.value

            # Parse constructor argument types
            arg_types = []
            while self._match("IDENT", "CONSTRUCTOR", "LPAREN"):
                # Don't consume if this looks like the start of a term declaration
                # (identifier/constructor followed by : or =)
                if self._peek(1).type in ("COLON", "EQUALS"):
                    # This looks like a term declaration name, not a type
                    break
                arg_types.append(self.parse_atom_type())

            constructors.append((con_name, arg_types))

            if not self._consume("BAR"):
                break

        return SurfaceDataDeclaration(
            name=name_tok.value,
            params=params,
            constructors=constructors,
            location=data_kw.location,
        )

    def parse_term_declaration(self) -> SurfaceTermDeclaration:
        """Parse: name : type = body  or  name = body."""
        name_tok = self._expect("IDENT")
        name = name_tok.value
        loc = name_tok.location

        type_annotation = None
        if self._consume("COLON"):
            type_annotation = self.parse_type()

        self._expect("EQUALS")
        body = self.parse_declaration_body()

        return SurfaceTermDeclaration(name, type_annotation, body, loc)

    def parse_declaration_body(self) -> SurfaceTerm:
        """Parse the body of a term declaration.

        This is like parse_term but stops when it sees what looks like
        the start of a new declaration (identifier/constructor followed by COLON).
        """
        term = self.parse_term()

        # Check if what follows looks like a new declaration
        # (identifier/constructor followed by :)
        # If so, don't include it in this body
        while not self.at_end():
            current = self._current()
            next_tok = self._peek(1)

            if current.type in ("IDENT", "CONSTRUCTOR") and next_tok.type in ("COLON", "EQUALS"):
                # This looks like a new declaration, stop here
                break

            # Otherwise, try to continue parsing as application
            if current.type in (
                "IDENT",
                "CONSTRUCTOR",
                "LPAREN",
                "LAMBDA",
                "LET",
                "CASE",
                "TYPELAMBDA",
                "NUMBER",
            ):
                loc = current.location
                next_atom = self.parse_atom()
                term = SurfaceApp(term, next_atom, loc)
            else:
                break

        return term

    # =====================================================================
    # Term Parsing
    # =====================================================================

    def parse_term(self) -> SurfaceTerm:
        """Parse a term."""
        return self.parse_lambda()

    def parse_lambda(self) -> SurfaceTerm:
        """Parse lambda, let, case, type abstraction, or application."""
        loc = self._current().location

        # Lambda abstraction: \x -> body or \x:T -> body
        if self._consume("LAMBDA"):
            var_tok = self._expect("IDENT")
            var = var_tok.value
            var_type = None

            if self._consume("COLON"):
                var_type = self._parse_type_for_annotation()

            self._expect("ARROW")
            body = self.parse_lambda()  # Right-associative
            return SurfaceAbs(var, var_type, body, loc)

        # Type abstraction: /\a. body
        if self._match("TYPELAMBDA") or (self._match("AT") and self._peek(1).type == "IDENT"):
            if self._match("TYPELAMBDA"):
                self._advance()
            else:
                self._advance()  # consume @
            var_tok = self._expect("IDENT")
            self._expect("DOT")
            body = self.parse_lambda()
            return SurfaceTypeAbs(var_tok.value, body, loc)

        # Let binding: let x = e1 in e2
        if self._consume("LET"):
            name_tok = self._expect("IDENT")
            self._expect("EQUALS")
            value = self.parse_lambda()
            self._expect("IN")
            body = self.parse_lambda()
            return SurfaceLet(name_tok.value, value, body, loc)

        # Case expression: case e of { branches }
        if self._consume("CASE"):
            scrutinee = self.parse_lambda()
            self._expect("OF")
            self._expect("LBRACE")
            branches = self.parse_branches()
            self._expect("RBRACE")
            return SurfaceCase(scrutinee, branches, loc)

        # Application
        return self.parse_application()

    def parse_branches(self) -> list:
        """Parse case branches separated by |."""
        branches = []
        while not self._match("RBRACE"):
            branch = self.parse_branch()
            branches.append(branch)
            if not self._consume("BAR"):
                break
        return branches

    def parse_branch(self) -> SurfaceBranch:
        """Parse a case branch: pattern -> body."""
        loc = self._current().location
        pattern = self.parse_pattern()
        self._expect("ARROW")
        body = self.parse_term()
        return SurfaceBranch(pattern, body, loc)

    def parse_pattern(self) -> SurfacePattern:
        """Parse a pattern: Con vars."""
        loc = self._current().location
        con_tok = self._expect("CONSTRUCTOR")
        con_name = con_tok.value

        vars = []
        while self._match("IDENT"):
            vars.append(self._advance().value)

        return SurfacePattern(con_name, vars, loc)

    def parse_application(self) -> SurfaceTerm:
        """Parse function application (left-associative)."""
        loc = self._current().location
        atom = self.parse_atom()

        # If the first atom is a NUMBER, don't treat it as a function
        # This prevents "1 y = 2" from being parsed as "(1 y) = 2"
        if isinstance(atom, SurfaceConstructor) and atom.name.isdigit():
            return atom

        # Build left-associative application chain
        while True:
            if self.at_end():
                break

            next_tok = self._current()

            # Type application: e @T or e [T]
            if next_tok.type == "AT":
                self._advance()
                type_arg = self.parse_type()
                atom = SurfaceTypeApp(atom, type_arg, loc)
                continue

            if next_tok.type == "LBRACKET":
                self._advance()
                type_arg = self.parse_type()
                self._expect("RBRACKET")
                atom = SurfaceTypeApp(atom, type_arg, loc)
                continue

            # Type annotation: e : T
            if next_tok.type == "COLON":
                self._advance()
                type_ann = self.parse_type()
                atom = SurfaceAnn(atom, type_ann, loc)
                continue

            # Check if next token can start a new atom
            if next_tok.type in (
                "IDENT",
                "CONSTRUCTOR",
                "LPAREN",
                "LAMBDA",
                "LET",
                "CASE",
                "TYPELAMBDA",
                "NUMBER",
            ):
                next_atom = self.parse_atom()
                atom = SurfaceApp(atom, next_atom, loc)
            else:
                break

        return atom

    def parse_atom(self) -> SurfaceTerm:
        """Parse atomic term."""
        loc = self._current().location

        # Parenthesized term
        if self._consume("LPAREN"):
            term = self.parse_term()
            self._expect("RPAREN")
            return term

        # Variable
        if self._match("IDENT"):
            tok = self._advance()
            return SurfaceVar(tok.value, tok.location)

        # Constructor application or nullary constructor
        if self._match("CONSTRUCTOR"):
            return self.parse_constructor()

        # Number literal (treated as constructor)
        if self._match("NUMBER"):
            tok = self._advance()
            return SurfaceConstructor(tok.value, [], tok.location)

        raise ParseError(f"Unexpected token: {self._current().type}", self._current().location)

    def parse_constructor(self) -> SurfaceTerm:
        """Parse constructor: Con args..."""
        loc = self._current().location
        con_tok = self._expect("CONSTRUCTOR")
        con_name = con_tok.value

        args = []
        while True:
            # Try to parse argument atoms
            if self._match("IDENT"):
                tok = self._current()
                args.append(SurfaceVar(tok.value, tok.location))
                self._advance()
            elif self._match("CONSTRUCTOR"):
                args.append(self.parse_constructor())
            elif self._match("LPAREN"):
                self._advance()
                term = self.parse_term()
                self._expect("RPAREN")
                args.append(term)
            elif self._match("NUMBER"):
                tok = self._advance()
                args.append(SurfaceConstructor(tok.value, [], tok.location))
            else:
                break

        return SurfaceConstructor(con_name, args, loc)

    # =====================================================================
    # Type Parsing
    # =====================================================================

    def parse_type(self) -> SurfaceType:
        """Parse a type expression."""
        return self.parse_forall_type()

    def parse_forall_type(self) -> SurfaceType:
        """Parse forall type or arrow type."""
        loc = self._current().location

        if self._consume("FORALL"):
            # Parse one or more type variables
            vars = []
            while self._match("IDENT"):
                vars.append(self._advance().value)

            if not vars:
                raise ParseError("Expected type variable after forall", self._current().location)

            self._expect("DOT")
            body = self.parse_forall_type()

            # Build nested forall types
            for var in reversed(vars):
                body = SurfaceTypeForall(var, body, loc)
            return body

        return self.parse_arrow_type()

    def parse_arrow_type(self) -> SurfaceType:
        """Parse arrow type (right-associative)."""
        loc = self._current().location
        arg = self.parse_app_type()

        if self._consume("ARROW"):
            ret = self.parse_arrow_type()  # Right-associative
            return SurfaceTypeArrow(arg, ret, loc)

        return arg

    def parse_app_type(self) -> SurfaceType:
        """Parse type application (left-associative)."""
        loc = self._current().location
        atom = self.parse_atom_type()

        # Build left-associative application chain
        atoms = [atom]
        while self._match("IDENT", "CONSTRUCTOR", "LPAREN"):
            atoms.append(self.parse_atom_type())

        # Combine atoms into application
        result = atoms[0]
        for next_atom in atoms[1:]:
            if isinstance(result, SurfaceTypeConstructor):
                # Add to existing constructor args
                result = SurfaceTypeConstructor(
                    result.name, result.args + [next_atom], result.location
                )
            else:
                # Start new constructor
                result = SurfaceTypeConstructor(str(result), [next_atom], loc)

        return result

    def parse_atom_type(self) -> SurfaceType:
        """Parse atomic type."""
        loc = self._current().location

        # Parenthesized type
        if self._consume("LPAREN"):
            ty = self.parse_type()
            self._expect("RPAREN")
            return ty

        # Type variable
        if self._match("IDENT"):
            tok = self._advance()
            return SurfaceTypeVar(tok.value, tok.location)

        # Type constructor
        if self._match("CONSTRUCTOR"):
            tok = self._advance()
            return SurfaceTypeConstructor(tok.value, [], tok.location)

        raise ParseError(
            f"Unexpected token in type: {self._current().type}", self._current().location
        )

    def _parse_type_for_annotation(self) -> "SurfaceType":
        r"""Parse type annotation, being careful not to consume lambda arrow.

        When parsing a type annotation like `\x:Int -> body`, we need to
        parse `Int` as the type, not `Int -> body`.

        We parse an app type and check if the next token is ARROW followed
        by something that looks like a type (not a term). If it looks like
        the lambda arrow, we stop and don't include it in the type.
        """
        loc = self._current().location
        arg = self.parse_app_type()

        # Check if this might be an arrow type vs lambda arrow
        # Only consume ARROW if followed by something that looks like a type
        # and not the body of a lambda
        if self._match("ARROW"):
            # Look ahead: if next tokens look like a type, it might be an arrow type
            # For now, we only parse app types in annotations (no arrows)
            # This is a conservative approach that can be refined
            pass

        return arg


# =============================================================================
# Convenience Functions
# =============================================================================


def parse_term(source: str, filename: str = "<stdin>") -> SurfaceTerm:
    """Parse a single term from source.

    Args:
        source: Source code string
        filename: Source filename for error messages

    Returns:
        Parsed surface term

    Example:
        >>> term = parse_term("\\x -> x")
        >>> print(term)
        \\x -> x
    """
    from systemf.surface.lexer import Lexer

    tokens = Lexer(source, filename).tokenize()
    parser = Parser(tokens)
    return parser.parse_term()


def parse_program(source: str, filename: str = "<stdin>") -> list[SurfaceDeclaration]:
    """Parse a full program from source.

    Args:
        source: Source code string
        filename: Source filename for error messages

    Returns:
        List of surface declarations

    Example:
        >>> decls = parse_program("x = 1")
        >>> len(decls)
        1
    """
    from systemf.surface.lexer import Lexer

    tokens = Lexer(source, filename).tokenize()
    parser = Parser(tokens)
    return parser.parse()
