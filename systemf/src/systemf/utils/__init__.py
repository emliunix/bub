"""Utilities: locations, pretty printing, etc."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import TypeVar
from systemf.utils.location import Location, Span

__all__ = ["Location", "Span"]


T = TypeVar("T")
R = TypeVar("R")


@contextmanager
def capture_return(gen: Generator[T, None, R]) -> Generator[tuple[Generator[T, None, None], list[R]], None, None]:
    """Run a generator to completion and return its final return value."""
    res: list[R] = []
    def wrapper():
        r = yield from gen
        res.append(r)
    yield (wrapper(), res)
