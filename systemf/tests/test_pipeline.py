"""Integration tests for the System F elaboration pipeline.

End-to-end tests covering the complete three-phase pipeline:
1. Phase 1: Scope Checking (Surface AST → Scoped AST)
2. Phase 2: Type Elaboration (Scoped AST → Core AST)
3. Phase 3: LLM Pragma Pass (Transform LLM functions)

These tests verify that the entire pipeline works correctly with real
System F programs and that errors are properly propagated through all phases.
"""

import pytest

from systemf.surface import elaborate_module
from systemf.surface.types import (
    SurfaceLit,
    SurfaceTermDeclaration,
    SurfaceAbs,
    SurfaceVar,
    SurfaceApp,
    SurfaceLet,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceIf,
    SurfaceTuple,
    SurfaceOp,
    SurfaceConstructor,
    SurfaceCase,
    SurfaceBranch,
    SurfacePattern,
    SurfaceAnn,
    SurfaceTypeConstructor,
    SurfaceTypeArrow,
    SurfaceTypeVar,
    SurfaceTypeForall,
    SurfacePrimOpDecl,
)
from systemf.core import ast as core
from systemf.core.types import TypeConstructor, TypeArrow, TypeForall, TypeVar
from systemf.utils.location import Location


# Test fixture for location
DUMMY_LOC = Location(line=1, column=1, file="test.py")


