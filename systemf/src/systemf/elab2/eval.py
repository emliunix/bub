"""
CEK evaluator
"""

from abc import ABC
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

from typing import Callable

@dataclass
class Term(ABC):
    pass

@dataclass
class GlobalVar(Term):
    name: str

@dataclass
class Lit(Term):
    v: int

@dataclass
class Var(Term):
    dbi: int
    name: str

@dataclass
class Lam(Term):
    body: Term

@dataclass
class App(Term):
    fun: Term
    arg: Term

@dataclass
class Let(Term):
    expr: Term
    body: Term

@dataclass
class LetRec(Term):
    # Parallel recursive bindings: all names are in scope for every expr and the body.
    # Stored in the same left-to-right order as the names passed to Builder.let_rec,
    # so bindings[i] corresponds to names[i].
    bindings: list[Term]
    body: Term

@dataclass
class Case(Term):
    scrutinee: Term
    cases: list[Alt]

@dataclass
class Alt:
    pass

@dataclass
class LitAlt(Alt):
    v: int
    body: Term

@dataclass
class DefaultAlt(Alt):
    body: Term

@dataclass
class DataAlt(Alt):
    tag: str
    body: Term

class Builder:
    def __init__(self):
        self.env: list[str] = []

    @contextmanager
    def extend(self, name: str) -> Generator[None, None, None]:
        self.env.append(name)
        yield None
        _ = self.env.pop()

    @contextmanager
    def extend_many(self, names: list[str]) -> Generator[None, None, None]:
        self.env.extend(names)
        yield None
        for _ in range(len(names)):
            _ = self.env.pop()

    def lookup(self, name: str) -> int | None:
        for i in reversed(range(len(self.env))):
            if self.env[i] == name:
                return len(self.env) - 1 - i
        return None

    def lit(self, v: int) -> Term:
        return Lit(v)

    def var(self, name: str) -> Term:
        if (i := self.lookup(name)) is not None:
            return Var(i, name)
        else:
            # Unbound locally — treat as a global variable reference.
            # The evaluator will resolve globals (data constructors and primops)
            # via `lookup_global` when encountering `GlobalVar`.
            return GlobalVar(name)

    def lam(self, name: str, body: Callable[[], Term]) -> Term:
        with self.extend(name):
            return Lam(body())

    def app(self, fun: Term, arg: Term) -> Term:
        return App(fun, arg)

    def let(self, name: str, expr: Callable[[], Term], body: Callable[[], Term]) -> Term:
        with self.extend(name):
            expr_term = expr()
            body_term = body()
        return Let(expr_term, body_term)

    def let_rec(self, names: list[str], exprs: list[Callable[[], Term]], body: Callable[[], Term]) -> Term:
        # All names are simultaneously in scope for every expr and for the body,
        # enabling mutual recursion.
        with self.extend_many(names):
            expr_terms = [expr() for expr in exprs]
            body_term = body()
        return LetRec(expr_terms, body_term)

    def case_lit(self, v: int, body: Callable[[], Term]) -> LitAlt:
        return LitAlt(v, body())

    def case_default(self, body: Callable[[], Term]) -> DefaultAlt:
        return DefaultAlt(body())

    def case_data(self, tag: str, args: list[str], body: Callable[[], Term]) -> DataAlt:
        with self.extend_many(args):
            body_term = body()
        return DataAlt(tag, body_term)

    def case(self, scrutinee: Term, cases: list[Callable[[], Alt]]) -> Term:
        return Case(scrutinee, [case() for case in cases])

    def ifte(self, cond: Term, then: Term, else_: Term) -> Term:
        return self.case(cond, [
            lambda: self.case_data("TRUE", [], lambda: then),
            lambda: self.case_data("FALSE", [], lambda: else_),
        ])

@dataclass
class Val:
    pass

type Env = list[Val]

@dataclass
class VLit(Val):
    v: int

@dataclass
class VPartial(Val):
    name: str
    arity: int
    done: list[Val]
    finish: Callable[[list[Val]], Val]

@dataclass
class VData(Val):
    tag: str
    vals: list[Val]

@dataclass
class VClosure(Val):
    env: Env
    fun: Lam

@dataclass
class Trap(Val):
    v: Val | None = None
    def set(self, v: Val):
        self.v = v

@dataclass
class Cont:
    pass

@dataclass
class Halt(Cont):
    pass

@dataclass
class Ar(Cont):
    arg: Term
    env: Env
    k: Cont

@dataclass
class Ap(Cont):
    closure: VClosure | VPartial
    k: Cont

@dataclass
class Kases(Cont):
    cases: list[Alt]
    env: Env
    k: Cont

@dataclass
class Backpatch(Cont):
    trap: Trap
    k: Cont

