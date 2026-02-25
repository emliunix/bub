"""Tests for the evaluator."""

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
from systemf.core.types import TypeArrow, TypeConstructor, TypeForall, TypeVar
from systemf.eval.machine import Evaluator
from systemf.eval.value import (
    Environment,
    VClosure,
    VConstructor,
    VTypeClosure,
)


def test_evaluate_var():
    """Test evaluating a variable."""
    evalr = Evaluator()
    env = Environment.empty().extend(VConstructor("True", []))
    result = evalr.evaluate(Var(0), env)
    assert result == VConstructor("True", [])


def test_evaluate_lambda():
    """Test evaluating a lambda creates a closure."""
    evalr = Evaluator()
    # λx.x
    lam = Abs(TypeConstructor("Int", []), Var(0))
    result = evalr.evaluate(lam)
    assert isinstance(result, VClosure)
    assert result.body == Var(0)


def test_evaluate_type_abs():
    """Test evaluating a type abstraction creates a type closure."""
    evalr = Evaluator()
    # Λa.λx:a.x
    tabs = TAbs("a", Abs(TypeVar("a"), Var(0)))
    result = evalr.evaluate(tabs)
    assert isinstance(result, VTypeClosure)


def test_evaluate_app():
    """Test evaluating function application."""
    evalr = Evaluator()
    # (λx.x) True
    lam = Abs(TypeConstructor("Bool", []), Var(0))
    app = App(lam, Constructor("True", []))
    result = evalr.evaluate(app)
    assert result == VConstructor("True", [])


def test_evaluate_constructor():
    """Test evaluating a constructor."""
    evalr = Evaluator()
    # Cons Int Nil
    cons = Constructor("Cons", [Constructor("Int", []), Constructor("Nil", [])])
    result = evalr.evaluate(cons)
    assert result.name == "Cons"
    assert len(result.args) == 2
    assert result.args[0].name == "Int"
    assert result.args[1].name == "Nil"


def test_evaluate_constructor_no_args():
    """Test evaluating a nullary constructor."""
    evalr = Evaluator()
    result = evalr.evaluate(Constructor("True", []))
    assert result == VConstructor("True", [])


def test_evaluate_case():
    """Test evaluating a case expression."""
    evalr = Evaluator()
    # case True of { True -> Int; False -> Bool }
    scrut = Constructor("True", [])
    branches = [
        Branch(Pattern("True", []), Constructor("Int", [])),
        Branch(Pattern("False", []), Constructor("Bool", [])),
    ]
    case_expr = Case(scrut, branches)
    result = evalr.evaluate(case_expr)
    assert result == VConstructor("Int", [])


def test_evaluate_case_with_bindings():
    """Test evaluating case with pattern bindings."""
    evalr = Evaluator()
    # case (Cons Int Nil) of { Nil -> Zero; Cons x xs -> x }
    # Pattern vars are ["x", "xs"], constructor args are [Int, Nil]
    # After matching, x -> Int, xs -> Nil
    # x should be at de Bruijn index 0
    scrut = Constructor("Cons", [Constructor("Int", []), Constructor("Nil", [])])
    branches = [
        Branch(Pattern("Nil", []), Constructor("Zero", [])),
        Branch(Pattern("Cons", ["x", "xs"]), Var(0)),  # Returns bound x (first pattern var)
    ]
    case_expr = Case(scrut, branches)
    result = evalr.evaluate(case_expr)
    assert result == VConstructor("Int", [])


def test_evaluate_let():
    """Test evaluating a let expression."""
    evalr = Evaluator()
    # let x = True in x
    let_expr = Let("x", Constructor("True", []), Var(0))
    result = evalr.evaluate(let_expr)
    assert result == VConstructor("True", [])


