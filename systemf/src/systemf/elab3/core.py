"""
Core language AST for systemf elaborator (elab3).

Self-contained — imports only from elab3.types.
Core terms use Id (Name + Type) for all variable references.
"""

from dataclasses import dataclass
from typing import Any

from systemf.elab3.types import Id, Lit, Name, Ty, TyVar, zonk_type


# =============================================================================
# Core Terms
# =============================================================================


@dataclass
class CoreTm:
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

    def subst(self, target: Name, replacement: CoreTm, expr: CoreTm) -> CoreTm:
        return subst_coretm(target, replacement, expr)


def subst_coretm(target: Name, replacement: CoreTm, expr: CoreTm) -> CoreTm:
    """Substitute variable named `target` with `replacement` in `expr`."""
    match expr:
        case CoreVar(id) if id.name == target:
            return replacement
        case CoreTyApp(fun, ty_arg):
            return CoreTyApp(subst_coretm(target, replacement, fun), ty_arg)
        case CoreTyLam(var, body):
            return CoreTyLam(var, subst_coretm(target, replacement, body))
        case CoreLam(param, body) if param.name == target:
            return expr
        case CoreLam(param, body):
            return CoreLam(param, subst_coretm(target, replacement, body))
        case CoreApp(fun, arg):
            return CoreApp(
                subst_coretm(target, replacement, fun),
                subst_coretm(target, replacement, arg),
            )
        case CoreLet(NonRec(binder, inner_expr), body):
            new_expr = subst_coretm(target, replacement, inner_expr)
            if binder.name == target:
                return CoreLet(NonRec(binder, new_expr), body)
            return CoreLet(NonRec(binder, new_expr), subst_coretm(target, replacement, body))
        case CoreLet(Rec(bindings), body):
            bound_names = {b.name for b, _ in bindings}
            if target in bound_names:
                return expr
            new_bindings = [(b, subst_coretm(target, replacement, e)) for b, e in bindings]
            return CoreLet(Rec(new_bindings), subst_coretm(target, replacement, body))
        case _:
            return expr


C = CoreBuilder()
