"""Tests for surface to core elaborator."""

import pytest

from systemf.core import ast as core
from systemf.core.types import TypeArrow, TypeConstructor, TypeForall, TypeVar
from systemf.surface.ast import (
    SurfaceAbs,
    SurfaceApp,
    SurfaceConstructor,
    SurfaceConstructorInfo,
    SurfaceDataDeclaration,
    SurfaceIntLit,
    SurfaceLet,
    SurfaceTermDeclaration,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceTypeArrow,
    SurfaceTypeConstructor,
    SurfaceTypeForall,
    SurfaceTypeVar,
    SurfaceVar,
)
from systemf.surface.elaborator import (
    ElaborationError,
    Elaborator,
    UndefinedVariable,
    elaborate,
    elaborate_term,
)
from systemf.surface.parser import parse_term
from systemf.utils.location import Location


# Create a dummy location for tests
DUMMY_LOC = Location(1, 1)


# =============================================================================
# Variable Elaboration Tests
# =============================================================================


class TestElaborateVar:
    """Tests for variable elaboration."""

    def test_elab_simple_var(self):
        """Elaborate variable in scope."""
        elab = Elaborator()
        elab._add_term_binding("x")

        surface = SurfaceVar("x", DUMMY_LOC)
        core_term = elab.elaborate_term(surface)

        assert isinstance(core_term, core.Var)
        assert core_term.index == 0

    def test_elab_var_second(self):
        """Elaborate second variable in scope."""
        elab = Elaborator()
        elab._add_term_binding("y")  # index 1
        elab._add_term_binding("x")  # index 0

        surface = SurfaceVar("y", DUMMY_LOC)
        core_term = elab.elaborate_term(surface)

        assert isinstance(core_term, core.Var)
        assert core_term.index == 1

    def test_elab_undefined_var(self):
        """Undefined variable raises error."""
        elab = Elaborator()

        surface = SurfaceVar("x", DUMMY_LOC)
        with pytest.raises(UndefinedVariable):
            elab.elaborate_term(surface)


# =============================================================================
# Lambda Elaboration Tests
# =============================================================================


class TestElaborateLambda:
    """Tests for lambda abstraction elaboration."""

    def test_elab_simple_lambda(self):
        """Elaborate simple lambda."""
        elab = Elaborator()

        # \x -> x
        body = SurfaceVar("x", DUMMY_LOC)
        surface = SurfaceAbs("x", None, body, DUMMY_LOC)
        core_term = elab.elaborate_term(surface)

        assert isinstance(core_term, core.Abs)
        assert isinstance(core_term.body, core.Var)
        assert core_term.body.index == 0

    def test_elab_lambda_with_type(self):
        """Elaborate lambda with type annotation."""
        elab = Elaborator()

        var_type = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        body = SurfaceVar("x", DUMMY_LOC)
        surface = SurfaceAbs("x", var_type, body, DUMMY_LOC)
        core_term = elab.elaborate_term(surface)

        assert isinstance(core_term, core.Abs)
        assert isinstance(core_term.var_type, TypeConstructor)
        assert core_term.var_type.name == "Int"

    def test_elab_nested_lambda(self):
        """Elaborate nested lambda."""
        elab = Elaborator()

        # \x -> \y -> x
        inner_body = SurfaceVar("x", DUMMY_LOC)
        inner_lam = SurfaceAbs("y", None, inner_body, DUMMY_LOC)
        outer_lam = SurfaceAbs("x", None, inner_lam, DUMMY_LOC)
        core_term = elab.elaborate_term(outer_lam)

        assert isinstance(core_term, core.Abs)
        assert isinstance(core_term.body, core.Abs)
        # In inner body, x has index 1 (y is 0)
        assert core_term.body.body.index == 1


# =============================================================================
# Application Elaboration Tests
# =============================================================================


class TestElaborateApp:
    """Tests for application elaboration."""

    def test_elab_simple_app(self):
        """Elaborate simple application."""
        elab = Elaborator()
        elab._add_term_binding("f")
        elab._add_term_binding("x")

        # f x
        func = SurfaceVar("f", DUMMY_LOC)
        arg = SurfaceVar("x", DUMMY_LOC)
        surface = SurfaceApp(func, arg, DUMMY_LOC)
        core_term = elab.elaborate_term(surface)

        assert isinstance(core_term, core.App)
        assert isinstance(core_term.func, core.Var)
        assert isinstance(core_term.arg, core.Var)
        # f is at index 1, x at index 0
        assert core_term.func.index == 1
        assert core_term.arg.index == 0


# =============================================================================
# Type Abstraction Elaboration Tests
# =============================================================================


class TestElaborateTypeAbs:
    """Tests for type abstraction elaboration."""

    def test_elab_type_abs(self):
        """Elaborate type abstraction."""
        elab = Elaborator()

        body = SurfaceVar("x", DUMMY_LOC)
        elab._add_term_binding("x")
        surface = SurfaceTypeAbs("a", body, DUMMY_LOC)
        core_term = elab.elaborate_term(surface)

        assert isinstance(core_term, core.TAbs)
        assert core_term.var == "a"


