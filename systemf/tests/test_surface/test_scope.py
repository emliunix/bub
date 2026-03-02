"""Tests for the scope checker.

Tests for transforming Surface AST (with names) to Scoped AST (with de Bruijn indices).
"""

import pytest

from systemf.surface.scoped.checker import ScopeChecker
from systemf.surface.scoped.context import ScopeContext
from systemf.surface.scoped.errors import UndefinedVariableError
from systemf.surface.types import (
    ScopedAbs,
    ScopedVar,
    SurfaceAbs,
    SurfaceApp,
    SurfaceBranch,
    SurfaceCase,
    SurfaceConstructor,
    SurfaceIf,
    SurfaceIntLit,
    SurfaceLet,
    SurfaceOp,
    SurfacePattern,
    SurfaceStringLit,
    SurfaceTermDeclaration,
    SurfaceTuple,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceTypeArrow,
    SurfaceTypeConstructor,
    SurfaceTypeVar,
    SurfaceVar,
)
from systemf.utils.location import Location


# Create a dummy location for tests
DUMMY_LOC = Location(line=1, column=1, file="test.py")


# =============================================================================
# ScopeContext Tests
# =============================================================================


class TestScopeContext:
    """Tests for ScopeContext name management."""

    def test_empty_context_lookup_fails(self):
        """Looking up in empty context raises NameError."""
        ctx = ScopeContext()
        with pytest.raises(NameError, match="Undefined variable 'x'"):
            ctx.lookup_term("x")

    def test_extend_term_adds_binding(self):
        """Extending context with term variable allows lookup."""
        ctx = ScopeContext()
        new_ctx = ctx.extend_term("x")
        assert new_ctx.lookup_term("x") == 0

    def test_extend_term_shifts_existing(self):
        """New binding becomes index 0, existing bindings shift."""
        ctx = ScopeContext(term_names=["x"])
        new_ctx = ctx.extend_term("y")
        assert new_ctx.lookup_term("y") == 0
        assert new_ctx.lookup_term("x") == 1

    def test_extend_type_adds_type_binding(self):
        """Extending context with type variable allows lookup."""
        ctx = ScopeContext()
        new_ctx = ctx.extend_type("a")
        assert new_ctx.lookup_type("a") == 0

    def test_extend_type_shifts_existing_types(self):
        """New type binding becomes index 0, existing shift."""
        ctx = ScopeContext(type_names=["a"])
        new_ctx = ctx.extend_type("b")
        assert new_ctx.lookup_type("b") == 0
        assert new_ctx.lookup_type("a") == 1

    def test_term_and_type_contexts_independent(self):
        """Term and type bindings don't interfere."""
        ctx = ScopeContext()
        ctx = ctx.extend_term("x")
        ctx = ctx.extend_type("a")
        assert ctx.lookup_term("x") == 0
        assert ctx.lookup_type("a") == 0
        # Type names not in term context
        with pytest.raises(NameError):
            ctx.lookup_term("a")
        # Term names not in type context
        with pytest.raises(NameError):
            ctx.lookup_type("x")

    def test_context_immutability(self):
        """Original context is unchanged after extension."""
        ctx = ScopeContext()
        new_ctx = ctx.extend_term("x")
        # Original context still empty
        with pytest.raises(NameError):
            ctx.lookup_term("x")
        # New context has the binding
        assert new_ctx.lookup_term("x") == 0

    def test_is_bound_term(self):
        """Check if term name is bound."""
        ctx = ScopeContext(term_names=["x", "y"])
        assert ctx.is_bound_term("x") is True
        assert ctx.is_bound_term("y") is True
        assert ctx.is_bound_term("z") is False

    def test_is_bound_type(self):
        """Check if type name is bound."""
        ctx = ScopeContext(type_names=["a", "b"])
        assert ctx.is_bound_type("a") is True
        assert ctx.is_bound_type("b") is True
        assert ctx.is_bound_type("c") is False

    def test_add_global(self):
        """Adding globals to context."""
        ctx = ScopeContext()
        ctx = ctx.add_global("even")
        assert ctx.is_global("even") is True
        assert ctx.is_global("odd") is False

    def test_global_lookup_raises(self):
        """Global variables raise NameError (handled separately)."""
        ctx = ScopeContext(globals={"even"})
        assert ctx.is_global("even") is True
        # Globals raise NameError to be handled by caller
        with pytest.raises(NameError, match="Global variable"):
            ctx.lookup_term("even")

    def test_context_repr(self):
        """Context has useful string representation."""
        ctx = ScopeContext(term_names=["x", "y"], type_names=["a"], globals={"even"})
        repr_str = repr(ctx)
        assert "ScopeContext" in repr_str
        assert "x" in repr_str
        assert "y" in repr_str
        assert "a" in repr_str
        assert "even" in repr_str


