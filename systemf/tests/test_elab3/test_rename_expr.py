"""Tests for RenameExpr.rename_expr method.

Tests expression renaming with structural comparison.
Uses the structural comparison style from docs/styles/testing-structural.md.

NOTE: Some tests are skipped due to parser limitations (not bugs):
- Unknown operators: lexer rejects $ and other unknown operators

The bugs that were previously blocking tests have been fixed:
✅ Literal types: parser produces "Int"/"String", renamer normalizes to lowercase
✅ Let expressions: parser returns ValBind objects, all downstream passes updated
"""

import pytest
from parsy import eof

from systemf.elab3.rename_expr import RenameExpr
from systemf.elab3.builtins import (
    BUILTIN_TRUE, BUILTIN_FALSE, BUILTIN_LIST_CONS, BUILTIN_LIST_NIL,
    BUILTIN_PAIR, BUILTIN_PAIR_MKPAIR, BUILTIN_BIN_OPS
)
from systemf.elab3.reader_env import ReaderEnv, ImportRdrElt, ImportSpec, RdrElt
from systemf.elab3.types import Name, TyInt, TyString, BoundTv, TyFun, TyForall
from systemf.elab3.ast import (
    Var, Lam, App, Let, Ann, LitExpr, Case, CaseBranch, ConPat, VarPat,
    Binding, AnnotName
)
from systemf.elab3.types import LitInt, LitString
from systemf.utils.uniq import Uniq
from systemf.utils.location import Location
from systemf.utils.ast_utils import structural_equals
from systemf.surface.parser import parse_expression


def mk_rename_expr_with_builtins(mod_name: str = "Test", uniq_start: int = 1000) -> RenameExpr:
    """Create RenameExpr with builtins imported as unqualified.
    
    Args:
        mod_name: Module name for new names
        uniq_start: Starting unique ID to avoid conflicts with builtins
    
    Returns:
        RenameExpr configured with builtins in reader_env
    """
    uniq = Uniq(uniq_start)
    spec = ImportSpec(module_name="builtins", alias=None, is_qual=False)
    
    # Import True, False for if-then-else tests, plus operators
    builtins = [BUILTIN_TRUE, BUILTIN_FALSE, BUILTIN_PAIR_MKPAIR]
    # Add binary operators that are Name objects
    for op_name in BUILTIN_BIN_OPS.values():
        if isinstance(op_name, Name) and op_name not in builtins:
            builtins.append(op_name)
    
    elts: list[RdrElt] = [ImportRdrElt.create(name, spec) for name in builtins]
    reader_env = ReaderEnv.from_elts(elts)
    return RenameExpr(reader_env, mod_name, uniq)


def parse_expr(source: str):
    """Parse expression text to SurfaceTerm.
    
    Args:
        source: Expression source code (e.g., "\\x -> x")
    
    Returns:
        Parsed SurfaceTerm
    """
    return parse_expression(source)


# =============================================================================
# Variable and Literal Tests
# =============================================================================

def test_rename_expr_variable():
    """Variable reference becomes Var with looked-up Name."""
    renamer = mk_rename_expr_with_builtins()
    
    # Create a local binding for x
    x_name = renamer.new_name("x")
    renamer.local_env.append(("x", x_name))
    
    expr = parse_expr("x")
    rn_expr = renamer.rename_expr(expr)
    
    expected = Var(name=x_name)
    assert structural_equals(rn_expr, expected)


def test_rename_expr_literal_int():
    """Integer literal becomes LitExpr with LitInt."""
    renamer = mk_rename_expr_with_builtins()
    expr = parse_expr("42")
    rn_expr = renamer.rename_expr(expr)
    
    expected = LitExpr(lit=LitInt(value=42))
    assert structural_equals(rn_expr, expected)


def test_rename_expr_literal_string():
    """String literal becomes LitExpr with LitString."""
    renamer = mk_rename_expr_with_builtins()
    expr = parse_expr('"hello"')
    rn_expr = renamer.rename_expr(expr)
    
    expected = LitExpr(lit=LitString(value="hello"))
    assert structural_equals(rn_expr, expected)


# =============================================================================
# Lambda Tests
# =============================================================================

