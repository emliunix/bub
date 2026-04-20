"""
Module system: Module, NameCache.
"""

from dataclasses import dataclass

from .ty import Name
from .tything import TypeEnv
from .core import CoreTm

@dataclass
class Module:
    """Complete compilation result. Stored in HPT."""
    name: str
    items: TypeEnv
    vals: dict[Name, CoreTm]
    exports: list[Name]
    source_path: str | None = None
