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
from systemf.elab3.name_gen import NameCache
from systemf.elab3.builtins import BUILTIN_BOOL, BUILTIN_LIST


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
def test_cache_builtin_lookup():
    cache = NameCache()
    n = cache.get("builtins", "Bool")
    assert n == BUILTIN_BOOL
def test_cache_unknown_returns_none():
    cache = NameCache()
    n = cache.get("M", "foo")
    assert n is None
def test_cache_put_and_get():
    cache = NameCache()
    name = Name(mod="M", surface="foo", unique=9999)
    cache.put(name)
    assert cache.get("M", "foo") == name
def test_cache_put_all():
    cache = NameCache()
    names = [
        Name(mod="M", surface="a", unique=9001),
        Name(mod="M", surface="b", unique=9002),
    ]
    cache.put_all(names)
    assert cache.get("M", "a") == names[0]
    assert cache.get("M", "b") == names[1]
def test_cache_builtin_prepopulated_all():
    cache = NameCache()
    assert cache.get("builtins", "Bool") is not None
    assert cache.get("builtins", "List") is not None
    assert cache.get("builtins", "Cons") is not None
def test_name_in_type_zonked():
    list_name = BUILTIN_LIST
    m = MetaTv(uniq=999, ref=Ref(TyInt()))
    list_ty = TyConApp(name=list_name, args=[m])
    result = zonk_type(list_ty)
    expected = TyConApp(name=list_name, args=[TyInt()])
    assert result == expected
