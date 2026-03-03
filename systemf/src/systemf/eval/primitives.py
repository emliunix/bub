"""Primitive operations for System F evaluator.

This module contains implementations of all primitive operations
that can be called from System F code.
"""

from __future__ import annotations

from typing import Callable

from systemf.eval.value import Value, VPrim, VConstructor


# Type alias for primitive implementations
PrimImpl = Callable[[Value, Value], Value]


def _int_plus(x: Value, y: Value) -> Value:
    """Integer addition."""
    if not isinstance(x, VPrim) or not isinstance(y, VPrim):
        raise RuntimeError("int_plus expects Int arguments")
    if x.prim_type != "Int" or y.prim_type != "Int":
        raise RuntimeError("int_plus expects Int arguments")
    return VPrim("Int", x.value + y.value)


def _int_minus(x: Value, y: Value) -> Value:
    """Integer subtraction."""
    if not isinstance(x, VPrim) or not isinstance(y, VPrim):
        raise RuntimeError("int_minus expects Int arguments")
    if x.prim_type != "Int" or y.prim_type != "Int":
        raise RuntimeError("int_minus expects Int arguments")
    return VPrim("Int", x.value - y.value)


def _int_multiply(x: Value, y: Value) -> Value:
    """Integer multiplication."""
    if not isinstance(x, VPrim) or not isinstance(y, VPrim):
        raise RuntimeError("int_multiply expects Int arguments")
    if x.prim_type != "Int" or y.prim_type != "Int":
        raise RuntimeError("int_multiply expects Int arguments")
    return VPrim("Int", x.value * y.value)


