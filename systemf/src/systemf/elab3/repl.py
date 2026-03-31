"""
REPL and REPLSession - orchestration and state management.
"""

from dataclasses import dataclass
from pathlib import Path

from . import builtins
from .mod import NameCache, Module
from .reader_env import ReaderEnv
from .tything import TyThing
from systemf.utils.uniq import Uniq


@dataclass
class REPLSession:
    """Accumulates imports and bindings. Corresponds to InteractiveContext."""
    repl: REPL
    reader_env: ReaderEnv         # Accumulated imports
    tythings: list[TyThing]       # Previous definitions


    @property
    def current_module(self) -> str:
        return f"REPL{self.repl.next_module_id()}"

    def fork(self) -> REPLSession:
        """
        Fork this session
        w/ session level states copied.
        """
        return REPLSession(
            repl=self.repl,
            reader_env=self.reader_env,
            tythings=self.tythings[:] # Copy tythings
        )

    def eval(self, input: str):
        """Evaluate input in the REPL session."""
        # TODO: Implement
        pass


@dataclass
class REPL:
    """Owns shared state, creates sessions, orchestrates module loading.
    
    Contains NameCache which wraps the Uniq counter for generating unique IDs.
    Also owns the session counter for unique module names.
    """
    uniq: Uniq
    name_cache: NameCache
    modules: dict[str, Module]
    search_paths: list[str]
    # Cycle detection
    _loading: set[str]
    _repl_mod_counter: int
    
    def __init__(self, search_paths: list[str] | None = None):
        self.uniq = Uniq(builtins.BUILTIN_ENDS)
        self.name_cache = NameCache(self.uniq)
        self.modules = {}
        self.search_paths = search_paths or ["."]
        self._loading = set()
        self._repl_mod_counter = 0
    
    def next_module_id(self) -> int:
        """Get next unique module ID."""
        self._repl_mod_counter += 1
        return self._repl_mod_counter
    
    def load(self, module_name: str) -> Module:
        """
        Load a module and its dependencies into HPT.
        """
        if (m := self.modules.get(module_name)) is not None:
            return m
        if module_name in self._loading:
            raise Exception("Cyclic imports detected")
        self._loading.add(module_name)
        def _get_module(mod_name: str) -> Module:
            if (m := self.modules.get(mod_name)) is not None:
                return m
            return self.load(mod_name)
            
        m = load_module(module_name, self._mod_file(module_name), _get_module)
        self.modules[module_name] = m
        self._loading.remove(module_name)
        return m

    def _mod_file(self, module_name: str) -> Path:
        parts = module_name.split(".")
        for sp in self.search_paths:
            p = Path(sp) / ("/".join(parts) + ".sf")
            if p.exists():
                return p
        raise Exception(f"module not found: {module_name}")
    
    def new_session(self) -> REPLSession:
        """Create a new REPL session with given state."""
        return REPLSession(
            repl=self,
            reader_env=ReaderEnv(),
            tythings=[],
        )
