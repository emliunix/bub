import itertools
from typing import Callable

from systemf.elab2.tyck import TyCk, TyCkImpl, allnames, quantify
from systemf.elab2.types import INT, TY, Lit, LitInt, SyntaxDSL, Ty, zonk_type

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
# forall a. a -> forall b. (forall c. c -> b -> a) -> b -> a


def test_skolemise():
    a = TY.bound_var("a")
    b = TY.bound_var("b")
    c = TY.bound_var("c")
    arg_forall = TY.forall([c], TY.fun(c, TY.fun(b, a)))
    ty = TY.forall([a], TY.fun(a, TY.forall([b], TY.fun(arg_forall, TY.fun(b, a)))))
    sks, actual = TyCkImpl().skolemise(ty)
    assert len(sks) == 2
    sk1, sk2 = sks

    expected = TY.fun(sk1, TY.fun(TY.forall([c], TY.fun(c, TY.fun(sk2, sk1))), TY.fun(sk2, sk1)))
    assert actual == expected


# ---
# test quantify
#
# quantify should correctly replace meta vars with bound vars


def test_quantify_replaces_meta_vars():
    # create two meta type variables
    m1 = TY.meta(1)
    m2 = TY.meta(2)
    # build a type: m1 -> (Int -> m2)
    ty = TY.fun(m1, TY.fun(TY.int_ty(), m2))
    q = quantify([m1, m2], ty)

    # result should be: forall a b. a -> (Int -> b)
    expected = TY.forall(
        [TY.bound_var("a"), TY.bound_var("b")],
        TY.fun(TY.bound_var("a"), TY.fun(TY.int_ty(), TY.bound_var("b"))),
    )
    assert q == expected

    # the original metas should have their refs set to the bound vars
    assert m1.ref.get() == TY.bound_var("a")
    assert m2.ref.get() == TY.bound_var("b")


# ---
# misc


def test_allnames():
    """
    allnames generates names correctly
    """
    assert list(itertools.islice(allnames(), 3)) == ["a", "b", "c"]
    assert list(itertools.islice(allnames(), 29))[-3:] == ["a1", "b1", "c1"]


# ---
# main tyck tests
# - Lit(1) => Int
# - let id = \x -> x in id i => Int
#


def typecheck_entry(expr: Callable[[SyntaxDSL[TyCk]], TyCk], ty: Ty):
    impl = TyCkImpl()
    assert zonk_type(impl.poly(expr(impl)).infer(None)) == ty


def test_tyck_lit():
    typecheck_entry(lambda s: s.lit(LitInt(1)), INT)


def test_tyck_let():
    # let id = \x -> x in id i => Int
    typecheck_entry(
        lambda s: s.let("id", s.lam("x", s.dbi(0)),
            s.app(s.dbi(0), s.lit(LitInt(1)))),
        INT
    )
