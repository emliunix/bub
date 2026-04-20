"""
Elab3 demo script: construct a REPL context and load a demo module.

Usage:
    cd systemf && uv run python -m systemf.elab3_demo
"""

from pathlib import Path

from systemf.elab3.pipeline import execute
from systemf.elab3.reader_env import ReaderEnv
from systemf.elab3.repl import REPL
from systemf.elab3.types import Module
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
    print(f"  Items: {list(demo_mod.items.keys())}")
    print(f"\n  Core terms (vals):")
    for name, term in demo_mod.vals.items():
        print(f"\n    {name.surface}:")
        for line in pp_core(term).split("\n"):
            print(f"      {line}")


if __name__ == "__main__":
    main()
