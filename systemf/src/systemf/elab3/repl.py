"""
REPL and REPLSession - orchestration and state management.

The REPL owns the evaluator and implements ``EvalCtx.lookup_gbl``, which
resolves module-level names at runtime.  Module loading is typecheck-time
(``_load``); evaluation happens on demand via ``lookup_gbl``.
"""

from dataclasses import dataclass
import itertools
from pathlib import Path
from typing import cast, override

from systemf.surface.parser import parse_expression, parse_program, ParseError
from systemf.surface.types import SurfaceTermDeclaration
from systemf.utils.uniq import Uniq

from . import pipeline
from . import builtins as bi
from . import builtins_rts as rts
from .name_gen import NameCacheImpl
from .reader_env import ImportSpec, ReaderEnv, RdrElt, ImportRdrElt
from .pipeline import Code, execute
from .eval import Evaluator, EvalCtx
from .types import Module, TyThing, REPLContext, Name, NameCache
from .types.ty import Ty, TyConApp, subst_ty
from .types.tything import ACon, ATyCon, AnId
from .types.val import Trap, VClosure, VData, VLit, VPartial, Val


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
        self.mod_insts: dict[str, dict[Name, Val]] = mod_insts
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

    def cmd_import(self, import_spec: ImportSpec) -> None:
        """Handle an import command by loading the module and updating state."""
        mod = self.ctx.load(import_spec.module_name)
        new_rdr_env = ReaderEnv.from_elts([
            ImportRdrElt.create(name, import_spec)
            for name, _ in mod.tythings
        ])
        self.reader_env = self.reader_env.merge(new_rdr_env)

    def eval(self, input: str) -> tuple[Ty, Val] | None:
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
        repl_mod = pipeline.execute(self.ctx, mod_name, file_path, ast, reader_env=self.reader_env)
        self.update_repl_with_mod(repl_mod)
        mod_inst = self.eval_mod(repl_mod)

        if is_expr:
            # Convention: REPL expressions bind to `it`
            ty = [cast(AnId, thing).id for n, thing in repl_mod.tythings if n.surface == "it"]
            it = [v for k, v in mod_inst.items() if k.surface == "it"]
            if ty and it:
                return ty[0].ty, it[0]
            raise Exception("REPL expression did not produce a value")
        return None

    def pp_val(self, ty: Ty, val: Val) -> str:
        """Pretty print a value using the evaluator's machinery."""
        def _pp(ty: Ty, val: Val) -> str:
            match ty, val:
                case TyConApp(name=con, args=arg_tys), VData(tag=tag, vals=args):
                    tycon, dcon = self.get_data_con(con, tag)
                    dcon_field_tys = [subst_ty(tycon.tyvars, arg_tys, ty) for ty in dcon.field_types]
                    vals_str = " ".join(_pp(ty, arg) for ty, arg in zip(dcon_field_tys, args))
                    return f"{dcon.name.surface} {vals_str}".strip()
                case _, VLit(lit=lit):
                    return f"{lit.v!r}"
                case _, VPartial(name=name, arity=arity):
                    return f"<func {name} {arity}>"
                case _, VClosure():
                    return "<closure>"
                case _, Trap(v=None):
                    return "<unfilled trap>"
                case _, Trap(v=v) if v is not None:
                    return _pp(ty, v)
                case _, _: return "<unknown>"
        return f"{_pp(ty, val)} :: {ty}"

    def get_data_con(self, con: Name, tag: int) -> tuple[ATyCon, ACon]:
        def _mod_lookup():
            # lazy load, cause REPL modules are not loadable
            for _, thing in self.ctx.load(con.mod).tythings:
                yield thing
        for tycon in itertools.chain(self.tythings, _mod_lookup()):
            if isinstance(tycon, ATyCon) and tycon.name == con:
                for acon in tycon.constructors:
                    if acon.tag == tag:
                        return tycon, acon
        raise Exception(f"Data constructor not found for {con} with tag {tag}")

    # --- EvalCtx implementation ---------------------------------------------

    def lookup_gbl(self, name: Name) -> Val:
        """Resolve a global name, loading and evaluating modules on demand."""
        mod_name = name.mod

        # 1. Check runtime value cache
        cached = self.mod_insts.get(mod_name, {}).get(name)
        if cached is not None:
            return cached

        # 2. Cycle detection for evaluation
        if mod_name in self._evaling:
            raise Exception(
                f"Cyclic evaluation detected: {'->'.join(self._evaling + [mod_name])}"
            )

        self._evaling.append(mod_name)
        try:
            # 3. Load the typechecked module
            mod = self.ctx.load(mod_name)
            
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
        mod_inst: dict[Name, Val] = {}
        for name, thing in mod.tythings:
            match thing:
                case ACon(name=con_name, tag=tag, arity=arity):
                    mod_inst[name] = VPartial.create(
                        con_name.surface, arity,
                        lambda args: VData(tag, args),  # type: ignore[misc]
                    )
                case AnId(name=name, is_prim=True):
                    mod_inst[name] = self.mk_primop(name)
        return mod_inst

    def mk_primop(self, name: Name) -> Val:
        if (p := self.ctx.get_primop(name)) is not None:
            return p
        raise Exception(f"Unknown primitive operation: {name}")


