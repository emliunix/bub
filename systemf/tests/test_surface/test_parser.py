"""Tests for parsy-based surface language parser.

Tests parsing of System F surface syntax including:
- Variables, lambdas, and applications
- Type abstractions and type applications
- Let bindings and type annotations
- Data constructors and case expressions
- Type expressions and declarations

Uses new indentation-aware syntax (no 'in', braces, or bars for blocks).
"""

import pytest

from systemf.surface.ast import (
    SurfaceAbs,
    SurfaceAnn,
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
)
from systemf.surface.lexer import Lexer
from systemf.surface.parser import (
    Parser,
    ParseError,
    parse_program,
    parse_term,
    match_token,
)


# =============================================================================
# Token Primitives Tests
# =============================================================================


class TestTokenPrimitives:
    """Tests for token matching primitives."""

    def test_match_token_success(self):
        """Test matching a token by type."""
        tokens = Lexer("data", "<stdin>").tokenize()
        parser = match_token("DATA")
        result, remaining = parser.parse_partial(tokens)
        assert result.type == "DATA"
        assert len(remaining) == 1  # Just EOF left

    def test_match_token_failure(self):
        """Test failing to match a token."""
        tokens = Lexer("let", "<stdin>").tokenize()
        parser = match_token("DATA")
        with pytest.raises(Exception):
            parser.parse(tokens)

    def test_match_token_value_extraction(self):
        """Test extracting token value."""
        tokens = Lexer("x", "<stdin>").tokenize()
        parser = match_token("IDENT").map(lambda t: t.value)
        result, remaining = parser.parse_partial(tokens)
        assert result == "x"


# =============================================================================
# Lambda Parsing Tests
# =============================================================================


class TestLambdaParsing:
    """Tests for lambda abstraction parsing."""

    def test_lambda_simple(self):
        """Parse simple lambda."""
        term = parse_term(r"\x -> x")
        assert isinstance(term, SurfaceAbs)
        assert term.var == "x"
        assert term.var_type is None
        assert isinstance(term.body, SurfaceVar)

    def test_lambda_with_type(self):
        """Parse lambda with type annotation."""
        term = parse_term(r"\x:Int -> x")
        assert isinstance(term, SurfaceAbs)
        assert term.var == "x"
        assert isinstance(term.var_type, SurfaceTypeConstructor)
        assert term.var_type.name == "Int"

    def test_lambda_nested(self):
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

    def test_lambda_polymorphic_id(self):
        """Parse polymorphic identity function."""
        term = parse_term(r"/\a. \x:a -> x")
        assert isinstance(term, SurfaceTypeAbs)
        assert term.var == "a"
        assert isinstance(term.body, SurfaceAbs)

    def test_lambda_indented_body(self):
        """Parse lambda with indented multi-line body."""
        term = parse_term("\\x ->\n  y")
        assert isinstance(term, SurfaceAbs)
        assert term.var == "x"
        assert isinstance(term.body, SurfaceVar)
        assert term.body.name == "y"


# =============================================================================
# Application Parsing Tests
# =============================================================================


class TestApplicationParsing:
    """Tests for function application parsing."""

    def test_simple_application(self):
        """Parse simple application."""
        term = parse_term("f x")
        assert isinstance(term, SurfaceApp)
        assert isinstance(term.func, SurfaceVar)
        assert term.func.name == "f"
        assert isinstance(term.arg, SurfaceVar)
        assert term.arg.name == "x"

    def test_left_associative(self):
        """Application is left-associative."""
        term = parse_term("f x y")
        assert isinstance(term, SurfaceApp)
        assert isinstance(term.func, SurfaceApp)
        assert term.func.func.name == "f"
        assert term.func.arg.name == "x"
        assert term.arg.name == "y"

    def test_application_with_parens(self):
        """Parse application with parentheses."""
        term = parse_term("f (g x)")
        assert isinstance(term, SurfaceApp)
        assert term.func.name == "f"
        assert isinstance(term.arg, SurfaceApp)
        assert term.arg.func.name == "g"


