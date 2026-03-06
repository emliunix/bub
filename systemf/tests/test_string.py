"""Integration tests for String primitive type support.

Tests cover the complete pipeline: parsing, elaboration, type checking, and evaluation.
"""

import pytest

import pytest
from systemf.core.ast import Lit, Global
from systemf.core.checker import TypeChecker
from systemf.core.context import Context
from systemf.core.types import PrimitiveType, TypeArrow
from systemf.eval.machine import Evaluator
from systemf.eval.value import VPrim
from systemf.surface.pipeline import elaborate_module
from systemf.surface.parser import lex
from systemf.surface.parser import Parser, parse_expression
from systemf.surface.parser.types import StringToken


class TestStringParsing:
    """Tests for string literal parsing."""

    def test_simple_string_literal(self):
        """Parse a simple string literal."""
        source = '"hello"'
        tokens = lex(source)

        # Should have STRING token and EOF
        assert any(isinstance(t, StringToken) for t in tokens)

        # Parse as term
        term = parse_expression(source)
        assert isinstance(term.value, str)
        assert term.value == "hello"

    def test_string_with_spaces(self):
        """Parse string containing spaces."""
        source = '"hello world"'
        term = parse_expression(source)
        assert term.value == "hello world"

    def test_empty_string(self):
        """Parse empty string."""
        source = '""'
        term = parse_expression(source)
        assert term.value == ""

    def test_string_with_escape_sequences(self):
        """Parse string with escape sequences."""
        source = r'"hello\nworld\ttab\"quote"'
        tokens = lex(source)

        # Find the STRING token
        string_token = None
        for t in tokens:
            if isinstance(t, StringToken):
                string_token = t
                break

        assert string_token is not None
        # Escape sequences should be processed
        assert "\n" in string_token.value
        assert "\t" in string_token.value
        assert '"' in string_token.value


@pytest.mark.skip(reason="Uses old elaborator API")
class TestStringElaboration:
    """Tests for surface to core AST elaboration."""

    def test_string_literal_elaboration(self):
        """Elaborate string literal to core Lit."""
        source = 'x = "hello"'

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        module = elaborate(surface_decls)

        assert len(module.declarations) == 1
        decl = module.declarations[0]
        assert isinstance(decl.body, Lit)
        assert decl.body.value == "hello"

    def test_string_in_let_binding(self):
        """Elaborate string in let binding."""
        source = r"""
        msg = "hello"
        """

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        module = elaborate(surface_decls)

        assert len(module.declarations) == 1
        assert module.declarations[0].name == "msg"
        assert isinstance(module.declarations[0].body, Lit)
        assert module.declarations[0].body.value == "hello"


class TestStringTypeChecking:
    """Tests for string literal type checking."""

    def test_string_literal_type_inference(self):
        """Type checker infers String type for string literals."""
        # Setup: Create a type checker with String type registered
        checker = TypeChecker(primitive_types={"String": PrimitiveType("String")})
        ctx = Context.empty()

        # Create a string literal
        string_lit = Lit(prim_type="String", value="hello")

        # Infer type
        ty = checker.infer(ctx, string_lit)

        assert isinstance(ty, PrimitiveType)
        assert ty.name == "String"

    @pytest.mark.skip(reason="Uses old elaborator API")
    def test_string_type_from_prelude(self):
        """Type check string using prelude-declared String type."""
        source = """
        prim_type String
        msg = "hello"
        """

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        module = elaborate(surface_decls)

        checker = TypeChecker(primitive_types={"String": PrimitiveType("String")})
        types = checker.check_program(module.declarations)

        assert "msg" in types
        assert isinstance(types["msg"], PrimitiveType)
        assert types["msg"].name == "String"


