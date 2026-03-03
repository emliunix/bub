"""Tests for bidirectional type checker."""

import pytest

from systemf.core.ast import (
    Abs,
    App,
    Branch,
    Case,
    Constructor,
    DataDeclaration,
    Let,
    Pattern,
    TAbs,
    TApp,
    TermDeclaration,
    Var,
)
from systemf.core.checker import TypeChecker
from systemf.core.context import Context
from systemf.core.errors import TypeMismatch, UndefinedConstructor, UndefinedVariable
from systemf.core.types import TypeArrow, TypeConstructor, TypeForall, TypeVar


# =============================================================================
# Basic Type Checking Tests
# =============================================================================


class TestInferVar:
    """Tests for variable type inference."""

    def test_infer_var_basic(self):
        """Infer type of variables at different indices."""
        checker = TypeChecker()

        # Single variable
        ctx1 = Context.empty().extend_term(TypeVar("a"))
        ty1 = checker.infer(ctx1, Var(index=0))
        assert ty1 == TypeVar("a")

        # Second variable in context
        ctx2 = Context.empty().extend_term(TypeVar("b")).extend_term(TypeVar("a"))
        ty2 = checker.infer(ctx2, Var(index=1))
        assert ty2 == TypeVar("b")

    def test_infer_undefined_var(self):
        """Should raise UndefinedVariable for out-of-bounds index."""
        ctx = Context.empty()
        checker = TypeChecker()
        with pytest.raises(UndefinedVariable):
            checker.infer(ctx, Var(index=0))


class TestInferApp:
    """Tests for function application type inference."""

    def test_infer_app_basic(self):
        """Test basic function applications."""
        # (λx:a. x) y : a
        a = TypeVar("a")
        ctx = Context.empty().extend_term(a)
        lam = Abs(var_type=a, body=Var(index=0))
        app = App(func=lam, arg=Var(index=0))
        checker = TypeChecker()
        ty = checker.infer(ctx, app)
        assert ty == a

        # (λx:Int. λy:Bool. x) 42 : Bool -> Int
        int_ty = TypeConstructor("Int", [])
        bool_ty = TypeConstructor("Bool", [])
        const = Abs(
            var_type=int_ty, body=Abs(var_type=bool_ty, body=Var(index=1))
        )  # λx:Int. λy:Bool. x
        constructors = {"Int": int_ty}
        checker2 = TypeChecker(constructors)
        app2 = App(func=const, arg=Constructor(name="Int", args=[]))
        ty2 = checker2.infer(Context.empty(), app2)
        assert ty2 == TypeArrow(bool_ty, int_ty)

    def test_infer_app_mismatch(self):
        """Should fail when argument type doesn't match."""
        int_ty = TypeConstructor("Int", [])
        bool_ty = TypeConstructor("Bool", [])
        id_int = Abs(var_type=int_ty, body=Var(index=0))
        # Register Bool constructor but not Int
        constructors = {"Bool": bool_ty}
        checker = TypeChecker(constructors)
        app = App(func=id_int, arg=Constructor(name="Bool", args=[]))
        with pytest.raises(TypeMismatch):
            checker.infer(Context.empty(), app)


class TestCheckAbs:
    """Tests for lambda abstraction checking mode."""

    def test_check_abs_basic(self):
        """Check λx:a. x : a -> a"""
        a = TypeVar("a")
        lam = Abs(var_type=a, body=Var(index=0))
        checker = TypeChecker()
        checker.check(Context.empty(), lam, TypeArrow(a, a))

    def test_check_abs_different_type(self):
        """Check λx:Int. x : Int -> Int"""
        int_ty = TypeConstructor("Int", [])
        lam = Abs(var_type=int_ty, body=Var(index=0))
        checker = TypeChecker()
        checker.check(Context.empty(), lam, TypeArrow(int_ty, int_ty))


# =============================================================================
# Polymorphism Tests
# =============================================================================


