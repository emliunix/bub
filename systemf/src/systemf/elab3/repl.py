"""
REPL and REPLSession - orchestration and state management.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, override

from systemf.elab3.rename_expr import RenameExpr
from systemf.elab3.types import REPLContext

from .builtins import BUILTIN_ENDS
from .types import Module, TyThing
from .reader_env import ReaderEnv
from systemf.utils.uniq import Uniq


@dataclass
class REPLSession:
    """Accumulates imports and bindings. Corresponds to InteractiveContext."""
    ctx: REPLContext
    reader_env: ReaderEnv         # Accumulated imports
    tythings: list[TyThing]       # Previous definitions


    @property
    def current_module(self) -> str:
        return f"REPL{self.ctx.next_replmod_id()}"

    def fork(self) -> REPLSession:
        """
        Fork this session
        w/ session level states copied.
        """
        return REPLSession(
            ctx=self.ctx,
            reader_env=self.reader_env,
            tythings=self.tythings[:] # Copy tythings
        )

    def eval(self, input: str):
        """Evaluate input in the REPL session."""
        # TODO: Implement
        pass


class REPL(REPLContext):
    """Owns shared state, creates sessions, orchestrates module loading.

    Contains NameCache which wraps the Uniq counter for generating unique IDs.
    Also owns the session counter for unique module names.
    """
    uniq: Uniq
    name_cache: NameCache
    modules: dict[str, Module]
    search_paths: list[str]
    # Cycle detection
    _loading: dict[str, str | None]
    _replmod_counter: int

    def __init__(self, search_paths: list[str] | None = None):
        self.uniq = Uniq(BUILTIN_ENDS)
        self.name_cache = NameCache(self.uniq)
        self.modules = {}
        self.search_paths = search_paths or ["."]
        self._loading = {}
        self._replmod_counter = 0

    @override
    def next_replmod_id(self) -> int:
        """Get next unique module ID."""
        v = self._replmod_counter
        self._replmod_counter += 1
        return v

    @override
    def load(self, name: str) -> Module:
        return self._load(name, None)

    def _load(self, name: str, from_mod: str | None = None) -> Module:
        """
        Load a module and its dependencies into HPT.
        """
        if (m := self.modules.get(name)) is not None:
            return m
        if name in self._loading:
            raise Exception(f"Cyclic imports detected: {_build_import_chain(self._loading, name)}")
        self._loading[name] = from_mod

        m = self._load_module(name, self._mod_file(name))
        self.modules[name] = m
        self._loading.remove(name)
        return m

    def _mod_file(self, module_name: str) -> Path:
        parts = module_name.split(".")
        for sp in self.search_paths:
            p = Path(sp) / ("/".join(parts) + ".sf")
            if p.exists():
                return p
        raise Exception(f"module not found: {module_name}")

    def _load_module(self, name: str, file: Path) -> Module:
        text = file.read_text(encoding="utf-8")
        pass

    def new_session(self) -> REPLSession:
        """Create a new REPL session with given state."""
        return REPLSession(
            self,
            reader_env=ReaderEnv.empty(),
            tythings=[],
        )


def _build_import_chain(loads: dict[str, str | None], start: str) -> str:
    chain = [start]
    s = start
    while (s := loads.get(start)) is not None:
        chain.append(s)
    return "->".join(list(reversed(chain)))
