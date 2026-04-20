"""
TyThing (type environment entries)
"""
from dataclasses import dataclass

from .ty import Id, Name, Ty, TyVar


@dataclass
class TyThing:
    pass


@dataclass
class AnId(TyThing):
    """Term-level binding: variable or function."""
    name: Name
    id: Id

    @staticmethod
    def from_id(id: Id) -> AnId:
        return AnId(id.name, id)


@dataclass
class ATyCon(TyThing):
    """Type constructor (data type or type synonym)."""
    name: Name
    tyvars: list[TyVar]
    constructors: list[ACon]


@dataclass
class ACon(TyThing):
    """Data constructor."""
    name: Name
    tag: int
    arity: int
    field_types: list[Ty]
    parent: Name


type TypeEnv = dict[Name, TyThing]
