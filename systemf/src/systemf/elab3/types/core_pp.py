"""
Pretty printer for core language terms.

Indent-aware, uses core-specific syntax (not surface syntax).
"""
from .core import (
    CoreApp,
    CoreCase,
    CoreGlobalVar,
    CoreLam,
    CoreLet,
    CoreLit,
    CoreTm,
    CoreTyApp,
    CoreTyLam,
    CoreVar,
    DataAlt,
    DefaultAlt,
    LitAlt,
    NonRec,
    Rec,
)
from .ty import Ty, TyInt, TyString


def _ty_str(ty: Ty) -> str:
    """Get string representation of a type (public wrapper)."""
    from .ty import _ty_repr
    return _ty_repr(ty, 0)


def pp_core(tm: CoreTm, *, width: int = 2) -> str:
    """Pretty-print a core term with indentation."""
    return "\n".join(_pp(tm, 0, width))


def _pp(tm: CoreTm, depth: int, width: int) -> list[str]:
    """Return lines for the term at given indent depth."""
    ind = " " * (depth * width)

    match tm:
        case CoreLit(value):
            return [f"{ind}{value.v!r}"]

        case CoreVar(id) | CoreGlobalVar(id):
            return [f"{ind}{id.name.surface}"]

        case CoreLam(param, body):
            ty_str = _ty_str(param.ty)
            return [
                f"{ind}\\{param.name.surface} :: {ty_str} ->",
                *_pp(body, depth + 1, width),
            ]

        case CoreTyLam(var, body):
            return [
                f"{ind}/\\{_ty_str(var)}.",
                *_pp(body, depth + 1, width),
            ]

        case CoreApp(fun, arg):
            fun_lines = _pp(fun, depth, width)
            arg_lines = _pp_atom(arg, depth + 1, width)
            return [_join_app(fun_lines, arg_lines)]

        case CoreTyApp(fun, tyarg):
            fun_lines = _pp(fun, depth, width)
            ty_str = _ty_str(tyarg)
            return [_join_tyapp(fun_lines, ty_str)]

        case CoreLet(NonRec(binder, expr), body):
            return [
                f"{ind}let {binder.name.surface} =",
                *_pp(expr, depth + 1, width),
                f"{ind}in",
                *_pp(body, depth + 1, width),
            ]

        case CoreLet(Rec(bindings), body):
            lines = [f"{ind}letrec"]
            for b, e in bindings:
                lines.append(f"{ind}{' ' * width}{b.name.surface} =")
                lines.extend(_pp(e, depth + 2, width))
            lines.append(f"{ind}in")
            lines.extend(_pp(body, depth + 1, width))
            return lines

        case CoreCase(scrut, var, res_ty, alts):
            inner_ind = ind + (" " * width)
            lines = [
                f"{ind}case {scrut_id(scrut)} of   -- {var.name.surface} :: {_ty_str(res_ty)}",
            ]
            for i, (alt, rhs) in enumerate(alts):
                sep = "|" if i > 0 else "{"
                alt_str = _pp_alt(alt)
                rhs_lines = _pp(rhs, depth + 3, width)
                rhs_text = rhs_lines[0].lstrip() if rhs_lines else ""
                if len(rhs_lines) == 1:
                    lines.append(f"{inner_ind} {sep} {alt_str} -> {rhs_text}")
                else:
                    lines.append(f"{inner_ind} {sep} {alt_str} -> {rhs_text}")
                    lines.extend(rhs_lines[1:])
            lines.append(f"{inner_ind} }}")
            return lines

        case _:
            return [f"{ind}<??? {type(tm).__name__}>"]


def _pp_atom(tm: CoreTm, depth: int, width: int) -> list[str]:
    """Print atom — parenthesize if complex."""
    match tm:
        case CoreVar() | CoreGlobalVar() | CoreLit():
            return _pp(tm, depth, width)
        case _:
            lines = _pp(tm, depth, width)
            return [f"({l.strip()})" for l in lines]


def _join_app(fun_lines: list[str], arg_lines: list[str]) -> str:
    """Join function and argument lines into a single application line."""
    if len(fun_lines) == 1 and len(arg_lines) == 1:
        return f"{fun_lines[0]} {arg_lines[0].lstrip()}"
    # Multi-line: keep function head, indent args below
    return "\n".join(fun_lines + arg_lines)


def _join_tyapp(fun_lines: list[str], ty_str: str) -> str:
    """Join function and type argument."""
    if len(fun_lines) == 1:
        return f"{fun_lines[0]} @{ty_str}"
    return "\n".join(fun_lines + [f"  @{ty_str}"])


def _pp_alt(alt) -> str:
    match alt:
        case DataAlt(con, vars):
            if vars:
                return f"{con.surface} {' '.join(v.name.surface for v in vars)}"
            return con.surface
        case LitAlt(lit):
            return repr(lit.v)
        case DefaultAlt():
            return "_"
        case _:
            return "<???>"


def scrut_id(tm: CoreTm) -> str:
    """Extract scrutinee identifier string."""
    match tm:
        case CoreVar(id) | CoreGlobalVar(id):
            return id.name.surface
        case _:
            return "..."
