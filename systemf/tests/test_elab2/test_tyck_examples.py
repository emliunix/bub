# =============================================================================
# Imports
# =============================================================================

import itertools
from typing import Any, Callable, TypeVar

import pytest

from systemf.elab2.tyck import Defer, TyCk, TyCkImpl, allnames, quantify, run_infer
from systemf.elab2.types import (
    C, INT, STRING, TY, CoreTm, Lit, LitInt, Ty, TyCkException,
    WpCast, WpFun, WpTyApp, WpTyLam, wp_compose, wp_fun, zonk_type, zonk_wrapper
)
from systemf.elab2.unify import WP_HOLE, WpCompose, unify

# =============================================================================
# Figure 9: Skolemization Tests (PR Rules)
# =============================================================================
# Tests for pr(sigma) - converting polymorphic types to weak-prenex form
# See tyck_examples.md "Figure 9: Subsumption and Skolemization"

def test_skolemise_mono():
    """PRMONO: pr(Int) = Int ↦ λx.x

    See tyck_examples.md "Figure 9: Subsumption and Skolemization" for full spec.
    """
    def _run(impl: TyCkImpl[Any]):
        sks, ty, w = impl.skolemise(INT)
        assert sks == []
        assert ty == INT
        assert w == WP_HOLE
    run_tyck(_run)


def test_skolemise_prpoly():
    """PRPOLY: pr(∀a. a → a) = sk_a → sk_a ↦ Λsk_a.[HOLE]

    See tyck_examples.md "PRPOLY — Polymorphic Type" for full spec.
    """
    a = TY.bound_var("a")
    t = TY.forall([a], TY.fun(a, a))
    def _run(impl: TyCkImpl[Any]):
        sks, ty, w = impl.skolemise(t)
        sk = TY.skolem("a", 0)
        assert sks == [sk]
        assert ty == TY.fun(sk, sk)
        # PRFUN on (sk_a → sk_a) produces WpFun(sk_a, WP_HOLE, WP_HOLE)
        # Then PRPOLY: WpCompose(WpTyLam(sk), WpFun(...))
        # No simplification applies (neither is WP_HOLE)
        prfun = wp_fun(sk, WP_HOLE, WP_HOLE)
        assert w == WpTyLam(sk)  # WpCompose(WpTyLam(sk), prfun)
    run_tyck(_run)


def test_skolemise_prfun():
    """PRFUN: pr(Int → ∀a. a) = Int → sk_a ↦ WpFun(Int, WP_HOLE, WpTyLam(sk_a))

    See tyck_examples.md "PRFUN — Function Type with Prenex Result" for full spec.
    """
    a = TY.bound_var("a")
    t = TY.fun(INT, TY.forall([a], a))
    def _run(impl: TyCkImpl[Any]):
        sks, ty, w = impl.skolemise(t)
        sk = TY.skolem("a", 0)
        assert sks == [sk]
        assert ty == TY.fun(INT, sk)
        # Inner wrap from PRPOLY: WpCompose(WpTyLam(sk), WP_HOLE) simplifies to WpTyLam(sk)
        inner_wrap = wp_compose(WpTyLam(sk), WP_HOLE)
        assert w == WpFun(INT, WP_HOLE, inner_wrap)
    run_tyck(_run)


def test_skolemise_prfun_poly_arg():
    """PRFUN with polymorphic argument: pr((∀a.a→a) → Int) = (∀a.a→a) → Int (no change)

    Forall in contravariant position is not prenex - no skolemization.
    """
    a = TY.bound_var("a")
    poly_id = TY.forall([a], TY.fun(a, a))
    t = TY.fun(poly_id, INT)
    def _run(impl: TyCkImpl[Any]):
        sks, ty, w = impl.skolemise(t)
        # No skolems introduced since forall is in contravariant position
        assert sks == []
        assert ty == TY.fun(poly_id, INT)
        assert w == wp_fun(poly_id, WP_HOLE, WP_HOLE)
    run_tyck(_run)


def test_skolemise_nested():
    """PRPOLY nested: pr(∀a.∀b. a → b → a) = sk_a → sk_b → sk_a

    See tyck_examples.md "Nested: ∀a. ∀b. a → b → a" for full spec.
    """
    a = TY.bound_var("a")
    b = TY.bound_var("b")
    t = TY.forall([a], TY.forall([b], TY.fun(a, TY.fun(b, a))))
    def _run(impl: TyCkImpl[Any]):
        sks, ty, w = impl.skolemise(t)
        sk1, sk2 = TY.skolem("a", 0), TY.skolem("b", 1)
        assert sks == [sk1, sk2]
        assert ty == TY.fun(sk1, TY.fun(sk2, sk1))
        # Inner: PRFUN on (sk_b → sk_a) with PRMONO result
        inner_prfun = wp_fun(sk2, WP_HOLE, WP_HOLE)
        # Middle: PRFUN on (sk_a → (sk_b → sk_a))
        middle_prfun = wp_fun(sk1, WP_HOLE, inner_prfun)
        # Outer PRPOLY on b: WpCompose(WpTyLam(sk2), middle_prfun)
        # No simplification (neither is WP_HOLE)
        middle_prpoly = wp_compose(WpTyLam(sk2), middle_prfun)
        # Outer PRPOLY on a: WpCompose(WpTyLam(sk1), middle_prpoly)
        # No simplification (neither is WP_HOLE)
        assert w == wp_compose(WpTyLam(sk1), middle_prpoly)
    run_tyck(_run)


