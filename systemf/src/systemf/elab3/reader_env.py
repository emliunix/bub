"""
Reader environment for name resolution.

Maps surface names (OccName) to resolved Names with provenance.
"""

from abc import ABC
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from systemf.elab3.types import Name

if TYPE_CHECKING:
    from systemf.elab3.mod import Module


type RdrName = QualName | UnqualName


@dataclass
class QualName:
    qual: str
    name: str


@dataclass
class UnqualName:
    name: str


@dataclass
class ImportList:
    """Import only these specific items."""
    items: list[str]


@dataclass
class HidingList:
    """Import all except these specific items."""
    items: list[str]


@dataclass
class ImportSpec:
    """How a name entered scope via import.
    
    items field captures three cases:
    - None: import all exported names
    - ImportList([...]): import only these names
    - HidingList([...]): import all except these names
    """
    module: str                    # Source module
    qualified: bool                # Was imported qualified?
    alias: str | None              # Import alias (e.g., 'as M')
    items: ImportList | HidingList | None = None


@dataclass
class RdrElt:
    """Reader environment element - a binding in scope.
    
    import_specs is a list because a name can be brought into scope
    by multiple imports (e.g., import M; import M as N).
    Empty list means locally defined.
    """
    name: Name
    is_local: bool              # True if defined locally
    import_specs: list[ImportSpec]  # Empty for local bindings


@dataclass(frozen=True)
class ReaderEnv:
    """Maps surface names to resolved Names.
    
    Key is unqualified surface name (OccName).
    Value is list of RdrElts (handles name clashes).
    
    Immutable - use factory methods to construct.
    """
    table: dict[str, list[RdrElt]] = field(default_factory=dict)
    
    def lookup(self, name: RdrName) -> list[RdrElt]:
        """Look up all bindings with the given surface name."""
        return self.table.get(surface, [])
    
    @staticmethod
    def empty() -> "ReaderEnv":
        """Create empty environment."""
        return ReaderEnv({})
    
    @staticmethod
    def from_module(module: Module, spec: ImportSpec) -> "ReaderEnv":
        """Build ReaderEnv from a single module import.
        
        Args:
            hpt: Home package table with loaded modules
            module_name: Name of module to import from
            spec: Import specification (qualified, alias, items/hiding)
        
        Returns:
            ReaderEnv with bindings from this import
        """
        result: dict[str, list[RdrElt]] = {}
        
        module = hpt.get(module_name)
        if module is None:
            # Module not loaded - should have been loaded before this
            raise ValueError(f"Module not found: {module_name}")
        
        # Determine which names to import
        names_to_import = _filter_exports(module.exports, spec.items)
        
        for name in names_to_import:
            # Create RdrElt for this import
            rdr_elt = RdrElt(
                name=name,
                is_local=False,
                import_specs=[spec]
            )
            
            # Add under surface name
            surface = name.surface
            if surface not in result:
                result[surface] = []
            result[surface].append(rdr_elt)
            
            # If qualified or aliased, also add under qualified name
            if spec.qualified or spec.alias:
                alias = spec.alias if spec.alias else module_name
                qualified_surface = f"{alias}.{surface}"
                if qualified_surface not in result:
                    result[qualified_surface] = []
                result[qualified_surface].append(rdr_elt)
        
        return ReaderEnv(result)
    
    @staticmethod
    def from_imports(modules: dict[str, Module], specs: list[ImportSpec]) -> "ReaderEnv":
        """Build ReaderEnv from multiple imports.
        
        Merges all imports together. Later imports shadow earlier ones
        in case of name clashes.
        """
        result = ReaderEnv.empty()
        for spec in specs:
            import_env = ReaderEnv.from_module(hpt, spec.module, spec)
            result = result.merge(import_env)
        return result
    
    def merge(self, other: "ReaderEnv") -> "ReaderEnv":
        """Merge two environments (bag union - keeps duplicates).
        
        Later bindings (from `other`) appear after earlier bindings.
        """
        result: dict[str, list[RdrElt]] = {}
        
        # Copy self
        for k, v in self.table.items():
            result[k] = v.copy()
        
        # Merge other
        for k, v in other.table.items():
            if k not in result:
                result[k] = []
            result[k].extend(v)
        
        return ReaderEnv(result)
    
    def extend_local(self, name: Name) -> "ReaderEnv":
        """Add a local binding to the environment.
        
        Returns new environment with the binding added.
        """
        result: dict[str, list[RdrElt]] = {}
        
        # Copy existing
        for k, v in self.table.items():
            result[k] = v.copy()
        
        # Add local binding
        surface = name.surface
        if surface not in result:
            result[surface] = []
        
        rdr_elt = RdrElt(
            name=name,
            is_local=True,
            import_specs=[]
        )
        result[surface].append(rdr_elt)
        
        return ReaderEnv(result)


def _filter_exports(exports: list[Name], items: ImportList | HidingList | None) -> list[Name]:
    """Filter module exports based on import specification.
    
    Args:
        exports: List of exported Names from module
        items: Import specification (None, ImportList, or HidingList)
    
    Returns:
        Filtered list of names to actually import
    """
    if items is None:
        # Import everything
        return list(exports)
    
    if isinstance(items, ImportList):
        # Import only specific items
        names_to_import = set(items.items)
        return [n for n in exports if n.surface in names_to_import]
    
    if isinstance(items, HidingList):
        # Import everything except specific items
        names_to_hide = set(items.items)
        return [n for n in exports if n.surface not in names_to_hide]
    
    # Shouldn't reach here
    return list(exports)
