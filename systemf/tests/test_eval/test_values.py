"""Tests for value representations and environment."""

import pytest

from systemf.core.ast import Var
from systemf.eval.value import (
    Environment,
    VClosure,
    VConstructor,
    VNeutral,
    VTypeClosure,
)


def test_closure_creation():
    """Test creating a closure."""
    env = Environment.empty()
    closure = VClosure(env, Var(0))
    assert closure.env == env
    assert closure.body == Var(0)


def test_type_closure_creation():
    """Test creating a type closure."""
    env = Environment.empty()
    closure = VTypeClosure(env, Var(0))
    assert closure.env == env
    assert closure.body == Var(0)


def test_constructor_value():
    """Test creating a constructor value."""
    val = VConstructor("Cons", [VConstructor("Int", []), VConstructor("Nil", [])])
    assert val.name == "Cons"
    assert len(val.args) == 2
    assert val.args[0].name == "Int"
    assert val.args[1].name == "Nil"


def test_constructor_string_no_args():
    """Test string representation of constructor without args."""
    val = VConstructor("True", [])
    assert str(val) == "True"


def test_constructor_string_with_args():
    """Test string representation of constructor with args."""
    val = VConstructor("Cons", [VConstructor("Int", []), VConstructor("Nil", [])])
    assert str(val) == "(Cons Int Nil)"


def test_environment_empty():
    """Test empty environment."""
    env = Environment.empty()
    assert len(env) == 0
    assert env.values == []


def test_environment_extend():
    """Test extending environment."""
    env = Environment.empty()
    env = env.extend(VConstructor("True", []))
    assert len(env) == 1

    env = env.extend(VConstructor("False", []))
    assert len(env) == 2


def test_environment_lookup():
    """Test looking up values in environment."""
    env = Environment.empty()
    env = env.extend(VConstructor("True", []))
    env = env.extend(VConstructor("False", []))

    # Index 0 is most recent (False)
    assert env.lookup(0) == VConstructor("False", [])
    # Index 1 is next (True)
    assert env.lookup(1) == VConstructor("True", [])


def test_environment_lookup_out_of_bounds():
    """Test looking up unbound variable raises error."""
    env = Environment.empty()

    with pytest.raises(RuntimeError, match="Unbound variable at index 0"):
        env.lookup(0)


def test_neutral_value():
    """Test creating a neutral value."""
    term = Var(0)
    neutral = VNeutral(term)
    assert neutral.term == term


def test_closure_str():
    """Test closure string representation."""
    env = Environment.empty()
    closure = VClosure(env, Var(0))
    assert str(closure) == "<function>"


def test_type_closure_str():
    """Test type closure string representation."""
    env = Environment.empty()
    closure = VTypeClosure(env, Var(0))
    assert str(closure) == "<type-function>"