def test_rename_expr_lambda_simple():
    """Lambda \\x -> x creates Lam with param and body referencing bound var."""
    renamer = mk_rename_expr_with_builtins()
    expr = parse_expr("\\x -> x")
    rn_expr = renamer.rename_expr(expr)
    
    # Lambda binds x, body references the bound x
    assert isinstance(rn_expr, Lam)
    assert len(rn_expr.args) == 1
    param = rn_expr.args[0]
    assert isinstance(param, Name)
    assert param.surface == "x"
    
    # Body should be Var referencing the same name
    assert isinstance(rn_expr.body, Var)
    assert rn_expr.body.name.unique == param.unique


def test_rename_expr_lambda_annotated():
    """Lambda with type annotation \\(x :: Int) -> x."""
    renamer = mk_rename_expr_with_builtins()
    expr = parse_expr("\\(x :: Int) -> x")
    rn_expr = renamer.rename_expr(expr)
    
    assert isinstance(rn_expr, Lam)
    assert len(rn_expr.args) == 1
    param = rn_expr.args[0]
    assert isinstance(param, AnnotName)
    assert param.name.surface == "x"
    # Type should be TyInt
    assert isinstance(param.type_ann, TyInt)


def test_rename_expr_lambda_multiple_params():
    """Lambda with multiple params \\x y -> x."""
    renamer = mk_rename_expr_with_builtins()
    expr = parse_expr("\\x y -> x")
    rn_expr = renamer.rename_expr(expr)
    
    assert isinstance(rn_expr, Lam)
    assert len(rn_expr.args) == 2
    param0 = rn_expr.args[0]
    param1 = rn_expr.args[1]
    assert isinstance(param0, Name)
    assert isinstance(param1, Name)
    assert param0.surface == "x"
    assert param1.surface == "y"


def test_rename_expr_lambda_nested():
    """Nested lambdas \\x -> \\y -> x with proper scoping."""
    renamer = mk_rename_expr_with_builtins()
    expr = parse_expr("\\x -> \\y -> x")
    rn_expr = renamer.rename_expr(expr)
    
    # Outer lambda binds x
    assert isinstance(rn_expr, Lam)
    outer_x = rn_expr.args[0]
    assert isinstance(outer_x, Name)
    assert outer_x.surface == "x"
    
    # Inner lambda binds y
    assert isinstance(rn_expr.body, Lam)
    inner_y = rn_expr.body.args[0]
    assert isinstance(inner_y, Name)
    assert inner_y.surface == "y"
    
    # Body references outer x (not y)
    assert isinstance(rn_expr.body.body, Var)
    assert rn_expr.body.body.name.unique == outer_x.unique


# =============================================================================
# Application Tests
# =============================================================================

def test_rename_expr_application():
    """Application f x becomes App(Var(f), Var(x))."""
    renamer = mk_rename_expr_with_builtins()
    
    # Create local bindings
    f_name = renamer.new_name("f")
    x_name = renamer.new_name("x")
    renamer.local_env.extend([("f", f_name), ("x", x_name)])
    
    expr = parse_expr("f x")
    rn_expr = renamer.rename_expr(expr)
    
    expected = App(func=Var(name=f_name), arg=Var(name=x_name))
    assert structural_equals(rn_expr, expected)


def test_rename_expr_application_nested():
    """Nested application f x y becomes App(App(Var(f), Var(x)), Var(y))."""
    renamer = mk_rename_expr_with_builtins()
    
    f_name = renamer.new_name("f")
    x_name = renamer.new_name("x")
    y_name = renamer.new_name("y")
    renamer.local_env.extend([("f", f_name), ("x", x_name), ("y", y_name)])
    
    expr = parse_expr("f x y")
    rn_expr = renamer.rename_expr(expr)
    
    # Should be left-associative: (f x) y
    assert isinstance(rn_expr, App)
    assert isinstance(rn_expr.arg, Var)
    assert rn_expr.arg.name.unique == y_name.unique
    assert isinstance(rn_expr.func, App)
    inner_app = rn_expr.func
    assert isinstance(inner_app.arg, Var)
    assert inner_app.arg.name.unique == x_name.unique
    assert isinstance(inner_app.func, Var)
    assert inner_app.func.name.unique == f_name.unique


# =============================================================================
# Let Tests (all skipped due to parser/renamer mismatch)
# =============================================================================

def test_rename_expr_let_simple():
    """Let binding let x = 1 in x."""
    renamer = mk_rename_expr_with_builtins()
    expr = parse_expr("let x = 1 in x")
    rn_expr = renamer.rename_expr(expr)
    
    assert isinstance(rn_expr, Let)
    assert len(rn_expr.bindings) == 1