def test_skolemise_complex():
    """Complex: pr(∀a. a → ∀b. b → a) from the paper example

    See tyck_examples.md "Complex Case: ∀a. a → ∀b. b → a" for full spec.
    """
    a = TY.bound_var("a")
    b = TY.bound_var("b")
    t = TY.forall([a], TY.fun(a, TY.forall([b], TY.fun(b, a))))
    def _run(impl: TyCkImpl[Any]):
        sks, ty, w = impl.skolemise(t)
        assert sks == [TY.skolem("a", 0), TY.skolem("b", 1)]
        sk1, sk2 = sks
        assert ty == TY.fun(sk1, TY.fun(sk2, sk1))
        # Innermost: PRFUN on (sk_b → sk_a) with PRMONO
        inner_prfun = wp_fun(sk2, WP_HOLE, WP_HOLE)
        # Inner PRPOLY on b: WpCompose(WpTyLam(sk2), inner_prfun)
        # No simplification (inner_prfun is not WP_HOLE)
        inner_prpoly = wp_compose(WpTyLam(sk2), inner_prfun)
        # Middle PRFUN: (sk_a → res)
        middle_prfun = wp_fun(sk1, WP_HOLE, inner_prpoly)
        # Outer PRPOLY on a: WpCompose(WpTyLam(sk1), middle_prfun)
        assert w == wp_compose(WpTyLam(sk1), middle_prfun)
    run_tyck(_run)

# =============================================================================
# Subsumption Tests (DSK Rules)
# =============================================================================
# Tests for subs_check(sigma1, sigma2) - checking sigma1 ≤ sigma2
# See tyck_examples.md "Subsumption Rules"

def test_subs_check_mono():
    """MONO: Int ≤ Int - monomorphic types unify directly.

    See tyck_examples.md "MONO" for full spec.
    """
    def _run(impl: TyCkImpl[Any]):
        wrap = impl.subs_check(INT, INT)
        # Unification succeeds, wrapper is WpCast(Int, Int)
        assert wrap == WpCast(INT, INT)
    run_tyck(_run)


def test_subs_check_deep_skol():
    """DEEP-SKOL: ∀a.a→a ≤ Int→Int - polymorphic to monomorphic subsumption.

    See tyck_examples.md "DEEP-SKOL" for full spec.
    """
    a = TY.bound_var("a")
    poly_id = TY.forall([a], TY.fun(a, a))
    mono_id = TY.fun(INT, INT)

    def _run(impl: TyCkImpl[Any]):
        wrap = impl.subs_check(poly_id, mono_id)
        wrap = zonk_wrapper(wrap)
        assert wrap == WpTyApp(INT)
    run_tyck(_run)

def test_subs_check_deep_skol_anti():
    """ANTI-CASE: Int→String ≤ ∀a.a→a MUST FAIL

    Rigid skolem cannot satisfy conflicting constraints.
    See tyck_examples.md "Anti-case explanation" for full spec.
    """
    a = TY.bound_var("a")
    poly_id = TY.forall([a], TY.fun(a, a))
    bad_mono = TY.fun(INT, STRING)

    def _run(impl: TyCkImpl[Any]):
        with pytest.raises(TyCkException):
            impl.subs_check(bad_mono, poly_id)
    run_tyck(_run)

# =============================================================================
# Test Helpers
# =============================================================================

def check_type(expected: Ty):
    def _check(ty: Ty):
        assert zonk_type(ty) == expected
    return _check

def equals_term(expected: CoreTm):
    def _check(term: CoreTm):
        assert term == expected
    return _check

def run_tyck(run: Callable[[TyCkImpl[CoreTm]], None]):
    impl = TyCkImpl(C)
    run(impl)

def run_tyck_term(expr: Callable[[TyCkImpl[CoreTm]], TyCk[Defer[CoreTm]]], check_ty: Callable[[Ty], None], check: Callable[[CoreTm], None]):
    def _run(impl):
        poly_term = impl.poly(expr(impl))
        ty, res = run_infer(None, poly_term)
        check_ty(ty)
        check(res())
    run_tyck(_run)

# =============================================================================
# Integration Tests (End-to-end type checking)
# =============================================================================

def test_simple1():
    run_tyck_term(
        lambda s: s.lit(LitInt(1)),
        check_type(INT),
        equals_term(C.lit(LitInt(1))),
    )

def test_simple2():
    # let id = \x -> x in id 1
    a = TY.bound_var("a")
    run_tyck_term(
        lambda s: s.let("id", s.lam("x", s.var("x")),
            s.app(s.var("id"), s.lit(LitInt(1)))),
        check_type(INT),
        equals_term(
            C.let(
                "id",
                TY.forall([a], TY.fun(a, a)),
                C.tylam(a, C.lam("x", a, C.var("x", a))),
                C.app(
                    C.tyapp(C.var("id", TY.forall([a], TY.fun(a, a))), INT),
                    C.lit(LitInt(1))
                )
            )
        )
    )
