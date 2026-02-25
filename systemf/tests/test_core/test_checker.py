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
        """Infer type of a single variable."""
        ctx = Context.empty().extend_term(TypeVar("a"))
        checker = TypeChecker()
        ty = checker.infer(ctx, Var(0))
        assert ty == TypeVar("a")

    def test_infer_var_second(self):
        """Infer type of the second variable in context."""
        ctx = Context.empty().extend_term(TypeVar("b")).extend_term(TypeVar("a"))
        checker = TypeChecker()
        ty = checker.infer(ctx, Var(1))
        assert ty == TypeVar("b")

    def test_infer_undefined_var(self):
        """Should raise UndefinedVariable for out-of-bounds index."""
        ctx = Context.empty()
        checker = TypeChecker()
        with pytest.raises(UndefinedVariable):
            checker.infer(ctx, Var(0))


class TestInferApp:
    """Tests for function application type inference."""

    def test_infer_app_identity(self):
        """(λx:a. x) y : a"""
        a = TypeVar("a")
        ctx = Context.empty().extend_term(a)
        lam = Abs(a, Var(0))
        app = App(lam, Var(0))
        checker = TypeChecker()
        ty = checker.infer(ctx, app)
        assert ty == a

    def test_infer_app_const(self):
        """(λx:Int. λy:Bool. x) 42 : Bool -> Int"""
        int_ty = TypeConstructor("Int", [])
        bool_ty = TypeConstructor("Bool", [])
        const = Abs(int_ty, Abs(bool_ty, Var(1)))  # λx:Int. λy:Bool. x
        # Register Int constructor (represents integer literals)
        constructors = {"Int": int_ty}
        checker = TypeChecker(constructors)
        app = App(const, Constructor("Int", []))  # Apply to some int
        ty = checker.infer(Context.empty(), app)
        assert ty == TypeArrow(bool_ty, int_ty)

    def test_infer_app_mismatch(self):
        """Should fail when argument type doesn't match."""
        int_ty = TypeConstructor("Int", [])
        bool_ty = TypeConstructor("Bool", [])
        id_int = Abs(int_ty, Var(0))
        # Register Bool constructor but not Int
        constructors = {"Bool": bool_ty}
        checker = TypeChecker(constructors)
        app = App(id_int, Constructor("Bool", []))
        with pytest.raises(TypeMismatch):
            checker.infer(Context.empty(), app)


class TestCheckAbs:
    """Tests for lambda abstraction checking mode."""

    def test_check_abs_basic(self):
        """Check λx:a. x : a -> a"""
        a = TypeVar("a")
        lam = Abs(a, Var(0))
        checker = TypeChecker()
        checker.check(Context.empty(), lam, TypeArrow(a, a))

    def test_check_abs_different_type(self):
        """Check λx:Int. x : Int -> Int"""
        int_ty = TypeConstructor("Int", [])
        lam = Abs(int_ty, Var(0))
        checker = TypeChecker()
        checker.check(Context.empty(), lam, TypeArrow(int_ty, int_ty))


# =============================================================================
# Polymorphism Tests
# =============================================================================


class TestPolymorphism:
    """Tests for type abstractions and applications."""

    def test_type_abstraction(self):
        """Λa. λx:a. x : ∀a. a → a"""
        body = Abs(TypeVar("a"), Var(0))
        tabs = TAbs("a", body)
        checker = TypeChecker()
        ty = checker.infer(Context.empty(), tabs)
        assert ty == TypeForall("a", TypeArrow(TypeVar("a"), TypeVar("a")))

    def test_type_application(self):
        """(Λa. λx:a. x) [Int] : Int → Int"""
        int_ty = TypeConstructor("Int", [])
        id_poly = TAbs("a", Abs(TypeVar("a"), Var(0)))
        tapp = TApp(id_poly, int_ty)
        checker = TypeChecker()
        ty = checker.infer(Context.empty(), tapp)
        assert ty == TypeArrow(int_ty, int_ty)

    def test_type_abstraction_check(self):
        """Check Λa. λx:a. x : ∀a. a → a"""
        a = TypeVar("a")
        body = Abs(a, Var(0))
        tabs = TAbs("a", body)
        checker = TypeChecker()
        expected = TypeForall("a", TypeArrow(a, a))
        checker.check(Context.empty(), tabs, expected)

    def test_type_application_chain(self):
        """Multiple type applications."""
        a = TypeVar("a")
        int_ty = TypeConstructor("Int", [])
        bool_ty = TypeConstructor("Bool", [])

        # Λa. Λb. λx:a. λy:b. x : ∀a. ∀b. a -> b -> a
        const_poly = TAbs("a", TAbs("b", Abs(a, Abs(bool_ty, Var(1)))))

        # Apply to [Int][Bool]
        tapp = TApp(TApp(const_poly, int_ty), bool_ty)

        checker = TypeChecker()
        ty = checker.infer(Context.empty(), tapp)
        assert ty == TypeArrow(int_ty, TypeArrow(bool_ty, int_ty))