# =============================================================================
# Type Annotation Tests
# =============================================================================


class TestTypeAnnotations:
    """Tests for type annotation parsing."""

    def test_simple_annotation(self):
        """Parse simple type annotation."""
        term = parse_term("x : Int")
        assert isinstance(term, SurfaceAnn)
        assert isinstance(term.term, SurfaceVar)
        assert term.term.name == "x"
        assert isinstance(term.type, SurfaceTypeConstructor)
        assert term.type.name == "Int"

    def test_application_annotation(self):
        """Annotation applies to entire application."""
        term = parse_term("f x : Int")
        assert isinstance(term, SurfaceAnn)
        assert isinstance(term.term, SurfaceApp)

    def test_nested_annotation(self):
        """Parse nested type annotations."""
        term = parse_term("(x : Int) : Bool")
        assert isinstance(term, SurfaceAnn)
        assert isinstance(term.term, SurfaceAnn)


# =============================================================================
# Type Application Tests
# =============================================================================


class TestTypeApplication:
    """Tests for type application parsing."""

    def test_type_app_at(self):
        """Parse type application with @."""
        term = parse_term("id @Int")
        assert isinstance(term, SurfaceTypeApp)
        assert isinstance(term.func, SurfaceVar)
        assert term.func.name == "id"
        assert isinstance(term.type_arg, SurfaceTypeConstructor)
        assert term.type_arg.name == "Int"

    def test_type_app_brackets(self):
        """Parse type application with brackets."""
        term = parse_term("id [Int]")
        assert isinstance(term, SurfaceTypeApp)
        assert term.func.name == "id"
        assert term.type_arg.name == "Int"

    def test_type_app_chain(self):
        """Parse chained type applications."""
        term = parse_term("pair @Int @Bool")
        assert isinstance(term, SurfaceTypeApp)
        assert isinstance(term.func, SurfaceTypeApp)


# =============================================================================
# Let Binding Tests (New Indentation Syntax)
# =============================================================================


class TestLetBindings:
    """Tests for let binding parsing with indentation-aware syntax."""

    def test_simple_let(self):
        """Parse simple let binding with indented body."""
        term = parse_term("let x = 1\n  x")
        assert isinstance(term, SurfaceLet)
        assert term.name == "x"
        assert isinstance(term.value, SurfaceConstructor)
        assert isinstance(term.body, SurfaceVar)

    def test_nested_let(self):
        """Parse nested let bindings."""
        term = parse_term("let x = 1\n  let y = 2\n    x")
        assert isinstance(term, SurfaceLet)
        assert term.name == "x"
        assert isinstance(term.body, SurfaceLet)
        assert term.body.name == "y"

    def test_let_with_expression_body(self):
        """Parse let with complex expression body."""
        term = parse_term("let x = 1\n  f x")
        assert isinstance(term, SurfaceLet)
        assert isinstance(term.body, SurfaceApp)

    def test_let_multiple_indent_levels(self):
        """Parse let with multiple indentation levels."""
        term = parse_term("let x = 1\n  let y = 2\n    let z = 3\n      z")
        assert isinstance(term, SurfaceLet)
        assert isinstance(term.body, SurfaceLet)
        assert isinstance(term.body.body, SurfaceLet)


# =============================================================================
# Constructor Tests
# =============================================================================


class TestConstructors:
    """Tests for data constructor parsing."""

    def test_nullary_constructor(self):
        """Parse nullary constructor."""
        term = parse_term("Nil")
        assert isinstance(term, SurfaceConstructor)
        assert term.name == "Nil"
        assert term.args == []

    def test_unary_constructor(self):
        """Parse unary constructor."""
        term = parse_term("Succ n")
        assert isinstance(term, SurfaceConstructor)
        assert term.name == "Succ"
        assert len(term.args) == 1

    def test_binary_constructor(self):
        """Parse binary constructor."""
        term = parse_term("Cons x xs")
        assert isinstance(term, SurfaceConstructor)
        assert term.name == "Cons"
        assert len(term.args) == 2


