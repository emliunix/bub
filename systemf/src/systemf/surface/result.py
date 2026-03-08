"""Result type for explicit error handling."""

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value

    def unwrap_or(self, default: T) -> T:
        return self.value

    def map(self, f: Callable[[T], U]) -> "Ok[U]":
        return Ok(f(self.value))

    def and_then(self, f: Callable[[T], "Result[U, E]"]) -> "Result[U, E]":
        return f(self.value)


@dataclass(frozen=True)
class Err(Generic[E]):
    error: E

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> T:
        raise ValueError(f"Called unwrap on Err: {self.error}")

    def unwrap_or(self, default: T) -> T:
        return default

    def map(self, f: Callable[[T], U]) -> "Err[E]":
        return self

    def and_then(self, f: Callable[[T], "Result[U, E]"]) -> "Err[E]":
        return self


type Result[T, E] = Ok[T] | Err[E]
