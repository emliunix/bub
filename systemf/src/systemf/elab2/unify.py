from systemf.elab2.types import *

def unify(ty1: Ty, ty2: Ty):
    match ty1, ty2:
        case (BoundTv(), _) | (_, BoundTv()):
            raise TypeError(f"Unexpected bound type variables to unify, got {ty1} and {ty2}")
        case (SkolemTv() as sk1, SkolemTv() as sk2) if sk1 == sk2:
            pass
        case (MetaTv() as m1, MetaTv() as m2) if m1 == m2:
            pass
        case (TyCon() as tc1, TyCon() as tc2) if tc1 == tc2:
            pass
        case (MetaTv() as m, ty):
            unify_var(m, ty)
        case (ty, MetaTv() as m):
            unify_var(m, ty)
        case TyFun(a1, r1), TyFun(a2, r2):
            # that means on construction, fun type are probed and
            # fun of metas created instead of a single meta
            unify(a1, a2)
            unify(r1, r2)
        case _:
            raise TypeError(f"Cannot unify types, got {ty1} and {ty2}")

def unify_var(m: MetaTv, ty: Ty):
    """
    unify meta var to other type
    """
    match m:
        case MetaTv(ref=Ref(inner=inner)) if inner:
            # unwrap left
            unify(inner, ty)
        case MetaTv(ref=Ref(inner=None)):
            # bind right
            unify_unbound_var(m, ty)

def unify_unbound_var(m: MetaTv, ty: Ty):
    """
    unify unbound meta var to other type
    """
    match ty:
        case MetaTv(ref=Ref(inner=inner)) if inner:
            # unwrap right
            unify(m, inner)
        case MetaTv(ref=Ref(inner=None)):
            # bind left to right
            # that's the most we can do now, connects to un-unified metas
            m.ref.set(ty)
        case _:
            if m in get_meta_vars([ty]):
                raise TypeError(f"Occurrence check failed: got {m} in {ty}")
            m.ref.set(ty)
