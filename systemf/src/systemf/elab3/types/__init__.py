from typing import Protocol

from systemf.utils.location import Location

from .mod import Module
from .ty import Name, Ty
from .tything import TyThing

from systemf.utils.uniq import Uniq

class REPLContext(Protocol):
    uniq: Uniq

    def load(self, name: str) -> Module: ...
    def next_replmod_id(self) -> int: ...


class NameGenerator(Protocol):
    def new_name(self, name: str, loc: Location | None) -> Name: ...


__all__ = [
    "REPLContext", "Name", "Ty", "Module", "TyThing"
]
