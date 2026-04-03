from __future__ import annotations

from systemf.elab3.types.ty import (
    BoundTv, Id, LitInt, LitString, MetaTv, Name, Ref,
    TyConApp, TyForall, TyFun, TyInt, TyString, TyVar, zonk_type,
)
from systemf.elab3.types.tything import AnId, ATyCon, ACon, TyThing
from systemf.elab3.types.core import CoreLet, CoreLit, CoreTm, CoreVar, NonRec, Rec
from systemf.elab3.builtins import BUILTIN_BOOL


def mk_name(surface: str, mod: str, unique: int) -> Name:
    return Name(mod=mod, surface=surface, unique=unique)


def mk_id(surface: str, mod: str, unique: int, ty: TyInt | TyVar = TyInt()) -> Id:
    return Id(name=mk_name(surface, mod, unique), ty=ty)


def test_anid_creation():
    name = mk_name("id", "Test", 1)
    ty = TyInt()
    anid = AnId(name=name, type=ty)
    assert anid.name == name
    assert anid.type == ty


def test_atycon_creation():
    name = mk_name("Bool", "Builtin", 2)
    tycon = ATyCon(name=name, tyvars=[], constructors=[])
    assert tycon.name == name
    assert tycon.tyvars == []
    assert tycon.constructors == []


def test_acon_creation():
    parent = mk_name("List", "Builtin", 4)
    con_name = mk_name("Cons", "Builtin", 100)
    acon = ACon(
        name=con_name,
        tag=0,
        arity=2,
        field_types=[],
        parent=parent,
    )
    assert acon.parent == parent
    assert acon.tag == 0
    assert acon.arity == 2


def test_corelet_nonrec():
    x_id = mk_id("x", "Test", 1)
    body = CoreVar(id=x_id)
    expr = CoreLit(value=LitInt(value=42))
    let_expr = CoreLet(binding=NonRec(binder=x_id, expr=expr), body=body)
    assert isinstance(let_expr.binding, NonRec)
    assert let_expr.binding.binder == x_id


def test_corelet_rec():
    x_id = mk_id("x", "Test", 1)
    y_id = mk_id("y", "Test", 2)
    body = CoreVar(id=x_id)
    bindings: list[tuple[Id, CoreTm]] = [
        (x_id, CoreLit(value=LitInt(value=1))),
        (y_id, CoreLit(value=LitInt(value=2))),
    ]
    let_expr = CoreLet(binding=Rec(bindings=bindings), body=body)
    assert isinstance(let_expr.binding, Rec)
    assert len(let_expr.binding.bindings) == 2