# =============================================================================
# Data Type Tests
# =============================================================================


class TestDataConstructors:
    """Tests for data constructor type checking."""

    def test_nil_constructor(self):
        """Nil : List _t0 (fresh metavar for type parameter)"""
        constructors = {
            "Nil": TypeForall("a", TypeConstructor("List", [TypeVar("a")])),
        }
        checker = TypeChecker(constructors)
        nil = Constructor("Nil", [])
        ty = checker.infer(Context.empty(), nil)
        # Should be List _t0 where _t0 is a fresh metavar
        assert isinstance(ty, TypeConstructor)
        assert ty.name == "List"
        assert len(ty.args) == 1
        assert isinstance(ty.args[0], TypeVar)
        assert ty.args[0].name.startswith("_t")  # Fresh metavar

    def test_cons_constructor(self):
        """Cons : ∀a. a → List a → List a"""
        a = TypeVar("a")
        list_a = TypeConstructor("List", [a])
        constructors = {
            "Cons": TypeForall("a", TypeArrow(a, TypeArrow(list_a, list_a))),
        }
        checker = TypeChecker(constructors)
        # Create fresh type variable for the instantiation
        cons = Constructor("Cons", [])
        # The type should be _t0 → List _t0 → List _t0
        ty = checker.infer(Context.empty(), cons)
        assert isinstance(ty, TypeArrow)
        assert isinstance(ty.ret, TypeArrow)
        assert isinstance(ty.ret.ret, TypeConstructor)
        assert ty.ret.ret.name == "List"

    def test_undefined_constructor(self):
        """Should fail for undefined constructor."""
        checker = TypeChecker()
        with pytest.raises(UndefinedConstructor):
            checker.infer(Context.empty(), Constructor("Unknown", []))

    def test_just_constructor(self):
        """Just : ∀a. a → Maybe a"""
        a = TypeVar("a")
        constructors = {
            "Just": TypeForall("a", TypeArrow(a, TypeConstructor("Maybe", [a]))),
        }
        checker = TypeChecker(constructors)
        # Just with argument should be Maybe _t0
        just = Constructor("Just", [])
        ty = checker.infer(Context.empty(), just)
        # The type should be _t0 → Maybe _t0
        assert isinstance(ty, TypeArrow)
        assert isinstance(ty.ret, TypeConstructor)
        assert ty.ret.name == "Maybe"


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

        scrut = Var(0)
        branches = [
            Branch(Pattern("Nil", []), Constructor("Int", [])),  # 0
            Branch(Pattern("Cons", ["y", "ys"]), Constructor("Int", [])),  # 1
        ]
        case_expr = Case(scrut, branches)

        ty = checker.infer(ctx, case_expr)
        assert ty == int_ty

    def test_case_identity(self):
        """case x of { Just y → y; Nothing → 0 } : Int"""
        int_ty = TypeConstructor("Int", [])
        maybe_int = TypeConstructor("Maybe", [int_ty])
        constructors = {
            "Just": TypeForall(
                "a", TypeArrow(TypeVar("a"), TypeConstructor("Maybe", [TypeVar("a")]))
            ),
            "Nothing": TypeForall("a", TypeConstructor("Maybe", [TypeVar("a")])),
            "Int": int_ty,  # For literals
        }
        checker = TypeChecker(constructors)
        ctx = Context.empty().extend_term(maybe_int)

        scrut = Var(0)
        branches = [
            Branch(Pattern("Just", ["y"]), Var(0)),  # y : Int
            Branch(Pattern("Nothing", []), Constructor("Int", [])),  # 0
        ]
        case_expr = Case(scrut, branches)

        ty = checker.infer(ctx, case_expr)
        assert ty == int_ty

    def test_case_different_constructors_same_type(self):
        """All branches must have the same type."""
        int_ty = TypeConstructor("Int", [])
        bool_ty = TypeConstructor("Bool", [])
        constructors = {
            "True": TypeConstructor("Bool", []),
            "False": TypeConstructor("Bool", []),
            "Int": int_ty,  # For literals
        }
        checker = TypeChecker(constructors)
        ctx = Context.empty().extend_term(bool_ty)

        scrut = Var(0)
        branches = [
            Branch(Pattern("True", []), Constructor("Int", [])),  # 0
            Branch(Pattern("False", []), Constructor("Int", [])),  # 0
        ]
        case_expr = Case(scrut, branches)

        ty = checker.infer(ctx, case_expr)
        assert ty == int_ty


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

        let_expr = Let("x", Constructor("Int", []), Var(0))
        ty = checker.infer(Context.empty(), let_expr)
        assert ty == int_ty

    def test_let_function(self):
        """let id = λx:a. x in id : a -> a"""
        a = TypeVar("a")
        id_func = Abs(a, Var(0))
        let_expr = Let("id", id_func, Var(0))

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
        inner = Let("y", Constructor("Bool", []), Var(1))  # x is now at index 1
        outer = Let("x", Constructor("Int", []), inner)

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
        lam = Abs(int_ty, App(Var(0), Var(0)))
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
            checker.check(Context.empty(), Constructor("Int", []), TypeArrow(int_ty, int_ty))

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

        scrut = Var(0)
        branches = [
            Branch(Pattern("True", []), Constructor("Int", [])),  # Int
            Branch(Pattern("False", []), Constructor("Bool", [])),  # Bool
        ]
        case_expr = Case(scrut, branches)

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
        body = App(Var(2), App(Var(1), Var(0)))  # f (g x)

        # λx:a. f (g x)
        lam_x = Abs(a, body)
        # λg:(a->b). λx:a. f (g x)
        lam_g = Abs(g_ty, lam_x)
        # λf:(b->c). λg:(a->b). λx:a. f (g x)
        compose = Abs(f_ty, lam_g)

        checker = TypeChecker()
        result_type = checker.infer(Context.empty(), compose)

        expected = TypeArrow(f_ty, TypeArrow(g_ty, TypeArrow(a, c)))
        assert result_type == expected

    def test_polymorphic_identity_application(self):
        """Apply polymorphic identity to multiple types."""
        int_ty = TypeConstructor("Int", [])
        bool_ty = TypeConstructor("Bool", [])

        # id = Λa. λx:a. x
        id_poly = TAbs("a", Abs(TypeVar("a"), Var(0)))

        # let id = ... in (id [Int] 42, id [Bool] true)
        # For testing, just check id [Int] 42
        id_int = TApp(id_poly, int_ty)
        constructors = {"Int": int_ty}
        checker = TypeChecker(constructors)

        app = App(id_int, Constructor("Int", []))
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
        nil_branch = Branch(Pattern("Nil", []), Constructor("Nil", []))

        # Check the branch in the correct context
        scrut = Var(0)  # xs : List a
        case_expr = Case(scrut, [nil_branch])

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
        id_body = TAbs("a", Abs(a, Var(0)))

        decl = TermDeclaration("id", id_type, id_body)

        checker = TypeChecker()
        result = checker.check_program([decl])

        assert "id" in result
        assert result["id"] == id_type

    def test_term_declaration_without_annotation(self):
        """Infer type for term declaration without annotation."""
        int_ty = TypeConstructor("Int", [])
        constructors = {"Int": int_ty}
        decl = TermDeclaration("x", None, Constructor("Int", []))

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

        case_expr = Case(Var(0), [])

        with pytest.raises(ValueError):
            checker.infer(ctx, case_expr)

    def test_nested_type_abstraction(self):
        """Multiple nested type abstractions."""
        checker = TypeChecker()

        # Λa. Λb. Λc. λx:a. x : ∀a. ∀b. ∀c. a -> a
        body = Abs(TypeVar("a"), Var(0))
        tabs = TAbs("a", TAbs("b", TAbs("c", body)))

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
        id_int = Abs(int_ty, Var(0))
        inner = App(id_int, Constructor("Int", []))
        outer = App(id_int, inner)

        ty = checker.infer(Context.empty(), outer)
        assert ty == int_ty
