from __future__ import annotations
from systemf.elab3.types.ty import (
    BoundTv,
    MetaTv,
    Name,
    Ref,
    TyConApp,
    TyForall,
    TyFun,
    TyInt,
    TyString,
    zonk_type,
)
from systemf.elab3.name_cache import NameCache
from systemf.elab3.builtins import BUILTIN_BOOL
from systemf.utils.uniq import Uniq


def test_zonk_unbound_meta():
    m = MetaTv(uniq=1, ref=Ref(None))
    result = zonk_type(m)
    assert result is m
def test_zonk_bound_meta():
    m = MetaTv(uniq=1, ref=Ref(TyInt()))
    result = zonk_type(m)
    assert result == TyInt()
def test_zonk_meta_chain():
    m3 = MetaTv(uniq=3, ref=Ref(TyInt()))
    m2 = MetaTv(uniq=2, ref=Ref(m3))
    m1 = MetaTv(uniq=1, ref=Ref(m2))
    result = zonk_type(m1)
    assert result == TyInt()
def test_zonk_path_compression():
    m2 = MetaTv(uniq=2, ref=Ref(TyInt()))
    m1 = MetaTv(uniq=1, ref=Ref(m2))
    result = zonk_type(m1)
    assert result == TyInt()
def test_zonk_function_type():
    m = MetaTv(uniq=1, ref=Ref(TyInt()))
    fun = TyFun(m, TyString())
    result = zonk_type(fun)
    assert result == TyFun(TyInt(), TyString())
def test_zonk_forall():
    m = MetaTv(uniq=1, ref=Ref(TyInt()))
    a = BoundTv(name=Name(mod="<local>", surface="a", unique=-1))
    forall_ty = TyForall(vars=[a], body=m)
    result = zonk_type(forall_ty)
    expected = TyForall(vars=[a], body=TyInt())
    assert result == expected
def test_zonk_nested_fun():
    m1 = MetaTv(uniq=1, ref=Ref(TyInt()))
    m2 = MetaTv(uniq=2, ref=Ref(TyString()))
    nested = TyFun(TyFun(m1, m2), m1)
    result = zonk_type(nested)
    expected = TyFun(TyFun(TyInt(), TyString()), TyInt())
    assert result == expected
def test_zonk_tycon_app():
    list_name = Name(mod="builtins", surface="List", unique=4)
    m = MetaTv(uniq=1, ref=Ref(TyInt()))
    list_ty = TyConApp(name=list_name, args=[m])
    result = zonk_type(list_ty)
    expected = TyConApp(name=list_name, args=[TyInt()])
    assert result == expected
START_UNIQ = 1000
def test_cache_allocates_new_unique():
    cache = NameCache(Uniq(START_UNIQ))
    name = cache.get("M", "foo")
    assert name.mod == "M"
    assert name.surface == "foo"
    assert name.unique >= START_UNIQ
def test_cache_stable_allocation():
    cache = NameCache(Uniq(START_UNIQ))
    n1 = cache.get("M", "foo")
    n2 = cache.get("M", "foo")
    assert n1.unique == n2.unique
def test_cache_different_surface():
    cache = NameCache(Uniq(START_UNIQ))
    n1 = cache.get("M", "foo")
    n2 = cache.get("M", "bar")
    assert n2.unique == n1.unique + 1
def test_cache_different_module():
    cache = NameCache(Uniq(START_UNIQ))
    n1 = cache.get("M", "foo")
    n2 = cache.get("N", "foo")
    assert n2.unique == n1.unique + 1
def test_cache_builtin_unique():
    cache = NameCache(Uniq(START_UNIQ))
    n = cache.get("builtins", "Bool")
    assert n.unique == BUILTIN_BOOL.unique
def test_cache_builtin_stable():
    cache = NameCache(Uniq(START_UNIQ))
    n1 = cache.get("builtins", "Int")
    n2 = cache.get("builtins", "Int")
    assert n1.unique == n2.unique
def test_cache_multiple_calls():
    cache = NameCache(Uniq(START_UNIQ))
    n1 = cache.get("M", "a")
    n2 = cache.get("M", "b")
    n3 = cache.get("M", "a")
    n4 = cache.get("N", "a")
    assert n3.unique == n1.unique
    assert n2.unique == n1.unique + 1
    assert n4.unique == n2.unique + 1
def test_name_in_type_zonked():
    cache = NameCache(Uniq(START_UNIQ))
    list_name = cache.get("builtins", "List")
    m = MetaTv(uniq=999, ref=Ref(TyInt()))
    list_ty = TyConApp(name=list_name, args=[m])
    result = zonk_type(list_ty)
    expected = TyConApp(name=list_name, args=[TyInt()])
    assert result == expected