def test_rename_expr_let_annotated():
    """Let with type annotation let x :: Int = 1 in x."""
    renamer = mk_rename_expr_with_builtins()
    expr = parse_expr("let x :: Int = 1 in x")
    rn_expr = renamer.rename_expr(expr)
    
    assert isinstance(rn_expr, Let)
    binding = rn_expr.bindings[0]
    assert isinstance(binding.name, AnnotName)
    assert binding.name.name.surface == "x"
    assert isinstance(binding.name.type_ann, TyInt)


def test_rename_expr_let_multiple():
    """Multiple let bindings via layout."""
    renamer = mk_rename_expr_with_builtins()
    expr = parse_expr("""let
  x = 1
  y = 2
in x + y""")
    rn_expr = renamer.rename_expr(expr)
    
    assert isinstance(rn_expr, Let)
    assert len(rn_expr.bindings) == 2


def test_rename_expr_let_mutual():
    """Mutually recursive let bindings share environment."""
    renamer = mk_rename_expr_with_builtins()
    expr = parse_expr("""let
  x = y
  y = 1
in x""")
    rn_expr = renamer.rename_expr(expr)
    
    assert isinstance(rn_expr, Let)
    assert len(rn_expr.bindings) == 2


def test_rename_expr_annotation():
    """Type annotation 1 :: Int becomes Ann(LitExpr(1), TyInt())."""
    renamer = mk_rename_expr_with_builtins()
    expr = parse_expr("1 :: Int")
    rn_expr = renamer.rename_expr(expr)
    
    assert isinstance(rn_expr, Ann)
    assert isinstance(rn_expr.expr, LitExpr)
    assert isinstance(rn_expr.ty, TyInt)


# =============================================================================
# If-Then-Else Tests (Desugaring)
# =============================================================================

def test_rename_expr_if_then_else():
    """If-then-else desugars to case on True/False."""
    renamer = mk_rename_expr_with_builtins()
    
    # Create local bindings
    cond_name = renamer.new_name("cond")
    then_name = renamer.new_name("then_val")
    else_name = renamer.new_name("else_val")
    renamer.local_env.extend([
        ("cond", cond_name),
        ("then_branch", then_name),
        ("else_branch", else_name)
    ])
    
    expr = parse_expr("if cond then then_branch else else_branch")
    rn_expr = renamer.rename_expr(expr)
    
    assert isinstance(rn_expr, Case)
    assert len(rn_expr.branches) == 2
    
    # First branch: True -> then_branch
    true_branch = rn_expr.branches[0]
    assert isinstance(true_branch, CaseBranch)
    assert isinstance(true_branch.pattern, ConPat)
    assert true_branch.pattern.con == BUILTIN_TRUE
    assert isinstance(true_branch.body, Var)
    assert true_branch.body.name.unique == then_name.unique
    
    # Second branch: False -> else_branch
    false_branch = rn_expr.branches[1]
    assert isinstance(false_branch.pattern, ConPat)
    assert false_branch.pattern.con == BUILTIN_FALSE
    assert isinstance(false_branch.body, Var)
    assert false_branch.body.name.unique == else_name.unique


# =============================================================================
# Binary Operator Tests
# =============================================================================

def test_rename_expr_binary_op():
    """Binary operator x + y desugars to App(App(Var(+), x), y)."""
    renamer = mk_rename_expr_with_builtins()
    
    # Check if + is available
    if "+" not in BUILTIN_BIN_OPS:
        pytest.skip("+ operator not in BUILTIN_BIN_OPS")
    
    x_name = renamer.new_name("x")
    y_name = renamer.new_name("y")
    renamer.local_env.extend([("x", x_name), ("y", y_name)])
    
    expr = parse_expr("x + y")
    rn_expr = renamer.rename_expr(expr)
    
    # Should be: App(App(Var(+), Var(x)), Var(y))
    assert isinstance(rn_expr, App)
    assert isinstance(rn_expr.func, App)
    assert isinstance(rn_expr.func.func, Var)
    # Operator name
    assert rn_expr.func.func.name == BUILTIN_BIN_OPS["+"]
    # First arg
    assert isinstance(rn_expr.func.arg, Var)
    assert rn_expr.func.arg.name.unique == x_name.unique
    # Second arg
    assert isinstance(rn_expr.arg, Var)
    assert rn_expr.arg.name.unique == y_name.unique


