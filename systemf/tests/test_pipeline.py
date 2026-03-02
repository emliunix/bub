"""Integration tests for the System F elaboration pipeline.

End-to-end tests covering the complete three-phase pipeline:
1. Phase 1: Scope Checking (Surface AST → Scoped AST)
2. Phase 2: Type Elaboration (Scoped AST → Core AST)
3. Phase 3: LLM Pragma Pass (Transform LLM functions)

These tests verify that the entire pipeline works correctly with real
System F programs and that errors are properly propagated through all phases.
"""

import pytest

from systemf.surface import ElaborationPipeline, elaborate_module
from systemf.surface.types import (
    SurfaceTermDeclaration,
    SurfaceAbs,
    SurfaceVar,
    SurfaceApp,
    SurfaceLet,
    SurfaceIntLit,
    SurfaceStringLit,
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
        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([])

        assert result.success is True
        assert len(result.module.declarations) == 0
        assert len(result.errors) == 0

    def test_simple_identity_function(self):
        """Full pipeline with simple identity function."""
        # id : Int -> Int
        # id = \x -> x
        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        arrow_type = SurfaceTypeArrow(int_type, int_type, location=DUMMY_LOC)

        body = SurfaceAbs("x", int_type, SurfaceVar("x", DUMMY_LOC), DUMMY_LOC)
        decl = SurfaceTermDeclaration(
            name="id", type_annotation=arrow_type, body=body, location=DUMMY_LOC
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        assert result.success is True
        assert len(result.module.declarations) == 1
        assert result.module.declarations[0].name == "id"
        assert "id" in result.module.global_types

    def test_constant_function(self):
        """Function that ignores its argument."""
        # const : Int -> Int -> Int
        # const = \x -> \y -> x
        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)

        # First lambda: \x -> ...
        inner_body = SurfaceAbs("y", int_type, SurfaceVar("x", DUMMY_LOC), DUMMY_LOC)
        outer_body = SurfaceAbs("x", int_type, inner_body, DUMMY_LOC)

        # Type: Int -> Int -> Int
        arrow1 = SurfaceTypeArrow(int_type, int_type, location=DUMMY_LOC)
        arrow2 = SurfaceTypeArrow(int_type, arrow1, location=DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="const", type_annotation=arrow2, body=outer_body, location=DUMMY_LOC
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        assert result.success is True
        assert "const" in result.module.global_types


class TestPolymorphism:
    """Tests for polymorphic type elaboration."""

    def test_polymorphic_identity(self):
        """Polymorphic identity function through full pipeline."""
        # id : forall a. a -> a
        # id = /\a. \x:a -> x

        type_var = SurfaceTypeVar("a", DUMMY_LOC)
        body = SurfaceAbs("x", type_var, SurfaceVar("x", DUMMY_LOC), DUMMY_LOC)
        type_abs = SurfaceTypeAbs("a", body, DUMMY_LOC)

        # Type: forall a. a -> a
        arrow = SurfaceTypeArrow(type_var, type_var, location=DUMMY_LOC)
        forall_type = SurfaceTypeForall("a", arrow, DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="id", type_annotation=forall_type, body=type_abs, location=DUMMY_LOC
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        assert result.success is True
        assert "id" in result.module.global_types

    def test_polymorphic_application(self):
        """Polymorphic function applied to concrete type."""
        # id @Int 42
        # where id = /\a. \x:a -> x

        type_var = SurfaceTypeVar("a", DUMMY_LOC)
        body = SurfaceAbs("x", type_var, SurfaceVar("x", DUMMY_LOC), DUMMY_LOC)
        type_abs = SurfaceTypeAbs("a", body, DUMMY_LOC)

        # id @Int
        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        type_app = SurfaceTypeApp(type_abs, int_type, DUMMY_LOC)

        # id @Int 42
        app = SurfaceApp(type_app, SurfaceIntLit(42, DUMMY_LOC), DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="result", type_annotation=int_type, body=app, location=DUMMY_LOC
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        assert result.success is True


class TestLetBindings:
    """Tests for let binding elaboration."""

    def test_simple_let(self):
        """Simple let binding through pipeline."""
        # let x = 42 in x + 1
        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)

        bindings = [("x", None, SurfaceIntLit(42, DUMMY_LOC))]
        body = SurfaceOp(SurfaceVar("x", DUMMY_LOC), "+", SurfaceIntLit(1, DUMMY_LOC), DUMMY_LOC)
        let_term = SurfaceLet(bindings, body, DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="result", type_annotation=int_type, body=let_term, location=DUMMY_LOC
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        assert result.success is True

    def test_nested_let(self):
        """Nested let bindings."""
        # let x = 1 in let y = 2 in x + y
        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)

        inner_bindings = [("y", None, SurfaceIntLit(2, DUMMY_LOC))]
        inner_body = SurfaceOp(
            SurfaceVar("x", DUMMY_LOC), "+", SurfaceVar("y", DUMMY_LOC), DUMMY_LOC
        )
        inner_let = SurfaceLet(inner_bindings, inner_body, DUMMY_LOC)

        outer_bindings = [("x", None, SurfaceIntLit(1, DUMMY_LOC))]
        outer_let = SurfaceLet(outer_bindings, inner_let, DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="result", type_annotation=int_type, body=outer_let, location=DUMMY_LOC
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

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

        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        bool_type = SurfaceTypeConstructor("Bool", [], DUMMY_LOC)
        arrow_type = SurfaceTypeArrow(int_type, bool_type, location=DUMMY_LOC)

        # Simplified: just test that both functions are visible
        # even = \n -> True (simplified)
        even_body = SurfaceAbs("n", int_type, SurfaceConstructor("True", [], DUMMY_LOC), DUMMY_LOC)
        even_decl = SurfaceTermDeclaration(
            name="even", type_annotation=arrow_type, body=even_body, location=DUMMY_LOC
        )

        # odd = \n -> False (simplified)
        odd_body = SurfaceAbs("n", int_type, SurfaceConstructor("False", [], DUMMY_LOC), DUMMY_LOC)
        odd_decl = SurfaceTermDeclaration(
            name="odd", type_annotation=arrow_type, body=odd_body, location=DUMMY_LOC
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([even_decl, odd_decl])

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

        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        arrow_type = SurfaceTypeArrow(int_type, int_type, location=DUMMY_LOC)

        # g = \y -> y
        g_body = SurfaceAbs("y", int_type, SurfaceVar("y", DUMMY_LOC), DUMMY_LOC)
        g_decl = SurfaceTermDeclaration(
            name="g", type_annotation=arrow_type, body=g_body, location=DUMMY_LOC
        )

        # f = \x -> g x (forward reference to g)
        # Note: This would need g in scope, so we define g first
        f_body = SurfaceAbs(
            "x",
            int_type,
            SurfaceApp(SurfaceVar("g", DUMMY_LOC), SurfaceVar("x", DUMMY_LOC), DUMMY_LOC),
            DUMMY_LOC,
        )
        f_decl = SurfaceTermDeclaration(
            name="f", type_annotation=arrow_type, body=f_body, location=DUMMY_LOC
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([f_decl, g_decl])

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

        str_type = SurfaceTypeConstructor("String", [], DUMMY_LOC)
        arrow_type = SurfaceTypeArrow(str_type, str_type, location=DUMMY_LOC)

        body = SurfaceAbs("text", str_type, SurfaceVar("text", DUMMY_LOC), DUMMY_LOC)
        decl = SurfaceTermDeclaration(
            name="translate",
            type_annotation=arrow_type,
            body=body,
            location=DUMMY_LOC,
            docstring="Translate text to French",
            pragma={"LLM": "model=gpt-4"},
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        # Should succeed (pragma detected, function body replaced with PrimOp)
        assert result.success is True
        assert "translate" in result.module.global_types

    def test_non_llm_function(self):
        """Function without LLM pragma should pass through unchanged."""
        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        arrow_type = SurfaceTypeArrow(int_type, int_type, location=DUMMY_LOC)

        body = SurfaceAbs("x", int_type, SurfaceVar("x", DUMMY_LOC), DUMMY_LOC)
        decl = SurfaceTermDeclaration(
            name="id", type_annotation=arrow_type, body=body, location=DUMMY_LOC
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        assert result.success is True
        assert "id" in result.module.global_types
        # No LLM metadata for non-LLM function


class TestComplexExpressions:
    """Tests for complex nested expressions."""

    def test_nested_lambda_application(self):
        """Nested lambda with application."""
        # (\f -> \x -> f x) (\y -> y) 42
        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)

        # \y -> y
        id_body = SurfaceAbs("y", int_type, SurfaceVar("y", DUMMY_LOC), DUMMY_LOC)

        # \x -> f x
        inner_app = SurfaceApp(SurfaceVar("f", DUMMY_LOC), SurfaceVar("x", DUMMY_LOC), DUMMY_LOC)
        inner_abs = SurfaceAbs("x", int_type, inner_app, DUMMY_LOC)

        # \f -> \x -> f x
        # f should be a function (Int -> Int), not Int
        outer_abs = SurfaceAbs("f", None, inner_abs, DUMMY_LOC)

        # (\f -> ...) (\y -> y)
        app1 = SurfaceApp(outer_abs, id_body, DUMMY_LOC)

        # ... 42
        app2 = SurfaceApp(app1, SurfaceIntLit(42, DUMMY_LOC), DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="result", type_annotation=int_type, body=app2, location=DUMMY_LOC
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        assert result.success is True

    def test_conditional_expression(self):
        """If-then-else expression."""
        # if True then 1 else 0
        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)

        if_term = SurfaceIf(
            SurfaceConstructor("True", [], DUMMY_LOC),
            SurfaceIntLit(1, DUMMY_LOC),
            SurfaceIntLit(0, DUMMY_LOC),
            DUMMY_LOC,
        )

        decl = SurfaceTermDeclaration(
            name="result", type_annotation=int_type, body=if_term, location=DUMMY_LOC
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        assert result.success is True

    def test_tuple_expression(self):
        """Tuple expression through pipeline."""
        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        str_type = SurfaceTypeConstructor("String", [], DUMMY_LOC)

        # (42, "hello")
        tuple_term = SurfaceTuple(
            [SurfaceIntLit(42, DUMMY_LOC), SurfaceStringLit("hello", DUMMY_LOC)], DUMMY_LOC
        )

        decl = SurfaceTermDeclaration(
            name="result",
            type_annotation=SurfaceTypeConstructor("Tuple", [int_type, str_type], DUMMY_LOC),
            body=tuple_term,
            location=DUMMY_LOC,
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        assert result.success is True


class TestErrorPropagation:
    """Tests for error propagation through pipeline phases."""

    def test_undefined_variable_error(self):
        """Undefined variable should be caught in scope checking phase."""
        # x is not defined
        body = SurfaceVar("undefined_var", DUMMY_LOC)

        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        decl = SurfaceTermDeclaration(
            name="bad", type_annotation=int_type, body=body, location=DUMMY_LOC
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        # Should report error (but pipeline completes)
        assert result.success is False
        assert len(result.errors) > 0

    def test_type_mismatch_error(self):
        """Type mismatch should be caught in type elaboration phase."""
        # (42 : String) - Int with String annotation
        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        str_type = SurfaceTypeConstructor("String", [], DUMMY_LOC)

        # 42 annotated as String
        ann_term = SurfaceAnn(SurfaceIntLit(42, DUMMY_LOC), str_type, DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="bad", type_annotation=str_type, body=ann_term, location=DUMMY_LOC
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        assert result.success is False
        assert len(result.errors) > 0


class TestModuleAssembly:
    """Tests for complete module assembly."""

    def test_module_metadata(self):
        """Module should contain correct metadata."""
        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        body = SurfaceAbs("x", int_type, SurfaceVar("x", DUMMY_LOC), DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="id",
            type_annotation=SurfaceTypeArrow(int_type, int_type, location=DUMMY_LOC),
            body=body,
            location=DUMMY_LOC,
            docstring="Identity function",
        )

        pipeline = ElaborationPipeline(module_name="my_module")
        result = pipeline.run([decl])

        assert result.module.name == "my_module"
        assert "id" in result.module.docstrings
        assert result.module.docstrings["id"] == "Identity function"

    def test_global_types_collection(self):
        """Module should collect all global type signatures."""
        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        bool_type = SurfaceTypeConstructor("Bool", [], DUMMY_LOC)

        decl1 = SurfaceTermDeclaration(
            name="f1",
            type_annotation=SurfaceTypeArrow(int_type, int_type, location=DUMMY_LOC),
            body=SurfaceAbs("x", int_type, SurfaceVar("x", DUMMY_LOC), DUMMY_LOC),
            location=DUMMY_LOC,
        )

        decl2 = SurfaceTermDeclaration(
            name="f2",
            type_annotation=SurfaceTypeArrow(bool_type, bool_type, location=DUMMY_LOC),
            body=SurfaceAbs("x", bool_type, SurfaceVar("x", DUMMY_LOC), DUMMY_LOC),
            location=DUMMY_LOC,
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl1, decl2])

        assert "f1" in result.module.global_types
        assert "f2" in result.module.global_types


class TestConvenienceFunction:
    """Tests for the elaborate_module convenience function."""

    def test_elaborate_module_function(self):
        """Convenience function should work correctly."""
        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        body = SurfaceAbs("x", int_type, SurfaceVar("x", DUMMY_LOC), DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="id",
            type_annotation=SurfaceTypeArrow(int_type, int_type, location=DUMMY_LOC),
            body=body,
            location=DUMMY_LOC,
        )

        module = elaborate_module([decl], module_name="test")

        assert module.name == "test"
        assert len(module.declarations) == 1
        assert module.declarations[0].name == "id"


class TestRealPrograms:
    """Tests with realistic System F programs."""

    def test_compose_function(self):
        """Function composition: compose f g x = f (g x)"""
        # compose : (b -> c) -> (a -> b) -> a -> c
        # compose = \f -> \g -> \x -> f (g x)

        type_a = SurfaceTypeVar("a", DUMMY_LOC)
        type_b = SurfaceTypeVar("b", DUMMY_LOC)
        type_c = SurfaceTypeVar("c", DUMMY_LOC)

        # f : b -> c
        # g : a -> b
        # x : a
        # result: f (g x) : c

        arrow_bc = SurfaceTypeArrow(type_b, type_c, location=DUMMY_LOC)
        arrow_ab = SurfaceTypeArrow(type_a, type_b, location=DUMMY_LOC)
        arrow_ac = SurfaceTypeArrow(type_a, type_c, location=DUMMY_LOC)

        # g x
        g_app = SurfaceApp(SurfaceVar("g", DUMMY_LOC), SurfaceVar("x", DUMMY_LOC), DUMMY_LOC)
        # f (g x)
        f_app = SurfaceApp(SurfaceVar("f", DUMMY_LOC), g_app, DUMMY_LOC)

        # \x -> f (g x)
        x_abs = SurfaceAbs("x", type_a, f_app, DUMMY_LOC)
        # \g -> \x -> f (g x)
        g_abs = SurfaceAbs("g", arrow_ab, x_abs, DUMMY_LOC)
        # \f -> \g -> \x -> f (g x)
        f_abs = SurfaceAbs("f", arrow_bc, g_abs, DUMMY_LOC)

        # Type: (b -> c) -> (a -> b) -> (a -> c)
        compose_type = SurfaceTypeArrow(
            arrow_bc, SurfaceTypeArrow(arrow_ab, arrow_ac, location=DUMMY_LOC), location=DUMMY_LOC
        )

        decl = SurfaceTermDeclaration(
            name="compose", type_annotation=compose_type, body=f_abs, location=DUMMY_LOC
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        assert result.success is True
        assert "compose" in result.module.global_types

    def test_flip_function(self):
        """flip f x y = f y x"""
        # flip : (a -> b -> c) -> b -> a -> c
        type_a = SurfaceTypeVar("a", DUMMY_LOC)
        type_b = SurfaceTypeVar("b", DUMMY_LOC)
        type_c = SurfaceTypeVar("c", DUMMY_LOC)

        arrow_bc = SurfaceTypeArrow(type_b, type_c, location=DUMMY_LOC)
        arrow_abc = SurfaceTypeArrow(type_a, arrow_bc, location=DUMMY_LOC)
        arrow_ac = SurfaceTypeArrow(type_a, type_c, location=DUMMY_LOC)
        arrow_bac = SurfaceTypeArrow(type_b, arrow_ac, location=DUMMY_LOC)

        # f y x
        f_y = SurfaceApp(SurfaceVar("f", DUMMY_LOC), SurfaceVar("y", DUMMY_LOC), DUMMY_LOC)
        f_y_x = SurfaceApp(f_y, SurfaceVar("x", DUMMY_LOC), DUMMY_LOC)

        # \x -> f y x
        x_abs = SurfaceAbs("x", type_a, f_y_x, DUMMY_LOC)
        # \y -> \x -> f y x
        y_abs = SurfaceAbs("y", type_b, x_abs, DUMMY_LOC)
        # \f -> \y -> \x -> f y x
        f_abs = SurfaceAbs("f", arrow_abc, y_abs, DUMMY_LOC)

        # Type: (a -> b -> c) -> (b -> a -> c)
        flip_type = SurfaceTypeArrow(arrow_abc, arrow_bac, location=DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="flip", type_annotation=flip_type, body=f_abs, location=DUMMY_LOC
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        assert result.success is True
        assert "flip" in result.module.global_types


class TestPipelineResult:
    """Tests for PipelineResult structure."""

    def test_successful_result(self):
        """Successful elaboration should have success=True."""
        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        body = SurfaceAbs("x", int_type, SurfaceVar("x", DUMMY_LOC), DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="id",
            type_annotation=SurfaceTypeArrow(int_type, int_type, location=DUMMY_LOC),
            body=body,
            location=DUMMY_LOC,
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        assert result.success is True
        assert result.module is not None
        assert len(result.errors) == 0

    def test_error_result(self):
        """Failed elaboration should have success=False and errors."""
        # Undefined variable
        body = SurfaceVar("not_defined", DUMMY_LOC)

        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        decl = SurfaceTermDeclaration(
            name="bad", type_annotation=int_type, body=body, location=DUMMY_LOC
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        assert result.success is False
        assert len(result.errors) > 0

    def test_warning_collection(self):
        """Warnings should be collected in result."""
        # For now, warnings are empty but structure should exist
        int_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        body = SurfaceAbs("x", int_type, SurfaceVar("x", DUMMY_LOC), DUMMY_LOC)

        decl = SurfaceTermDeclaration(
            name="id",
            type_annotation=SurfaceTypeArrow(int_type, int_type, location=DUMMY_LOC),
            body=body,
            location=DUMMY_LOC,
        )

        pipeline = ElaborationPipeline(module_name="test")
        result = pipeline.run([decl])

        # Warnings list should exist even if empty
        assert hasattr(result, "warnings")
        assert isinstance(result.warnings, list)
