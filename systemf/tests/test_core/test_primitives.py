"""Tests for primitive operations and type checking."""

import pytest

from systemf.core.ast import (
    App,
    Constructor,
    DataDeclaration,
    IntLit,
    PrimOp,
    TermDeclaration,
)
from systemf.core.checker import TypeChecker
from systemf.core.context import Context
from systemf.core.types import TypeArrow, TypeConstructor, TypeForall
from systemf.eval.machine import Evaluator
from systemf.eval.value import VInt, VPrimOp


# =============================================================================
# Type Checking Tests
# =============================================================================


class TestTypeCheckIntLit:
    """Tests for integer literal type checking."""

    def test_int_lit_looks_up_primitive_type(self):
        """IntLit(42) should lookup Int type from primitive_types registry."""
        int_ty = TypeConstructor("Int", [])
        checker = TypeChecker(primitive_types={"Int": int_ty})
        ty = checker.infer(Context.empty(), IntLit(42))
        assert ty == int_ty

    def test_int_lit_raises_when_int_not_registered(self):
        """IntLit should raise error when Int type not in primitive_types."""
        checker = TypeChecker()
        with pytest.raises(TypeError, match="Int type not registered"):
            checker.infer(Context.empty(), IntLit(42))


class TestTypeCheckPrimOp:
    """Tests for primitive operation type checking."""

    def test_prim_op_looks_up_global_types(self):
        """PrimOp('int_plus') should lookup $prim.int_plus from global_types."""
        int_ty = TypeConstructor("Int", [])
        int_plus_ty = TypeArrow(int_ty, TypeArrow(int_ty, int_ty))
        checker = TypeChecker(
            primitive_types={"Int": int_ty}, global_types={"$prim.int_plus": int_plus_ty}
        )
        ty = checker.infer(Context.empty(), PrimOp("int_plus"))
        assert ty == int_plus_ty

    def test_prim_op_raises_when_unknown(self):
        """PrimOp should raise error when primitive not in global_types."""
        checker = TypeChecker()
        with pytest.raises(TypeError, match="Unknown primitive"):
            checker.infer(Context.empty(), PrimOp("unknown_op"))

    def test_prim_op_application_type_checks(self):
        """App(PrimOp('int_plus'), IntLit(1)) should type check."""
        int_ty = TypeConstructor("Int", [])
        int_plus_ty = TypeArrow(int_ty, TypeArrow(int_ty, int_ty))
        checker = TypeChecker(
            primitive_types={"Int": int_ty}, global_types={"$prim.int_plus": int_plus_ty}
        )
        # int_plus 1
        app1 = App(PrimOp("int_plus"), IntLit(1))
        ty1 = checker.infer(Context.empty(), app1)
        assert ty1 == TypeArrow(int_ty, int_ty)
        # (int_plus 1) 2
        app2 = App(app1, IntLit(2))
        ty2 = checker.infer(Context.empty(), app2)
        assert ty2 == int_ty


class TestNoHardcodedSignatures:
    """Tests that type checker has no hardcoded primitive signatures."""

    def test_int_type_comes_from_primitive_types_not_hardcoded(self):
        """IntLit should fail if Int not in primitive_types, even with Int constructor."""
        int_ty = TypeConstructor("Int", [])
        # Only register constructors, not primitive_types
        checker = TypeChecker(datatype_constructors={"Int": int_ty})
        with pytest.raises(TypeError):
            checker.infer(Context.empty(), IntLit(42))

    def test_prim_op_type_comes_from_global_types_not_hardcoded(self):
        """PrimOp should fail if not in global_types, even for standard ops."""
        checker = TypeChecker(primitive_types={"Int": TypeConstructor("Int", [])})
        with pytest.raises(TypeError, match="Unknown primitive: int_plus"):
            checker.infer(Context.empty(), PrimOp("int_plus"))


# =============================================================================
# Evaluation Tests
# =============================================================================


class TestEvalIntLit:
    """Tests for integer literal evaluation."""

    def test_int_lit_evaluates_to_vint(self):
        """IntLit(42) should evaluate to VInt(42)."""
        evaluator = Evaluator()
        result = evaluator.evaluate(IntLit(42))
        assert result == VInt(42)


