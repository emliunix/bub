from typing import Protocol

from .mod import Module
from .ty import Name, Ty
from .tything import TyThing

from systemf.utils.uniq import Uniq

class REPLContext(Protocol):
    uniq: Uniq

    def load(self, name: str) -> Module: ...
    def next_replmod_id(self) -> int: ...

__all__ = [
    "REPLContext", "Name", "Ty", "Module", "TyThing"
]
