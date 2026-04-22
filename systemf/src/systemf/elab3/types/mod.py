"""
Module system: Module, NameCache.
"""

from dataclasses import dataclass

from . import core
from .ty import Name
from .tything import TypeEnv

@dataclass
class Module:
    """Complete compilation result. Stored in HPT."""
    name: str
    items: TypeEnv
    bindings: dict[Name, core.Binding]
    exports: list[Name]
    source_path: str | None = None