class TestPolymorphism:
    """Tests for type abstractions and applications."""

    def test_type_abstraction(self):
        """Λa. λx:a. x : ∀a. a → a"""
        body = Abs(var_type=TypeVar("a"), body=Var(index=0))
        tabs = TAbs(var="a", body=body)
        checker = TypeChecker()
        ty = checker.infer(Context.empty(), tabs)
        assert ty == TypeForall("a", TypeArrow(TypeVar("a"), TypeVar("a")))

    def test_type_application(self):
        """(Λa. λx:a. x) [Int] : Int → Int"""
        int_ty = TypeConstructor("Int", [])
        id_poly = TAbs(var="a", body=Abs(var_type=TypeVar("a"), body=Var(index=0)))
        tapp = TApp(func=id_poly, type_arg=int_ty)
        checker = TypeChecker()
        ty = checker.infer(Context.empty(), tapp)
        assert ty == TypeArrow(int_ty, int_ty)

    def test_type_abstraction_check(self):
        """Check Λa. λx:a. x : ∀a. a → a"""
        a = TypeVar("a")
        body = Abs(var_type=a, body=Var(index=0))
        tabs = TAbs(var="a", body=body)
        checker = TypeChecker()
        expected = TypeForall("a", TypeArrow(a, a))
        checker.check(Context.empty(), tabs, expected)

    def test_type_application_chain(self):
        """Multiple type applications."""
        a = TypeVar("a")
        int_ty = TypeConstructor("Int", [])
        bool_ty = TypeConstructor("Bool", [])

        # Λa. Λb. λx:a. λy:b. x : ∀a. ∀b. a -> b -> a
        const_poly = TAbs(
            var="a",
            body=TAbs(var="b", body=Abs(var_type=a, body=Abs(var_type=bool_ty, body=Var(index=1)))),
        )

        # Apply to [Int][Bool]
        tapp = TApp(func=TApp(func=const_poly, type_arg=int_ty), type_arg=bool_ty)

        checker = TypeChecker()
        ty = checker.infer(Context.empty(), tapp)
        assert ty == TypeArrow(int_ty, TypeArrow(bool_ty, int_ty))


# =============================================================================
# Data Type Tests
# =============================================================================


class TestDataConstructors:
    """Tests for data constructor type checking."""

    def test_nullary_constructor(self):
        """Test nullary constructors like Nil and Nothing."""
        constructors = {
            "Nil": TypeForall("a", TypeConstructor("List", [TypeVar("a")])),
            "Nothing": TypeForall("a", TypeConstructor("Maybe", [TypeVar("a")])),
        }
        checker = TypeChecker(constructors)

        # Nil should be List _t0 where _t0 is a fresh metavar
        nil = Constructor(name="Nil", args=[])
        nil_ty = checker.infer(Context.empty(), nil)
        assert isinstance(nil_ty, TypeConstructor)
        assert nil_ty.name == "List"
        assert len(nil_ty.args) == 1
        assert isinstance(nil_ty.args[0], TypeVar)
        assert nil_ty.args[0].name.startswith("_t")  # Fresh metavar

        # Nothing should be Maybe _t0
        nothing = Constructor(name="Nothing", args=[])
        nothing_ty = checker.infer(Context.empty(), nothing)
        assert isinstance(nothing_ty, TypeConstructor)
        assert nothing_ty.name == "Maybe"

    def test_unary_constructor(self):
        """Test unary constructors like Cons and Just."""
        a = TypeVar("a")
        constructors = {
            "Cons": TypeForall(
                "a",
                TypeArrow(
                    TypeVar("a"),
                    TypeArrow(
                        TypeConstructor("List", [TypeVar("a")]),
                        TypeConstructor("List", [TypeVar("a")]),
                    ),
                ),
            ),
            "Just": TypeForall("a", TypeArrow(a, TypeConstructor("Maybe", [a]))),
        }
        checker = TypeChecker(constructors)

        # Cons should be _t0 → List _t0 → List _t0
        cons = Constructor(name="Cons", args=[])
        cons_ty = checker.infer(Context.empty(), cons)
        assert isinstance(cons_ty, TypeArrow)
        assert isinstance(cons_ty.ret, TypeArrow)
        assert isinstance(cons_ty.ret.ret, TypeConstructor)
        assert cons_ty.ret.ret.name == "List"

        # Just should be _t0 → Maybe _t0
        just = Constructor(name="Just", args=[])
        just_ty = checker.infer(Context.empty(), just)
        assert isinstance(just_ty, TypeArrow)
        assert isinstance(just_ty.ret, TypeConstructor)
        assert just_ty.ret.name == "Maybe"

    def test_undefined_constructor(self):
        """Should fail for undefined constructor."""
        checker = TypeChecker()
        with pytest.raises(UndefinedConstructor):
            checker.infer(Context.empty(), Constructor(name="Unknown", args=[]))


