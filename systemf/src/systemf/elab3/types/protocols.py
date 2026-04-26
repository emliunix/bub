from collections.abc import Iterable
from typing import Callable, Protocol

from systemf.utils.location import Location

from .ast import ImportDecl
from .mod import Module
from .ty import Id, Name, Ty
from .val import Val
from .tything import AnId, TyThing

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
    def get_primop(self, name: Name, thing: AnId, session: REPLSessionProto) -> Val | None: ...


class REPLSessionProto(Protocol):
    def fork(self) -> REPLSessionProto: ...
    def cmd_add_args(self, args: list[tuple[str, Val, Ty]]) -> None: ...
    def cmd_import(self, decl: ImportDecl) -> None: ...
    def eval(self, input: str) -> tuple[Val, Ty] | None: ...


class NameGenerator(Protocol):
    def new_name(self, name: str | Callable[[int], str], loc: Location | None) -> Name: ...
    def new_id(self, name: str | Callable[[int], str], ty: Ty) -> Id: ...


class TyLookup(Protocol):
    def lookup(self, name: Name) -> TyThing: ...


class Synthesizer(Protocol):
    def get_primop(self, name: Name, thing: AnId, session: REPLSessionProto) -> Callable[[list[Val]], Val]: ...