class TestStringEvaluation:
    """Tests for string literal evaluation."""

    def test_string_literal_evaluation(self):
        """Evaluate string literal to VPrim value."""
        string_lit = Lit(prim_type="String", value="hello")

        evaluator = Evaluator()
        result = evaluator.evaluate(string_lit)

        assert isinstance(result, VPrim)
        assert result.value == "hello"

    def test_empty_string_evaluation(self):
        """Evaluate empty string."""
        string_lit = Lit(prim_type="String", value="")

        evaluator = Evaluator()
        result = evaluator.evaluate(string_lit)

        assert isinstance(result, VPrim)
        assert result.value == ""

    def test_string_in_program(self):
        """Evaluate program with string declaration."""
        from systemf.core.ast import TermDeclaration

        decls = [
            TermDeclaration("msg", None, Lit(prim_type="String", value="hello world")),
        ]

        evaluator = Evaluator()
        values = evaluator.evaluate_program(decls)

        assert "msg" in values
        assert isinstance(values["msg"], VPrim)
        assert values["msg"].value == "hello world"


class TestStringPrimitiveOperations:
    """Tests for string primitive operations."""

    def test_string_concat_operation(self):
        """Test string concatenation primitive."""
        from systemf.core.ast import App, PrimOp

        # $prim.string_concat "hello" " world"
        concat_op = PrimOp(name="string_concat")
        hello = Lit(prim_type="String", value="hello")
        world = Lit(prim_type="String", value=" world")
        expr = App(func=App(func=concat_op, arg=hello), arg=world)

        evaluator = Evaluator()
        result = evaluator.evaluate(expr)

        assert isinstance(result, VPrim)
        assert result.value == "hello world"

    def test_string_length_operation(self):
        """Test string length primitive."""
        from systemf.core.ast import App, PrimOp

        # $prim.string_length "hello" "ignored"
        length_op = PrimOp(name="string_length")
        hello = Lit(prim_type="String", value="hello")
        ignored = Lit(prim_type="String", value="ignored")
        expr = App(func=App(func=length_op, arg=hello), arg=ignored)

        evaluator = Evaluator()
        result = evaluator.evaluate(expr)

        assert isinstance(result, VPrim)
        assert result.value == 5

    def test_string_concat_type_checking(self):
        """Type check string concatenation."""
        from systemf.core.ast import App, PrimOp
        from systemf.core.types import TypeArrow

        # Setup type checker with String type and string_concat primitive
        string_type = PrimitiveType("String")
        concat_type = TypeArrow(string_type, TypeArrow(string_type, string_type))

        checker = TypeChecker(
            primitive_types={"String": string_type},
            global_types={"$prim.string_concat": concat_type},
        )
        ctx = Context.empty()

        # $prim.string_concat "hello" " world"
        concat_op = PrimOp(name="string_concat")
        hello = Lit(prim_type="String", value="hello")
        world = Lit(prim_type="String", value=" world")
        expr = App(func=App(func=concat_op, arg=hello), arg=world)

        ty = checker.infer(ctx, expr)

        assert isinstance(ty, PrimitiveType)
        assert ty.name == "String"


