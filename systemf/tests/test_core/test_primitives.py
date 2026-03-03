"""Tests for primitive operations and type checking."""

import pytest

from systemf.core.ast import (
    App,
    Constructor,
    DataDeclaration,
    Lit,
    PrimOp,
    TermDeclaration,
)
from systemf.core.checker import TypeChecker
from systemf.core.context import Context
from systemf.core.types import TypeArrow, TypeConstructor, TypeForall
from systemf.eval.machine import Evaluator
from systemf.eval.value import VPrim, VPrimOp


# =============================================================================
# Type Checking Tests
# =============================================================================


class TestTypeCheckIntLit:
    """Tests for integer literal type checking."""

    def test_int_lit_looks_up_primitive_type(self):
        """IntLit(42) should lookup Int type from primitive_types registry."""
        int_ty = TypeConstructor("Int", [])
        checker = TypeChecker(primitive_types={"Int": int_ty})
        ty = checker.infer(Context.empty(), Lit(prim_type="Int", value=42))
        assert ty == int_ty

    def test_int_lit_raises_when_int_not_registered(self):
        """IntLit should raise error when Int type not in primitive_types."""
        checker = TypeChecker()
        with pytest.raises(TypeError, match="Int type not registered"):
            checker.infer(Context.empty(), Lit(prim_type="Int", value=42))


class TestTypeCheckPrimOp:
    """Tests for primitive operation type checking."""

    def test_prim_op_looks_up_global_types(self):
        """PrimOp('int_plus') should lookup $prim.int_plus from global_types."""
        int_ty = TypeConstructor("Int", [])
        int_plus_ty = TypeArrow(int_ty, TypeArrow(int_ty, int_ty))
        checker = TypeChecker(
            primitive_types={"Int": int_ty}, global_types={"$prim.int_plus": int_plus_ty}
        )
        ty = checker.infer(Context.empty(), PrimOp(name="int_plus"))
        assert ty == int_plus_ty

    def test_prim_op_application_type_checks(self):
        """App(PrimOp('int_plus'), IntLit(1)) should type check."""
        int_ty = TypeConstructor("Int", [])
        int_plus_ty = TypeArrow(int_ty, TypeArrow(int_ty, int_ty))
        checker = TypeChecker(
            primitive_types={"Int": int_ty}, global_types={"$prim.int_plus": int_plus_ty}
        )
        app1 = App(func=PrimOp(name="int_plus"), arg=Lit(prim_type="Int", value=1))
        ty = checker.infer(Context.empty(), app1)
        assert ty == TypeArrow(int_ty, int_ty)

    def test_prim_op_unknown_raises_error(self):
        """PrimOp('unknown_op') should raise error."""
        int_ty = TypeConstructor("Int", [])
        checker = TypeChecker(primitive_types={"Int": int_ty}, global_types={})
        with pytest.raises(TypeError, match="Unknown primitive"):
            checker.infer(Context.empty(), PrimOp(name="unknown_op"))


class TestNoHardcodedSignatures:
    """Tests that primitive signatures come from prelude, not hardcoded."""

    def test_prim_op_type_comes_from_global_types_not_hardcoded(self):
        """Type checking should use global_types, not hardcoded signatures."""
        int_ty = TypeConstructor("Int", [])
        # Use a non-standard type for int_plus
        weird_ty = TypeArrow(int_ty, int_ty)
        checker = TypeChecker(
            primitive_types={"Int": int_ty}, global_types={"$prim.int_plus": weird_ty}
        )
        # Should get the weird type, not the standard Int -> Int -> Int
        ty = checker.infer(Context.empty(), PrimOp(name="int_plus"))
        assert ty == weird_ty


# =============================================================================
# Evaluation Tests
# =============================================================================


class TestEvalPrimOp:
    """Tests for primitive operation evaluation."""

    def test_prim_op_creates_closure(self):
        """PrimOp should create a VPrimOp closure."""
        evaluator = Evaluator()
        result = evaluator.evaluate(PrimOp(name="int_plus"))
        assert isinstance(result, VPrimOp)
        assert result.name == "int_plus"

    @pytest.mark.parametrize(
        "op_name,a,b,expected",
        [
            ("int_plus", 1, 2, 3),
            ("int_minus", 5, 3, 2),
            ("int_multiply", 3, 4, 12),
            ("int_divide", 7, 2, 3),
        ],
    )
    def test_arithmetic_operation(self, op_name, a, b, expected):
        """Test arithmetic operations evaluate correctly."""
        evaluator = Evaluator()
        expr = App(
            func=App(func=PrimOp(name=op_name), arg=Lit(prim_type="Int", value=a)),
            arg=Lit(prim_type="Int", value=b),
        )
        result = evaluator.evaluate(expr)
        assert result == VPrim("Int", expected)

    def test_int_div_by_zero_raises(self):
        """int_div 1 0 should raise RuntimeError."""
        evaluator = Evaluator()
        expr = App(
            func=App(func=PrimOp(name="int_divide"), arg=Lit(prim_type="Int", value=1)),
            arg=Lit(prim_type="Int", value=0),
        )
        with pytest.raises(RuntimeError, match="Division by zero"):
            evaluator.evaluate(expr)


class TestPrimitiveImplsRegistry:
    """Tests for primitive_impls registry."""

    @pytest.mark.parametrize(
        "op", ["$prim.int_plus", "$prim.int_minus", "$prim.int_multiply", "$prim.int_divide"]
    )
    def test_registry_has_primitive(self, op):
        """primitive_impls should contain arithmetic primitives."""
        evaluator = Evaluator()
        assert op in evaluator.primitive_impls


class TestPrimitiveIntegration:
    """Integration tests for primitives in context."""

    def test_arithmetic_expression(self):
        """Test: (3 + 4) * 2 = 14"""
        evaluator = Evaluator()
        # Build: multiply (add 3 4) 2
        # multiply (add 3 4) 2
        add_expr = App(
            func=App(func=PrimOp(name="int_plus"), arg=Lit(prim_type="Int", value=3)),
            arg=Lit(prim_type="Int", value=4),
        )
        expr = App(
            func=App(func=PrimOp(name="int_multiply"), arg=add_expr),
            arg=Lit(prim_type="Int", value=2),
        )
        result = evaluator.evaluate(expr)
        assert result == VPrim("Int", 14)

    def test_unknown_primitive_raises(self):
        """Unknown primitive should raise RuntimeError."""
        evaluator = Evaluator()
        with pytest.raises(RuntimeError, match="Unknown primitive"):
            evaluator.evaluate(PrimOp(name="unknown_op"))