def test_evaluate_let_with_computation():
    """Test evaluating let with a computation."""
    evalr = Evaluator()
    # let f = λx.x in f True
    lam = Abs(TypeConstructor("Bool", []), Var(0))
    let_expr = Let("f", lam, App(Var(0), Constructor("True", [])))
    result = evalr.evaluate(let_expr)
    assert result == VConstructor("True", [])


def test_evaluate_type_app():
    """Test evaluating type application (types erased)."""
    evalr = Evaluator()
    # (Λa.λx:a.x) [Bool]
    tabs = TAbs("a", Abs(TypeVar("a"), Var(0)))
    tapp = TApp(tabs, TypeConstructor("Bool", []))
    # Apply to True
    app = App(tapp, Constructor("True", []))
    result = evalr.evaluate(app)
    assert result == VConstructor("True", [])


def test_evaluate_polymorphic_id():
    """Test evaluating polymorphic identity function."""
    evalr = Evaluator()
    # id = Λa.λx:a.x
    # id @Int Int
    id_func = TAbs("a", Abs(TypeVar("a"), Var(0)))
    id_inst = TApp(id_func, TypeConstructor("Int", []))
    app = App(id_inst, Constructor("Int", []))
    result = evalr.evaluate(app)
    assert result == VConstructor("Int", [])


def test_apply_non_function_raises():
    """Test applying a non-function raises error."""
    evalr = Evaluator()
    with pytest.raises(RuntimeError, match="Cannot apply non-function"):
        evalr.apply(VConstructor("Int", []), VConstructor("True", []))


def test_type_apply_non_type_abs_raises():
    """Test type-applying a non-type-abstraction raises error."""
    evalr = Evaluator()
    with pytest.raises(RuntimeError, match="Cannot type-apply"):
        evalr.type_apply(VClosure(Environment.empty(), Var(0)))


def test_evaluate_program_empty():
    """Test evaluating empty program."""
    evalr = Evaluator()
    result = evalr.evaluate_program([])
    assert result == {}


def test_evaluate_program_term_decl():
    """Test evaluating program with term declaration."""
    evalr = Evaluator()
    decls = [TermDeclaration("x", None, Constructor("True", []))]
    result = evalr.evaluate_program(decls)
    assert "x" in result
    assert result["x"] == VConstructor("True", [])


def test_evaluate_program_data_decl_ignored():
    """Test that data declarations don't produce values."""
    evalr = Evaluator()
    decls = [
        DataDeclaration("Bool", [], [("True", []), ("False", [])]),
        TermDeclaration("x", None, Constructor("True", [])),
    ]
    result = evalr.evaluate_program(decls)
    assert "x" in result
    assert len(result) == 1  # Only term decl produces value


def test_nested_function_application():
    """Test nested function applications."""
    evalr = Evaluator()
    # (λf.λx.f x) (λy.y) True
    # = (λx.(λy.y) x) True
    # = (λy.y) True
    # = True
    inner_lam = Abs(TypeConstructor("Bool", []), Var(0))  # λy.y
    outer_lam = Abs(
        TypeArrow(TypeConstructor("Bool", []), TypeConstructor("Bool", [])),
        Abs(TypeConstructor("Bool", []), App(Var(1), Var(0))),
    )
    # Apply outer to inner
    app1 = App(outer_lam, inner_lam)
    # Apply result to True
    app2 = App(app1, Constructor("True", []))
    result = evalr.evaluate(app2)
    assert result == VConstructor("True", [])


def test_closure_captures_environment():
    """Test that closures properly capture their environment."""
    evalr = Evaluator()
    # let x = True in λy.y x (where y ignores x)
    # Actually: let x = True in λy.x
    # This creates a closure that captures x=True
    lam = Abs(TypeConstructor("Unit", []), Var(1))  # λy.x (x is at index 1 in body)
    let_expr = Let("x", Constructor("True", []), lam)
    # Apply to some argument
    app = App(let_expr, Constructor("Unit", []))
    result = evalr.evaluate(app)
    assert result == VConstructor("True", [])