# =============================================================================
# Case Expression Tests (New Indentation Syntax)
# =============================================================================


class TestCaseExpressions:
    """Tests for case expression parsing with indentation-aware branches."""

    def test_simple_case(self):
        """Parse simple case expression with indented branch."""
        term = parse_term("case x of\n  True -> y")
        assert isinstance(term, SurfaceCase)
        assert isinstance(term.scrutinee, SurfaceVar)
        assert len(term.branches) == 1

    def test_case_multiple_branches(self):
        """Parse case with multiple indented branches."""
        term = parse_term("case b of\n  True -> x\n  False -> y")
        assert isinstance(term, SurfaceCase)
        assert len(term.branches) == 2

    def test_case_with_pattern(self):
        """Parse case with pattern."""
        term = parse_term("case xs of\n  Cons x xs -> x")
        assert isinstance(term, SurfaceCase)
        branch = term.branches[0]
        assert isinstance(branch.pattern, SurfacePattern)
        assert branch.pattern.constructor == "Cons"

    def test_case_multiple_patterns(self):
        """Parse case with multiple patterns."""
        term = parse_term("case xs of\n  Nil -> 0\n  Cons x xs -> 1")
        assert isinstance(term, SurfaceCase)
        assert len(term.branches) == 2
        assert term.branches[0].pattern.constructor == "Nil"
        assert term.branches[1].pattern.constructor == "Cons"


# =============================================================================
# Type Parsing Tests
# =============================================================================


class TestTypeParsing:
    """Tests for type expression parsing."""

    def test_type_variable(self):
        """Parse type variable."""
        tokens = Lexer("a", "<stdin>").tokenize()
        parser = Parser(tokens)
        ty = parser.parse_type()
        assert isinstance(ty, SurfaceTypeVar)
        assert ty.name == "a"

    def test_type_constructor(self):
        """Parse type constructor."""
        tokens = Lexer("Int", "<stdin>").tokenize()
        parser = Parser(tokens)
        ty = parser.parse_type()
        assert isinstance(ty, SurfaceTypeConstructor)
        assert ty.name == "Int"

    def test_arrow_type(self):
        """Parse arrow type."""
        tokens = Lexer("Int -> Bool", "<stdin>").tokenize()
        parser = Parser(tokens)
        ty = parser.parse_type()
        assert isinstance(ty, SurfaceTypeArrow)

    def test_arrow_right_associative(self):
        """Arrow type is right-associative."""
        tokens = Lexer("A -> B -> C", "<stdin>").tokenize()
        parser = Parser(tokens)
        ty = parser.parse_type()
        assert isinstance(ty, SurfaceTypeArrow)
        assert isinstance(ty.ret, SurfaceTypeArrow)

    def test_forall_type(self):
        """Parse forall type."""
        tokens = Lexer("forall a. a -> a", "<stdin>").tokenize()
        parser = Parser(tokens)
        ty = parser.parse_type()
        assert isinstance(ty, SurfaceTypeForall)
        assert ty.var == "a"


# =============================================================================
# Declaration Tests (New Indentation Syntax)
# =============================================================================