class TestCaseExpressions:
    """Tests for pattern matching with case expressions."""

    def test_case_simple_list(self):
        """case xs of { Nil → 0; Cons y ys → 1 }"""
        int_ty = TypeConstructor("Int", [])
        constructors = {
            "Nil": TypeForall("a", TypeConstructor("List", [TypeVar("a")])),
            "Cons": TypeForall(
                "a",
                TypeArrow(
                    TypeVar("a"),
                    TypeArrow(
                        TypeConstructor("List", [TypeVar("a")]),
                        TypeConstructor("List", [TypeVar("a")]),
                    ),
                ),
            ),
        }
        # Register Int constructor for literals
        constructors["Int"] = int_ty
        checker = TypeChecker(constructors)
        # xs : List Int
        xs_ty = TypeConstructor("List", [int_ty])
        ctx = Context.empty().extend_term(xs_ty)

        scrut = Var(index=0)
        branches = [
            Branch(
                pattern=Pattern(constructor="Nil", vars=[]), body=Constructor(name="Int", args=[])
            ),  # 0
            Branch(
                pattern=Pattern(constructor="Cons", vars=["y", "ys"]),
                body=Constructor(name="Int", args=[]),
            ),  # 1
        ]
        case_expr = Case(scrutinee=scrut, branches=branches)

        ty = checker.infer(ctx, case_expr)
        assert ty == int_ty

    def test_case_comprehensive(self):
        """Test case expressions with variables and multiple constructors."""
        int_ty = TypeConstructor("Int", [])
        bool_ty = TypeConstructor("Bool", [])
        maybe_int = TypeConstructor("Maybe", [int_ty])
        constructors = {
            # Maybe constructors
            "Just": TypeForall(
                "a", TypeArrow(TypeVar("a"), TypeConstructor("Maybe", [TypeVar("a")]))
            ),
            "Nothing": TypeForall("a", TypeConstructor("Maybe", [TypeVar("a")])),
            # Bool constructors
            "True": TypeConstructor("Bool", []),
            "False": TypeConstructor("Bool", []),
            "Int": int_ty,  # For literals
        }
        checker = TypeChecker(constructors)

        # Test 1: case with pattern variables (Just y → y)
        ctx = Context.empty().extend_term(maybe_int)
        scrut = Var(index=0)
        branches = [
            Branch(pattern=Pattern(constructor="Just", vars=["y"]), body=Var(index=0)),  # y : Int
            Branch(
                pattern=Pattern(constructor="Nothing", vars=[]),
                body=Constructor(name="Int", args=[]),
            ),  # 0
        ]
        case_expr = Case(scrutinee=scrut, branches=branches)
        ty = checker.infer(ctx, case_expr)
        assert ty == int_ty

        # Test 2: case with different constructors, same result type
        ctx2 = Context.empty().extend_term(bool_ty)
        scrut2 = Var(index=0)
        branches2 = [
            Branch(
                pattern=Pattern(constructor="True", vars=[]), body=Constructor(name="Int", args=[])
            ),  # Int
            Branch(
                pattern=Pattern(constructor="False", vars=[]), body=Constructor(name="Int", args=[])
            ),  # Int
        ]
        case_expr2 = Case(scrutinee=scrut2, branches=branches2)
        ty2 = checker.infer(ctx2, case_expr2)
        assert ty2 == int_ty


# =============================================================================
# Let Binding Tests
# =============================================================================


class TestLetBindings:
    """Tests for let expressions."""

    def test_let_simple(self):
        """let x = 42 in x : Int"""
        int_ty = TypeConstructor("Int", [])
        constructors = {"Int": int_ty}
        checker = TypeChecker(constructors)

        let_expr = Let(name="x", value=Constructor(name="Int", args=[]), body=Var(index=0))
        ty = checker.infer(Context.empty(), let_expr)
        assert ty == int_ty

    def test_let_function(self):
        """let id = λx:a. x in id : a -> a"""
        a = TypeVar("a")
        id_func = Abs(var_type=a, body=Var(index=0))
        let_expr = Let(name="id", value=id_func, body=Var(index=0))

        checker = TypeChecker()
        ty = checker.infer(Context.empty(), let_expr)
        assert ty == TypeArrow(a, a)

    def test_let_nested(self):
        """Nested let expressions."""
        int_ty = TypeConstructor("Int", [])
        bool_ty = TypeConstructor("Bool", [])
        constructors = {
            "Int": int_ty,
            "Bool": bool_ty,
        }
        checker = TypeChecker(constructors)

        # let x = 42 in let y = true in x
        inner = Let(
            name="y", value=Constructor(name="Bool", args=[]), body=Var(index=1)
        )  # x is now at index 1
        outer = Let(name="x", value=Constructor(name="Int", args=[]), body=inner)

        ty = checker.infer(Context.empty(), outer)
        assert ty == int_ty


