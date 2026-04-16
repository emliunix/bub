"""
Core language AST for systemf elaborator (elab3).

Self-contained — imports only from elab3.types.
Core terms use Id (Name + Type) for all variable references.
"""

from abc import ABC
from dataclasses import dataclass
from typing import cast

from .ty import Id, Lit, Name, Ty, TyVar, zonk_type


# =============================================================================
# Core Terms
# =============================================================================


class CoreTm(ABC):
    """Base class for core language terms."""
    pass


@dataclass
class CoreLit(CoreTm):
    """Literal value."""
    value: Lit


@dataclass
class CoreVar(CoreTm):
    """Local variable reference (lambda param, let-bound)."""
    id: Id


@dataclass
class CoreGlobalVar(CoreTm):
    """Top-level / module-level variable reference.

    Unlike CoreVar (local), a global var is defined at module scope and
    resolved via the module's type/value environment. Not substituted by
    local let/lambda binders.
    """
    id: Id


@dataclass
class CoreLam(CoreTm):
    """Lambda abstraction."""
    param: Id
    body: CoreTm


@dataclass
class CoreApp(CoreTm):
    """Function application."""
    fun: CoreTm
    arg: CoreTm


@dataclass
class CoreTyLam(CoreTm):
    """Type abstraction (polymorphic lambda)."""
    var: TyVar
    body: CoreTm


@dataclass
class CoreTyApp(CoreTm):
    """Type application (explicit instantiation)."""
    fun: CoreTm
    tyarg: Ty


# =============================================================================
# Bindings
# =============================================================================


@dataclass
class Binding:
    """Base class for bindings."""
    pass


@dataclass
class NonRec(Binding):
    """Non-recursive binding: let x = expr in body"""
    binder: Id
    expr: CoreTm


@dataclass
class Rec(Binding):
    """Recursive bindings: letrec { x = e1; y = e2 } in body

    All names are in scope for all expressions (mutual recursion).
    """
    bindings: list[tuple[Id, CoreTm]]


@dataclass
class CoreLet(CoreTm):
    """Let binding with NonRec or Rec."""
    binding: Binding
    body: CoreTm


# =============================================================================
# patterns
# =============================================================================


@dataclass
class CoreCase(CoreTm):
    scrut: CoreTm
    var: Id
    res_ty: Ty
    alts: list[tuple[Alt, CoreTm]]


@dataclass
class DataAlt:
    con: Name
    vars: list[Id]


@dataclass
class LitAlt:
    lit: Lit


@dataclass
class DefaultAlt:
    pass


type Alt = DataAlt | LitAlt | DefaultAlt


# =============================================================================
# Core Term Builder
# =============================================================================


class CoreBuilder:
    """Builder for constructing core terms."""

    def lit(self, value: Lit) -> CoreTm:
        return CoreLit(value)

    def var(self, id: Id) -> CoreTm:
        return CoreVar(Id(id.name, zonk_type(id.ty)))

    def lam(self, param: Id, body: CoreTm) -> CoreTm:
        return CoreLam(Id(param.name, zonk_type(param.ty)), body)

    def app(self, fun: CoreTm, arg: CoreTm) -> CoreTm:
        return CoreApp(fun, arg)

    def tylam(self, var: TyVar, body: CoreTm) -> CoreTm:
        return CoreTyLam(var, body)

    def tyapp(self, fun: CoreTm, tyarg: Ty) -> CoreTm:
        return CoreTyApp(fun, zonk_type(tyarg))

    def let(self, binder: Id, expr: CoreTm, body: CoreTm) -> CoreTm:
        return CoreLet(NonRec(binder, expr), body)

    def letrec(self, bindings: list[tuple[Id, CoreTm]], body: CoreTm) -> CoreTm:
        return CoreLet(Rec(bindings), body)

    def case_lit(self, scrut: CoreTm, v: Id, res_ty: Ty,
                 alts: list[tuple[Lit, CoreTm]], default: CoreTm | None) -> CoreTm:
        alts_ = [(cast(Alt, LitAlt(lit)), rhs)for lit, rhs in alts]
        if default is not None:
            alts_.append((DefaultAlt(), default))
        return CoreCase(scrut, v, res_ty, alts_)

    def case_data(self, scrut: CoreTm, v: Id, res_ty: Ty,
                  alts: list[tuple[Name, list[Id], CoreTm]], default: CoreTm | None) -> CoreTm:
        alts_ = [(cast(Alt, DataAlt(con, vars)), rhs) for con, vars, rhs in alts]
        if default is not None:
            alts_.append((DefaultAlt(), default))
        return CoreCase(scrut, v, res_ty, alts_)

    def subst(self, substs: dict[Id, CoreTm], expr: CoreTm) -> CoreTm:
        return subst_coretm(substs, expr)


def subst_coretm(substs: dict[Id, CoreTm], expr: CoreTm) -> CoreTm:
    """Substitute variable named `target` with `replacement` in `expr`."""
    match expr:
        case CoreVar(id) if id in substs:
            return substs[id]
        case CoreTyApp(fun, ty_arg):
            return CoreTyApp(subst_coretm(substs, fun), ty_arg)
        case CoreTyLam(var, body):
            return CoreTyLam(var, subst_coretm(substs, body))
        case CoreLam(param, body):
            substs_ = shift_substs(substs, [param])
            if len(substs_) > 0:
                return CoreLam(param, subst_coretm(substs_, body))
            else:
                return expr
        case CoreApp(fun, arg):
            return CoreApp(
                subst_coretm(substs, fun),
                subst_coretm(substs, arg),
            )
        case CoreLet(NonRec(binder, expr), body):
            expr_ = subst_coretm(substs, expr)
            substs_ = shift_substs(substs, [binder])
            if len(substs_) > 0:
                return CoreLet(NonRec(binder, expr_), subst_coretm(substs_, body))
            else:
                return CoreLet(NonRec(binder, expr_), body)
        case CoreLet(Rec(bindings), body):
            substs_ = shift_substs(substs, [b for b, _ in bindings])
            if len(substs_) > 0:
                bindings_ = [(b, subst_coretm(substs, e)) for b, e in bindings]
                body_ = subst_coretm(substs, body)
                return CoreLet(Rec(bindings_), body_)
            else:
                return expr
        case CoreCase(scrut, var, res_ty, alts):
            return CoreCase(
                subst_coretm(substs, scrut),
                var,
                res_ty,
                [(alt, _subst_alt(substs, var, alt, tm)) for alt, tm in alts]
            )
        case CoreLit() | CoreTm():
            return expr


def _subst_alt(substs: dict[Id, CoreTm], scrut_var: Id, alt: Alt, tm: CoreTm) -> CoreTm:
    substs1 = shift_substs(substs, [scrut_var])
    match alt:
        case DataAlt(_, vars):
            substs2 = shift_substs(substs1, vars)
            if len(substs2) > 0:
                return subst_coretm(substs2, tm)
            else:
                return tm
        case LitAlt() | DefaultAlt():
            return subst_coretm(substs1, tm)


def shift_substs(substs: dict[Id, CoreTm], ids: list[Id]) -> dict[Id, CoreTm]:
    id_set = set(ids)
    return {k: v for k, v in substs.items() if k not in id_set}


C = CoreBuilder()