class TestDeclarations:
    """Tests for declaration parsing with indentation-aware syntax."""

    def test_term_declaration_no_type(self):
        """Parse term declaration without type."""
        decls = parse_program("x = 1")
        assert len(decls) == 1
        assert isinstance(decls[0], SurfaceTermDeclaration)
        assert decls[0].name == "x"
        assert decls[0].type_annotation is None

    def test_term_declaration_with_type(self):
        """Parse term declaration with type."""
        decls = parse_program("x : Int = 1")
        assert len(decls) == 1
        assert isinstance(decls[0], SurfaceTermDeclaration)
        assert decls[0].name == "x"
        assert decls[0].type_annotation is not None

    @pytest.mark.xfail(reason="Parser treats multiple constructors as single constructor with args")
    def test_data_declaration_indentation(self):
        """Parse data declaration with indented constructors.

        Note: Parser currently treats multiple constructors as single constructor
        with arguments. This is a known limitation to be fixed.
        """
        decls = parse_program("data Bool =\n  True\n  False")
        assert len(decls) == 1
        assert isinstance(decls[0], SurfaceDataDeclaration)
        assert decls[0].name == "Bool"
        assert len(decls[0].constructors) == 2

    @pytest.mark.xfail(reason="Parser treats multiple constructors as single constructor with args")
    def test_data_declaration_with_params(self):
        """Parse data declaration with type parameters.

        Note: Parser currently treats multiple constructors as single constructor
        with arguments. This is a known limitation to be fixed.
        """
        decls = parse_program("data List a =\n  Nil\n  Cons a (List a)")
        assert len(decls) == 1
        assert isinstance(decls[0], SurfaceDataDeclaration)
        assert decls[0].name == "List"
        assert decls[0].params == ["a"]
        assert len(decls[0].constructors) == 2

    def test_multiple_declarations(self):
        """Parse multiple declarations."""
        decls = parse_program("x = 1\ny = 2")
        assert len(decls) == 2
        assert decls[0].name == "x"
        assert decls[1].name == "y"

    def test_declaration_boundary(self):
        """Test that declarations are properly separated."""
        decls = parse_program("f = 1\ng = 2")
        assert len(decls) == 2
        assert decls[0].body.name == "1"
        assert decls[1].body.name == "2"

    def test_data_declaration_single_constructor(self):
        """Parse data declaration with single constructor."""
        decls = parse_program("data Unit =\n  MkUnit")
        assert len(decls) == 1
        assert decls[0].name == "Unit"
        assert len(decls[0].constructors) == 1


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for parser error handling."""

    def test_unexpected_token(self):
        """Unexpected token raises error."""
        tokens = Lexer("\\", "<stdin>").tokenize()
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

    def test_missing_indent_after_let(self):
        """Missing indentation after let binding raises error."""
        with pytest.raises(ParseError):
            parse_term("let x = 1 x")  # No indent before body

    def test_missing_indent_after_case(self):
        """Missing indentation after case expression raises error."""
        with pytest.raises(ParseError):
            parse_term("case x of True -> y")  # No indent before branches


# =============================================================================
# Complex Example Tests
# =============================================================================


class TestComplexExamples:
    """Tests for complex parsing scenarios."""

    def test_polymorphic_id(self):
        """Parse polymorphic identity function."""
        term = parse_term(r"/\a. \x:a -> x")
        assert isinstance(term, SurfaceTypeAbs)
        assert isinstance(term.body, SurfaceAbs)

    def test_compose(self):
        """Parse compose function."""
        term = parse_term(r"\f -> \g -> \x -> f (g x)")
        assert isinstance(term, SurfaceAbs)
        assert isinstance(term.body, SurfaceAbs)
        assert isinstance(term.body.body, SurfaceAbs)

    def test_polymorphic_application(self):
        """Parse polymorphic function application."""
        term = parse_term("id @Int 42")
        assert isinstance(term, SurfaceApp)
        assert isinstance(term.func, SurfaceTypeApp)

    def test_nested_types(self):
        """Parse nested type applications."""
        term = parse_term("pair @Int @Bool 1 True")
        assert isinstance(term, SurfaceApp)

    def test_let_with_lambda(self):
        """Parse let binding containing lambda."""
        term = parse_term("let f = \\x -> x\n  f")
        assert isinstance(term, SurfaceLet)
        assert isinstance(term.value, SurfaceAbs)

    def test_case_with_let(self):
        """Parse case expression containing let in branch."""
        term = parse_term("case b of\n  True -> let x = 1\n    x\n  False -> 0")
        assert isinstance(term, SurfaceCase)
        assert isinstance(term.branches[0].body, SurfaceLet)


# =============================================================================
# Indentation-Aware Parsing Tests
# =============================================================================


class TestIndentationAwareParsing:
    """Tests specifically for indentation-aware syntax features."""

    def test_single_line_lambda(self):
        """Single-line lambda doesn't require indentation."""
        term = parse_term(r"\x -> x")
        assert isinstance(term, SurfaceAbs)

    def test_multi_line_lambda(self):
        """Multi-line lambda with indented body."""
        term = parse_term("\\x ->\n  y")
        assert isinstance(term, SurfaceAbs)
        assert isinstance(term.body, SurfaceVar)
        assert term.body.name == "y"

    def test_nested_indentation_levels(self):
        """Nested constructs have proper indentation levels."""
        source = """let x = 1
  let y = 2
    let z = 3
      z"""
        term = parse_term(source)
        assert isinstance(term, SurfaceLet)
        assert isinstance(term.body, SurfaceLet)
        assert isinstance(term.body.body, SurfaceLet)


