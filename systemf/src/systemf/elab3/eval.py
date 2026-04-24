"""
CEK evaluator for elab3 Core.

Architecture:
- Evaluator is a strict CBV expression-driven CEK machine.
- eval_mod evaluates a topo-sorted list of bindings and returns all results.
- Variable resolution: local env -> ctx.lookup_gbl for module-level references.
- No binding-level caching. The context owns all caching and module management.
- No item types — the evaluator only sees CoreTm and Binding types.
"""

from dataclasses import dataclass
from typing import Protocol

from systemf.elab3.types.core import (
    CoreTm, CoreLit, CoreVar, CoreGlobalVar, CoreLam, CoreApp,
    CoreTyLam, CoreTyApp, CoreLet, CoreCase,
    NonRec, Rec,
    DataAlt, LitAlt, DefaultAlt, Alt,
)
from .types.ty import Id, Lit, LitInt, Name
from .types.mod import Module
from .types.val import Val, VLit, VClosure, VPartial, VData, Trap, Env



# =============================================================================
# Continuations
# =============================================================================

@dataclass
class Cont:
    pass


@dataclass
class Halt(Cont):
    pass


@dataclass
class Ar(Cont):
    """Evaluate the argument next, then apply."""
    arg: CoreTm
    env: Env
    k: Cont


@dataclass
class Ap(Cont):
    """Apply a closure/partial/primop to the incoming value."""
    closure: VClosure | VPartial
    k: Cont


@dataclass
class LetBind(Cont):
    """Bind the incoming value to a variable and continue with the body."""
    binder: Id
    body: CoreTm
    env: Env
    k: Cont


@dataclass
class Kases(Cont):
    """Match the incoming value against a list of alts."""
    alts: list[tuple[Alt, CoreTm]]
    scrut_var: Id
    env: Env
    k: Cont


@dataclass
class BackpatchNext(Cont):
    """
    Fill `trap` with the incoming value, then either kick off the next
    (trap, expr) pair in `rest`, or — when `rest` is empty — evaluate `body`
    in `new_env` (all traps filled by then).
    """
    trap: Trap
    rest: list[tuple[Trap, CoreTm]]
    new_env: Env
    body: CoreTm
    k: Cont


# =============================================================================
# EvalCtx protocol
# =============================================================================


class EvalCtx(Protocol):
    """Protocol for the context that resolves module-level names at runtime."""

    def lookup_gbl(self, name: Name) -> Val: ...


# =============================================================================
# Evaluator
# =============================================================================

type Config = tuple[CoreTm, Env, Cont]