# =============================================================================
# Error Cases
# =============================================================================


class TestTypeErrors:
    """Tests for type error detection."""

    def test_type_mismatch_self_application(self):
        """λx:Int. x x  (applying Int to Int - should fail)"""
        int_ty = TypeConstructor("Int", [])
        lam = Abs(var_type=int_ty, body=App(func=Var(index=0), arg=Var(index=0)))
        checker = TypeChecker()
        with pytest.raises(TypeMismatch):
            checker.check(Context.empty(), lam, TypeArrow(int_ty, int_ty))

    def test_type_mismatch_arrow_expected(self):
        """Should fail when expecting arrow but getting non-arrow."""
        int_ty = TypeConstructor("Int", [])
        # Register Int constructor
        constructors = {"Int": int_ty}
        checker = TypeChecker(constructors)
        with pytest.raises(TypeMismatch):
            checker.check(
                Context.empty(), Constructor(name="Int", args=[]), TypeArrow(int_ty, int_ty)
            )

    def test_case_branch_type_mismatch(self):
        """Branches with different types should fail."""
        int_ty = TypeConstructor("Int", [])
        bool_ty = TypeConstructor("Bool", [])
        constructors = {
            "True": TypeConstructor("Bool", []),
            "False": TypeConstructor("Bool", []),
            "Int": int_ty,
            "Bool": bool_ty,
        }
        checker = TypeChecker(constructors)
        ctx = Context.empty().extend_term(bool_ty)

        scrut = Var(index=0)
        branches = [
            Branch(
                pattern=Pattern(constructor="True", vars=[]), body=Constructor(name="Int", args=[])
            ),  # Int
            Branch(
                pattern=Pattern(constructor="False", vars=[]),
                body=Constructor(name="Bool", args=[]),
            ),  # Bool
        ]
        case_expr = Case(scrutinee=scrut, branches=branches)

        with pytest.raises(TypeMismatch):
            checker.infer(ctx, case_expr)


# =============================================================================
# Complex Programs
# =============================================================================


class TestComplexPrograms:
    """Tests for more complex type checking scenarios."""

    def test_compose(self):
        """λf:(b->c). λg:(a->b). λx:a. f (g x) : (b->c) -> (a->b) -> a -> c"""
        a, b, c = TypeVar("a"), TypeVar("b"), TypeVar("c")

        # Types for f, g, x
        f_ty = TypeArrow(b, c)
        g_ty = TypeArrow(a, b)

        # Body: f (g x)
        body = App(func=Var(index=2), arg=App(func=Var(index=1), arg=Var(index=0)))  # f (g x)

        # λx:a. f (g x)
        lam_x = Abs(var_type=a, body=body)
        # λg:(a->b). λx:a. f (g x)
        lam_g = Abs(var_type=g_ty, body=lam_x)
        # λf:(b->c). λg:(a->b). λx:a. f (g x)
        compose = Abs(var_type=f_ty, body=lam_g)

        checker = TypeChecker()
        result_type = checker.infer(Context.empty(), compose)

        expected = TypeArrow(f_ty, TypeArrow(g_ty, TypeArrow(a, c)))
        assert result_type == expected

    def test_polymorphic_identity_application(self):
        """Apply polymorphic identity to multiple types."""
        int_ty = TypeConstructor("Int", [])
        bool_ty = TypeConstructor("Bool", [])

        # id = Λa. λx:a. x
        id_poly = TAbs(var="a", body=Abs(var_type=TypeVar("a"), body=Var(index=0)))

        # let id = ... in (id [Int] 42, id [Bool] true)
        # For testing, just check id [Int] 42
        id_int = TApp(func=id_poly, type_arg=int_ty)
        constructors = {"Int": int_ty}
        checker = TypeChecker(constructors)

        app = App(func=id_int, arg=Constructor(name="Int", args=[]))
        ty = checker.infer(Context.empty(), app)
        assert ty == int_ty

    def test_list_map_type(self):
        """Type check a simple map function for lists."""
        a, b = TypeVar("a"), TypeVar("b")
        list_a = TypeConstructor("List", [a])
        list_b = TypeConstructor("List", [b])

        constructors = {
            "Nil": TypeForall("a", list_a),
            "Cons": TypeForall("a", TypeArrow(a, TypeArrow(list_a, list_a))),
        }

        # map : (a -> b) -> List a -> List b
        # map f xs = case xs of
        #   Nil -> Nil
        #   Cons y ys -> Cons (f y) (map f ys)

        # For this test, just check the type of the Nil case
        checker = TypeChecker(constructors)
        ctx = Context.empty().extend_type("a").extend_type("b")
        ctx = ctx.extend_term(TypeArrow(a, b)).extend_term(list_a)

        # Nil case returns Nil - which has type List _t0 (fresh metavar)
        nil_branch = Branch(
            pattern=Pattern(constructor="Nil", vars=[]), body=Constructor(name="Nil", args=[])
        )

        # Check the branch in the correct context
        scrut = Var(index=0)  # xs : List a
        case_expr = Case(scrutinee=scrut, branches=[nil_branch])

        ty = checker.infer(ctx, case_expr)
        # In inference mode, Nil creates a fresh metavar: List _t0
        assert isinstance(ty, TypeConstructor)
        assert ty.name == "List"
        assert len(ty.args) == 1
        assert isinstance(ty.args[0], TypeVar)
        assert ty.args[0].name.startswith("_t")


