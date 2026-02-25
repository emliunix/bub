"""Tests for surface language parser."""

import pytest

from systemf.surface.ast import (
    SurfaceAbs,
    SurfaceApp,
    SurfaceBranch,
    SurfaceCase,
    SurfaceConstructor,
    SurfaceDataDeclaration,
    SurfaceLet,
    SurfacePattern,
    SurfaceTermDeclaration,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceTypeArrow,
    SurfaceTypeConstructor,
    SurfaceTypeForall,
    SurfaceTypeVar,
    SurfaceVar,
    SurfaceAnn,
)
from systemf.surface.lexer import lex
from systemf.surface.parser import ParseError, Parser, parse_program, parse_term


# =============================================================================
# Variable Parsing Tests
# =============================================================================


class TestParseVar:
    """Tests for variable parsing."""

    def test_parse_simple_var(self):
        """Parse simple variable."""
        term = parse_term("x")
        assert isinstance(term, SurfaceVar)
        assert term.name == "x"

    def test_parse_var_underscore(self):
        """Parse variable with underscore."""
        term = parse_term("_foo")
        assert isinstance(term, SurfaceVar)
        assert term.name == "_foo"


# =============================================================================
# Lambda Parsing Tests
# =============================================================================


class TestParseLambda:
    """Tests for lambda abstraction parsing."""

    def test_parse_simple_lambda(self):
        """Parse simple lambda."""
        term = parse_term(r"\x -> x")
        assert isinstance(term, SurfaceAbs)
        assert term.var == "x"
        assert term.var_type is None
        assert isinstance(term.body, SurfaceVar)
        assert term.body.name == "x"

    def test_parse_annotated_lambda(self):
        """Parse lambda with type annotation."""
        term = parse_term(r"\x:Int -> x")
        assert isinstance(term, SurfaceAbs)
        assert term.var == "x"
        assert term.var_type is not None
        assert isinstance(term.var_type, SurfaceTypeConstructor)
        assert term.var_type.name == "Int"

    def test_parse_nested_lambda(self):
        """Parse nested lambda."""
        term = parse_term(r"\x -> \y -> x")
        assert isinstance(term, SurfaceAbs)
        assert term.var == "x"
        assert isinstance(term.body, SurfaceAbs)
        assert term.body.var == "y"

    def test_lambda_arrow_right_associative(self):
        """Lambda arrow is right-associative."""
        term = parse_term(r"\x -> \y -> z")
        assert isinstance(term, SurfaceAbs)
        assert isinstance(term.body, SurfaceAbs)


# =============================================================================
# Application Parsing Tests
# =============================================================================


class TestParseApp:
    """Tests for function application parsing."""

    def test_parse_simple_app(self):
        """Parse simple application."""
        term = parse_term("f x")
        assert isinstance(term, SurfaceApp)
        assert isinstance(term.func, SurfaceVar)
        assert term.func.name == "f"
        assert isinstance(term.arg, SurfaceVar)
        assert term.arg.name == "x"

    def test_parse_multi_app(self):
        """Parse multiple application (left-associative)."""
        term = parse_term("f x y")
        # Should be (f x) y
        assert isinstance(term, SurfaceApp)
        assert isinstance(term.func, SurfaceApp)
        assert term.func.func.name == "f"
        assert term.func.arg.name == "x"
        assert term.arg.name == "y"

    def test_parse_app_in_parens(self):
        """Parse parenthesized application."""
        term = parse_term("f (g x)")
        assert isinstance(term, SurfaceApp)
        assert term.func.name == "f"
        assert isinstance(term.arg, SurfaceApp)
        assert term.arg.func.name == "g"


# =============================================================================
# Type Abstraction Parsing Tests
# =============================================================================


class TestParseTypeAbs:
    """Tests for type abstraction parsing."""

    def test_parse_type_lambda(self):
        """Parse type abstraction."""
        term = parse_term("/\\a. x")
        assert isinstance(term, SurfaceTypeAbs)
        assert term.var == "a"
        assert isinstance(term.body, SurfaceVar)


# =============================================================================
# Type Application Parsing Tests
# =============================================================================