class REPL(REPLContext):
    """Owns shared state, creates sessions, orchestrates module loading.

    Contains NameCache which wraps the Uniq counter for generating unique IDs.
    Also owns the session counter for unique module names.
    """
    uniq: Uniq
    name_cache: NameCache
    modules: dict[str, Module]
    _prim_ops: dict[str, dict[str, Val]]
    search_paths: list[str]
    _loading: dict[str, str | None]
    _replmod_counter: int

    def __init__(self, search_paths: list[str] | None = None):
        self.uniq = Uniq(bi.BUILTIN_ENDS)
        self.name_cache = NameCacheImpl()
        self.modules = {}
        self.search_paths = search_paths or [".", str(Path(__file__).parent.parent)]
        self._loading = {}
        self._replmod_counter = 0
        self._prim_ops = _populate_primops()

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

    @override
    def get_primop(self, name: Name) -> Val | None:
        return self._prim_ops.get(name.mod, {}).get(name.surface)

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


def _populate_primops() -> dict[str, dict[str, Val]]:
    """Build the primop cache. Called once at REPL init."""

    # FIX: this is hacky, but we need rename phase of bulitins to get the tags assigned
    # so we just hardcode what will be assigned
    true_val = VData(0, [])
    false_val = VData(1, [])

    builtins: dict[str, Val] = {}

    def _reg(surface: str, arity: int, func):
        builtins[surface] = VPartial.create(surface, arity, func)

    _reg(bi.BUILTIN_INT_PLUS.surface, 2, rts.int_plus)
    _reg(bi.BUILTIN_INT_MINUS.surface, 2, rts.int_minus)
    _reg(bi.BUILTIN_INT_MULTIPLY.surface, 2, rts.int_multiply)
    _reg(bi.BUILTIN_INT_DIVIDE.surface, 2, rts.int_divide)
    _reg(bi.BUILTIN_INT_EQ.surface, 2, rts.mk_int_eq(true_val, false_val))
    _reg(bi.BUILTIN_INT_NEQ.surface, 2, rts.mk_int_neq(true_val, false_val))
    _reg(bi.BUILTIN_INT_LT.surface, 2, rts.mk_int_lt(true_val, false_val))
    _reg(bi.BUILTIN_INT_GT.surface, 2, rts.mk_int_gt(true_val, false_val))
    _reg(bi.BUILTIN_INT_LE.surface, 2, rts.mk_int_le(true_val, false_val))
    _reg(bi.BUILTIN_INT_GE.surface, 2, rts.mk_int_ge(true_val, false_val))
    _reg(bi.BUILTIN_STRING_CONCAT.surface, 2, rts.string_concat)
    _reg(bi.BUILTIN_ERROR.surface, 1, rts.error)

    return {"builtins": builtins}


def _build_import_chain(loads: dict[str, str | None], start: str) -> str:
    chain = [start]
    parent = loads.get(start)
    while parent is not None:
        chain.append(parent)
        parent = loads.get(parent)
    return "->".join(list(reversed(chain)))


def normalize_input(file_path: str, input: str) -> tuple[bool, Code]:
    """Normalize REPL input.

    Try expression parsing first. If that fails, try program parsing.
    If program parsing also fails, report the expression parse error
    (it's usually more informative).

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
    except ParseError as expr_err:
        pass

    try:
        code: Code = input
        _, decls = parse_program(input, file_path)
        if not decls:
            raise expr_err
        return False, code
    except ParseError:
        raise expr_err