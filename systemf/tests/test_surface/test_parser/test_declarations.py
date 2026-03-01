"""Unit tests for declaration parsers.

Tests for individual declaration parsers from declarations.py.
These tests validate the grammar from syntax.md Section 7.
"""

import pytest
from systemf.surface.parser import (
    decl_parser,
    data_parser,
    term_parser,
    prim_type_parser,
    prim_op_parser,
    type_parser,
    lex,
)
from systemf.surface.types import (
    SurfaceDataDeclaration,
    SurfaceTermDeclaration,
    SurfacePrimTypeDecl,
    SurfacePrimOpDecl,
    SurfaceTypeConstructor,
    SurfaceConstructorInfo,
)


class TestDataDeclaration:
    """Test data declaration parser."""

    def test_simple_data(self):
        """Parse data Bool = True | False."""
        tokens = lex("data Bool = True | False")
        result = data_parser().parse(tokens)
        assert isinstance(result, SurfaceDataDeclaration)
        assert result.name == "Bool"
        assert len(result.constructors) == 2

    def test_data_with_param(self):
        """Parse data Maybe a = Nothing | Just a."""
        tokens = lex("data Maybe a = Nothing | Just a")
        result = data_parser().parse(tokens)
        assert isinstance(result, SurfaceDataDeclaration)
        assert result.name == "Maybe"
        assert "a" in result.params

    def test_data_with_multiple_params(self):
        """Parse data Either a b = Left a | Right b."""
        tokens = lex("data Either a b = Left a | Right b")
        result = data_parser().parse(tokens)
        assert isinstance(result, SurfaceDataDeclaration)
        assert result.name == "Either"
        assert len(result.params) == 2

    def test_data_single_constructor(self):
        """Parse data Identity a = Identity a."""
        tokens = lex("data Identity a = Identity a")
        result = data_parser().parse(tokens)
        assert isinstance(result, SurfaceDataDeclaration)
        assert len(result.constructors) == 1

    def test_recursive_data(self):
        """Parse recursive data type."""
        source = """data List a =
  Nil
  | Cons a (List a)"""
        tokens = lex(source)
        result = decl_parser().parse(tokens)
        assert isinstance(result, SurfaceDataDeclaration)
        assert result.name == "List"

    def test_data_constructor_with_args(self):
        """Parse constructor with multiple arguments."""
        tokens = lex("data Pair a b = Pair a b")
        result = data_parser().parse(tokens)
        assert isinstance(result, SurfaceDataDeclaration)
        cons = result.constructors[0]
        # Constructor should have 2 arguments
        assert len(cons.args) == 2


class TestTermDeclaration:
    """Test term (function) declaration parser."""

    def test_simple_function(self):
        """Parse x : Int = 42."""
        tokens = lex("x : Int = 42")
        result = term_parser().parse(tokens)
        assert isinstance(result, SurfaceTermDeclaration)
        assert result.name == "x"

    def test_function_with_lambda(self):
        """Parse identity : forall a. a -> a = λx → x."""
        tokens = lex("identity : forall a. a -> a = λx → x")
        result = term_parser().parse(tokens)
        assert isinstance(result, SurfaceTermDeclaration)
        assert result.name == "identity"

    def test_function_with_params(self):
        """Parse add x y : Int = x + y."""
        # Note: This syntax is shorthand for add = λx y → x + y
        tokens = lex("add : Int -> Int -> Int = λx y → x + y")
        result = term_parser().parse(tokens)
        assert isinstance(result, SurfaceTermDeclaration)
        assert result.name == "add"

    def test_polymorphic_function(self):
        """Parse map function with higher-order type."""
        tokens = lex("map : forall a b. (a -> b) -> List a -> List b = λf xs → xs")
        result = term_parser().parse(tokens)
        assert isinstance(result, SurfaceTermDeclaration)

    def test_recursive_function(self):
        """Parse recursive factorial."""
        source = """factorial : Int -> Int =
  λn → if n == 0 then 1 else n * factorial (n - 1)"""
        tokens = lex(source)
        result = term_parser().parse(tokens)
        assert isinstance(result, SurfaceTermDeclaration)