class TestParseTypeApp:
    """Tests for type application parsing."""

    def test_parse_type_app_at(self):
        """Parse type application with @."""
        term = parse_term("id @Int")
        assert isinstance(term, SurfaceTypeApp)
        assert isinstance(term.func, SurfaceVar)
        assert term.func.name == "id"
        assert isinstance(term.type_arg, SurfaceTypeConstructor)
        assert term.type_arg.name == "Int"

    def test_parse_type_app_brackets(self):
        """Parse type application with brackets."""
        term = parse_term("id [Int]")
        assert isinstance(term, SurfaceTypeApp)
        assert term.func.name == "id"
        assert term.type_arg.name == "Int"


# =============================================================================
# Let Binding Parsing Tests
# =============================================================================


class TestParseLet:
    """Tests for let binding parsing."""

    def test_parse_simple_let(self):
        """Parse simple let binding."""
        term = parse_term("let x = y in z")
        assert isinstance(term, SurfaceLet)
        assert term.name == "x"
        assert isinstance(term.value, SurfaceVar)
        assert term.value.name == "y"
        assert isinstance(term.body, SurfaceVar)
        assert term.body.name == "z"

    def test_parse_nested_let(self):
        """Parse nested let."""
        term = parse_term("let x = 1 in let y = 2 in x")
        assert isinstance(term, SurfaceLet)
        assert isinstance(term.body, SurfaceLet)


# =============================================================================
# Type Annotation Parsing Tests
# =============================================================================


class TestParseAnnotation:
    """Tests for type annotation parsing."""

    def test_parse_type_annotation(self):
        """Parse type annotation."""
        term = parse_term("x : Int")
        assert isinstance(term, SurfaceAnn)
        assert isinstance(term.term, SurfaceVar)
        assert term.term.name == "x"
        assert isinstance(term.type, SurfaceTypeConstructor)
        assert term.type.name == "Int"

    def test_parse_annotated_application(self):
        """Parse application with type annotation."""
        term = parse_term("f x : Int")
        assert isinstance(term, SurfaceAnn)
        assert isinstance(term.term, SurfaceApp)


# =============================================================================
# Constructor Parsing Tests
# =============================================================================


class TestParseConstructor:
    """Tests for data constructor parsing."""

    def test_parse_nullary_constructor(self):
        """Parse nullary constructor."""
        term = parse_term("Nil")
        assert isinstance(term, SurfaceConstructor)
        assert term.name == "Nil"
        assert term.args == []

    def test_parse_unary_constructor(self):
        """Parse constructor with one argument."""
        term = parse_term("Succ n")
        assert isinstance(term, SurfaceConstructor)
        assert term.name == "Succ"
        assert len(term.args) == 1
        assert isinstance(term.args[0], SurfaceVar)
        assert term.args[0].name == "n"

    def test_parse_binary_constructor(self):
        """Parse constructor with two arguments."""
        term = parse_term("Cons x xs")
        assert isinstance(term, SurfaceConstructor)
        assert term.name == "Cons"
        assert len(term.args) == 2


# =============================================================================
# Case Expression Parsing Tests
# =============================================================================


class TestParseCase:
    """Tests for case expression parsing."""

    def test_parse_simple_case(self):
        """Parse simple case expression."""
        term = parse_term("case x of { True -> y }")
        assert isinstance(term, SurfaceCase)
        assert isinstance(term.scrutinee, SurfaceVar)
        assert len(term.branches) == 1

    def test_parse_case_with_pattern(self):
        """Parse case with pattern."""
        term = parse_term("case xs of { Cons x xs -> x }")
        assert isinstance(term, SurfaceCase)
        branch = term.branches[0]
        assert isinstance(branch.pattern, SurfacePattern)
        assert branch.pattern.constructor == "Cons"
        assert branch.pattern.vars == ["x", "xs"]

    def test_parse_case_multiple_branches(self):
        """Parse case with multiple branches."""
        term = parse_term("case b of { True -> x | False -> y }")
        assert isinstance(term, SurfaceCase)
        assert len(term.branches) == 2


# =============================================================================
# Type Parsing Tests
# =============================================================================


