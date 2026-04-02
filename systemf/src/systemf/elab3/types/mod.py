"""
Module system: Module, NameCache.
"""

from dataclasses import dataclass

from .ty import Name
from .tything import TyThing

@dataclass
class Module:
    """Complete compilation result. Stored in HPT."""
    name: str
    items: list[TyThing]
    exports: list[Name]
    source_path: str | None = None