@dataclass
class BackpatchNext(Cont):
    # Backpatch `trap` with the current value, then either kick off the next
    # (trap, expr) pair in `rest`, or — when `rest` is empty — evaluate `body`
    # in `new_env` (whose traps are all filled by that point).
    trap: Trap
    rest: list[tuple[Trap, Term]]
    new_env: Env
    body: Term
    k: Cont

def vdata(tag: str) -> Callable[[list[Val]], Val]:
    def _go(args: list[Val]) -> Val:
        return VData(tag, args)
    return _go

def mk_primop(func: Callable[..., int]) -> Callable[[list[Val]], Val]:
    def _go(args: list[Val]) -> Val:
        return VLit(func(*[v.v for v in args]))
    return _go

def mk_partial(name: str, arity: int, func: Callable[[list[Val]], Val]) -> Val:
    return VPartial(name, arity, [], func)

GLOBALS: dict[str, Val] = {
    # Bool
    "TRUE": vdata("TRUE")([]),
    "FALSE": vdata("FALSE")([]),
    # Pair
    "PAIR": mk_partial("PAIR", 2, vdata("PAIR")),
    # Unit
    "UNIT": vdata("UNIT")([]),
    # List
    "CONS": mk_partial("CONS", 2, vdata("CONS")),
    "NIL": vdata("NIL")([]),
    # prim ops
    "+": mk_partial("+", 2, mk_primop(lambda x, y: x + y)),
    "-": mk_partial("-", 2, mk_primop(lambda x, y: x - y)),
    "*": mk_partial("*", 2, mk_primop(lambda x, y: x * y)),
    "/": mk_partial("/", 2, mk_primop(lambda x, y: x // y)),
}

def lookup_global(name: str) -> Val:
    if (val := GLOBALS.get(name)) is None:
        raise Exception(f"unknown primitive operation: {name}")
    return val

type Config = tuple[Term, Env, Cont]

def call_continue(v: Val, k: Cont) -> Config | Val:
    match k:
        case Ar(arg, env, k):
            if not isinstance(v, (VClosure, VPartial)):
                raise Exception(f"expected closure or partial data, got: {v}")
            return (arg, env, Ap(v, k))
        case Ap(f, k):
            match f:
                case VClosure(env, Lam(body)):
                    return (body, env + [v], k)
                case VPartial(tag, arity, done, finish):
                    if arity == len(done) + 1:
                        return call_continue(finish(done + [v]), k)
                    else:
                        return call_continue(VPartial(tag, arity, done + [v], finish), k)
                # case _:
                #     raise Exception(f"expected closure, got: {v}")
        case Backpatch(trap, k):
            trap.set(v)
            return call_continue(v, k)
        case BackpatchNext(trap, rest, new_env, body, k):
            trap.set(v)
            if rest:
                next_trap, next_expr = rest[0]
                return (next_expr, new_env, BackpatchNext(next_trap, rest[1:], new_env, body, k))
            else:
                return (body, new_env, k)
        case Kases(cases, env, k):
            for case in cases:
                match case:
                    case LitAlt(v_, body) if VLit(v_) == v:
                        return (body, env, k)
                    case DataAlt(tag, body) if isinstance(v, VData) and v.tag == tag:
                        return (body, env + v.vals, k)
                    case DefaultAlt(body):
                        return (body, env, k)
                    case _:
                        continue
            raise Exception(f"no matching case for value: {v}")
        case Halt():
            return v
        case _:
            raise Exception(f"invalid continuation: {k}")

def step(t: Term, env: Env, k: Cont) -> Config | Val:
    match t:
        case Lit(v):
            return call_continue(VLit(v), k)
        case Var(i, _):
            match env[-i - 1]:
                case Trap(v) if v is not None:
                    return call_continue(v, k)
                case Trap():
                    raise Exception(f"referencing trapped value {i}, possibly due to recursion")
                case v:
                    return call_continue(v, k)
        case Lam(body):
            return call_continue(VClosure(env, Lam(body)), k)
        case App(fun, arg):
            return (fun, env, Ar(arg, env, k))
        case GlobalVar(name):
            return call_continue(lookup_global(name), k)
        case Let(expr, body):
            trap = Trap()
            return (expr, env + [trap], Backpatch(trap, Ap(VClosure(env, Lam(body)), k)))
        case LetRec(bindings, body):
            traps: list[Trap] = [Trap() for _ in bindings]
            new_env = env + traps
            if not bindings:
                return (body, env, k)
            rest = list(zip(traps[1:], bindings[1:]))
            return (bindings[0], new_env, BackpatchNext(traps[0], rest, new_env, body, k))
        case Case(scrutinee, cases):
            return (scrutinee, env, Kases(cases, env, k))
        case _:
            raise Exception(f"invalid term: {t}")

def eval(t: Term) -> Val:
    config: Config | Val = (t, [], Halt())
    while isinstance(config, tuple):
        config = step(*config)
    return config