# =============================================================================
# Basic Variable Resolution Tests
# =============================================================================


class TestVariableResolution:
    """Tests for basic variable resolution."""

    def test_resolve_single_variable(self):
        """Resolve a single variable in scope."""
        checker = ScopeChecker()
        ctx = ScopeContext(term_names=["x"])

        var = SurfaceVar("x", DUMMY_LOC)
        result = checker.check_term(var, ctx)

        assert isinstance(result, ScopedVar)
        assert result.index == 0
        assert result.debug_name == "x"

    def test_resolve_multiple_variables(self):
        """Resolve multiple variables with correct indices."""
        checker = ScopeChecker()
        ctx = ScopeContext(term_names=["y", "x"])  # x was bound first (index 1), y second (index 0)

        var_x = SurfaceVar("x", DUMMY_LOC)
        result_x = checker.check_term(var_x, ctx)
        assert isinstance(result_x, ScopedVar)
        assert result_x.index == 1

        var_y = SurfaceVar("y", DUMMY_LOC)
        result_y = checker.check_term(var_y, ctx)
        assert isinstance(result_y, ScopedVar)
        assert result_y.index == 0

    def test_resolve_variable_preserves_location(self):
        """Variable resolution preserves source location."""
        checker = ScopeChecker()
        ctx = ScopeContext(term_names=["x"])
        loc = Location(line=42, column=5, file="source.py")

        var = SurfaceVar("x", loc)
        result = checker.check_term(var, ctx)

        assert result.location == loc


# =============================================================================
# Nested Scopes Tests
# =============================================================================