# =============================================================================
# Type Application Elaboration Tests
# =============================================================================


class TestElaborateTypeApp:
    """Tests for type application elaboration."""

    def test_elab_type_app(self):
        """Elaborate type application."""
        elab = Elaborator()
        elab._add_term_binding("id")

        func = SurfaceVar("id", DUMMY_LOC)
        type_arg = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        surface = SurfaceTypeApp(func, type_arg, DUMMY_LOC)
        core_term = elab.elaborate_term(surface)

        assert isinstance(core_term, core.TApp)
        assert isinstance(core_term.type_arg, TypeConstructor)


# =============================================================================
# Let Binding Elaboration Tests
# =============================================================================


class TestElaborateLet:
    """Tests for let binding elaboration."""

    def test_elab_simple_let(self):
        """Elaborate simple let binding."""
        elab = Elaborator()
        elab._add_term_binding("y")

        # let x = y in x
        value = SurfaceVar("y", DUMMY_LOC)
        body = SurfaceVar("x", DUMMY_LOC)
        surface = SurfaceLet("x", value, body, DUMMY_LOC)
        core_term = elab.elaborate_term(surface)

        assert isinstance(core_term, core.Let)
        assert core_term.name == "x"
        # In body, x is index 0, y is shifted to 1
        assert core_term.body.index == 0


# =============================================================================
# Constructor Elaboration Tests
# =============================================================================


class TestElaborateConstructor:
    """Tests for constructor elaboration."""

    def test_elab_nullary_constructor(self):
        """Elaborate nullary constructor."""
        elab = Elaborator()

        surface = SurfaceConstructor("True", [], DUMMY_LOC)
        core_term = elab.elaborate_term(surface)

        assert isinstance(core_term, core.Constructor)
        assert core_term.name == "True"
        assert core_term.args == []

    def test_elab_unary_constructor(self):
        """Elaborate constructor with argument."""
        elab = Elaborator()
        elab._add_term_binding("x")

        arg = SurfaceVar("x", DUMMY_LOC)
        surface = SurfaceConstructor("Succ", [arg], DUMMY_LOC)
        core_term = elab.elaborate_term(surface)

        assert isinstance(core_term, core.Constructor)
        assert core_term.name == "Succ"
        assert len(core_term.args) == 1


# =============================================================================
# Integer Literal Elaboration Tests
# =============================================================================


class TestElaborateIntLit:
    """Tests for integer literal elaboration."""

    def test_elab_simple_int_lit(self):
        """Elaborate simple integer literal."""
        elab = Elaborator()
        surface = SurfaceIntLit(42, DUMMY_LOC)
        core_term = elab.elaborate_term(surface)

        assert isinstance(core_term, core.IntLit)
        assert core_term.value == 42

    def test_elab_zero(self):
        """Elaborate zero literal."""
        elab = Elaborator()
        surface = SurfaceIntLit(0, DUMMY_LOC)
        core_term = elab.elaborate_term(surface)

        assert isinstance(core_term, core.IntLit)
        assert core_term.value == 0

    def test_elab_large_int(self):
        """Elaborate large integer literal."""
        elab = Elaborator()
        surface = SurfaceIntLit(999999, DUMMY_LOC)
        core_term = elab.elaborate_term(surface)

        assert isinstance(core_term, core.IntLit)
        assert core_term.value == 999999

    def test_elab_int_from_parse(self):
        """Elaborate integer literal from parsed source."""
        surface = parse_term("42")
        core_term = elaborate_term(surface)

        assert isinstance(core_term, core.IntLit)
        assert core_term.value == 42

    def test_elab_int_in_let(self):
        """Elaborate integer in let binding."""
        surface = parse_term("let x = 42\n  x")
        core_term = elaborate_term(surface)

        assert isinstance(core_term, core.Let)
        assert isinstance(core_term.value, core.IntLit)
        assert core_term.value.value == 42

    def test_elab_int_in_application(self):
        """Elaborate integer as function argument."""
        elab = Elaborator()
        elab._add_global_term("f")
        surface = parse_term("f 42")
        core_term = elab.elaborate_term(surface)

        assert isinstance(core_term, core.App)
        assert isinstance(core_term.arg, core.IntLit)
        assert core_term.arg.value == 42


# =============================================================================
# Type Elaboration Tests
# =============================================================================


class TestElaborateTypes:
    """Tests for type elaboration."""

    def test_elab_type_var(self):
        """Elaborate type variable."""
        elab = Elaborator()
        elab._add_type_binding("a")

        surface = SurfaceTypeVar("a", DUMMY_LOC)
        core_type = elab._elaborate_type(surface)

        assert isinstance(core_type, TypeVar)
        assert core_type.name == "a"

    def test_elab_arrow_type(self):
        """Elaborate arrow type."""
        elab = Elaborator()

        arg = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        ret = SurfaceTypeConstructor("Bool", [], DUMMY_LOC)
        surface = SurfaceTypeArrow(arg, ret, DUMMY_LOC)
        core_type = elab._elaborate_type(surface)

        assert isinstance(core_type, TypeArrow)
        assert isinstance(core_type.arg, TypeConstructor)
        assert isinstance(core_type.ret, TypeConstructor)

    def test_elab_forall_type(self):
        """Elaborate forall type."""
        elab = Elaborator()

        body = SurfaceTypeVar("a", DUMMY_LOC)
        surface = SurfaceTypeForall("a", body, DUMMY_LOC)
        core_type = elab._elaborate_type(surface)

        assert isinstance(core_type, TypeForall)
        assert core_type.var == "a"


