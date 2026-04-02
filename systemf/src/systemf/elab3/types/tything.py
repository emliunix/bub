"""
TyThing (type environment entries)
"""
from dataclasses import dataclass

from .ty import (Name, Ty, BoundTv)

@dataclass
class TyThing:
    pass

@dataclass
class AnId(TyThing):
    """Term-level binding: variable or function."""
    name: Name
    type: Ty

@dataclass
class ATyCon(TyThing):
    """Type constructor (data type or type synonym)."""
    name: Name
    tyvars: list[BoundTv]
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