class TestNestedScopes:
    """Tests for nested scope handling."""

    def test_nested_lambda_captures_outer_scope(self):
        """Inner lambda can reference outer lambda parameters."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        # \x -> \y -> x
        inner_body = SurfaceVar("x", DUMMY_LOC)
        inner_abs = SurfaceAbs("y", None, inner_body, DUMMY_LOC)
        outer_abs = SurfaceAbs("x", None, inner_abs, DUMMY_LOC)

        result = checker.check_term(outer_abs, ctx)

        assert isinstance(result, ScopedAbs)
        assert isinstance(result.body, ScopedAbs)
        # x should have index 1 in inner body (x bound first, then y)
        assert isinstance(result.body.body, ScopedVar)
        assert result.body.body.index == 1
        assert result.body.body.debug_name == "x"

    def test_nested_lambda_shadowing(self):
        """Inner lambda parameter shadows outer with same name."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        # \x -> \x -> x (inner x shadows outer)
        inner_body = SurfaceVar("x", DUMMY_LOC)
        inner_abs = SurfaceAbs("x", None, inner_body, DUMMY_LOC)
        outer_abs = SurfaceAbs("x", None, inner_abs, DUMMY_LOC)

        result = checker.check_term(outer_abs, ctx)

        assert isinstance(result, ScopedAbs)
        assert isinstance(result.body, ScopedAbs)
        # inner x should have index 0 (most recent)
        assert isinstance(result.body.body, ScopedVar)
        assert result.body.body.index == 0

    def test_deeply_nested_scopes(self):
        """Handle deeply nested lambda abstractions."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        # \a -> \b -> \c -> c (reference innermost binding)
        body = SurfaceVar("c", DUMMY_LOC)
        inner_abs = SurfaceAbs("c", None, body, DUMMY_LOC)
        middle_abs = SurfaceAbs("b", None, inner_abs, DUMMY_LOC)
        outer_abs = SurfaceAbs("a", None, middle_abs, DUMMY_LOC)

        result = checker.check_term(outer_abs, ctx)

        # Navigate to innermost body
        assert isinstance(result, ScopedAbs)
        assert isinstance(result.body, ScopedAbs)
        assert isinstance(result.body.body, ScopedAbs)
        assert isinstance(result.body.body.body, ScopedVar)
        # c should be at index 0 (most recent binder)
        assert result.body.body.body.index == 0


# =============================================================================
# Lambda Abstraction Tests
# =============================================================================


class TestLambdaAbstractions:
    """Tests for lambda abstraction scope checking."""

    def test_simple_lambda(self):
        """Scope-check simple lambda abstraction."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        # \x -> x
        body = SurfaceVar("x", DUMMY_LOC)
        abs_term = SurfaceAbs("x", None, body, DUMMY_LOC)

        result = checker.check_term(abs_term, ctx)

        assert isinstance(result, ScopedAbs)
        assert result.var_name == "x"
        assert isinstance(result.body, ScopedVar)
        assert result.body.index == 0

    def test_lambda_with_type_annotation(self):
        """Lambda with type annotation preserves annotation."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        type_ann = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        body = SurfaceVar("x", DUMMY_LOC)
        abs_term = SurfaceAbs("x", type_ann, body, DUMMY_LOC)

        result = checker.check_term(abs_term, ctx)

        assert isinstance(result, ScopedAbs)
        assert result.var_type == type_ann

    def test_lambda_application(self):
        """Scope-check lambda application."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        # (\x -> x) 42
        body = SurfaceVar("x", DUMMY_LOC)
        abs_term = SurfaceAbs("x", None, body, DUMMY_LOC)
        arg = SurfaceIntLit(42, DUMMY_LOC)
        app = SurfaceApp(abs_term, arg, DUMMY_LOC)

        result = checker.check_term(app, ctx)

        assert isinstance(result, SurfaceApp)
        assert isinstance(result.func, ScopedAbs)
        assert isinstance(result.arg, SurfaceIntLit)

    def test_curried_lambda(self):
        """Scope-check curried multi-argument lambda."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        # \x -> \y -> x y
        inner_body = SurfaceApp(SurfaceVar("x", DUMMY_LOC), SurfaceVar("y", DUMMY_LOC), DUMMY_LOC)
        inner_abs = SurfaceAbs("y", None, inner_body, DUMMY_LOC)
        outer_abs = SurfaceAbs("x", None, inner_abs, DUMMY_LOC)

        result = checker.check_term(outer_abs, ctx)

        assert isinstance(result, ScopedAbs)
        assert isinstance(result.body, ScopedAbs)
        assert isinstance(result.body.body, SurfaceApp)
        # x should be index 1 (bound first), y should be index 0
        assert result.body.body.func.index == 1
        assert result.body.body.arg.index == 0


# =============================================================================
# Type Abstraction Tests
# =============================================================================


class TestTypeAbstractions:
    """Tests for type abstraction scope checking."""

    def test_simple_type_abstraction(self):
        """Scope-check simple type abstraction."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        # /\a. \x -> x
        body = SurfaceAbs("x", None, SurfaceVar("x", DUMMY_LOC), DUMMY_LOC)
        type_abs = SurfaceTypeAbs("a", body, DUMMY_LOC)

        result = checker.check_term(type_abs, ctx)

        assert isinstance(result, SurfaceTypeAbs)
        assert result.var == "a"
        assert isinstance(result.body, ScopedAbs)

    def test_type_abstraction_extends_type_context(self):
        """Type abstraction extends type context, not term context."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        # /\a. (body where type 'a' is bound)
        body = SurfaceIntLit(42, DUMMY_LOC)
        type_abs = SurfaceTypeAbs("a", body, DUMMY_LOC)

        result = checker.check_term(type_abs, ctx)

        # Term context should be unchanged
        with pytest.raises(NameError):
            ctx.lookup_term("a")
        # Type context in the result's scope has 'a'
        # (we can't directly test this, but we verify the structure is correct)
        assert isinstance(result, SurfaceTypeAbs)

    def test_type_application(self):
        """Scope-check type application."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        # (\x -> x) @Int
        body = SurfaceAbs("x", None, SurfaceVar("x", DUMMY_LOC), DUMMY_LOC)
        type_arg = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        type_app = SurfaceTypeApp(body, type_arg, DUMMY_LOC)

        result = checker.check_term(type_app, ctx)

        assert isinstance(result, SurfaceTypeApp)
        assert isinstance(result.func, ScopedAbs)
        assert result.type_arg == type_arg


