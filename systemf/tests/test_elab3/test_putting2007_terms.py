"""Bidirectional type checking term tests from Putting2007 (JFP).

Ported from elab2 test_tyck_examples_terms.py.

These tests validate Figure 8: Bidirectional Type Checking Rules.
They require the full pipeline (parse → rename → typecheck) or
a TypeChecker test harness built on the elab3 surface AST.

Status: TODO — needs TypeChecker harness or pipeline integration.
The elab2 tests used TyCkImpl monad; elab3 uses TypeChecker(Unifier).
"""

import pytest

from systemf.elab3.tc_ctx import Unifier
from systemf.elab3.types.ty import (
    BoundTv,
    Name,
    Ty,
    TyForall,
    TyFun,
    TyInt,
    TyString,
    zonk_type,
)
from systemf.utils.uniq import Uniq


INT = TyInt()
STRING = TyString()


class FakeTypeChecker(Unifier):
    def __init__(self) -> None:
        super().__init__("PuttingTermsTest", Uniq(6000))

    def lookup_gbl(self, name: Name):
        raise KeyError(name)


# =============================================================================
# TODO: Port term-level tests
#
# The following tests from elab2 need TypeChecker.expr() integration:
#
# Figure 8 — INT rule:
#   test_int_infer: 42 synthesizes Int
#   test_int_check: 42 checks against Int
#   test_int_check_fail: 42 checking against String fails
#
# Figure 8 — VAR rule:
#   test_var_mono: x:Int in env yields Int
#   test_var_poly: id:∀a.a→a instantiates
#
# Figure 8 — ABS rule:
#   test_abs1_infer: λx.x infers ?→?
#   test_abs2_check: λx.x checks against Int→Int
#   test_abs2_check_fail: λx.x checking against Int→String fails
#
# Figure 8 — APP rule:
#   test_app_mono: id 42 where id:Int→Int yields Int
#   test_app_poly: id 42 where id:∀a.a→a yields Int
#
# Figure 8 — LET rule:
#   test_let_simple: let x = 42 in x yields Int
#   test_let_poly: let id = λx.x in id 42 yields Int
#
# Figure 8 — GEN rule:
#   test_gen1_infer: λx.x generalizes to ∀a.a→a
#   test_gen2_check: λx.x checks against ∀a.a→a
#
# Integration:
#   test_integration_identity: end-to-end with core term verification
#
# To port these, we need either:
# 1. A test harness wrapping TypeChecker.expr() with surface AST nodes
# 2. Pipeline-based tests: parse source → execute → check module types
# =============================================================================