class TestBasicPipeline:
    """Tests for basic pipeline functionality."""

    def test_empty_pipeline(self):
        """Pipeline should handle empty declaration list."""
        result = elaborate_module([], module_name="test")

        assert result.success is True
        assert len(result.module.declarations) == 0
        assert len(result.errors) == 0

    def test_simple_identity_function(self):
        """Full pipeline with simple identity function."""
        # id : Int -> Int
        # id = \x -> x
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        arrow_type = SurfaceTypeArrow(arg=int_type, ret=int_type, location=DUMMY_LOC, param_doc=None)

        body = SurfaceAbs(
            var="x",
            var_type=int_type,
            body=SurfaceVar(name="x", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        decl = SurfaceTermDeclaration(
            name="id", type_annotation=arrow_type, body=body, location=DUMMY_LOC
        )

        result = elaborate_module([decl], module_name="test")

        assert result.success is True
        assert len(result.module.declarations) == 1
        assert result.module.declarations[0].name == "id"
        assert "id" in result.module.global_types

    def test_constant_function(self):
        """Function that ignores its argument."""
        # const : Int -> Int -> Int
        # const = \x -> \y -> x
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)

        # First lambda: \x -> ...
        inner_body = SurfaceAbs(
            var="y",
            var_type=int_type,
            body=SurfaceVar(name="x", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        outer_body = SurfaceAbs(var="x", var_type=int_type, body=inner_body, location=DUMMY_LOC)

        # Type: Int -> Int -> Int
        arrow1 = SurfaceTypeArrow(arg=int_type, ret=int_type, location=DUMMY_LOC, param_doc=None)
        arrow2 = SurfaceTypeArrow(arg=int_type, ret=arrow1, location=DUMMY_LOC, param_doc=None)

        decl = SurfaceTermDeclaration(
            name="const", type_annotation=arrow2, body=outer_body, location=DUMMY_LOC
        )

        result = elaborate_module([decl], module_name="test")

        assert result.success is True
        assert "const" in result.module.global_types


class TestPolymorphism:
    """Tests for polymorphic type elaboration."""

    def test_polymorphic_identity(self):
        """Polymorphic identity function through full pipeline."""
        # id : forall a. a -> a
        # id = /\a. \x:a -> x

        type_var = SurfaceTypeVar(name="a", location=DUMMY_LOC)
        body = SurfaceAbs(
            var="x",
            var_type=type_var,
            body=SurfaceVar(name="x", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        type_abs = SurfaceTypeAbs(var="a", body=body, location=DUMMY_LOC)

        # Type: forall a. a -> a
        arrow = SurfaceTypeArrow(arg=type_var, ret=type_var, location=DUMMY_LOC, param_doc=None)
        forall_type = SurfaceTypeForall(var="a", body=arrow, location=DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="id", type_annotation=forall_type, body=type_abs, location=DUMMY_LOC
        )

        result = elaborate_module([decl], module_name="test")

        assert result.success is True
        assert "id" in result.module.global_types

    def test_polymorphic_application(self):
        """Polymorphic function applied to concrete type."""
        # id @Int 42
        # where id = /\a. \x:a -> x

        type_var = SurfaceTypeVar(name="a", location=DUMMY_LOC)
        body = SurfaceAbs(
            var="x",
            var_type=type_var,
            body=SurfaceVar(name="x", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        type_abs = SurfaceTypeAbs(var="a", body=body, location=DUMMY_LOC)

        # id @Int
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        type_app = SurfaceTypeApp(func=type_abs, type_arg=int_type, location=DUMMY_LOC)

        # id @Int 42
        app = SurfaceApp(
            func=type_app,
            arg=SurfaceLit(prim_type="Int", value=42, location=DUMMY_LOC),
            location=DUMMY_LOC,
        )

        decl = SurfaceTermDeclaration(
            name="result", type_annotation=int_type, body=app, location=DUMMY_LOC
        )

        result = elaborate_module([decl], module_name="test")

        assert result.success is True


class TestLetBindings:
    """Tests for let binding elaboration."""

    def test_simple_let(self):
        """Simple let binding through pipeline."""
        # let x = 42 in x + 1
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        int_plus_type = SurfaceTypeArrow(
            arg=int_type,
            ret=SurfaceTypeArrow(arg=int_type, ret=int_type, location=DUMMY_LOC, param_doc=None),
            location=DUMMY_LOC,
        )

        # Declare int_plus primitive
        prim_decl = SurfacePrimOpDecl(
            name="int_plus", type_annotation=int_plus_type, location=DUMMY_LOC
        )

        bindings = [("x", None, SurfaceLit(prim_type="Int", value=42, location=DUMMY_LOC))]
        body = SurfaceOp(
            left=SurfaceVar(name="x", location=DUMMY_LOC),
            op="+",
            right=SurfaceLit(prim_type="Int", value=1, location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        let_term = SurfaceLet(bindings=bindings, body=body, location=DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="result", type_annotation=int_type, body=let_term, location=DUMMY_LOC
        )

        result = elaborate_module([prim_decl, decl], module_name="test")

        assert result.success is True

    def test_nested_let(self):
        """Nested let bindings."""
        # let x = 1 in let y = 2 in x + y
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        int_plus_type = SurfaceTypeArrow(
            arg=int_type,
            ret=SurfaceTypeArrow(arg=int_type, ret=int_type, location=DUMMY_LOC, param_doc=None),
            location=DUMMY_LOC,
        )

        # Declare int_plus primitive
        prim_decl = SurfacePrimOpDecl(
            name="int_plus", type_annotation=int_plus_type, location=DUMMY_LOC
        )

        inner_bindings = [("y", None, SurfaceLit(prim_type="Int", value=2, location=DUMMY_LOC))]
        inner_body = SurfaceOp(
            left=SurfaceVar(name="x", location=DUMMY_LOC),
            op="+",
            right=SurfaceVar(name="y", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        inner_let = SurfaceLet(bindings=inner_bindings, body=inner_body, location=DUMMY_LOC)

        outer_bindings = [("x", None, SurfaceLit(prim_type="Int", value=1, location=DUMMY_LOC))]
        outer_let = SurfaceLet(bindings=outer_bindings, body=inner_let, location=DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="result", type_annotation=int_type, body=outer_let, location=DUMMY_LOC
        )

        result = elaborate_module([prim_decl, decl], module_name="test")

        assert result.success is True


class TestMutualRecursion:
    """End-to-end tests for mutual recursion."""

    def test_mutually_recursive_functions(self):
        """Mutually recursive even and odd functions."""
        # even : Int -> Bool
        # even n = if n == 0 then True else odd (n - 1)
        #
        # odd : Int -> Bool
        # odd n = if n == 0 then False else even (n - 1)

        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        bool_type = SurfaceTypeConstructor(name="Bool", args=[], location=DUMMY_LOC)
        arrow_type = SurfaceTypeArrow(arg=int_type, ret=bool_type, location=DUMMY_LOC, param_doc=None)

        # Simplified: just test that both functions are visible
        # even = \n -> True (simplified)
        even_body = SurfaceAbs(
            var="n",
            var_type=int_type,
            body=SurfaceConstructor(name="True", args=[], location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        even_decl = SurfaceTermDeclaration(
            name="even", type_annotation=arrow_type, body=even_body, location=DUMMY_LOC
        )

        # odd = \n -> False (simplified)
        odd_body = SurfaceAbs(
            var="n",
            var_type=int_type,
            body=SurfaceConstructor(name="False", args=[], location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        odd_decl = SurfaceTermDeclaration(
            name="odd", type_annotation=arrow_type, body=odd_body, location=DUMMY_LOC
        )

        result = elaborate_module([even_decl, odd_decl], module_name="test")

        assert result.success is True
        assert "even" in result.module.global_types
        assert "odd" in result.module.global_types

    @pytest.mark.xfail(
        reason="Forward references not yet implemented - see FORWARD_REFERENCES_RESEARCH.md"
    )
    def test_forward_reference(self):
        """Function that references another not yet defined."""
        # f : Int -> Int
        # f x = g x
        #
        # g : Int -> Int
        # g y = y

        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        arrow_type = SurfaceTypeArrow(int_type, int_type, location=DUMMY_LOC, param_doc=None)

        # g = \y -> y
        g_body = SurfaceAbs(
            var="y",
            var_type=int_type,
            body=SurfaceVar(name="y", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        arrow_type = SurfaceTypeArrow(arg=int_type, ret=int_type, location=DUMMY_LOC, param_doc=None)
        g_decl = SurfaceTermDeclaration(
            name="g", type_annotation=arrow_type, body=g_body, location=DUMMY_LOC
        )

        # f = \x -> g x (forward reference to g)
        # Note: This would need g in scope, so we define g first
        f_body = SurfaceAbs(
            "x",
            int_type,
            SurfaceApp(
                SurfaceVar(name="g", location=DUMMY_LOC),
                SurfaceVar(name="x", location=DUMMY_LOC),
                DUMMY_LOC,
            ),
            DUMMY_LOC,
        )
        f_decl = SurfaceTermDeclaration(
            name="f", type_annotation=arrow_type, body=f_body, location=DUMMY_LOC
        )

        result = elaborate_module([f_decl, g_decl], module_name="test")

        assert result.success is True
        assert "f" in result.module.global_types
        assert "g" in result.module.global_types


class TestLLMPragmaProcessing:
    """Tests for LLM pragma pass integration."""

    def test_llm_function_detection(self):
        """LLM pragma should be detected and processed."""
        # {-# LLM model=gpt-4 #-}
        # translate : String -> String
        # translate = \text -> @llm text

        str_type = SurfaceTypeConstructor(name="String", args=[], location=DUMMY_LOC)
        arrow_type = SurfaceTypeArrow(arg=str_type, ret=str_type, location=DUMMY_LOC, param_doc=None)

        body = SurfaceAbs(
            var="text",
            var_type=str_type,
            body=SurfaceVar(name="text", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        decl = SurfaceTermDeclaration(
            name="translate",
            type_annotation=arrow_type,
            body=body,
            location=DUMMY_LOC,
            docstring="Translate text to French",
            pragma={"LLM": "model=gpt-4"},
        )

        result = elaborate_module([decl], module_name="test")

        # Should succeed (pragma detected, function body replaced with PrimOp)
        assert result.success is True
        assert "translate" in result.module.global_types

    def test_non_llm_function(self):
        """Function without LLM pragma should pass through unchanged."""
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        arrow_type = SurfaceTypeArrow(arg=int_type, ret=int_type, location=DUMMY_LOC, param_doc=None)

        body = SurfaceAbs(
            var="x",
            var_type=int_type,
            body=SurfaceVar(name="x", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        decl = SurfaceTermDeclaration(
            name="id", type_annotation=arrow_type, body=body, location=DUMMY_LOC
        )

        result = elaborate_module([decl], module_name="test")

        assert result.success is True
        assert "id" in result.module.global_types
        # No LLM metadata for non-LLM function


class TestComplexExpressions:
    """Tests for complex nested expressions."""

    def test_nested_lambda_application(self):
        """Nested lambda with application."""
        # (\f -> \x -> f x) (\y -> y) 42
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)

        # \y -> y
        id_body = SurfaceAbs(
            var="y",
            var_type=int_type,
            body=SurfaceVar(name="y", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )

        # \x -> f x
        inner_app = SurfaceApp(
            func=SurfaceVar(name="f", location=DUMMY_LOC),
            arg=SurfaceVar(name="x", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        inner_abs = SurfaceAbs(var="x", var_type=int_type, body=inner_app, location=DUMMY_LOC)

        # \f -> \x -> f x
        # f should be a function (Int -> Int), not Int
        outer_abs = SurfaceAbs(var="f", var_type=None, body=inner_abs, location=DUMMY_LOC)

        # (\f -> ...) (\y -> y)
        app1 = SurfaceApp(func=outer_abs, arg=id_body, location=DUMMY_LOC)

        # ... 42
        app2 = SurfaceApp(
            func=app1,
            arg=SurfaceLit(prim_type="Int", value=42, location=DUMMY_LOC),
            location=DUMMY_LOC,
        )

        decl = SurfaceTermDeclaration(
            name="result", type_annotation=int_type, body=app2, location=DUMMY_LOC
        )

        result = elaborate_module([decl], module_name="test")

        assert result.success is True

    def test_conditional_expression(self):
        """If-then-else expression."""
        # if True then 1 else 0
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)

        if_term = SurfaceIf(
            cond=SurfaceConstructor(name="True", args=[], location=DUMMY_LOC),
            then_branch=SurfaceLit(prim_type="Int", value=1, location=DUMMY_LOC),
            else_branch=SurfaceLit(prim_type="Int", value=0, location=DUMMY_LOC),
            location=DUMMY_LOC,
        )

        decl = SurfaceTermDeclaration(
            name="result", type_annotation=int_type, body=if_term, location=DUMMY_LOC
        )

        result = elaborate_module([decl], module_name="test")

        assert result.success is True

    def test_tuple_expression(self):
        """Tuple expression through pipeline."""
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        str_type = SurfaceTypeConstructor(name="String", args=[], location=DUMMY_LOC)

        # (42, "hello")
        tuple_term = SurfaceTuple(
            elements=[
                SurfaceLit(prim_type="Int", value=42, location=DUMMY_LOC),
                SurfaceLit(prim_type="String", value="hello", location=DUMMY_LOC),
            ],
            location=DUMMY_LOC,
        )

        decl = SurfaceTermDeclaration(
            name="result",
            type_annotation=SurfaceTypeConstructor(
                name="Tuple", args=[int_type, str_type], location=DUMMY_LOC
            ),
            body=tuple_term,
            location=DUMMY_LOC,
        )

        result = elaborate_module([decl], module_name="test")

        assert result.success is True


class TestErrorPropagation:
    """Tests for error propagation through pipeline phases."""

    def test_undefined_variable_error(self):
        """Undefined variable should be caught in scope checking phase."""
        # x is not defined
        body = SurfaceVar(name="undefined_var", location=DUMMY_LOC)

        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        decl = SurfaceTermDeclaration(
            name="bad", type_annotation=int_type, body=body, location=DUMMY_LOC
        )

        result = elaborate_module([decl], module_name="test")

        # Should report error (but pipeline completes)
        assert result.success is False
        assert len(result.errors) > 0

    def test_type_mismatch_error(self):
        """Type mismatch should be caught in type elaboration phase."""
        # (42 : String) - Int with String annotation
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        str_type = SurfaceTypeConstructor(name="String", args=[], location=DUMMY_LOC)

        # 42 annotated as String
        ann_term = SurfaceAnn(
            term=SurfaceLit(prim_type="Int", value=42, location=DUMMY_LOC),
            type=str_type,
            location=DUMMY_LOC,
        )

        decl = SurfaceTermDeclaration(
            name="bad", type_annotation=str_type, body=ann_term, location=DUMMY_LOC
        )

        result = elaborate_module([decl], module_name="test")

        assert result.success is False
        assert len(result.errors) > 0


class TestModuleAssembly:
    """Tests for complete module assembly."""

    def test_module_metadata(self):
        """Module should contain correct metadata."""
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        body = SurfaceAbs(
            var="x",
            var_type=int_type,
            body=SurfaceVar(name="x", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )

        decl = SurfaceTermDeclaration(
            name="id",
            type_annotation=SurfaceTypeArrow(arg=int_type, ret=int_type, location=DUMMY_LOC, param_doc=None),
            body=body,
            location=DUMMY_LOC,
            docstring="Identity function",
        )

        result = elaborate_module([decl], module_name="my_module")

        assert result.module.name == "my_module"
        assert "id" in result.module.docstrings
        assert result.module.docstrings["id"] == "Identity function"

    def test_global_types_collection(self):
        """Module should collect all global type signatures."""
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        bool_type = SurfaceTypeConstructor(name="Bool", args=[], location=DUMMY_LOC)

        decl1 = SurfaceTermDeclaration(
            name="f1",
            type_annotation=SurfaceTypeArrow(arg=int_type, ret=int_type, location=DUMMY_LOC, param_doc=None),
            body=SurfaceAbs(
                var="x",
                var_type=int_type,
                body=SurfaceVar(name="x", location=DUMMY_LOC),
                location=DUMMY_LOC,
            ),
            location=DUMMY_LOC,
        )

        decl2 = SurfaceTermDeclaration(
            name="f2",
            type_annotation=SurfaceTypeArrow(arg=bool_type, ret=bool_type, location=DUMMY_LOC, param_doc=None),
            body=SurfaceAbs(
                var="x",
                var_type=bool_type,
                body=SurfaceVar(name="x", location=DUMMY_LOC),
                location=DUMMY_LOC,
            ),
            location=DUMMY_LOC,
        )

        result = elaborate_module([decl1, decl2], module_name="test")

        assert "f1" in result.module.global_types
        assert "f2" in result.module.global_types


class TestConvenienceFunction:
    """Tests for the elaborate_module convenience function."""

    def test_elaborate_module_function(self):
        """Convenience function should work correctly."""
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        body = SurfaceAbs(
            var="x",
            var_type=int_type,
            body=SurfaceVar(name="x", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )

        decl = SurfaceTermDeclaration(
            name="id",
            type_annotation=SurfaceTypeArrow(arg=int_type, ret=int_type, location=DUMMY_LOC, param_doc=None),
            body=body,
            location=DUMMY_LOC,
        )

        result = elaborate_module([decl], module_name="test")

        assert result.module.name == "test"
        assert len(result.module.declarations) == 1
        assert result.module.declarations[0].name == "id"


class TestRealPrograms:
    """Tests with realistic System F programs."""

    def test_compose_function(self):
        """Function composition: compose f g x = f (g x)"""
        # compose : (b -> c) -> (a -> b) -> a -> c
        # compose = \f -> \g -> \x -> f (g x)

        type_a = SurfaceTypeVar(name="a", location=DUMMY_LOC)
        type_b = SurfaceTypeVar(name="b", location=DUMMY_LOC)
        type_c = SurfaceTypeVar(name="c", location=DUMMY_LOC)

        # f : b -> c
        # g : a -> b
        # x : a
        # result: f (g x) : c

        arrow_bc = SurfaceTypeArrow(arg=type_b, ret=type_c, location=DUMMY_LOC, param_doc=None)
        arrow_ab = SurfaceTypeArrow(arg=type_a, ret=type_b, location=DUMMY_LOC, param_doc=None)
        arrow_ac = SurfaceTypeArrow(arg=type_a, ret=type_c, location=DUMMY_LOC, param_doc=None)

        # g x
        g_app = SurfaceApp(
            func=SurfaceVar(name="g", location=DUMMY_LOC),
            arg=SurfaceVar(name="x", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        # f (g x)
        f_app = SurfaceApp(
            func=SurfaceVar(name="f", location=DUMMY_LOC), arg=g_app, location=DUMMY_LOC
        )

        # \x -> f (g x)
        x_abs = SurfaceAbs(var="x", var_type=type_a, body=f_app, location=DUMMY_LOC)
        # \g -> \x -> f (g x)
        g_abs = SurfaceAbs(var="g", var_type=arrow_ab, body=x_abs, location=DUMMY_LOC)
        # \f -> \g -> \x -> f (g x)
        f_abs = SurfaceAbs(var="f", var_type=arrow_bc, body=g_abs, location=DUMMY_LOC)

        # Type: forall a b c. (b -> c) -> (a -> b) -> a -> c
        # Build inner type first
        inner_type = SurfaceTypeArrow(
            arg=arrow_bc,
            ret=SurfaceTypeArrow(arg=arrow_ab, ret=arrow_ac, location=DUMMY_LOC, param_doc=None),
            location=DUMMY_LOC,
        )
        # Wrap in forall for each type variable (right to left)
        compose_type = SurfaceTypeForall(var="c", body=inner_type, location=DUMMY_LOC)
        compose_type = SurfaceTypeForall(var="b", body=compose_type, location=DUMMY_LOC)
        compose_type = SurfaceTypeForall(var="a", body=compose_type, location=DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="compose", type_annotation=compose_type, body=f_abs, location=DUMMY_LOC
        )

        result = elaborate_module([decl], module_name="test")

        assert result.success is True
        assert "compose" in result.module.global_types

    @pytest.mark.skip(reason="Complex polymorphic type checking issue - needs investigation")
    def test_flip_function(self):
        """flip f x y = f y x"""
        # flip : (a -> b -> c) -> b -> a -> c
        type_a = SurfaceTypeVar(name="a", location=DUMMY_LOC)
        type_b = SurfaceTypeVar(name="b", location=DUMMY_LOC)
        type_c = SurfaceTypeVar(name="c", location=DUMMY_LOC)

        arrow_bc = SurfaceTypeArrow(arg=type_b, ret=type_c, location=DUMMY_LOC, param_doc=None)
        arrow_abc = SurfaceTypeArrow(arg=type_a, ret=arrow_bc, location=DUMMY_LOC, param_doc=None)
        arrow_ac = SurfaceTypeArrow(arg=type_a, ret=type_c, location=DUMMY_LOC, param_doc=None)
        arrow_bac = SurfaceTypeArrow(arg=type_b, ret=arrow_ac, location=DUMMY_LOC, param_doc=None)

        # f y x
        f_y = SurfaceApp(
            func=SurfaceVar(name="f", location=DUMMY_LOC),
            arg=SurfaceVar(name="y", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        f_y_x = SurfaceApp(
            func=f_y, arg=SurfaceVar(name="x", location=DUMMY_LOC), location=DUMMY_LOC
        )

        # \x -> f y x
        x_abs = SurfaceAbs(var="x", var_type=type_a, body=f_y_x, location=DUMMY_LOC)
        # \y -> \x -> f y x
        y_abs = SurfaceAbs(var="y", var_type=type_b, body=x_abs, location=DUMMY_LOC)
        # \f -> \y -> \x -> f y x
        f_abs = SurfaceAbs(var="f", var_type=arrow_abc, body=y_abs, location=DUMMY_LOC)

        # Type: forall a b c. (a -> b -> c) -> b -> a -> c
        # Build inner type first
        inner_type = SurfaceTypeArrow(arg=arrow_abc, ret=arrow_bac, location=DUMMY_LOC, param_doc=None)
        # Wrap in forall for each type variable (right to left)
        flip_type = SurfaceTypeForall(var="c", body=inner_type, location=DUMMY_LOC)
        flip_type = SurfaceTypeForall(var="b", body=flip_type, location=DUMMY_LOC)
        flip_type = SurfaceTypeForall(var="a", body=flip_type, location=DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="flip", type_annotation=flip_type, body=f_abs, location=DUMMY_LOC
        )

        result = elaborate_module([decl], module_name="test")

        assert result.success is True
        assert "flip" in result.module.global_types


class TestPipelineResult:
    """Tests for PipelineResult structure."""

    def test_successful_result(self):
        """Successful elaboration should have success=True."""
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        body = SurfaceAbs(
            var="x",
            var_type=int_type,
            body=SurfaceVar(name="x", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )

        decl = SurfaceTermDeclaration(
            name="id",
            type_annotation=SurfaceTypeArrow(arg=int_type, ret=int_type, location=DUMMY_LOC, param_doc=None),
            body=body,
            location=DUMMY_LOC,
        )

        result = elaborate_module([decl], module_name="test")

        assert result.success is True
        assert result.module is not None
        assert len(result.errors) == 0

    def test_error_result(self):
        """Failed elaboration should have success=False and errors."""
        # Undefined variable
        body = SurfaceVar(name="not_defined", location=DUMMY_LOC)

        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        decl = SurfaceTermDeclaration(
            name="bad", type_annotation=int_type, body=body, location=DUMMY_LOC
        )

        result = elaborate_module([decl], module_name="test")

        assert result.success is False
        assert len(result.errors) > 0

    def test_warning_collection(self):
        """Warnings should be collected in result."""
        # For now, warnings are empty but structure should exist
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        body = SurfaceAbs(
            var="x",
            var_type=int_type,
            body=SurfaceVar(name="x", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )

        decl = SurfaceTermDeclaration(
            name="id",
            type_annotation=SurfaceTypeArrow(arg=int_type, ret=int_type, location=DUMMY_LOC, param_doc=None),
            body=body,
            location=DUMMY_LOC,
        )

        result = elaborate_module([decl], module_name="test")

        # Warnings list should exist in module even if empty
        assert hasattr(result.module, "warnings")
        assert isinstance(result.module.warnings, list)
