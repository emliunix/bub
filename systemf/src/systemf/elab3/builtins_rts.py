"""Runtime support for builtin primitive operations.

This module provides the function implementations and a dispatcher
(``mk_primop``) used by ``EvalCtx`` implementations.
"""

from typing import Callable

from .eval import VPrimOp, VLit, VData, Val
from .types.ty import LitInt, LitString, Name
from .types.tything import AnId


# --- helpers ---

def _expect_int(v: Val) -> int:
    match v:
        case VLit(lit=LitInt(value=n)):
            return n
    raise Exception(f"expected int, got {v}")


def _expect_string(v: Val) -> str:
    match v:
        case VLit(lit=LitString(value=s)):
            return s
    raise Exception(f"expected string, got {v}")


def _bool_val(v: Val) -> bool:
    from .builtins import BUILTIN_TRUE
    match v:
        case VData(tag=tag) if tag.unique == BUILTIN_TRUE.unique:
            return True
    return False


def _bool_data(b: bool) -> Val:
    from .builtins import BUILTIN_TRUE, BUILTIN_FALSE
    return VData(BUILTIN_TRUE if b else BUILTIN_FALSE, [])


# --- primop implementations ---

def _int_plus(args: list[Val]) -> Val:
    a, b = args
    return VLit(LitInt(_expect_int(a) + _expect_int(b)))


def _int_minus(args: list[Val]) -> Val:
    a, b = args
    return VLit(LitInt(_expect_int(a) - _expect_int(b)))


def _int_multiply(args: list[Val]) -> Val:
    a, b = args
    return VLit(LitInt(_expect_int(a) * _expect_int(b)))


def _int_divide(args: list[Val]) -> Val:
    a, b = args
    return VLit(LitInt(_expect_int(a) // _expect_int(b)))


def _int_eq(args: list[Val]) -> Val:
    a, b = args
    return _bool_data(_expect_int(a) == _expect_int(b))


def _int_neq(args: list[Val]) -> Val:
    a, b = args
    return _bool_data(_expect_int(a) != _expect_int(b))


def _int_lt(args: list[Val]) -> Val:
    a, b = args
    return _bool_data(_expect_int(a) < _expect_int(b))


def _int_gt(args: list[Val]) -> Val:
    a, b = args
    return _bool_data(_expect_int(a) > _expect_int(b))


def _int_le(args: list[Val]) -> Val:
    a, b = args
    return _bool_data(_expect_int(a) <= _expect_int(b))


def _int_ge(args: list[Val]) -> Val:
    a, b = args
    return _bool_data(_expect_int(a) >= _expect_int(b))


def _bool_and(args: list[Val]) -> Val:
    a, b = args
    return _bool_data(_bool_val(a) and _bool_val(b))


def _bool_or(args: list[Val]) -> Val:
    a, b = args
    return _bool_data(_bool_val(a) or _bool_val(b))


def _bool_not(args: list[Val]) -> Val:
    (a,) = args
    return _bool_data(not _bool_val(a))


def _string_concat(args: list[Val]) -> Val:
    a, b = args
    return VLit(LitString(_expect_string(a) + _expect_string(b)))


def _error(args: list[Val]) -> Val:
    (a,) = args
    match a:
        case VLit(lit=LitString(value=s)):
            raise Exception(f"runtime error: {s}")
        case _:
            raise Exception(f"runtime error: {a!r}")


# --- registry ---

_PRIM_OPS: dict[str, tuple[int, Callable[[list[Val]], Val]]] = {
    "int_plus":     (2, _int_plus),
    "int_minus":    (2, _int_minus),
    "int_multiply": (2, _int_multiply),
    "int_divide":   (2, _int_divide),
    "int_eq":       (2, _int_eq),
    "int_neq":      (2, _int_neq),
    "int_lt":       (2, _int_lt),
    "int_gt":       (2, _int_gt),
    "int_le":       (2, _int_le),
    "int_ge":       (2, _int_ge),
    "bool_and":     (2, _bool_and),
    "bool_or":      (2, _bool_or),
    "bool_not":     (1, _bool_not),
    "string_concat": (2, _string_concat),
    "error":        (1, _error),
}


def mk_primop(name: Name, tything: AnId) -> Val:
    """Create a ``VPrimOp`` for the given builtin name."""
    entry = _PRIM_OPS.get(name.surface)
    if entry is None:
        raise Exception(f"unknown primop: {name.surface!r}")
    arity, func = entry
    return VPrimOp(name, arity, func)
