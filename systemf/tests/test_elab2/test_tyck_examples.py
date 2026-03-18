import itertools
from typing import Any, Callable, TypeVar

from systemf.elab2.tyck import Defer, TyCk, TyCkImpl, allnames, quantify, run_infer
from systemf.elab2.types import C, INT, TY, CoreTm, Lit, LitInt, SyntaxDSL, Ty, WpFun, WpTyLam, zonk_type
from systemf.elab2.unify import WP_HOLE, WpCompose

# ---
# test subsumption check
# this relies soely on uniq <- make_skolem <- skolemise
# and it's functionally independent of others

# ---
# test poly check
# - i don't know, looks we need to rely on syntax

# ---
# test skolemise
#
# skolemise should process forall at prenex position

def test_skolemise_mono():
    """PRMONO: pr(Int) = Int ↦ λx.x"""
    def _run(impl: TyCkImpl[Any]):
        sks, ty, w = impl.skolemise(INT)
        assert sks == []
        assert ty == INT
        assert w == WP_HOLE
    run_tyck(_run)


def test_skolemise_prpoly():
    """PRPOLY: pr(∀a. a → a) = sk_a → sk_a ↦ Λsk_a.[HOLE]"""
    a = TY.bound_var("a")
    t = TY.forall([a], TY.fun(a, a))
    def _run(impl: TyCkImpl[Any]):
        sks, ty, w = impl.skolemise(t)
        sk = TY.skolem("a", 0)
        assert sks == [sk]
        assert ty == TY.fun(sk, sk)
        assert w == WpTyLam(sk)
    run_tyck(_run)


def test_skolemise_prfun():
    """PRFUN: pr(Int → ∀a. a) = Int → sk_a ↦ WpFun(Int, WP_HOLE, Λsk_a.[HOLE])"""
    a = TY.bound_var("a")
    t = TY.fun(INT, TY.forall([a], a))
    def _run(impl: TyCkImpl[Any]):
        sks, ty, w = impl.skolemise(t)
        sk = TY.skolem("a", 0)
        assert sks == [sk]
        assert ty == TY.fun(INT, sk)
        assert w == WpFun(INT, WP_HOLE, WpTyLam(sk))
    run_tyck(_run)


def test_skolemise_prfun_poly_arg():
    """PRFUN with polymorphic argument: pr((∀a.a→a) → Int) = (∀a.a→a) → Int (no change)"""
    a = TY.bound_var("a")
    poly_id = TY.forall([a], TY.fun(a, a))
    t = TY.fun(poly_id, INT)
    def _run(impl: TyCkImpl[Any]):
        sks, ty, w = impl.skolemise(t)
        # No skolems introduced since forall is in contravariant position
        assert sks == []
        assert ty == TY.fun(poly_id, INT)
        assert w == WpFun(poly_id, WP_HOLE, WP_HOLE)
    run_tyck(_run)


def test_skolemise_nested():
    """PRPOLY nested: pr(∀a.∀b. a → b → a) = sk_a → sk_b → sk_a"""
    a = TY.bound_var("a")
    b = TY.bound_var("b")
    t = TY.forall([a], TY.forall([b], TY.fun(a, TY.fun(b, a))))
    def _run(impl: TyCkImpl[Any]):
        sks, ty, w = impl.skolemise(t)
        sk1, sk2 = TY.skolem("a", 0), TY.skolem("b", 1)
        assert sks == [sk1, sk2]
        assert ty == TY.fun(sk1, TY.fun(sk2, sk1))
        # Wrapper: Λsk_a. Λsk_b. [HOLE]
        assert w == WpCompose(WpTyLam(sk1), WpTyLam(sk2))
    run_tyck(_run)


def test_skolemise_complex():
    """Complex: pr(∀a. a → ∀b. b → a) from the paper example"""
    a = TY.bound_var("a")
    b = TY.bound_var("b")
    t = TY.forall([a], TY.fun(a, TY.forall([b], TY.fun(b, a))))
    def _run(impl: TyCkImpl[Any]):
        sks, ty, w = impl.skolemise(t)
        assert sks == [TY.skolem("a", 0), TY.skolem("b", 1)]
        sk1, sk2 = sks
        assert ty == TY.fun(sk1, TY.fun(sk2, sk1))
        assert w == (
            WpCompose(
            WpTyLam(sk1),
            WpFun(sk1, WP_HOLE,
                WpCompose(
                    WpTyLam(sk2),
                    WpFun(sk2, WP_HOLE, WP_HOLE)))))
    run_tyck(_run)

# ---
# helpers
#

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

# ---
# example tests

def test_simple1():
    run_tyck_term(
        lambda s: s.lit(LitInt(1)),
        check_type(INT),
        equals_term(C.lit(LitInt(1))),
    )

def test_simple2():
    # let id = \x -> x in id i => Int
    run_tyck_term(
        lambda s: s.let("id", s.lam("x", s.var("x")),
            s.app(s.var("id"), s.lit(LitInt(1)))),
        check_type(INT),
        equals_term(C.lit(LitInt(1))),
    )