# =============================================================================
# Tuple Tests (Desugaring)
# =============================================================================

def test_rename_expr_tuple_pair():
    """Tuple (1, 2) desugars to nested pair constructor."""
    renamer = mk_rename_expr_with_builtins()
    expr = parse_expr("(1, 2)")
    rn_expr = renamer.rename_expr(expr)
    
    # Should be: App(App(Var(BUILTIN_PAIR_MKPAIR), LitExpr(1)), LitExpr(2))
    assert isinstance(rn_expr, App)
    assert isinstance(rn_expr.func, App)
    assert isinstance(rn_expr.func.func, Var)
    assert rn_expr.func.func.name == BUILTIN_PAIR_MKPAIR


def test_rename_expr_tuple_triple():
    """Triple (1, 2, 3) desugars to nested pair constructors."""
    renamer = mk_rename_expr_with_builtins()
    expr = parse_expr("(1, 2, 3)")
    rn_expr = renamer.rename_expr(expr)
    
    # Should be: App(App(Var(mkPair), 1), App(App(Var(mkPair), 2), 3))
    # Or equivalent nested structure
    assert isinstance(rn_expr, App)


# =============================================================================
# Case Expression Tests
# =============================================================================

def test_rename_expr_case_simple():
    """Simple case expression case x of with layout syntax."""
    renamer = mk_rename_expr_with_builtins()

    x_name = renamer.new_name("x")
    renamer.local_env.append(("x", x_name))

    expr = parse_expr("""case x of
  True -> 1
  False -> 0""")
    rn_expr = renamer.rename_expr(expr)
    
    assert isinstance(rn_expr, Case)
    # Scrutinee
    assert isinstance(rn_expr.scrutinee, Var)
    assert rn_expr.scrutinee.name.unique == x_name.unique
    # Two branches
    assert len(rn_expr.branches) == 2


# =============================================================================
# Error Cases
# =============================================================================

def test_rename_expr_unresolved_variable():
    """Unresolved variable raises exception."""
    renamer = mk_rename_expr_with_builtins()
    expr = parse_expr("unknown_var")
    
    with pytest.raises(Exception, match="unresolved variable"):
        renamer.rename_expr(expr)


@pytest.mark.skip(reason="BUG: lexer rejects unknown operators like $")
def test_rename_expr_unknown_operator():
    """Unknown operator raises exception."""
    renamer = mk_rename_expr_with_builtins()
    
    x_name = renamer.new_name("x")
    y_name = renamer.new_name("y")
    renamer.local_env.extend([("x", x_name), ("y", y_name)])
    
    expr = parse_expr("x $ y")  # $ is not a builtin operator
    
    with pytest.raises(Exception, match="unknown operator"):
        renamer.rename_expr(expr)


# =============================================================================
# Shadowing Tests
# =============================================================================

def test_rename_expr_lambda_shadowing():
    """Lambda param shadows outer binding."""
    renamer = mk_rename_expr_with_builtins()
    
    # Create outer binding for x
    outer_x = renamer.new_name("x")
    renamer.local_env.append(("x", outer_x))
    
    expr = parse_expr("\\x -> x")
    rn_expr = renamer.rename_expr(expr)
    
    # Lambda creates new binding for x
    assert isinstance(rn_expr, Lam)
    inner_x = rn_expr.args[0]
    assert isinstance(inner_x, Name)
    assert inner_x.unique != outer_x.unique
    
    # Body references inner x
    assert isinstance(rn_expr.body, Var)
    assert rn_expr.body.name.unique == inner_x.unique


def test_rename_expr_let_shadowing():
    """Let binding shadows outer binding."""
    renamer = mk_rename_expr_with_builtins()
    
    # Create outer binding for x
    outer_x = renamer.new_name("x")
    renamer.local_env.append(("x", outer_x))
    
    expr = parse_expr("let x = 1 in x")
    rn_expr = renamer.rename_expr(expr)
    
    # Let creates new binding for x
    assert isinstance(rn_expr, Let)
    let_x = rn_expr.bindings[0].name
    assert isinstance(let_x, Name)
    assert let_x.unique != outer_x.unique
    
    # Body references let x
    assert isinstance(rn_expr.body, Var)
    assert rn_expr.body.name.unique == let_x.unique