class TestEvalPrimOp:
    """Tests for primitive operation evaluation."""

    def test_prim_op_creates_closure(self):
        """PrimOp should create a VPrimOp closure."""
        evaluator = Evaluator()
        result = evaluator.evaluate(PrimOp("int_plus"))
        assert isinstance(result, VPrimOp)
        assert result.name == "int_plus"

    def test_int_plus_evaluates(self):
        """int_plus 1 2 should evaluate to 3."""
        evaluator = Evaluator()
        # (int_plus 1) 2
        expr = App(App(PrimOp("int_plus"), IntLit(1)), IntLit(2))
        result = evaluator.evaluate(expr)
        assert result == VInt(3)

    def test_int_minus_evaluates(self):
        """int_minus 5 3 should evaluate to 2."""
        evaluator = Evaluator()
        expr = App(App(PrimOp("int_minus"), IntLit(5)), IntLit(3))
        result = evaluator.evaluate(expr)
        assert result == VInt(2)

    def test_int_mult_evaluates(self):
        """int_mult 3 4 should evaluate to 12."""
        evaluator = Evaluator()
        expr = App(App(PrimOp("int_multiply"), IntLit(3)), IntLit(4))
        result = evaluator.evaluate(expr)
        assert result == VInt(12)

    def test_int_div_evaluates(self):
        """int_div 7 2 should evaluate to 3 (integer division)."""
        evaluator = Evaluator()
        expr = App(App(PrimOp("int_divide"), IntLit(7)), IntLit(2))
        result = evaluator.evaluate(expr)
        assert result == VInt(3)

    def test_int_div_by_zero_raises(self):
        """int_div 1 0 should raise RuntimeError."""
        evaluator = Evaluator()
        expr = App(App(PrimOp("int_divide"), IntLit(1)), IntLit(0))
        with pytest.raises(RuntimeError, match="Division by zero"):
            evaluator.evaluate(expr)

    def test_unknown_primitive_raises(self):
        """Unknown primitive should raise RuntimeError."""
        evaluator = Evaluator()
        with pytest.raises(RuntimeError, match="Unknown primitive"):
            evaluator.evaluate(PrimOp("unknown_op"))


class TestPrimitiveImplsRegistry:
    """Tests for primitive_impls registry."""

    def test_registry_has_int_plus(self):
        """primitive_impls should contain int_plus."""
        evaluator = Evaluator()
        assert "int_plus" in evaluator.primitive_impls

    def test_registry_has_int_minus(self):
        """primitive_impls should contain int_minus."""
        evaluator = Evaluator()
        assert "int_minus" in evaluator.primitive_impls

    def test_registry_has_int_mult(self):
        """primitive_impls should contain int_mult."""
        evaluator = Evaluator()
        assert "int_multiply" in evaluator.primitive_impls

    def test_registry_has_int_div(self):
        """primitive_impls should contain int_div."""
        evaluator = Evaluator()
        assert "int_divide" in evaluator.primitive_impls


# =============================================================================
# Integration Tests
# =============================================================================


class TestPrimitiveIntegration:
    """Integration tests combining type checking and evaluation."""

    def test_arithmetic_expression(self):
        """Test a complex arithmetic expression."""
        int_ty = TypeConstructor("Int", [])
        int_plus_ty = TypeArrow(int_ty, TypeArrow(int_ty, int_ty))
        int_minus_ty = TypeArrow(int_ty, TypeArrow(int_ty, int_ty))
        int_mult_ty = TypeArrow(int_ty, TypeArrow(int_ty, int_ty))

        checker = TypeChecker(
            primitive_types={"Int": int_ty},
            global_types={
                "$prim.int_plus": int_plus_ty,
                "$prim.int_minus": int_minus_ty,
                "$prim.int_multiply": int_mult_ty,
            },
        )
        evaluator = Evaluator()

        # Expression: (1 + 2) * 3 = 9
        # ((int_mult (int_plus 1 2)) 3)
        expr = App(
            App(PrimOp("int_multiply"), App(App(PrimOp("int_plus"), IntLit(1)), IntLit(2))), IntLit(3)
        )

        # Type check
        ty = checker.infer(Context.empty(), expr)
        assert ty == int_ty

        # Evaluate
        result = evaluator.evaluate(expr)
        assert result == VInt(9)