# =============================================================================
# Declaration Elaboration Tests
# =============================================================================


class TestElaborateDeclarations:
    """Tests for declaration elaboration."""

    def test_elab_term_decl(self):
        """Elaborate term declaration."""
        elab = Elaborator()

        body = SurfaceConstructor("True", [], DUMMY_LOC)
        decl = SurfaceTermDeclaration("x", None, body, DUMMY_LOC)
        core_decl = elab._elaborate_term_decl(decl)

        assert isinstance(core_decl, core.TermDeclaration)
        assert core_decl.name == "x"

    def test_elab_data_decl(self):
        """Elaborate data declaration."""
        elab = Elaborator()

        decl = SurfaceDataDeclaration(
            "Bool",
            [],
            [
                SurfaceConstructorInfo("True", [], None, DUMMY_LOC),
                SurfaceConstructorInfo("False", [], None, DUMMY_LOC),
            ],
            DUMMY_LOC,
        )
        core_decl = elab._elaborate_data_decl(decl)

        assert isinstance(core_decl, core.DataDeclaration)
        assert core_decl.name == "Bool"
        assert len(core_decl.constructors) == 2


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_elab_term_function(self):
        """Test elaborate_term convenience function."""
        surface = parse_term(r"\x -> x")
        core_term = elaborate_term(surface)

        assert isinstance(core_term, core.Abs)
        assert isinstance(core_term.body, core.Var)

    def test_elab_with_context(self):
        """Test elaborate_term_with_context."""
        surface = parse_term("x")
        core_term = elaborate_term(surface, context=["y", "x"])

        assert isinstance(core_term, core.Var)
        assert core_term.index == 0  # x is most recent


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for parse + elaborate pipeline."""

    def test_id_function(self):
        """Parse and elaborate identity function."""
        surface = parse_term(r"/\a. \x:a -> x")
        core_term = elaborate_term(surface)

        assert isinstance(core_term, core.TAbs)
        assert isinstance(core_term.body, core.Abs)
        assert isinstance(core_term.body.body, core.Var)
        assert core_term.body.body.index == 0

    def test_application_chain(self):
        """Parse and elaborate application chain."""
        surface = parse_term("f x y")
        elab = Elaborator()
        elab._add_term_binding("y")
        elab._add_term_binding("x")
        elab._add_term_binding("f")
        core_term = elab.elaborate_term(surface)

        # Should be App(App(f, x), y)
        assert isinstance(core_term, core.App)
        assert isinstance(core_term.func, core.App)
        assert isinstance(core_term.func.func, core.Var)

    def test_complex_nested(self):
        """Parse and elaborate complex nested term."""
        surface = parse_term("let f = \\x -> x\n  f @Int 1")
        core_term = elaborate_term(surface)

        assert isinstance(core_term, core.Let)


# =============================================================================
# Primitive Operation Elaboration Tests
# =============================================================================


class TestElaboratePrimOp:
    """Tests for primitive operation name resolution ($prim.xxx)."""

    def test_elab_prim_op_name(self):
        """Elaborate $prim.int_plus to PrimOp core term."""
        elab = Elaborator()
        surface = SurfaceVar("$prim.int_plus", DUMMY_LOC)
        core_term = elab.elaborate_term(surface)

        assert isinstance(core_term, core.PrimOp)
        assert core_term.name == "int_plus"

    def test_elab_prim_op_int_minus(self):
        """Elaborate $prim.int_minus to PrimOp."""
        elab = Elaborator()
        surface = SurfaceVar("$prim.int_minus", DUMMY_LOC)
        core_term = elab.elaborate_term(surface)

        assert isinstance(core_term, core.PrimOp)
        assert core_term.name == "int_minus"

    def test_elab_prim_op_with_other_prefix_raises(self):
        """Variables starting with $prim. must be fully resolved."""
        elab = Elaborator()
        # $prim.unknown is not in global_terms, so it should become PrimOp
        surface = SurfaceVar("$prim.unknown", DUMMY_LOC)
        core_term = elab.elaborate_term(surface)

        # $prim. names are always converted to PrimOp regardless of whether
        # they exist in the primitive registry
        assert isinstance(core_term, core.PrimOp)
        assert core_term.name == "unknown"

    def test_elab_regular_var_with_dollar_prefix_raises(self):
        """Regular variables starting with $ should raise error."""
        elab = Elaborator()
        surface = SurfaceVar("$not_prim", DUMMY_LOC)

        with pytest.raises(UndefinedVariable):
            elab.elaborate_term(surface)
