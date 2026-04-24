"""
Elab3 demo script: construct a REPL context and load a demo module.

Usage:
    cd systemf && uv run python -m systemf.elab3_demo
"""

from pathlib import Path

from systemf.elab3.pipeline import execute
from systemf.elab3.reader_env import ReaderEnv
from systemf.elab3.repl import REPL
from systemf.elab3.types import Module, core
from systemf.elab3.types.core_pp import pp_core


def main() -> None:
    # Search path is the directory containing this file
    demo_dir = Path(__file__).parent.resolve()
    search_path = str(demo_dir)

    # 1. Construct REPLContext
    ctx = REPL(search_paths=[search_path])

    # 2. Load builtins first (so demo can import it)
    builtins_mod = ctx.load("builtins")
    print(f"Loaded builtins module: {builtins_mod.name}")
    print(f"  Exports: {[n.surface for n in builtins_mod.exports]}")

    # 3. Load demo module
    demo_mod = ctx.load("demo")
    print(f"\nLoaded demo module: {demo_mod.name}")
    print(f"  Exports: {[n.surface for n in demo_mod.exports]}")
    print(f"  TyThings: {[n.surface for n, _ in demo_mod.tythings]}")
    print(f"\n  Core terms (vals):")
    for binding in demo_mod.bindings:
        print(f"\n    {pp_binding_name(binding)}:")
        for line in pp_binding(binding).split("\n"):
            print(f"      {line}")


def pp_binding_name(b: core.Binding) -> str:
    match b:
        case core.NonRec(name, _):
            return name.name.surface
        case core.Rec(bindings):
            return ", ".join(name.name.surface for name, _ in bindings)
        case _:
            return "?"


def pp_binding(b: core.Binding) -> str:
    match b:
        case core.NonRec(name, expr):
            return f"{name} = {pp_core(expr)}"
        case core.Rec(bindings):
            binds_str = "\n".join(f"  {name} = {pp_core(expr)}" for name, expr in bindings)
            return f"rec {{\n{binds_str}\n}}"
        case _:
            return f"<unknown binding: {b}>"


if __name__ == "__main__":
    main()
