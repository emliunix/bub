"""
REPL and REPLSession - orchestration and state management.

The REPL owns the evaluator and implements ``EvalCtx.lookup_gbl``, which
resolves module-level names at runtime.  Module loading is typecheck-time
(``_load``); evaluation happens on demand via ``lookup_gbl``.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import override

from systemf.elab3.types.tything import ACon, AnId
from systemf.elab3.types.val import VPartial
from systemf.surface.parser import parse_expression, ParseError
from systemf.surface.types import SurfaceTermDeclaration
from systemf.utils.uniq import Uniq

from .name_gen import NameCacheImpl
from .reader_env import ImportSpec, ReaderEnv, RdrElt, ImportRdrElt
from .pipeline import Code, execute
from .builtins import BUILTIN_ENDS
from .eval import Evaluator, EvalCtx, VData, Val
from .types import Module, TyThing, REPLContext, Name, NameCache
from . import pipeline


class REPLSession(EvalCtx):
    """Accumulates imports and bindings. Corresponds to InteractiveContext."""
    ctx: REPLContext
    reader_env: ReaderEnv                 # Accumulated imports
    tythings: list[TyThing]               # Previous definitions
    # keep all evaluated REPL modules and normal modules
    mod_insts: dict[str, dict[Name, Val]] # Cache for evaluated module instances

    _evaling: list[str]                   # Modules currently being evaluated (for cycle detection)
    _evaluator: Evaluator

    def __init__(self, ctx: REPLContext, reader_env: ReaderEnv, tythings: list[TyThing], mod_insts: dict[str, dict[Name, Val]]):
        self.ctx = ctx
        self.reader_env = reader_env
        self.tythings = tythings
        self.mod_insts = mod_insts # Cache for evaluated module instances
        self._evaluator = Evaluator(self)
        self._evaling = []

    def fork(self) -> REPLSession:
        """
        Fork this session
        w/ session level states copied.
        """
        return REPLSession(
            ctx=self.ctx,
            reader_env=self.reader_env,
            tythings=self.tythings[:], # Copy tythings
            mod_insts=self.mod_insts.copy() # Copy module instances
        )

    def eval(self, input: str) -> Val | None:
        """
        Evaluate a REPL expression by wrapping it in a synthetic module,
        typechecking, then running ``eval_mod``.

        This is where REPL-level caching (e.g. RefCell) would be wired up.
        """
        repl_id = self.ctx.next_replmod_id()
        mod_name = f"REPL{repl_id}"

        # FIX: the pipeline should be able to take ast directly
        # cause we need to probe if input is an expression or a valid program
        # and for an expression, we need to make up a "it = <expr>" declaration
        file_path = f"<repl {repl_id}>"
        is_expr, ast = normalize_input(file_path, input)
        mod = pipeline.execute(self.ctx, mod_name, file_path, ast)
        self.update_repl_with_mod(mod)
        mod_inst = self.eval_mod(mod)

        if is_expr:
            # Convention: REPL expressions bind to `it`
            it = [v for k, v in mod_inst.items() if k.surface == "it"]
            if it:
                return it[0]
            raise Exception("REPL expression did not produce a value")

    # --- EvalCtx implementation ---------------------------------------------

    def lookup_gbl(self, name: Name) -> Val:
        """Resolve a global name, loading and evaluating modules on demand."""
        mod = name.mod

        # 1. Check runtime value cache
        cached = self.mod_insts.get(mod, {}).get(name)
        if cached is not None:
            return cached

        # 2. Cycle detection for evaluation
        if mod in self._evaling:
            raise Exception(
                f"Cyclic evaluation detected: {'->'.join(self._evaling + [mod])}"
            )

        self._evaling.append(mod)
        try:
            # 3. Load the typechecked module
            mod = self.ctx.load(mod)
            
            # 4. Eager whole module processing & return
            mod_inst = self.eval_mod(mod)
            return mod_inst[name]
        finally:
            self._evaling.pop()

    def eval_mod(self, mod: Module) -> dict[Name, Val]:
        mod_inst = self.mk_mod_inst(mod)
        mod_inst = self._evaluator.eval_mod(mod, mod_inst)
        self.mod_insts[mod.name] = mod_inst
        return mod_inst
    
    # --- State management ---

    def update_repl_with_mod(self, mod: Module):
        new_names = [n for n, _ in mod.tythings]
        new_rdr_env = ReaderEnv.from_elts([
            ImportRdrElt.create(name, ImportSpec(mod.name, None, False))
            for name, _ in mod.tythings
        ])

        # update REPL session state
        self.reader_env = self.reader_env.shadow(set(new_names)).merge(new_rdr_env)
        self.tythings.extend(thing for _, thing in mod.tythings)
    
    def mk_mod_inst(self, mod: Module) -> dict[Name, Val]:
        """
        Populate mod_inst with primitive values first
        """
        mod_inst = {}
        for name, thing in mod.tythings:
            match thing:
                case ACon(con=con, arity=arity):
                    mod_inst[name] = self.mk_con_func(name, con, arity)
                case AnId(name=name, is_prim=True):
                    mod_inst[name] = self.mk_primop(name)
        return mod_inst
    
    def mk_con_func(self, name: Name, tag: int, arity: int) -> Val:
        def con_func(args: list[Val]) -> Val:
            if len(args) != arity:
                raise Exception(f"Constructor {name} expects {arity} arguments, got {len(args)}")
            return VData(tag, args)
        return VPartial(name.surface, arity, [], con_func)

    def mk_primop(self, name: Name) -> Val:
        if (p := self.ctx.get_primop(name)) is not None:
            return p
        raise Exception(f"Unknown primitive operation: {name}")


class REPL(REPLContext):
    """Owns shared state, creates sessions, orchestrates module loading.

    Contains NameCache which wraps the Uniq counter for generating unique IDs.
    Also owns the session counter for unique module names.

    Implements EvalCtx.lookup_gbl to resolve names at runtime.  The REPL
    manages ``mod_insts`` — the runtime value cache — and uses a separate
    ``_evaling`` set for cycle detection during evaluation (distinct from
    ``_loading`` which guards typecheck-time import cycles).
    """
    uniq: Uniq
    name_cache: NameCache
    modules: dict[str, Module]
    search_paths: list[str]
    _loading: dict[str, str | None]
    _replmod_counter: int

    def __init__(self, search_paths: list[str] | None = None):
        self.uniq = Uniq(BUILTIN_ENDS)
        self.name_cache = NameCacheImpl()
        self.modules = {}
        self.mod_insts = {}
        self.search_paths = search_paths or ["."]
        self._loading = {}
        self._replmod_counter = 0

    # --- REPLContext implementation -----------------------------------------

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
        try:
            m = self._load_module(name, self._mod_file(name))
            self.modules[name] = m
            return m
        finally:
            del self._loading[name]

    def _mod_file(self, module_name: str) -> Path:
        parts = module_name.split(".")
        for sp in self.search_paths:
            p = Path(sp) / ("/".join(parts) + ".sf")
            if p.exists():
                return p
        raise Exception(f"module not found: {module_name}")

    def _load_module(self, name: str, file: Path) -> Module:
        text = file.read_text(encoding="utf-8")
        return execute(self, name, str(file), text)

    def new_session(self) -> REPLSession:
        """Create a new REPL session with given state."""
        return REPLSession(
            self,
            reader_env=ReaderEnv.empty(),
            tythings=[],
            mod_insts={},
        )


def _build_import_chain(loads: dict[str, str | None], start: str) -> str:
    chain = [start]
    parent = loads.get(start)
    while parent is not None:
        chain.append(parent)
        parent = loads.get(parent)
    return "->".join(list(reversed(chain)))


def normalize_input(file_path: str, input: str) -> tuple[bool, Code]:
    """Normalize REPL input.
    
    :returns: (is_expr, code)
    """
    try:
        expr = parse_expression(input, file_path)
        return True, (
            [],
            [SurfaceTermDeclaration(
                name="it",
                type_annotation=None,
                body=expr,
                docstring=None,
                pragma=None,
            )],
        )
    except ParseError:
        return False, input