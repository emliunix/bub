
from .types.protocols import TyLookup
from .types.ty import Ty, TyConApp, subst_ty
from .types.val import Val, Trap, VPartial, VData, VClosure, VLit
from .core_extra import lookup_data_con_by_tag


def pp_val(ctx: TyLookup, val: Val, ty: Ty) -> str:
    """Pretty print a value using the evaluator's machinery."""
    def _pp(val: Val, ty: Ty) -> str:
        match ty, val:
            case TyConApp(name=con, args=arg_tys), VData(tag=tag, vals=args):
                tycon, dcon, _ = lookup_data_con_by_tag(ctx, con, tag)
                dcon_field_tys = [subst_ty(tycon.tyvars, arg_tys, ty) for ty in dcon.field_types]
                vals_str = " ".join(_pp(arg, ty) for ty, arg in zip(dcon_field_tys, args))
                return f"{dcon.name.surface} {vals_str}".strip()
            case _, VLit(lit=lit):
                return f"{lit.v!r}"
            case _, VPartial(name=name, arity=arity):
                return f"<func {name} {arity}>"
            case _, VClosure():
                return "<closure>"
            case _, Trap(v=None):
                return "<unfilled trap>"
            case _, Trap(v=v) if v is not None:
                return _pp(v, ty)
            case _, _: return "<unknown>"
    return f"{_pp(val, ty)} :: {ty}"
