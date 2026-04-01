"""Comprehensive tests for each elaborator synthesis rule.

Tests every case in the elaborator's infer() and check() methods
to ensure complete coverage of the bidirectional type checking algorithm.
"""

import pytest
from systemf.core import ast as core
from systemf.core.types import (
    TypeArrow,
    TypeConstructor,
    TypeForall,
    TypeVar,
)
from systemf.surface.inference import BidiInference
from systemf.surface.inference.context import TypeContext
from systemf.utils.location import Location
from systemf.surface.types import (
    ScopedAbs,
    ScopedVar,
    SurfaceAbs,
    SurfaceAnn,
    SurfaceApp,
    SurfaceCase,
    SurfaceConstructor,
    SurfaceIf,
    SurfaceLet,
    SurfaceLit,
    SurfaceOp,
    SurfacePattern,
    SurfaceBranch,
    SurfaceTuple,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceTypeArrow,
    SurfaceTypeConstructor,
    SurfaceTypeForall,
    SurfaceTypeVar,
    SurfaceVarPattern,
)

# Test fixture location
DUMMY_LOC = Location(line=1, column=1, file="test.py")


class TestSynthesisRules:
    """Test each synthesis rule in the elaborator."""

    def test_literal_int_synthesis(self):
        """Rule: SurfaceLit(prim_type="Int") => Int"""
        elab = BidiInference()
        ctx = TypeContext()

        lit = SurfaceLit(prim_type="Int", value=42, location=DUMMY_LOC)
        core_term, ty = elab.infer(lit, ctx)

        assert isinstance(core_term, core.Lit)
        assert core_term.prim_type == "Int"
        assert isinstance(ty, TypeConstructor)
        assert ty.name == "Int"

    def test_literal_string_synthesis(self):
        """Rule: SurfaceLit(prim_type="String") => String"""
        elab = BidiInference()
        ctx = TypeContext()

        lit = SurfaceLit(prim_type="String", value="hello", location=DUMMY_LOC)
        core_term, ty = elab.infer(lit, ctx)

        assert isinstance(core_term, core.Lit)
        assert core_term.prim_type == "String"
        assert isinstance(ty, TypeConstructor)
        assert ty.name == "String"

    def test_variable_lookup_synthesis(self):
        """Rule: ScopedVar(index) => ctx.lookup_term(index)"""
        elab = BidiInference()
        ctx = TypeContext(term_types=[TypeConstructor("Int", [])])

        var = ScopedVar(index=0, debug_name="x", location=DUMMY_LOC)
        core_term, ty = elab.infer(var, ctx)

        assert isinstance(core_term, core.Var)
        assert core_term.index == 0
        assert isinstance(ty, TypeConstructor)
        assert ty.name == "Int"

    def test_lambda_with_annotation_synthesis(self):
        """Rule: ScopedAbs(var, Some(type), body) => type -> body_type"""
        elab = BidiInference()
        ctx = TypeContext()

        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        body = ScopedVar(index=0, debug_name="x", location=DUMMY_LOC)
        abs_term = ScopedAbs(var_name="x", var_type=int_type, body=body, location=DUMMY_LOC)

        core_term, ty = elab.infer(abs_term, ctx)

        assert isinstance(core_term, core.Abs)
        assert isinstance(ty, TypeArrow)
        assert ty.arg.name == "Int"
        assert ty.ret.name == "Int"

    def test_lambda_without_annotation_synthesis(self):
        """Rule: ScopedAbs(var, None, body) => _a -> body_type"""
        elab = BidiInference()
        ctx = TypeContext()

        body = ScopedVar(index=0, debug_name="x", location=DUMMY_LOC)
        abs_term = ScopedAbs(var_name="x", var_type=None, body=body, location=DUMMY_LOC)

        core_term, ty = elab.infer(abs_term, ctx)

        assert isinstance(core_term, core.Abs)
        # Should create identity function type _a -> _a
        assert isinstance(ty, TypeArrow)

    def test_application_arrow_synthesis(self):
        """Rule: SurfaceApp(func, arg) where func => A -> B, arg <= A => B"""
        elab = BidiInference()
        ctx = TypeContext()

        # Create: (\x:Int -> x) 42
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        body = ScopedVar(index=0, debug_name="x", location=DUMMY_LOC)
        abs_term = ScopedAbs(var_name="x", var_type=int_type, body=body, location=DUMMY_LOC)
        arg = SurfaceLit(prim_type="Int", value=42, location=DUMMY_LOC)
        app = SurfaceApp(func=abs_term, arg=arg, location=DUMMY_LOC)

        core_term, ty = elab.infer(app, ctx)

        assert isinstance(core_term, core.App)
        assert isinstance(ty, TypeConstructor)
        assert ty.name == "Int"

    def test_type_abstraction_synthesis(self):
        """Rule: SurfaceTypeAbs(var, body) => forall var. body_type"""
        elab = BidiInference()
        ctx = TypeContext()

        # /\a. \x:a -> x
        type_var = SurfaceTypeVar(name="a", location=DUMMY_LOC)
        var_type = SurfaceTypeVar(name="a", location=DUMMY_LOC)
        body = ScopedAbs(
            var_name="x",
            var_type=var_type,
            body=ScopedVar(index=0, debug_name="x", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        type_abs = SurfaceTypeAbs(var="a", body=body, location=DUMMY_LOC)

        core_term, ty = elab.infer(type_abs, ctx)

        assert isinstance(core_term, core.TAbs)
        assert isinstance(ty, TypeForall)

    def test_type_application_synthesis(self):
        """Rule: SurfaceTypeApp(func, type_arg) where func => forall a. body => body[a/type_arg]"""
        elab = BidiInference()
        ctx = TypeContext()

        # id : forall a. a -> a
        # id @Int
        type_var = SurfaceTypeVar(name="a", location=DUMMY_LOC)
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)

        # Create polymorphic identity
        body = ScopedAbs(
            var_name="x",
            var_type=type_var,
            body=ScopedVar(index=0, debug_name="x", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        type_abs = SurfaceTypeAbs(var="a", body=body, location=DUMMY_LOC)

        # Apply to Int
        type_app = SurfaceTypeApp(func=type_abs, type_arg=int_type, location=DUMMY_LOC)

        core_term, ty = elab.infer(type_app, ctx)

        assert isinstance(core_term, core.TApp)
        # Type should be Int -> Int after instantiation
        assert isinstance(ty, TypeArrow)

    def test_let_binding_synthesis(self):
        """Rule: SurfaceLet(bindings, body) => body_type (after extending ctx)"""
        elab = BidiInference()
        ctx = TypeContext()

        # let x = 42 in x
        bindings = [("x", None, SurfaceLit(prim_type="Int", value=42, location=DUMMY_LOC))]
        body = ScopedVar(index=0, debug_name="x", location=DUMMY_LOC)
        let_term = SurfaceLet(bindings=bindings, body=body, location=DUMMY_LOC)

        core_term, ty = elab.infer(let_term, ctx)

        assert isinstance(core_term, core.Let)
        assert isinstance(ty, TypeConstructor)
        assert ty.name == "Int"

    def test_annotation_synthesis(self):
        """Rule: SurfaceAnn(term, type) => type (after checking term <= type)"""
        elab = BidiInference()
        ctx = TypeContext()

        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        ann_term = SurfaceAnn(
            term=SurfaceLit(prim_type="Int", value=42, location=DUMMY_LOC),
            type=int_type,
            location=DUMMY_LOC,
        )

        core_term, ty = elab.infer(ann_term, ctx)

        assert isinstance(core_term, core.Lit)
        assert isinstance(ty, TypeConstructor)
        assert ty.name == "Int"

    def test_constructor_synthesis(self):
        """Rule: SurfaceConstructor(name, args) => constructor_type (instantiated)"""
        elab = BidiInference()
        # Register a constructor
        ctx = TypeContext(constructors={"True": TypeConstructor("Bool", [])})

        constr = SurfaceConstructor(name="True", args=[], location=DUMMY_LOC)
        core_term, ty = elab.infer(constr, ctx)

        assert isinstance(core_term, core.Constructor)
        assert isinstance(ty, TypeConstructor)
        assert ty.name == "Bool"

    def test_case_synthesis(self):
        """Rule: SurfaceCase(scrutinee, branches) => common_type (after checking all branches)"""
        elab = BidiInference()
        ctx = TypeContext(
            constructors={"True": TypeConstructor("Bool", []), "False": TypeConstructor("Bool", [])}
        )

        branches = [
            SurfaceBranch(
                pattern=SurfacePattern(patterns=[SurfaceVarPattern(name="True", location=DUMMY_LOC)], location=DUMMY_LOC),
                body=SurfaceLit(prim_type="Int", value=1, location=DUMMY_LOC),
                location=DUMMY_LOC,
            ),
            SurfaceBranch(
                pattern=SurfacePattern(patterns=[SurfaceVarPattern(name="False", location=DUMMY_LOC)], location=DUMMY_LOC),
                body=SurfaceLit(prim_type="Int", value=0, location=DUMMY_LOC),
                location=DUMMY_LOC,
            ),
        ]
        case_term = SurfaceCase(
            scrutinee=SurfaceConstructor(name="True", args=[], location=DUMMY_LOC),
            branches=branches,
            location=DUMMY_LOC,
        )

        core_term, ty = elab.infer(case_term, ctx)

        assert isinstance(core_term, core.Case)
        assert isinstance(ty, TypeConstructor)
        assert ty.name == "Int"

    def test_tuple_synthesis(self):
        """Rule: SurfaceTuple(elements) => Tuple constructor with args"""
        elab = BidiInference()
        ctx = TypeContext()

        tuple_term = SurfaceTuple(
            elements=[
                SurfaceLit(prim_type="Int", value=1, location=DUMMY_LOC),
                SurfaceLit(prim_type="Int", value=2, location=DUMMY_LOC),
            ],
            location=DUMMY_LOC,
        )

        core_term, ty = elab.infer(tuple_term, ctx)

        # Tuples create a Tuple constructor application
        assert isinstance(core_term, core.Constructor)
        assert core_term.name == "Tuple"
        assert len(core_term.args) == 2

    def test_operator_synthesis(self):
        """Rule: SurfaceOp(left, op, right) where op desugars to primitive => result_type"""
        elab = BidiInference()
        ctx = TypeContext()

        op_term = SurfaceOp(
            left=SurfaceLit(prim_type="Int", value=1, location=DUMMY_LOC),
            op="+",
            right=SurfaceLit(prim_type="Int", value=2, location=DUMMY_LOC),
            location=DUMMY_LOC,
        )

        core_term, ty = elab.infer(op_term, ctx)

        # After desugaring, should be application of int_plus
        assert isinstance(core_term, core.App)


class TestCheckingRules:
    """Test each checking rule in the elaborator."""

    def test_lambda_checking(self):
        """Rule: check(ScopedAbs, A -> B) => Abs (after extending ctx with A)"""
        elab = BidiInference()
        ctx = TypeContext()

        # Check \x -> x against Int -> Int
        int_type = TypeConstructor("Int", [])
        expected = TypeArrow(int_type, int_type)

        body = ScopedVar(index=0, debug_name="x", location=DUMMY_LOC)
        abs_term = ScopedAbs(var_name="x", var_type=None, body=body, location=DUMMY_LOC)

        core_term = elab.check(abs_term, expected, ctx)

        assert isinstance(core_term, core.Abs)

    def test_annotation_checking(self):
        """Rule: check(SurfaceAnn(term, ann), expected) => check(term, ann) if ann == expected"""
        elab = BidiInference()
        ctx = TypeContext()

        int_type_surf = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        int_type_core = TypeConstructor("Int", [])

        ann_term = SurfaceAnn(
            term=SurfaceLit(prim_type="Int", value=42, location=DUMMY_LOC),
            type=int_type_surf,
            location=DUMMY_LOC,
        )

        core_term = elab.check(ann_term, int_type_core, ctx)

        assert isinstance(core_term, core.Lit)

    def test_fallback_infer_check(self):
        """Rule: check(term, expected) where term not specifically handled =>
        infer(term) then unify with expected"""
        elab = BidiInference()
        ctx = TypeContext()

        int_type = TypeConstructor("Int", [])
        lit = SurfaceLit(prim_type="Int", value=42, location=DUMMY_LOC)

        # Should work since lit infers to Int
        core_term = elab.check(lit, int_type, ctx)

        assert isinstance(core_term, core.Lit)


class TestTypeConversionRules:
    """Test type conversion rules."""

    def test_surface_type_var_conversion(self):
        """Convert SurfaceTypeVar to TypeVar"""
        elab = BidiInference()
        ctx = TypeContext(type_vars=[("a", None)])

        type_var = SurfaceTypeVar(name="a", location=DUMMY_LOC)
        core_type = elab._surface_to_core_type(type_var, ctx)

        assert isinstance(core_type, TypeVar)
        assert core_type.name == "a"

    def test_surface_type_constructor_conversion(self):
        """Convert SurfaceTypeConstructor to TypeConstructor"""
        elab = BidiInference()
        ctx = TypeContext()

        constr = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        core_type = elab._surface_to_core_type(constr, ctx)

        assert isinstance(core_type, TypeConstructor)
        assert core_type.name == "Int"

    def test_surface_type_arrow_conversion(self):
        """Convert SurfaceTypeArrow to TypeArrow"""
        elab = BidiInference()
        ctx = TypeContext()

        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)
        arrow = SurfaceTypeArrow(arg=int_type, ret=int_type, param_doc=None, location=DUMMY_LOC)
        core_type = elab._surface_to_core_type(arrow, ctx)

        assert isinstance(core_type, TypeArrow)
        assert core_type.arg.name == "Int"
        assert core_type.ret.name == "Int"

    def test_surface_type_forall_conversion(self):
        """Convert SurfaceTypeForall to TypeForall"""
        elab = BidiInference()
        ctx = TypeContext()

        type_var = SurfaceTypeVar(name="a", location=DUMMY_LOC)
        arrow = SurfaceTypeArrow(arg=type_var, ret=type_var, param_doc=None, location=DUMMY_LOC)
        forall = SurfaceTypeForall(var="a", body=arrow, location=DUMMY_LOC)
        core_type = elab._surface_to_core_type(forall, ctx)

        assert isinstance(core_type, TypeForall)


class TestPolymorphismRules:
    """Test polymorphism and instantiation rules."""

    def test_implicit_instantiation(self):
        """Test that polymorphic functions are implicitly instantiated at application."""
        elab = BidiInference()
        ctx = TypeContext()

        # Create: id @Int 42 where id : forall a. a -> a
        type_var = SurfaceTypeVar(name="a", location=DUMMY_LOC)
        int_type = SurfaceTypeConstructor(name="Int", args=[], location=DUMMY_LOC)

        # id = /\a. \x:a -> x
        id_body = ScopedAbs(
            var_name="x",
            var_type=type_var,
            body=ScopedVar(index=0, debug_name="x", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        id_fn = SurfaceTypeAbs(var="a", body=id_body, location=DUMMY_LOC)

        # Apply to Int type
        id_int = SurfaceTypeApp(func=id_fn, type_arg=int_type, location=DUMMY_LOC)

        # Apply to value
        app = SurfaceApp(
            func=id_int,
            arg=SurfaceLit(prim_type="Int", value=42, location=DUMMY_LOC),
            location=DUMMY_LOC,
        )

        core_term, ty = elab.infer(app, ctx)

        assert isinstance(core_term, core.App)
        assert isinstance(ty, TypeConstructor)
        assert ty.name == "Int"

    def test_polymorphic_identity_synthesis(self):
        """Test synthesis of polymorphic identity function."""
        elab = BidiInference()
        ctx = TypeContext()

        # id : forall a. a -> a
        type_var = SurfaceTypeVar(name="a", location=DUMMY_LOC)
        body = ScopedAbs(
            var_name="x",
            var_type=type_var,
            body=ScopedVar(index=0, debug_name="x", location=DUMMY_LOC),
            location=DUMMY_LOC,
        )
        id_fn = SurfaceTypeAbs(var="a", body=body, location=DUMMY_LOC)

        core_term, ty = elab.infer(id_fn, ctx)

        assert isinstance(core_term, core.TAbs)
        assert isinstance(ty, TypeForall)
        assert ty.var == "a"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
