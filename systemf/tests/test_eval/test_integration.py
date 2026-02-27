"""Integration tests for the full evaluation pipeline."""

import pytest

from systemf.core.ast import (
    Abs,
    App,
    Branch,
    Case,
    Constructor,
    Let,
    Pattern,
    Var,
)
from systemf.core.types import TypeArrow, TypeConstructor, TypeVar
from systemf.core.checker import TypeChecker
from systemf.core.context import Context
from systemf.eval.machine import Evaluator
from systemf.eval.value import VConstructor, VClosure


def test_core_to_eval_lambda():
    """Test evaluation of core lambda term (bypassing surface language)."""
    # (λx.x) True
    lam = Abs(TypeConstructor("Bool", []), Var(0))
    app = App(lam, Constructor("True", []))

    # Type check
    checker = TypeChecker({"True": TypeConstructor("Bool", [])})
    ctx = Context.empty()
    ty = checker.infer(ctx, app)

    # Evaluate
    evalr = Evaluator()
    result = evalr.evaluate(app)

    assert result == VConstructor("True", [])


def test_core_to_eval_case():
    """Test evaluation of core case term."""
    # case True of { True -> One; False -> Two }
    scrut = Constructor("True", [])
    branches = [
        Branch(Pattern("True", []), Constructor("One", [])),
        Branch(Pattern("False", []), Constructor("Two", [])),
    ]
    case_expr = Case(scrut, branches)

    # Type check - both branches return the same type
    checker = TypeChecker(
        {
            "True": TypeConstructor("Bool", []),
            "False": TypeConstructor("Bool", []),
            "One": TypeConstructor("Nat", []),
            "Two": TypeConstructor("Nat", []),
        }
    )
    ctx = Context.empty()
    ty = checker.infer(ctx, case_expr)

    # Evaluate
    evalr = Evaluator()
    result = evalr.evaluate(case_expr)

    assert result == VConstructor("One", [])


def test_core_to_eval_let():
    """Test evaluation of core let term."""
    # let x = True in x
    let_expr = Let("x", Constructor("True", []), Var(0))

    # Type check
    checker = TypeChecker({"True": TypeConstructor("Bool", [])})
    ctx = Context.empty()
    ty = checker.infer(ctx, let_expr)

    # Evaluate
    evalr = Evaluator()
    result = evalr.evaluate(let_expr)

    assert result == VConstructor("True", [])


def test_core_to_eval_program():
    """Test evaluation of multiple declarations."""
    from systemf.core.ast import TermDeclaration, DataDeclaration

    decls = [
        DataDeclaration("Bool", [], [("True", []), ("False", [])]),
        TermDeclaration("result", None, Constructor("True", [])),
    ]

    # Type check
    checker = TypeChecker()
    types = checker.check_program(decls)

    # Evaluate
    evalr = Evaluator()
    values = evalr.evaluate_program(decls)

    assert "result" in values
    assert values["result"] == VConstructor("True", [])


@pytest.mark.skip(reason="Surface language parser syntax not finalized")
def test_full_pipeline_simple():
    """Test full pipeline with simple expression (requires surface parser)."""
    from systemf.surface.lexer import Lexer
    from systemf.surface.parser import Parser
    from systemf.surface.elaborator import Elaborator

    source = "x = True"

    # Parse
    tokens = Lexer(source).tokenize()
    surface = Parser(tokens).parse()

    # Elaborate
    elab = Elaborator()
    module = elab.elaborate(surface)

    # Type check
    checker = TypeChecker(module.constructor_types)
    types = checker.check_program(module.declarations)

    # Evaluate
    evalr = Evaluator()
    values = evalr.evaluate_program(module.declarations)

    assert "x" in values
    assert values["x"] == VConstructor("True", [])