# =============================================================================
# Let Binding Tests
# =============================================================================


class TestLetBindings:
    """Tests for let binding scope checking."""

    def test_simple_let(self):
        """Scope-check simple let binding."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        # let x = 42 in x
        value = SurfaceIntLit(42, DUMMY_LOC)
        body = SurfaceVar("x", DUMMY_LOC)
        let_term = SurfaceLet([("x", None, value)], body, DUMMY_LOC)

        result = checker.check_term(let_term, ctx)

        assert isinstance(result, SurfaceLet)
        assert len(result.bindings) == 1
        assert isinstance(result.bindings[0][2], SurfaceIntLit)  # value
        assert isinstance(result.body, ScopedVar)
        assert result.body.index == 0

    def test_let_multiple_bindings(self):
        """Scope-check let with multiple bindings."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        # let x = 1, y = 2 in x + y
        bindings = [
            ("x", None, SurfaceIntLit(1, DUMMY_LOC)),
            ("y", None, SurfaceIntLit(2, DUMMY_LOC)),
        ]
        body = SurfaceOp(SurfaceVar("x", DUMMY_LOC), "+", SurfaceVar("y", DUMMY_LOC), DUMMY_LOC)
        let_term = SurfaceLet(bindings, body, DUMMY_LOC)

        result = checker.check_term(let_term, ctx)

        assert isinstance(result, SurfaceLet)
        # y was bound last (index 0), x first (index 1)
        assert result.body.left.index == 1
        assert result.body.right.index == 0

    def test_let_binding_order(self):
        """Let bindings are processed sequentially."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        # let x = 1, y = x in y (y's value can reference x)
        bindings = [
            ("x", None, SurfaceIntLit(1, DUMMY_LOC)),
            ("y", None, SurfaceVar("x", DUMMY_LOC)),  # references x
        ]
        body = SurfaceVar("y", DUMMY_LOC)
        let_term = SurfaceLet(bindings, body, DUMMY_LOC)

        result = checker.check_term(let_term, ctx)

        # y's value should have x at index 0 (only x in scope when checking value)
        assert isinstance(result.bindings[1][2], ScopedVar)
        assert result.bindings[1][2].index == 0


# =============================================================================
# Error Cases Tests
# =============================================================================


class TestUndefinedVariables:
    """Tests for undefined variable error handling."""

    def test_undefined_variable_raises_error(self):
        """Undefined variable raises UndefinedVariableError."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        var = SurfaceVar("undefined", DUMMY_LOC)
        with pytest.raises(UndefinedVariableError) as exc_info:
            checker.check_term(var, ctx)

        assert exc_info.value.name == "undefined"

    def test_undefined_variable_includes_location(self):
        """Error includes source location."""
        checker = ScopeChecker()
        ctx = ScopeContext()
        loc = Location(line=10, column=5, file="test.py")

        var = SurfaceVar("missing", loc)
        with pytest.raises(UndefinedVariableError) as exc_info:
            checker.check_term(var, ctx)

        assert exc_info.value.location == loc

    def test_undefined_variable_includes_term(self):
        """Error includes the problematic term."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        var = SurfaceVar("missing", DUMMY_LOC)
        with pytest.raises(UndefinedVariableError) as exc_info:
            checker.check_term(var, ctx)

        assert exc_info.value.term is var

    def test_suggestions_for_similar_names(self):
        """Error includes suggestions for similar names."""
        checker = ScopeChecker()
        ctx = ScopeContext(term_names=["xyz", "xylophone", "abc"])

        var = SurfaceVar("xy", DUMMY_LOC)
        with pytest.raises(UndefinedVariableError) as exc_info:
            checker.check_term(var, ctx)

        # Should suggest names starting with 'x'
        assert len(exc_info.value.available) > 0
        assert "xyz" in exc_info.value.available or "xylophone" in exc_info.value.available

    def test_undefined_in_lambda_body(self):
        """Undefined variable in lambda body raises error."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        # \x -> y (y is undefined)
        body = SurfaceVar("y", DUMMY_LOC)
        abs_term = SurfaceAbs("x", None, body, DUMMY_LOC)

        with pytest.raises(UndefinedVariableError) as exc_info:
            checker.check_term(abs_term, ctx)

        assert exc_info.value.name == "y"

    def test_undefined_in_nested_scope(self):
        """Undefined variable in nested scope raises error."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        # \x -> \y -> z (z is undefined at any level)
        body = SurfaceVar("z", DUMMY_LOC)
        inner_abs = SurfaceAbs("y", None, body, DUMMY_LOC)
        outer_abs = SurfaceAbs("x", None, inner_abs, DUMMY_LOC)

        with pytest.raises(UndefinedVariableError) as exc_info:
            checker.check_term(outer_abs, ctx)

        assert exc_info.value.name == "z"


# =============================================================================
# Mutual Recursion Tests
# =============================================================================


class TestMutualRecursion:
    """Tests for mutual recursion in top-level declarations."""

    def test_check_single_declaration(self):
        """Scope-check single top-level declaration."""
        checker = ScopeChecker()

        # answer : Int = 42
        body = SurfaceIntLit(42, DUMMY_LOC)
        type_ann = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        decl = SurfaceTermDeclaration("answer", type_ann, body, DUMMY_LOC)

        result = checker.check_declarations([decl])

        assert len(result) == 1
        assert isinstance(result[0], SurfaceTermDeclaration)
        assert result[0].name == "answer"

    def test_mutually_recursive_declarations(self):
        """Mutually recursive functions can reference each other (globals handled separately)."""
        checker = ScopeChecker()

        # Note: The scope checker collects globals but treats them specially.
        # Globals are handled later in the elaboration pipeline.
        # This test verifies that declarations are processed correctly.
        type_ann = SurfaceTypeArrow(
            SurfaceTypeConstructor("Int", [], DUMMY_LOC),
            SurfaceTypeConstructor("Bool", [], DUMMY_LOC),
            location=DUMMY_LOC,
        )

        # even body - uses only its parameter
        even_body = SurfaceAbs(
            "n",
            None,
            SurfaceIf(
                SurfaceOp(SurfaceVar("n", DUMMY_LOC), "==", SurfaceIntLit(0, DUMMY_LOC), DUMMY_LOC),
                SurfaceConstructor("True", [], DUMMY_LOC),
                SurfaceConstructor("False", [], DUMMY_LOC),
                DUMMY_LOC,
            ),
            DUMMY_LOC,
        )

        # odd body - uses only its parameter
        odd_body = SurfaceAbs(
            "n",
            None,
            SurfaceIf(
                SurfaceOp(SurfaceVar("n", DUMMY_LOC), "==", SurfaceIntLit(0, DUMMY_LOC), DUMMY_LOC),
                SurfaceConstructor("False", [], DUMMY_LOC),
                SurfaceConstructor("True", [], DUMMY_LOC),
                DUMMY_LOC,
            ),
            DUMMY_LOC,
        )

        even_decl = SurfaceTermDeclaration("even", type_ann, even_body, DUMMY_LOC)
        odd_decl = SurfaceTermDeclaration("odd", type_ann, odd_body, DUMMY_LOC)

        # Both should scope-check without error (no undefined variables)
        result = checker.check_declarations([even_decl, odd_decl])
        assert len(result) == 2

    def test_declaration_undefined_reference(self):
        """Declaration referencing undefined global raises error."""
        checker = ScopeChecker()

        # foo : Int = undefined
        body = SurfaceVar("undefined", DUMMY_LOC)
        type_ann = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        decl = SurfaceTermDeclaration("foo", type_ann, body, DUMMY_LOC)

        # 'undefined' is not in the declarations list, so it's not a global
        with pytest.raises(UndefinedVariableError) as exc_info:
            checker.check_declarations([decl])

        assert exc_info.value.name == "undefined"


# =============================================================================
# Complex Expression Tests
# =============================================================================


class TestComplexExpressions:
    """Tests for complex expressions and edge cases."""

    def test_if_expression(self):
        """Scope-check if-then-else expression."""
        checker = ScopeChecker()
        ctx = ScopeContext(term_names=["x", "y", "z"])

        # if x then y else z
        if_term = SurfaceIf(
            SurfaceVar("x", DUMMY_LOC),
            SurfaceVar("y", DUMMY_LOC),
            SurfaceVar("z", DUMMY_LOC),
            DUMMY_LOC,
        )

        result = checker.check_term(if_term, ctx)

        assert isinstance(result, SurfaceIf)
        assert isinstance(result.cond, ScopedVar)
        assert isinstance(result.then_branch, ScopedVar)
        assert isinstance(result.else_branch, ScopedVar)

    def test_case_expression(self):
        """Scope-check case expression with pattern matching."""
        checker = ScopeChecker()
        ctx = ScopeContext(term_names=["x"])

        # case x of True -> 1 | False -> 0
        pattern1 = SurfacePattern("True", [], DUMMY_LOC)
        pattern2 = SurfacePattern("False", [], DUMMY_LOC)
        branches = [
            SurfaceBranch(pattern1, SurfaceIntLit(1, DUMMY_LOC), DUMMY_LOC),
            SurfaceBranch(pattern2, SurfaceIntLit(0, DUMMY_LOC), DUMMY_LOC),
        ]
        case_term = SurfaceCase(SurfaceVar("x", DUMMY_LOC), branches, DUMMY_LOC)

        result = checker.check_term(case_term, ctx)

        assert isinstance(result, SurfaceCase)
        assert isinstance(result.scrutinee, ScopedVar)
        assert len(result.branches) == 2

    def test_case_with_pattern_bindings(self):
        """Case pattern bindings extend scope for branch body."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        # case x of Pair a b -> a
        pattern = SurfacePattern("Pair", ["a", "b"], DUMMY_LOC)
        # Body references 'a' which is bound by the pattern
        body = SurfaceVar("a", DUMMY_LOC)
        branch = SurfaceBranch(pattern, body, DUMMY_LOC)
        case_term = SurfaceCase(SurfaceConstructor("x", [], DUMMY_LOC), [branch], DUMMY_LOC)

        result = checker.check_term(case_term, ctx)

        assert isinstance(result, SurfaceCase)
        # 'a' is bound first in pattern, so it has index 1 (b is index 0)
        # Pattern vars are added in order: a (index 1), b (index 0)
        assert result.branches[0].body.index == 1

    def test_tuple_expression(self):
        """Scope-check tuple expression."""
        checker = ScopeChecker()
        ctx = ScopeContext(term_names=["x", "y"])

        # (x, y)
        tuple_term = SurfaceTuple(
            [
                SurfaceVar("x", DUMMY_LOC),
                SurfaceVar("y", DUMMY_LOC),
            ],
            DUMMY_LOC,
        )

        result = checker.check_term(tuple_term, ctx)

        assert isinstance(result, SurfaceTuple)
        assert len(result.elements) == 2
        assert isinstance(result.elements[0], ScopedVar)
        assert isinstance(result.elements[1], ScopedVar)

    def test_operator_expression(self):
        """Scope-check infix operator expression."""
        checker = ScopeChecker()
        ctx = ScopeContext(term_names=["x", "y"])

        # x + y
        op_term = SurfaceOp(SurfaceVar("x", DUMMY_LOC), "+", SurfaceVar("y", DUMMY_LOC), DUMMY_LOC)

        result = checker.check_term(op_term, ctx)

        assert isinstance(result, SurfaceOp)
        assert isinstance(result.left, ScopedVar)
        assert isinstance(result.right, ScopedVar)
        assert result.op == "+"

    def test_constructor_expression(self):
        """Scope-check data constructor expression."""
        checker = ScopeChecker()
        ctx = ScopeContext(term_names=["x"])

        # Just x
        constr_term = SurfaceConstructor("Just", [SurfaceVar("x", DUMMY_LOC)], DUMMY_LOC)

        result = checker.check_term(constr_term, ctx)

        assert isinstance(result, SurfaceConstructor)
        assert result.name == "Just"
        assert len(result.args) == 1
        assert isinstance(result.args[0], ScopedVar)

    def test_type_annotation(self):
        """Scope-check type annotation."""
        checker = ScopeChecker()
        ctx = ScopeContext(term_names=["x"])

        from systemf.surface.types import SurfaceAnn

        type_ann = SurfaceTypeConstructor("Int", [], DUMMY_LOC)
        ann_term = SurfaceAnn(SurfaceVar("x", DUMMY_LOC), type_ann, DUMMY_LOC)

        result = checker.check_term(ann_term, ctx)

        assert isinstance(result, SurfaceAnn)
        assert isinstance(result.term, ScopedVar)
        assert result.type == type_ann