class TestPrimitiveDeclarations:
    """Test primitive type and operation declarations."""

    def test_prim_type(self):
        """Parse prim_type Int."""
        tokens = lex("prim_type Int")
        result = prim_type_parser().parse(tokens)
        assert isinstance(result, SurfacePrimTypeDecl)
        assert result.name == "Int"

    def test_prim_type_bool(self):
        """Parse prim_type Bool."""
        tokens = lex("prim_type Bool")
        result = prim_type_parser().parse(tokens)
        assert isinstance(result, SurfacePrimTypeDecl)

    def test_prim_op(self):
        """Parse prim_op int_plus : Int -> Int -> Int."""
        tokens = lex("prim_op int_plus : Int -> Int -> Int")
        result = prim_op_parser().parse(tokens)
        assert isinstance(result, SurfacePrimOpDecl)
        assert result.name == "int_plus"

    def test_prim_op_arithmetic(self):
        """Parse multiple arithmetic primitives."""
        ops = [
            "prim_op int_plus : Int -> Int -> Int",
            "prim_op int_minus : Int -> Int -> Int",
            "prim_op int_mult : Int -> Int -> Int",
        ]
        for op in ops:
            tokens = lex(op)
            result = prim_op_parser().parse(tokens)
            assert isinstance(result, SurfacePrimOpDecl)

    def test_prim_op_comparison(self):
        """Parse comparison primitives."""
        tokens = lex("prim_op int_eq : Int -> Int -> Bool")
        result = prim_op_parser().parse(tokens)
        assert isinstance(result, SurfacePrimOpDecl)


class TestDeclarationCombinations:
    """Test combining different declaration types."""

    def test_data_then_term(self):
        """Parse data then function using that type."""
        # Individual declarations, not a sequence
        data_tokens = lex("data Bool = True | False")
        term_tokens = lex("not : Bool -> Bool = λx → x")

        data_result = decl_parser().parse(data_tokens)
        term_result = decl_parser().parse(term_tokens)

        assert isinstance(data_result, SurfaceDataDeclaration)
        assert isinstance(term_result, SurfaceTermDeclaration)

    def test_multiple_primitives(self):
        """Parse multiple primitive declarations."""
        types = [
            "prim_type Int",
            "prim_type Bool",
            "prim_type String",
        ]
        for t in types:
            tokens = lex(t)
            result = decl_parser().parse(tokens)
            assert isinstance(result, SurfacePrimTypeDecl)

    def test_complete_program_structure(self):
        """Parse typical program structure."""
        # This is what a typical System F program looks like
        decls = [
            "data Bool = True | False",
            "data Maybe a = Nothing | Just a",
            "prim_type Int",
            "id : forall a. a -> a = λx → x",
            "const : forall a b. a -> b -> a = λx y → x",
        ]

        for decl in decls:
            tokens = lex(decl)
            result = decl_parser().parse(tokens)
            assert result is not None


class TestTypeParser:
    """Test the type parser (from declarations module)."""

    def test_simple_type(self):
        """Parse Int type."""
        tokens = lex("Int")
        result = type_parser().parse(tokens)
        assert isinstance(result, SurfaceTypeConstructor)
        assert result.name == "Int"

    def test_type_variable(self):
        """Parse type variable 'a'."""
        tokens = lex("a")
        result = type_parser().parse(tokens)
        assert result is not None

    def test_arrow_type(self):
        """Parse Int -> Bool."""
        tokens = lex("Int -> Bool")
        result = type_parser().parse(tokens)
        assert result is not None

    def test_forall_type(self):
        """Parse forall a. a -> a."""
        tokens = lex("forall a. a -> a")
        result = type_parser().parse(tokens)
        assert result is not None

    def test_higher_order_type(self):
        """Parse (a -> b) -> List a -> List b."""
        tokens = lex("(a -> b) -> List a -> List b")
        result = type_parser().parse(tokens)
        assert result is not None

    def test_type_application(self):
        """Parse List Int."""
        tokens = lex("List Int")
        result = type_parser().parse(tokens)
        assert isinstance(result, SurfaceTypeConstructor)

    def test_nested_forall(self):
        """Parse forall a b c. a -> b -> c -> a."""
        tokens = lex("forall a b c. a -> b -> c -> a")
        result = type_parser().parse(tokens)
        assert result is not None

    def test_unit_type(self):
        """Parse unit type ()."""
        tokens = lex("()")
        result = type_parser().parse(tokens)
        assert result is not None

    def test_tuple_type(self):
        """Parse (Int, Bool) tuple."""
        tokens = lex("(Int, Bool)")
        result = type_parser().parse(tokens)
        assert result is not None

    def test_rank2_type(self):
        """Parse rank-2 type (forall a. a -> a) -> Int."""
        tokens = lex("(forall a. a -> a) -> Int")
        result = type_parser().parse(tokens)
        assert result is not None