class TestParseTypes:
    """Tests for type expression parsing."""

    def test_parse_type_var(self):
        """Parse type variable."""
        tokens = lex("a")
        parser = Parser(tokens)
        ty = parser.parse_type()
        assert isinstance(ty, SurfaceTypeVar)
        assert ty.name == "a"

    def test_parse_type_constructor(self):
        """Parse type constructor."""
        tokens = lex("Int")
        parser = Parser(tokens)
        ty = parser.parse_type()
        assert isinstance(ty, SurfaceTypeConstructor)
        assert ty.name == "Int"

    def test_parse_arrow_type(self):
        """Parse arrow type."""
        tokens = lex("Int -> Bool")
        parser = Parser(tokens)
        ty = parser.parse_type()
        assert isinstance(ty, SurfaceTypeArrow)
        assert ty.arg.name == "Int"
        assert ty.ret.name == "Bool"

    def test_parse_arrow_right_associative(self):
        """Arrow type is right-associative."""
        tokens = lex("A -> B -> C")
        parser = Parser(tokens)
        ty = parser.parse_type()
        assert isinstance(ty, SurfaceTypeArrow)
        assert isinstance(ty.ret, SurfaceTypeArrow)

    def test_parse_forall_type(self):
        """Parse forall type."""
        tokens = lex("forall a. a -> a")
        parser = Parser(tokens)
        ty = parser.parse_type()
        assert isinstance(ty, SurfaceTypeForall)
        assert ty.var == "a"
        assert isinstance(ty.body, SurfaceTypeArrow)


# =============================================================================
# Declaration Parsing Tests
# =============================================================================


class TestParseDeclarations:
    """Tests for declaration parsing."""

    def test_parse_term_decl_no_type(self):
        """Parse term declaration without type."""
        decls = parse_program("x = 1")
        assert len(decls) == 1
        assert isinstance(decls[0], SurfaceTermDeclaration)
        assert decls[0].name == "x"
        assert decls[0].type_annotation is None

    def test_parse_term_decl_with_type(self):
        """Parse term declaration with type."""
        decls = parse_program("x : Int = 1")
        assert len(decls) == 1
        assert isinstance(decls[0], SurfaceTermDeclaration)
        assert decls[0].name == "x"
        assert decls[0].type_annotation is not None

    def test_parse_data_decl_simple(self):
        """Parse simple data declaration."""
        decls = parse_program("data Bool = True | False")
        assert len(decls) == 1
        assert isinstance(decls[0], SurfaceDataDeclaration)
        assert decls[0].name == "Bool"
        assert len(decls[0].constructors) == 2

    def test_parse_data_decl_with_params(self):
        """Parse data declaration with type parameters."""
        decls = parse_program("data List a = Nil | Cons a (List a)")
        assert len(decls) == 1
        assert isinstance(decls[0], SurfaceDataDeclaration)
        assert decls[0].name == "List"
        assert decls[0].params == ["a"]
        assert len(decls[0].constructors) == 2

    def test_parse_multiple_decls(self):
        """Parse multiple declarations."""
        decls = parse_program("x = 1\ny = 2")
        assert len(decls) == 2


# =============================================================================
# Error Tests
# =============================================================================


class TestParseErrors:
    """Tests for parser error handling."""

    def test_unexpected_token(self):
        """Unexpected token raises error."""
        tokens = lex("\\")
        parser = Parser(tokens)
        with pytest.raises(ParseError):
            parser.parse_term()

    def test_missing_arrow(self):
        """Missing arrow in lambda raises error."""
        with pytest.raises(ParseError):
            parse_term(r"\x x")

    def test_unclosed_paren(self):
        """Unclosed parenthesis raises error."""
        with pytest.raises(ParseError):
            parse_term("(x")


# =============================================================================
# Complex Examples
# =============================================================================


class TestComplexExamples:
    """Tests for complex parsing scenarios."""

    def test_id_function(self):
        """Parse identity function."""
        term = parse_term(r"/\a. \x:a -> x")
        assert isinstance(term, SurfaceTypeAbs)
        assert isinstance(term.body, SurfaceAbs)

    def test_compose_function(self):
        """Parse compose function."""
        term = parse_term(r"\f -> \g -> \x -> f (g x)")
        assert isinstance(term, SurfaceAbs)
        # Check nested structure
        assert isinstance(term.body, SurfaceAbs)
        assert isinstance(term.body.body, SurfaceAbs)

    def test_polymorphic_app(self):
        """Parse polymorphic function application."""
        term = parse_term("id @Int 42")
        assert isinstance(term, SurfaceApp)
        assert isinstance(term.func, SurfaceTypeApp)