def _int_divide(x: Value, y: Value) -> Value:
    """Integer division."""
    if not isinstance(x, VPrim) or not isinstance(y, VPrim):
        raise RuntimeError("int_divide expects Int arguments")
    if x.prim_type != "Int" or y.prim_type != "Int":
        raise RuntimeError("int_divide expects Int arguments")
    if y.value == 0:
        raise RuntimeError("Division by zero")
    return VPrim("Int", x.value // y.value)


def _int_negate(x: Value, _y: Value) -> Value:
    """Integer negation (unary minus).

    Note: This is a unary operation (Int -> Int) but the primitive
    infrastructure expects binary operations. The second argument is ignored.
    """
    if not isinstance(x, VPrim) or x.prim_type != "Int":
        raise RuntimeError("int_negate expects Int argument")
    return VPrim("Int", -x.value)


def _int_eq(x: Value, y: Value) -> Value:
    """Integer equality."""
    if not isinstance(x, VPrim) or not isinstance(y, VPrim):
        raise RuntimeError("int_eq expects Int arguments")
    if x.prim_type != "Int" or y.prim_type != "Int":
        raise RuntimeError("int_eq expects Int arguments")
    return VConstructor("True" if x.value == y.value else "False", [])


def _int_neq(x: Value, y: Value) -> Value:
    """Integer inequality."""
    if not isinstance(x, VPrim) or not isinstance(y, VPrim):
        raise RuntimeError("int_neq expects Int arguments")
    if x.prim_type != "Int" or y.prim_type != "Int":
        raise RuntimeError("int_neq expects Int arguments")
    return VConstructor("True" if x.value != y.value else "False", [])


def _int_lt(x: Value, y: Value) -> Value:
    """Integer less than."""
    if not isinstance(x, VPrim) or not isinstance(y, VPrim):
        raise RuntimeError("int_lt expects Int arguments")
    if x.prim_type != "Int" or y.prim_type != "Int":
        raise RuntimeError("int_lt expects Int arguments")
    return VConstructor("True" if x.value < y.value else "False", [])


def _int_gt(x: Value, y: Value) -> Value:
    """Integer greater than."""
    if not isinstance(x, VPrim) or not isinstance(y, VPrim):
        raise RuntimeError("int_gt expects Int arguments")
    if x.prim_type != "Int" or y.prim_type != "Int":
        raise RuntimeError("int_gt expects Int arguments")
    return VConstructor("True" if x.value > y.value else "False", [])


def _int_le(x: Value, y: Value) -> Value:
    """Integer less than or equal."""
    if not isinstance(x, VPrim) or not isinstance(y, VPrim):
        raise RuntimeError("int_le expects Int arguments")
    if x.prim_type != "Int" or y.prim_type != "Int":
        raise RuntimeError("int_le expects Int arguments")
    return VConstructor("True" if x.value <= y.value else "False", [])


def _int_ge(x: Value, y: Value) -> Value:
    """Integer greater than or equal."""
    if not isinstance(x, VPrim) or not isinstance(y, VPrim):
        raise RuntimeError("int_ge expects Int arguments")
    if x.prim_type != "Int" or y.prim_type != "Int":
        raise RuntimeError("int_ge expects Int arguments")
    return VConstructor("True" if x.value >= y.value else "False", [])


def _bool_and(x: Value, y: Value) -> Value:
    """Boolean AND."""
    # Booleans are constructors: True/False with no args
    if not isinstance(x, VConstructor) or not isinstance(y, VConstructor):
        raise RuntimeError("bool_and expects Bool arguments")
    result = x.name == "True" and y.name == "True"
    return VConstructor("True" if result else "False", [])


def _bool_or(x: Value, y: Value) -> Value:
    """Boolean OR."""
    if not isinstance(x, VConstructor) or not isinstance(y, VConstructor):
        raise RuntimeError("bool_or expects Bool arguments")
    result = x.name == "True" or y.name == "True"
    return VConstructor("True" if result else "False", [])


def _bool_not(x: Value, _y: Value) -> Value:
    """Boolean NOT (negation).

    Note: This is a unary operation (Bool -> Bool) but the primitive
    infrastructure expects binary operations. The second argument is ignored.
    """
    if not isinstance(x, VConstructor):
        raise RuntimeError("bool_not expects Bool argument")
    result = x.name == "False"
    return VConstructor("True" if result else "False", [])


def _string_concat(x: Value, y: Value) -> Value:
    """String concatenation."""
    if not isinstance(x, VPrim) or not isinstance(y, VPrim):
        raise RuntimeError("string_concat expects String arguments")
    if x.prim_type != "String" or y.prim_type != "String":
        raise RuntimeError("string_concat expects String arguments")
    return VPrim("String", x.value + y.value)


def _string_length(x: Value, _y: Value) -> Value:
    """String length.

    Note: This is a unary operation (String -> Int) but the primitive
    infrastructure expects binary operations. The second argument is ignored.
    """
    if not isinstance(x, VPrim) or x.prim_type != "String":
        raise RuntimeError("string_length expects String argument")
    return VPrim("Int", len(x.value))


# Registry of all primitive implementations
PRIMITIVE_IMPLEMENTATIONS: dict[str, PrimImpl] = {
    "$prim.int_plus": _int_plus,
    "$prim.int_minus": _int_minus,
    "$prim.int_multiply": _int_multiply,
    "$prim.int_divide": _int_divide,
    "$prim.int_negate": _int_negate,
    "$prim.int_eq": _int_eq,
    "$prim.int_neq": _int_neq,
    "$prim.int_lt": _int_lt,
    "$prim.int_gt": _int_gt,
    "$prim.int_le": _int_le,
    "$prim.int_ge": _int_ge,
    "$prim.bool_and": _bool_and,
    "$prim.bool_or": _bool_or,
    "$prim.bool_not": _bool_not,
    "$prim.string_concat": _string_concat,
    "$prim.string_length": _string_length,
}


def get_primitive_impl(name: str) -> PrimImpl | None:
    """Get primitive implementation by name.

    Args:
        name: Primitive name (with $prim. prefix)

    Returns:
        Implementation function or None if not found
    """
    return PRIMITIVE_IMPLEMENTATIONS.get(name)


def is_primitive(name: str) -> bool:
    """Check if a name is a registered primitive.

    Args:
        name: Primitive name (with $prim. prefix)

    Returns:
        True if primitive exists
    """
    return name in PRIMITIVE_IMPLEMENTATIONS
