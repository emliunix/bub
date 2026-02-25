"""Tests for pattern matching."""

import pytest

from systemf.core.ast import Pattern
from systemf.eval.pattern import MatchResult, PatternMatcher
from systemf.eval.value import VConstructor


def test_match_constructor_success():
    """Test matching constructor pattern successfully."""
    matcher = PatternMatcher()
    value = VConstructor("Cons", [VConstructor("Int", []), VConstructor("Nil", [])])
    pattern = Pattern("Cons", ["x", "xs"])

    result = matcher.match(value, pattern)
    assert result.success is True
    assert len(result.bindings) == 2
    assert result.bindings[0] == VConstructor("Int", [])
    assert result.bindings[1] == VConstructor("Nil", [])


def test_match_constructor_wrong_name():
    """Test matching constructor with wrong name fails."""
    matcher = PatternMatcher()
    value = VConstructor("Nil", [])
    pattern = Pattern("Cons", ["x", "xs"])

    result = matcher.match(value, pattern)
    assert result.success is False
    assert result.bindings == []


def test_match_constructor_wrong_arity():
    """Test matching constructor with wrong arity fails."""
    matcher = PatternMatcher()
    value = VConstructor("Cons", [VConstructor("Int", [])])
    pattern = Pattern("Cons", ["x", "xs"])

    result = matcher.match(value, pattern)
    assert result.success is False
    assert result.bindings == []


def test_match_zero_arg_constructor():
    """Test matching zero-argument constructor."""
    matcher = PatternMatcher()
    value = VConstructor("True", [])
    pattern = Pattern("True", [])

    result = matcher.match(value, pattern)
    assert result.success is True
    assert result.bindings == []


def test_select_branch_first_match():
    """Test selecting first matching branch."""
    from systemf.core.ast import Branch, Term

    matcher = PatternMatcher()
    value = VConstructor("True", [])

    branches = [
        Branch(Pattern("True", []), Term()),
        Branch(Pattern("False", []), Term()),
    ]

    branch, bindings = matcher.select_branch(value, branches)
    assert branch.pattern.constructor == "True"
    assert bindings == []


def test_select_branch_second_match():
    """Test selecting second matching branch."""
    from systemf.core.ast import Branch, Term

    matcher = PatternMatcher()
    value = VConstructor("False", [])

    branches = [
        Branch(Pattern("True", []), Term()),
        Branch(Pattern("False", []), Term()),
    ]

    branch, bindings = matcher.select_branch(value, branches)
    assert branch.pattern.constructor == "False"
    assert bindings == []


def test_select_branch_no_match():
    """Test that non-exhaustive patterns raises error."""
    from systemf.core.ast import Branch, Term

    matcher = PatternMatcher()
    value = VConstructor("Other", [])

    branches = [
        Branch(Pattern("True", []), Term()),
        Branch(Pattern("False", []), Term()),
    ]

    with pytest.raises(RuntimeError, match="Non-exhaustive patterns"):
        matcher.select_branch(value, branches)


def test_select_branch_with_bindings():
    """Test selecting branch returns correct bindings."""
    from systemf.core.ast import Branch, Term

    matcher = PatternMatcher()
    value = VConstructor("Cons", [VConstructor("Int", []), VConstructor("Nil", [])])

    branches = [
        Branch(Pattern("Nil", []), Term()),
        Branch(Pattern("Cons", ["x", "xs"]), Term()),
    ]

    branch, bindings = matcher.select_branch(value, branches)
    assert branch.pattern.constructor == "Cons"
    assert len(bindings) == 2
    assert bindings[0].name == "Int"
    assert bindings[1].name == "Nil"