class Evaluator:
    """Strict CBV CEK evaluator."""

    def __init__(self, ctx: EvalCtx):
        self.ctx = ctx

    # --- public API ---------------------------------------------------------

    def eval_mod(self, mod: Module, mod_inst: dict[Name, Val]) -> dict[Name, Val]:
        """Evaluate topo-sorted bindings and return all bound values.

        Each binding is evaluated independently.  For NonRec, the expression
        result is stored under ``binder.name``.  For Rec, the whole group is
        evaluated once and all member values are extracted.
        """
        
        for binding in mod.bindings:
            match binding:
                case NonRec(binder, expr):
                    mod_inst[binder.name] = self._eval_expr(expr, {})
                case Rec(rec_bindings):
                    mod_inst.update(self._eval_rec_many(rec_bindings))
                case _:
                    raise Exception(f"unexpected binding type: {binding!r}")
        return mod_inst

    # --- CEK machine --------------------------------------------------------

    def _eval_expr(self, t: CoreTm, env: Env | None = None) -> Val:
        """Evaluate a CoreTm to a Val using the CEK machine."""
        if env is None:
            env = {}
        cur: Config | Val = (t, env, Halt())
        while not isinstance(cur, Val):
            t1, env1, k1 = cur
            cur = self.step(t1, env1, k1)
        return cur

    def _eval_rec_many(self, pairs: list[tuple[Id, CoreTm]]) -> dict[Name, Val]:
        """Evaluate a Rec group once and return all bound values.

        Implements the same trap/backpatch mechanism as ``step`` for Rec,
        but extracts all filled trap values after the run instead of a
        single body result.
        """
        if not pairs:
            return {}

        traps = [(Trap(), expr) for _, expr in pairs]
        new_env: Env = {}
        for (trap, _), (binder, _) in zip(traps, pairs):
            new_env[binder.name.unique] = trap

        first_trap, first_expr = traps[0]
        rest = traps[1:]
        cur: Config | Val = (
            first_expr,
            new_env,
            BackpatchNext(first_trap, rest, new_env, CoreLit(LitInt(0)), Halt()),
        )

        while not isinstance(cur, Val):
            t1, env1, k1 = cur
            cur = self.step(t1, env1, k1)

        results: dict[Name, Val] = {}
        for (binder, _), (trap, _) in zip(pairs, traps):
            v = trap.v
            if v is None:
                raise Exception(
                    f"Rec binding {binder.name.surface!r} was not initialized "
                    f"(non-productive recursion)"
                )
            results[binder.name] = v

        return results

    def step(self, t: CoreTm, env: Env, k: Cont) -> Config | Val:
        match t:
            case CoreLit(value=value):
                return self.call_continue(VLit(value), k)

            case CoreVar(id=id):
                raw = env.get(id.name.unique)
                if raw is not None:
                    match raw:
                        case Trap(v=inner) if inner is not None:
                            return self.call_continue(inner, k)
                        case Trap():
                            raise Exception(
                                f"referencing uninitialized letrec trap for "
                                f"{id.name.surface!r} (possible non-productive recursion)"
                            )
                        case _:
                            return self.call_continue(raw, k)
                else:
                    return self.call_continue(self.ctx.lookup_gbl(id.name), k)

            case CoreGlobalVar(id=id):
                return self.step(CoreVar(id), env, k)

            case CoreLam(param=param, body=body):
                return self.call_continue(VClosure(env, param, body), k)

            case CoreApp(fun=fun, arg=arg):
                return (fun, env, Ar(arg, env, k))

            case CoreTyLam(body=body):
                return (body, env, k)

            case CoreTyApp(fun=fun):
                return (fun, env, k)

            case CoreLet(binding=NonRec(binder=binder, expr=expr), body=body):
                return (expr, env, LetBind(binder, body, env, k))

            case CoreLet(binding=Rec(bindings=bindings), body=body):
                if not bindings:
                    return (body, env, k)

                trap_pairs: list[tuple[Trap, CoreTm]] = [
                    (Trap(), expr) for _, expr in bindings
                ]
                new_env: Env = dict(env)
                for (trap, _), (binder, _) in zip(trap_pairs, bindings):
                    new_env[binder.name.unique] = trap

                first_trap, first_expr = trap_pairs[0]
                rest = trap_pairs[1:]
                return (
                    first_expr,
                    new_env,
                    BackpatchNext(first_trap, rest, new_env, body, k),
                )

            case CoreCase(scrut=scrut, var=var, alts=alts):
                return (scrut, env, Kases(alts, var, env, k))

            case _:
                raise Exception(f"step: unhandled term: {t!r}")

    def call_continue(self, v: Val, k: Cont) -> "Config | Val":
        match k:
            case Ar(arg=arg, env=env, k=k2):
                match v:
                    case VClosure() | VPartial():
                        return (arg, env, Ap(v, k2))
                    case _:
                        raise Exception(
                            f"expected closure, partial, or primop in function position, got: {v!r}"
                        )

            case Ap(closure=f, k=k2):
                match f:
                    case VClosure(env=cenv, param=param, body=body):
                        return (body, cenv | {param.name.unique: v}, k2)
                    case VPartial(name=name, arity=arity, done=done, finish=finish):
                        new_done = done + [v]
                        if arity == len(new_done):
                            return self.call_continue(finish(new_done), k2)
                        else:
                            return self.call_continue(
                                VPartial(name, arity, new_done, finish), k2
                            )
            case LetBind(binder=binder, body=body, env=env, k=k2):
                return (body, env | {binder.name.unique: v}, k2)

            case BackpatchNext(trap=trap, rest=rest, new_env=new_env, body=body, k=k2):
                trap.set(v)
                if rest:
                    next_trap, next_expr = rest[0]
                    return (
                        next_expr,
                        new_env,
                        BackpatchNext(next_trap, rest[1:], new_env, body, k2),
                    )
                else:
                    return (body, new_env, k2)

            case Kases(alts=alts, scrut_var=scrut_var, env=env, k=k2):
                scrut_key = scrut_var.name.unique
                match v:
                    case VLit(lit=lit):
                        for alt, body in alts:
                            match alt:
                                case LitAlt(lit=lit_) if lit_ == lit:
                                    return (body, env | {scrut_key: v}, k2)
                                case DefaultAlt():
                                    return (body, env | {scrut_key: v}, k2)
                    case VData(tag=tag, vals=vals):
                        for alt, body in alts:
                            match alt:
                                case DataAlt(tag=tag_, vars=alt_vars) if tag_ == tag:
                                    alt_env: Env = dict(env)
                                    alt_env[scrut_key] = v
                                    for var_id, field_val in zip(alt_vars, vals):
                                        alt_env[var_id.name.unique] = field_val
                                    return (body, alt_env, k2)
                                case DefaultAlt():
                                    return (body, env | {scrut_key: v}, k2)
                    case _:
                        for alt, body in alts:
                            match alt:
                                case DefaultAlt():
                                    return (body, env | {scrut_key: v}, k2)

                raise Exception(f"no matching case for value: {v!r}")

            case Halt():
                return v

            case _:
                raise Exception(f"invalid continuation: {k!r}")
