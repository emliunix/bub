"""Pattern matching implementation for System F interpreter."""

from dataclasses import dataclass
from typing import Optional

from systemf.core.ast import Pattern, Branch
from systemf.eval.value import Value, VConstructor


@dataclass(frozen=True)
class MatchResult:
    """Result of pattern matching."""

    success: bool
    bindings: list[Value]  # Values bound to pattern variables (in order)


class PatternMatcher:
    """Pattern matching implementation."""

    def match(self, value: Value, pattern: Pattern) -> MatchResult:
        """Match a value against a pattern.

        Returns bindings for pattern variables on success.
        Bindings are returned in the order they appear in the pattern.
        """
        match (value, pattern):
            case (VConstructor(name1, args), Pattern(constructor=name2, vars=vars)):
                if name1 != name2:
                    return MatchResult(False, [])
                if len(args) != len(vars):
                    return MatchResult(False, [])
                return MatchResult(True, args)
            case _:
                # Shouldn't happen if type checking passed
                raise RuntimeError(
                    f"Cannot match {value} against pattern for {pattern.constructor}"
                )

    def select_branch(self, value: Value, branches: list[Branch]) -> tuple[Branch, list[Value]]:
        """Select matching branch and return bindings.

        Raises RuntimeError if no branch matches.
        """
        for branch in branches:
            result = self.match(value, branch.pattern)
            if result.success:
                return branch, result.bindings
        raise RuntimeError(f"Non-exhaustive patterns: no branch matches {value}")