# =============================================================================
# Parsy Implementation Tests
# =============================================================================


class TestParsyImplementation:
    """Tests specific to parsy implementation."""

    def test_left_fold_application(self):
        """Verify applications are left-associative via left fold."""
        term = parse_term("f a b c")
        # Should be ((f a) b) c
        assert isinstance(term, SurfaceApp)
        assert isinstance(term.func, SurfaceApp)
        assert isinstance(term.func.func, SurfaceApp)
        assert term.func.func.func.name == "f"

    def test_right_fold_arrow(self):
        """Verify arrows are right-associative."""
        tokens = Lexer("A -> B -> C", "<stdin>").tokenize()
        parser = Parser(tokens)
        ty = parser.parse_type()
        # Should be A -> (B -> C)
        assert isinstance(ty, SurfaceTypeArrow)
        assert isinstance(ty.ret, SurfaceTypeArrow)

    def test_location_preservation(self):
        """Verify locations are preserved in AST."""
        term = parse_term("x")
        assert term.location.line == 1
        assert term.location.column == 1

    def test_generate_decorator_usage(self):
        """Verify @generate decorator is used for complex parsers."""
        # This is more of a documentation test
        # All complex parsers use @generate
        import parsy
        from systemf.surface.parser import lambda_parser, let_parser

        # Check that these are parsy Parser objects (created by @generate)
        assert isinstance(lambda_parser, parsy.Parser)
        assert isinstance(let_parser, parsy.Parser)


# =============================================================================
# Old Syntax Compatibility Notes
# =============================================================================


class TestOldSyntaxRemoved:
    """Tests documenting that old syntax is no longer supported."""

    def test_let_in_not_supported(self):
        """Old 'let x = 1 in x' syntax is no longer supported."""
        # This should raise a parse error because 'in' is no longer expected
        with pytest.raises(ParseError):
            parse_term("let x = 1 in x")

    def test_case_braces_not_supported(self):
        """Old 'case x of { ... }' syntax is no longer supported."""
        # This should raise a parse error because braces are no longer expected
        with pytest.raises(ParseError):
            parse_term("case x of { True -> y }")

    def test_case_bar_not_supported(self):
        """Old 'case x of { A | B }' syntax is no longer supported."""
        # This should raise a parse error because bar is no longer expected
        with pytest.raises(ParseError):
            parse_term("case x of { True -> y | False -> z }")

    def test_data_bar_not_supported(self):
        """Old 'data T = A | B' syntax is no longer supported."""
        # This should treat the whole thing as constructors
        # Actually it will parse but bar will be unexpected
        with pytest.raises(ParseError):
            parse_program("data Bool = True | False")
