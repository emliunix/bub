from collections.abc import Iterable
from typing import Callable, Protocol

from systemf.utils.location import Location

from .mod import Module
from .ty import Id, Name, Ty

from systemf.utils.uniq import Uniq


class NameCache(Protocol):
    def get(self, module: str, name: str) -> Name | None:
        """Get Name for the given module and surface name."""
        ...
    def put(self, name: Name): ...
    def put_all(self, names: Iterable[Name]): ...


class REPLContext(Protocol):
    uniq: Uniq
    name_cache: NameCache

    def load(self, name: str) -> Module: ...
    def next_replmod_id(self) -> int: ...


class NameGenerator(Protocol):
    def new_name(self, name: str | Callable[[int], str], loc: Location | None) -> Name: ...
    def new_id(self, name: str | Callable[[int], str], ty: Ty) -> Id: ...