# =============================================================================
# Declaration Tests
# =============================================================================


class TestDeclarations:
    """Tests for type declarations."""

    def test_data_declaration(self):
        """Declare a List data type and check constructors."""
        # data List a = Nil | Cons a (List a)
        list_decl = DataDeclaration(
            "List",
            ["a"],
            [
                ("Nil", []),
                ("Cons", [TypeVar("a"), TypeConstructor("List", [TypeVar("a")])]),
            ],
        )

        checker = TypeChecker()
        checker.check_program([list_decl])

        # Now check that constructors are registered
        assert "Nil" in checker.constructors
        assert "Cons" in checker.constructors

    def test_term_declaration_with_annotation(self):
        """Check term declaration with type annotation."""
        a = TypeVar("a")
        id_type = TypeForall("a", TypeArrow(a, a))
        id_body = TAbs(var="a", body=Abs(var_type=a, body=Var(index=0)))

        decl = TermDeclaration("id", id_type, id_body)

        checker = TypeChecker()
        result = checker.check_program([decl])

        assert "id" in result
        assert result["id"] == id_type

    def test_term_declaration_without_annotation(self):
        """Infer type for term declaration without annotation."""
        int_ty = TypeConstructor("Int", [])
        constructors = {"Int": int_ty}
        decl = TermDeclaration("x", None, Constructor(name="Int", args=[]))

        checker = TypeChecker(constructors)
        result = checker.check_program([decl])

        assert "x" in result
        assert result["x"] == int_ty


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_case_fails(self):
        """Case expression with no branches should fail."""
        int_ty = TypeConstructor("Int", [])
        constructors = {"Int": int_ty}
        checker = TypeChecker(constructors)
        ctx = Context.empty().extend_term(int_ty)

        case_expr = Case(scrutinee=Var(index=0), branches=[])

        with pytest.raises(ValueError):
            checker.infer(ctx, case_expr)

    def test_nested_type_abstraction(self):
        """Multiple nested type abstractions."""
        checker = TypeChecker()

        # Λa. Λb. Λc. λx:a. x : ∀a. ∀b. ∀c. a -> a
        body = Abs(var_type=TypeVar("a"), body=Var(index=0))
        tabs = TAbs(var="a", body=TAbs(var="b", body=TAbs(var="c", body=body)))

        ty = checker.infer(Context.empty(), tabs)
        expected = TypeForall(
            "a", TypeForall("b", TypeForall("c", TypeArrow(TypeVar("a"), TypeVar("a"))))
        )
        assert ty == expected

    def test_deeply_nested_app(self):
        """Deeply nested function applications."""
        int_ty = TypeConstructor("Int", [])
        constructors = {"Int": int_ty}
        checker = TypeChecker(constructors)

        # Build ((λx:Int. x) ((λy:Int. y) 42))
        id_int = Abs(var_type=int_ty, body=Var(index=0))
        inner = App(func=id_int, arg=Constructor(name="Int", args=[]))
        outer = App(func=id_int, arg=inner)

        ty = checker.infer(Context.empty(), outer)
        assert ty == int_ty
