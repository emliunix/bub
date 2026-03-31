from systemf.elab2.types import BoundTv
from systemf.elab3.types import Name, TyThing, AnId, ATyCon, ACon
from systemf.elab3.core import CoreLit, CoreVar, CoreLam, CoreApp, NonRec, Rec, CoreLet

# ---
# test Name

def test_name_equality_by_unique():
    """Names with same unique are equal regardless of other fields."""
    n1 = Name("foo", 42, "ModuleA")
    n2 = Name("bar", 42, "ModuleB")  # Different surface and module, same unique
    n3 = Name("foo", 43, "ModuleA")  # Same surface and module, different unique
    
    assert n1 == n2
    assert n1 != n3
    assert hash(n1) == hash(n2)

def test_name_hash_by_unique():
    """Name hash is based on unique field."""
    n1 = Name("x", 1, "M")
    n2 = Name("y", 1, "N")
    
    assert hash(n1) == hash(n2)

# ---
# test TyThing

def test_anid_creation():
    """AnId carries name, term, and type scheme."""
    name = Name("id", 1, "Test")
    term = CoreLit(None)  # Dummy term
    ty = None  # Would be a proper type
    
    anid = AnId(name, term, ty)
    assert anid.name == name
    assert anid.term == term

def test_atycon_creation():
    """ATyCon carries name, tyvars, and constructors."""
    name = Name("Bool", 2, "Builtin")
    tycon = ATyCon(name, [], [])  # No type params, no constructors
    
    assert tycon.name == name
    assert tycon.tyvars == []
    assert tycon.constructors == []

# ---
# test ACon

def test_acon_creation():
    """ACon links constructor to parent type with field types."""
    parent = Name("List", 4, "Builtin")
    con_name = Name("Cons", 100, "Builtin")
    
    acon = ACon(
        name=con_name,
        tag=0,
        arity=2,
        field_types=[],  # Would contain element type and List type
        parent=parent
    )
    
    assert acon.parent == parent
    assert acon.tag == 0
    assert acon.arity == 2

# ---
# test CoreLet with bindings

def test_corelet_nonrec():
    """NonRec binding in let."""
    body = CoreVar("x", None)
    expr = CoreLit(None)
    let_expr = CoreLet(NonRec("x", expr), body)
    
    assert isinstance(let_expr.binding, NonRec)
    assert let_expr.binding.name == "x"

def test_corelet_rec():
    """Rec binding in let with mutual recursion."""
    body = CoreVar("x", None)
    bindings = [
        ("x", CoreLit(None)),
        ("y", CoreLit(None)),
    ]
    let_expr = CoreLet(Rec(bindings), body)
    
    assert isinstance(let_expr.binding, Rec)
    assert len(let_expr.binding.bindings) == 2
