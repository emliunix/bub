"""
Core types for the systemf elaborator (elab3).

Self-contained — no imports from elab2 or core packages.

Design:
- Name: globally unique identifier (from NameCache)
- Id: Name + Type (like GHC's Id), used in Core
- Ty: type hierarchy with TyConApp using Name
- Lit: runtime literal values
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar, override

from systemf.utils.location import Location

T = TypeVar("T")


# =============================================================================
# Mutable reference (for MetaTv unification)
# =============================================================================


@dataclass
class Ref(Generic[T]):
    """Mutable reference cell."""
    inner: T | None = field(default=None)

    def set(self, value: T) -> None:
        self.inner = value

    def get(self) -> T | None:
        return self.inner


# =============================================================================
# Name
# =============================================================================


@dataclass(frozen=True)
class Name:
    """Globally unique identifier. Uses unique field for O(1) equality.

    Like GHC's Name: human-readable surface form + globally unique ID +
    defining module provenance.
    """
    mod: str
    surface: str
    unique: int
    loc: Location | None = None


# =============================================================================
# Id (Name + Type)
# =============================================================================


@dataclass(frozen=True)
class Id:
    """Term-level variable: Name + Type.

    Like GHC's Id (Var with Id constructor). Used in renamed and core terms
    wherever a variable reference carries both identity and type information.
    """
    name: Name
    ty: Ty


# =============================================================================
# Type hierarchy
# =============================================================================


@dataclass(frozen=True, repr=False)
class Ty:
    """Base for all types."""
    @override
    def __repr__(self) -> str:
        return _ty_repr(self, 0)


@dataclass(frozen=True, repr=False)
class TyLit(Ty):
    pass


@dataclass(frozen=True, repr=False)
class TyInt(TyLit):
    pass


@dataclass(frozen=True, repr=False)
class TyString(TyLit):
    pass


@dataclass(frozen=True, repr=False)
class TyPrim(Ty):
    name: str


@dataclass(frozen=True, repr=False)
class TyVar(Ty):
    """Base for type variables."""
    pass


@dataclass(frozen=True, repr=False)
class BoundTv(TyVar):
    """Bound type variable (local binder in forall/tylam).

    Like GHC's TyVar with Internal NameSort. Stays as str — bound type vars
    don't need global identity.
    """
    name: Name


@dataclass(frozen=True, repr=False)
class SkolemTv(TyVar):
    """Skolem type variable (from type signature instantiation).

    Like GHC's TyVar with skolem details — rigid type variable introduced
    during polymorphic type checking.
    """
    name: Name


@dataclass(frozen=True, repr=False)
class MetaTv(Ty):
    """Meta type variable (unification variable).

    Like GHC's TcTyVar — exists only during type inference, gets solved
    (zonked) away before entering core terms.
    """
    uniq: int
    ref: Ref[Ty] | None


@dataclass(frozen=True, repr=False)
class TyConApp(Ty):
    """Type constructor application: T arg1 arg2 ...

    Like GHC's TyConApp constructor of Type. The head is a Name (resolved
    type constructor), args are a flat list of types.

    Invariant (from GHC): the arg list may be undersaturated but never
    oversaturated.
    """
    name: Name
    args: list[Ty] = field(default_factory=list, compare=True, hash=False)


@dataclass(frozen=True, repr=False)
class TyFun(Ty):
    """Function type: arg -> result."""
    arg: Ty
    result: Ty


@dataclass(frozen=True, repr=False)
class TyForall(Ty):
    """Universally quantified type: forall a b. body."""
    vars: list[TyVar]
    body: Ty


# =============================================================================
# Runtime literals
# =============================================================================


class Lit:
    """Base for runtime literal values."""
    pass


@dataclass(frozen=True)
class LitInt(Lit):
    """Integer literal."""
    value: int


@dataclass(frozen=True)
class LitString(Lit):
    """String literal."""
    value: str


# =============================================================================
# Type utilities
# =============================================================================


def zonk_type(ty: Ty) -> Ty:
    """Resolve all meta variables to their solutions."""
    match ty:
        case TyVar() | TyLit() | TyPrim():
            return ty
        case TyConApp(name, args):
            return TyConApp(name, [zonk_type(a) for a in args])
        case TyFun():
            return TyFun(zonk_type(ty.arg), zonk_type(ty.result))
        case TyForall():
            return TyForall(ty.vars, zonk_type(ty.body))
        case MetaTv(ref=ref) if ref is not None and ref.inner is not None:
            solved = zonk_type(ref.inner)
            ref.set(solved)
            return solved
        case MetaTv():
            return ty
        case _:
            raise ValueError(f"Unknown type: {ty}")


def _ty_repr(ty: Ty, prec: int) -> str:
    def _show() -> tuple[int, str]:
        match ty:
            case TyInt():
                return 3, "Int"
            case TyString():
                return 3, "String"
            case TyPrim(name=name):
                return 3, name
            case BoundTv(name=name):
                return 1, name.surface
            case SkolemTv(name=name):
                return 1, f"${name.unique}_{name.surface}"
            case TyConApp(name=name, args=args):
                if not args:
                    return 1, name.surface
                args_str = " ".join(_ty_repr(a, 2) for a in args)
                return 2, f"{name.surface} {args_str}"
            case TyFun(arg=arg, result=res):
                return 1, f"{_ty_repr(arg, 1)} -> {_ty_repr(res, 0)}"
            case TyForall(vars=vars, body=body):
                var_strs = " ".join(
                    v.name.surface for v in vars if isinstance(v, (BoundTv, SkolemTv))
                )
                return 0, f"forall {var_strs}. {_ty_repr(body, 0)}"
            case MetaTv(uniq=uniq):
                return 1, f"?{uniq}"
            case _:
                raise TypeError(f"Unexpected type in repr: {type(ty)}")

    p, s = _show()
    if p < prec:
        return f"({s})"
    return s
