"""
CEK evaluator for core
"""

# from . import core

from abc import ABC
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

from typing import Callable, cast


@dataclass
class Term(ABC):
    pass

@dataclass
class Data(Term):
    tag: str
    arity: int

@dataclass
class PrimOp(Term):
    name: str
    arity: int

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

DATAS = {
    # Bool
    "TRUE": Data("TRUE", 0),
    "FALSE": Data("FALSE", 0),
    # Pair
    "PAIR": Data("PAIR", 2),
    # Unit
    "UNIT": Data("UNIT", 0),
    # List
    "CONS": Data("CONS", 2),
    "NIL": Data("NIL", 0),
}

PRIMOPS = {
    "+": PrimOp("+", 2),
    "-": PrimOp("-", 2),
    "*": PrimOp("*", 2),
    "/": PrimOp("/", 2),
}

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
        elif (data := DATAS.get(name)) is not None:
            return data
        elif (primop := PRIMOPS.get(name)) is not None:
            return primop
        raise Exception(f"unbound variable: {name}")

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

PRIMOP_FUNCS = {
    "+": lambda x, y: x + y,
    "-": lambda x, y: x - y,
    "*": lambda x, y: x * y,
    "/": lambda x, y: x // y,
}

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

def vpartial_primop(name: str, arity: int, done: list[Val]) -> VPartial:
    def _finish(args: list[Val]) -> Val:
        func = PRIMOP_FUNCS.get(name)
        if func is None:
            raise Exception(f"unknown primitive operation: {name}")
        return VLit(func(*(val.v for val in cast(list[VLit], args))))
    return VPartial(name, arity, done, _finish)

def vpartial_data(tag: str, arity: int, done: list[Val]) -> VPartial:
    def _finish(args: list[Val]) -> Val:
        return VData(tag, args)
    return VPartial(tag, arity, done, _finish)

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
class NextCases(Cont):
    cases: list[Alt]
    env: Env
    k: Cont

@dataclass
class Backpatch(Cont):
    trap: Trap
    k: Cont

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
        case NextCases([], _, _):
            raise Exception(f"no matching case for value: {v}")
        case NextCases([case, *cases], env, k):
            match case:
                case LitAlt(v_, body) if VLit(v_) == v:
                    return (body, env, k)
                case DataAlt(tag, body) if isinstance(v, VData) and v.tag == tag:
                    return (body, env + v.vals, k)
                case DefaultAlt(body):
                    return (body, env, k)
                case _:
                    return call_continue(v, NextCases(cases, env, k))
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
        case Data(tag, arity):
            if arity == 0:
                return call_continue(VData(tag, []), k)
            else:
                return call_continue(vpartial_data(tag, arity, []), k)
        case PrimOp(name, arity):
            return call_continue(vpartial_primop(name, arity, []), k)
        case Let(expr, body):
            trap = Trap()
            return (expr, env + [trap], Backpatch(trap, Ap(VClosure(env, Lam(body)), k)))
        case Case(scrutinee, cases):
            return (scrutinee, env, NextCases(cases, env, k))
        case _:
            raise Exception(f"invalid term: {t}")

def eval(t: Term) -> Val:
    config: Config | Val = (t, [], Halt())
    while isinstance(config, tuple):
        config = step(*config)
    return config
