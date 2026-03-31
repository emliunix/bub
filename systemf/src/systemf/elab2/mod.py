"""
The module system

how it's used:
    - repl, single input is a module
    - module, links through imports
    - decls, with extra annotation
"""

from dataclasses import dataclass
from typing import Any

from systemf.elab2.types import Name, TyVar
from systemf.utils.uniq import Uniq

@dataclass
class DataCon:
    name: str
    args: list[str]

@dataclass
class DataDecl:
    name: Name
    tyvars: list[TyVar]
    datas: list[DataCon]

@dataclass
class Module:
    """
    The instantiated module. Built gradually during elaboration.
    """
    name: str
    types: dict[Name, Any]
    decls: dict[Name, Any]

class NameCache:
    def __init__(self, uniq: Uniq):
        self.uniq = uniq
        self.names: dict[tuple[str, str], Name] = {}

    def get(self, module: str, name: str) -> Name:
        if (n := self.names.get((module, name))) is None:
            n = Name(name, self.uniq.make_uniq())
            self.names[(module, name)] = n
        return n

class ElabModuleReader:
    def __init__(self, module: Module, name_cache: NameCache):
        self.module = module
        self.name_cache = name_cache

    def lookup(self, name: Name) -> Any:
        pass
