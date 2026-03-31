"""Tests for zonk_type and NameCache - core elab3 infrastructure."""

from systemf.elab3.types import (
    BoundTv, MetaTv, Ref, TyConApp, TyForall, TyFun, TyInt, TyString, zonk_type
)
from systemf.elab3.mod import NameCache
from systemf.elab3.builtins import BUILTIN_BOOL
from systemf.utils.uniq import Uniq


# =============================================================================
# zonk_type tests
# =============================================================================


def test_zonk_unbound_meta():
    """Unbound meta type variable returns itself."""
    m = MetaTv(uniq=1, ref=Ref(None))
    result = zonk_type(m)
    # Identity check: unbound meta should return the exact same object
    assert result is m


def test_zonk_bound_meta():
    """Bound meta returns its solution."""
    m = MetaTv(uniq=1, ref=Ref(TyInt()))
    result = zonk_type(m)
    assert result == TyInt()


def test_zonk_meta_chain():
    """Chain of metas resolves to final solution."""
    # m3 -> Int, m2 -> m3, m1 -> m2
    m3 = MetaTv(uniq=3, ref=Ref(TyInt()))
    m2 = MetaTv(uniq=2, ref=Ref(m3))
    m1 = MetaTv(uniq=1, ref=Ref(m2))
    
    result = zonk_type(m1)
    assert result == TyInt()


def test_zonk_path_compression():
    """zonk_type resolves chains correctly."""
    # m2 -> Int, m1 -> m2
    m2 = MetaTv(uniq=2, ref=Ref(TyInt()))
    m1 = MetaTv(uniq=1, ref=Ref(m2))
    
    # Just test the behavior - zonk returns correct result
    result = zonk_type(m1)
    assert result == TyInt()


def test_zonk_function_type():
    """Function type with meta vars gets recursively zonked."""
    m = MetaTv(uniq=1, ref=Ref(TyInt()))
    fun = TyFun(m, TyString())
    
    result = zonk_type(fun)
    assert result == TyFun(TyInt(), TyString())


def test_zonk_forall():
    """Forall with meta vars in body gets zonked."""
    m = MetaTv(uniq=1, ref=Ref(TyInt()))
    a = BoundTv(name="a")
    forall_ty = TyForall(vars=[a], body=m)
    
    result = zonk_type(forall_ty)
    expected = TyForall(vars=[a], body=TyInt())
    assert result == expected


def test_zonk_nested_fun():
    """Nested function types are fully zonked."""
    m1 = MetaTv(uniq=1, ref=Ref(TyInt()))
    m2 = MetaTv(uniq=2, ref=Ref(TyString()))
    nested = TyFun(TyFun(m1, m2), m1)
    
    result = zonk_type(nested)
    expected = TyFun(TyFun(TyInt(), TyString()), TyInt())
    assert result == expected


def test_zonk_tycon_app():
    """Type constructor application with meta args gets zonked."""
    from systemf.elab3.types import Name
    
    # List m where m -> Int
    list_name = Name(mod="builtins", surface="List", unique=4)
    m = MetaTv(uniq=1, ref=Ref(TyInt()))
    list_ty = TyConApp(name=list_name, args=[m])
    
    result = zonk_type(list_ty)
    expected = TyConApp(name=list_name, args=[TyInt()])
    assert result == expected


# =============================================================================
# NameCache tests
# =============================================================================


START_UNIQ = 1000


def test_cache_allocates_new_unique():
    """First call allocates a new unique."""
    cache = NameCache(Uniq(START_UNIQ))
    name = cache.get("M", "foo")
    
    assert name.mod == "M"
    assert name.surface == "foo"
    assert name.unique >= START_UNIQ


def test_cache_stable_allocation():
    """Same (module, surface) returns same Name."""
    cache = NameCache(Uniq(START_UNIQ))
    n1 = cache.get("M", "foo")
    n2 = cache.get("M", "foo")
    
    assert n1.unique == n2.unique


def test_cache_different_surface():
    """Different surface name gets different unique."""
    cache = NameCache(Uniq(START_UNIQ))
    n1 = cache.get("M", "foo")
    n2 = cache.get("M", "bar")
    
    # Sequential allocation
    assert n2.unique == n1.unique + 1


def test_cache_different_module():
    """Different module gets different unique."""
    cache = NameCache(Uniq(START_UNIQ))
    n1 = cache.get("M", "foo")
    n2 = cache.get("N", "foo")
    
    # Sequential allocation
    assert n2.unique == n1.unique + 1


def test_cache_builtin_unique():
    """Builtin names get predefined uniques."""
    cache = NameCache(Uniq(START_UNIQ))
    n = cache.get("builtins", "Bool")
    
    assert n.unique == BUILTIN_BOOL.unique


def test_cache_builtin_stable():
    """Builtin names are stable like others."""
    cache = NameCache(Uniq(START_UNIQ))
    n1 = cache.get("builtins", "Int")
    n2 = cache.get("builtins", "Int")
    
    assert n1.unique == n2.unique


def test_cache_multiple_calls():
    """Multiple calls interleaved work correctly."""
    cache = NameCache(Uniq(START_UNIQ))
    
    n1 = cache.get("M", "a")
    n2 = cache.get("M", "b")
    n3 = cache.get("M", "a")  # Should return n1
    n4 = cache.get("N", "a")
    
    # n3 should have same unique as n1 (cached)
    assert n3.unique == n1.unique
    # Sequential allocation for new names
    assert n2.unique == n1.unique + 1
    assert n4.unique == n2.unique + 1


# =============================================================================
# Integration: NameCache + zonk_type
# =============================================================================


def test_name_in_type_zonked():
    """Type containing Name from cache can be zonked."""
    cache = NameCache(Uniq(START_UNIQ))
    list_name = cache.get("builtins", "List")
    
    m = MetaTv(uniq=999, ref=Ref(TyInt()))
    list_ty = TyConApp(name=list_name, args=[m])
    
    result = zonk_type(list_ty)
    expected = TyConApp(name=list_name, args=[TyInt()])
    assert result == expected