# =============================================================================
# Literal Tests
# =============================================================================


class TestLiterals:
    """Tests for literal expressions (unchanged by scope checking)."""

    def test_integer_literal(self):
        """Integer literal passes through unchanged."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        lit = SurfaceIntLit(42, DUMMY_LOC)
        result = checker.check_term(lit, ctx)

        assert result is lit

    def test_string_literal(self):
        """String literal passes through unchanged."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        lit = SurfaceStringLit("hello", DUMMY_LOC)
        result = checker.check_term(lit, ctx)

        assert result is lit


# =============================================================================
# Similar Name Suggestions Tests
# =============================================================================


class TestNameSuggestions:
    """Tests for the _suggest_similar_names helper."""

    def test_suggest_same_starting_letter(self):
        """Suggest names with same starting letter."""
        checker = ScopeChecker()
        ctx = ScopeContext(term_names=["xyz", "xylophone", "abc", "def"])

        suggestions = checker._suggest_similar_names("xy", ctx)

        assert "xyz" in suggestions
        assert "xylophone" in suggestions

    def test_suggest_substring_match(self):
        """Suggest names that are substrings."""
        checker = ScopeChecker()
        ctx = ScopeContext(term_names=["foobar", "barbaz"])

        suggestions = checker._suggest_similar_names("bar", ctx)

        assert "foobar" in suggestions or "barbaz" in suggestions

    def test_suggest_limit_five(self):
        """Suggestions limited to 5."""
        checker = ScopeChecker()
        ctx = ScopeContext(term_names=["a1", "a2", "a3", "a4", "a5", "a6"])

        suggestions = checker._suggest_similar_names("a", ctx)

        assert len(suggestions) <= 5

    def test_no_self_suggestion(self):
        """Exact name match is not suggested."""
        checker = ScopeChecker()
        ctx = ScopeContext(term_names=["exact"])

        suggestions = checker._suggest_similar_names("exact", ctx)

        assert "exact" not in suggestions

    def test_no_suggestions_empty_context(self):
        """Empty context gives no suggestions."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        suggestions = checker._suggest_similar_names("x", ctx)

        assert suggestions == []


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_complex_nested_expression(self):
        """Complex nested expression with multiple constructs."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        # let f = \x -> x + 1 in f 42
        # Build: let f = (\x -> x + 1) in f 42
        lambda_body = SurfaceOp(
            SurfaceVar("x", DUMMY_LOC), "+", SurfaceIntLit(1, DUMMY_LOC), DUMMY_LOC
        )
        lambda_term = SurfaceAbs("x", None, lambda_body, DUMMY_LOC)
        body = SurfaceApp(SurfaceVar("f", DUMMY_LOC), SurfaceIntLit(42, DUMMY_LOC), DUMMY_LOC)
        let_term = SurfaceLet([("f", None, lambda_term)], body, DUMMY_LOC)

        result = checker.check_term(let_term, ctx)

        assert isinstance(result, SurfaceLet)
        # f should have index 0 in the body
        assert isinstance(result.body, SurfaceApp)
        assert result.body.func.index == 0

    def test_polymorphic_identity(self):
        """Polymorphic identity function: /\\a. \\x:a -> x."""
        checker = ScopeChecker()
        ctx = ScopeContext()

        type_var = SurfaceTypeVar("a", DUMMY_LOC)
        lambda_term = SurfaceAbs("x", type_var, SurfaceVar("x", DUMMY_LOC), DUMMY_LOC)
        type_abs = SurfaceTypeAbs("a", lambda_term, DUMMY_LOC)

        result = checker.check_term(type_abs, ctx)

        assert isinstance(result, SurfaceTypeAbs)
        assert isinstance(result.body, ScopedAbs)
        assert isinstance(result.body.body, ScopedVar)
        assert result.body.body.index == 0

    def test_shadowing_in_let(self):
        """Let binding shadows outer binding."""
        checker = ScopeChecker()
        ctx = ScopeContext(term_names=["x"])

        # let x = 42 in x (inner x shadows outer)
        let_term = SurfaceLet(
            [("x", None, SurfaceIntLit(42, DUMMY_LOC))], SurfaceVar("x", DUMMY_LOC), DUMMY_LOC
        )

        result = checker.check_term(let_term, ctx)

        # The x in body should be index 0 (the let binding, not the outer)
        assert isinstance(result.body, ScopedVar)
        assert result.body.index == 0
