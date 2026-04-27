"""Pretty printer for TyThing type environment entries.

Produces source-accurate syntax matching the parser grammar:

    prim_op name :: forall a. a -- ^ arg doc
        -> a -- ^ result doc
    name :: Type
    prim_type name a b c
    data Name a b c
        = Con x -- ^ doc for x
            y z
        | Con2

Docstrings: split on newline, one ``-- |`` per line.
Arg docs: inline ``-- ^`` after each argument, multi-line with indented ``->``.
Every line ends with a newline.
"""

from .types.ty import Ty, TyForall, TyFun, TyVar, _ty_repr
from .types.tything import ACon, APrimTy, ATyCon, AnId, Metas, TyThing


def _ty_str(ty: Ty) -> str:
    return _ty_repr(ty, 0)


def _ty_str_arg(ty: Ty) -> str:
    return _ty_repr(ty, 2)


def _peel_forall(ty: Ty) -> tuple[list[list[str]], Ty]:
    varss: list[list[str]] = []
    rest = ty
    while isinstance(rest, TyForall):
        varss.append([_ty_repr(v, 0) for v in rest.vars])
        rest = rest.body
    return varss, rest


def _peel_fun(ty: Ty) -> tuple[list[Ty], Ty]:
    args: list[Ty] = []
    rest = ty
    while isinstance(rest, TyFun):
        args.append(rest.arg)
        rest = rest.result
    return args, rest


def _pp_pragma_lines(metas: Metas | None) -> list[str]:
    if metas is None or not metas.pragma:
        return []
    return [f"{{-# {k} {v} #-}}" for k, v in metas.pragma.items()]


def _pp_doc_lines(doc: str | None) -> list[str]:
    if not doc:
        return []
    return [f"-- | {line}" for line in doc.split("\n")]


def _has_arg_docs(metas: Metas | None) -> bool:
    return metas is not None and any(d is not None for d in metas.arg_docs)


def _forall_prefix(varss: list[list[str]]) -> str:
    if not varss:
        return ""
    parts = " ".join(v for vs in varss for v in vs)
    return f"forall {parts}. "


# =============================================================================
# Public API
# =============================================================================


def pp_tything(thing: TyThing) -> str:
    match thing:
        case AnId(name=name, id=id, is_prim=is_prim, metas=metas):
            return _pp_binding(name.surface, id.ty, is_prim, metas)
        case ATyCon(name=name, tyvars=tyvars, constructors=cons):
            return _pp_data(name.surface, tyvars, cons)
        case ACon(name=name, field_types=fields):
            return _pp_acon(name.surface, fields)
        case APrimTy(name=name, tyvars=tyvars):
            return _pp_prim_type(name.surface, tyvars)
        case _:
            return f"<unknown TyThing: {type(thing).__name__}>\n"


# =============================================================================
# Private helpers
# =============================================================================


def _pp_binding(name: str, ty: Ty, is_prim: bool, metas: Metas | None) -> str:
    lines: list[str] = []
    lines.extend(_pp_doc_lines(metas.doc if metas else None))
    lines.extend(_pp_pragma_lines(metas))

    kw = "prim_op " if is_prim else ""
    prefix = f"{kw}{name} :: "

    varss, body = _peel_forall(ty)
    forall_str = _forall_prefix(varss)
    args, result = _peel_fun(body)

    arg_docs = (metas.arg_docs if metas else None) or []
    all_tys = args + [result]

    if not _has_arg_docs(metas):
        lines.append(f"{prefix}{_ty_str(ty)}")
    else:
        first_ty, *rest_tys = all_tys
        first_doc = arg_docs[0] if arg_docs else None
        first_s = _ty_str_arg(first_ty)
        first_doc_s = f" -- ^ {first_doc}" if first_doc else ""
        lines.append(f"{prefix}{forall_str}{first_s}{first_doc_s}")

        for i, arg_ty in enumerate(rest_tys, start=1):
            doc = arg_docs[i] if i < len(arg_docs) else None
            arg_s = _ty_str_arg(arg_ty)
            doc_s = f" -- ^ {doc}" if doc else ""
            lines.append(f"    -> {arg_s}{doc_s}")

    return "\n".join(lines) + "\n"


def _pp_data(name: str, tyvars: list[TyVar], constructors: list[ACon]) -> str:
    var_str = " ".join(_ty_repr(v, 0) for v in tyvars) if tyvars else ""
    header = f"data {name}"
    if var_str:
        header += f" {var_str}"

    if not constructors:
        return header + "\n"

    lines: list[str] = [header]
    if constructors:
        lines.append(f"    = {_pp_acon_inline(constructors[0])}")
        for con in constructors[1:]:
            lines.append(f"    | {_pp_acon_inline(con)}")

    return "\n".join(lines) + "\n"


def _pp_acon_inline(con: ACon) -> str:
    """Format a data constructor and its fields on one line."""
    parts = [con.name.surface]
    for ft in con.field_types:
        parts.append(_ty_str_arg(ft))
    return " ".join(parts)


def _pp_acon(name: str, fields: list[Ty]) -> str:
    parts = [name]
    for f in fields:
        parts.append(_ty_str_arg(f))
    return " ".join(parts) + "\n"


def _pp_prim_type(name: str, tyvars: list[TyVar]) -> str:
    var_str = " ".join(_ty_repr(v, 0) for v in tyvars) if tyvars else ""
    if var_str:
        return f"prim_type {name} {var_str}\n"
    return f"prim_type {name}\n"