@pytest.mark.skip(reason="Uses old elaborator API")
class TestStringFullPipeline:
    """End-to-end tests for complete String pipeline."""

    def test_string_literal_full_pipeline(self):
        """Full pipeline: parse, elaborate, type check, evaluate string literal."""
        source = """
        prim_type String
        greeting = "hello"
        """

        # Parse
        tokens = lex(source)
        surface_decls = Parser(tokens).parse()

        # Elaborate
        module = elaborate(surface_decls)

        # Type check
        checker = TypeChecker(primitive_types={"String": PrimitiveType("String")})
        types = checker.check_program(module.declarations)

        # Evaluate
        evaluator = Evaluator()
        values = evaluator.evaluate_program(module.declarations)

        # Verify
        assert "greeting" in types
        assert isinstance(types["greeting"], PrimitiveType)
        assert types["greeting"].name == "String"

        assert "greeting" in values
        assert isinstance(values["greeting"], VPrim)
        assert values["greeting"].value == "hello"

    def test_string_concat_full_pipeline(self):
        """Full pipeline with string concatenation."""
        from systemf.core.ast import App, PrimOp, TermDeclaration

        # Build core declarations directly
        string_type = PrimitiveType("String")
        concat_type = TypeArrow(string_type, TypeArrow(string_type, string_type))

        # hello = "hello"
        # world = "world"
        # greeting = $prim.string_concat hello world
        core_decls = [
            TermDeclaration("hello", string_type, Lit(prim_type="String", value="hello")),
            TermDeclaration("world", string_type, Lit(prim_type="String", value="world")),
        ]

        concat_op = PrimOp(name="string_concat")
        hello_ref = Global(name="hello")
        world_ref = Global(name="world")
        greeting_expr = App(func=App(func=concat_op, arg=hello_ref), arg=world_ref)
        core_decls.append(TermDeclaration("greeting", string_type, greeting_expr))

        # Type check
        checker = TypeChecker(
            primitive_types={"String": string_type},
            global_types={"$prim.string_concat": concat_type},
        )
        types = checker.check_program(core_decls)

        # Evaluate
        evaluator = Evaluator()
        values = evaluator.evaluate_program(core_decls)

        # Verify
        assert "greeting" in values
        assert isinstance(values["greeting"], VPrim)
        assert values["greeting"].value == "helloworld"

    @pytest.mark.skip(reason="Uses old elaborator API")
    def test_multiple_strings_in_program(self):
        """Program with multiple string declarations."""
        source = """
        prim_type String
        
        first = "first"
        second = "second"
        third = "third"
        """

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        module = elaborate(surface_decls)

        checker = TypeChecker(primitive_types={"String": PrimitiveType("String")})
        types = checker.check_program(module.declarations)

        evaluator = Evaluator()
        values = evaluator.evaluate_program(module.declarations)

        assert len(values) == 3
        assert values["first"].value == "first"
        assert values["second"].value == "second"
        assert values["third"].value == "third"

    @pytest.mark.skip(reason="Uses old elaborator API")
    def test_string_with_special_characters(self):
        """Parse and evaluate string with special characters."""
        source = r"""
        prim_type String
        msg = "hello\tworld\nline2"
        """

        tokens = lex(source)
        surface_decls = Parser(tokens).parse()
        module = elaborate(surface_decls)

        evaluator = Evaluator()
        values = evaluator.evaluate_program(module.declarations)

        assert "msg" in values
        assert isinstance(values["msg"], VPrim)
        assert "\t" in values["msg"].value
        assert "\n" in values["msg"].value


class TestStringErrorCases:
    """Tests for error conditions."""

    def test_unclosed_string(self):
        """Parser should reject unclosed string."""
        source = '"hello'

        with pytest.raises(Exception):
            tokens = lex(source)
            Parser(tokens).parse_expression()

    def test_string_concat_with_wrong_types(self):
        """String concat should fail with wrong argument types."""
        from systemf.core.ast import App, PrimOp, Lit

        concat_op = PrimOp(name="string_concat")
        hello = Lit(prim_type="String", value="hello")
        number = Lit(prim_type="Int", value=42)
        expr = App(func=App(func=concat_op, arg=hello), arg=number)

        evaluator = Evaluator()

        with pytest.raises(RuntimeError, match="string_concat expects String arguments"):
            evaluator.evaluate(expr)

    def test_string_length_with_wrong_type(self):
        """String length should fail with wrong argument type."""
        from systemf.core.ast import App, PrimOp, Lit

        length_op = PrimOp(name="string_length")
        number = Lit(prim_type="Int", value=42)
        ignored = Lit(prim_type="Int", value=0)
        expr = App(func=App(func=length_op, arg=number), arg=ignored)

        evaluator = Evaluator()

        with pytest.raises(RuntimeError, match="string_length expects String argument"):
            evaluator.evaluate(expr)
