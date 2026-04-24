"""
Elab3 e2e demo: load modules via REPL, evaluate expressions via REPLSession.

Usage:
    cd systemf && uv run python -m systemf.elab3_demo
"""

from pathlib import Path

from systemf.elab3.repl import REPL
from systemf.elab3.types import Module, core
from systemf.elab3.types.core_pp import pp_core
from systemf.elab3.types.val import VLit, VData
from systemf.elab3.types.ty import LitInt, LitString


def main() -> None:
    demo_dir = Path(__file__).parent.resolve()
    search_path = str(demo_dir)

    # 1. Construct REPLContext
    ctx = REPL(search_paths=[search_path])
    print("=== Module loading ===\n")

    # 2. Load builtins first (so demo can import it)
    builtins_mod = ctx.load("builtins")
    print(f"Loaded builtins module: {builtins_mod.name}")
    print(f"  Exports: {[n.surface for n in builtins_mod.exports]}")

    # 3. Load demo module
    demo_mod = ctx.load("demo")
    print(f"\nLoaded demo module: {demo_mod.name}")
    print(f"  Exports: {[n.surface for n in demo_mod.exports]}")
    print(f"  TyThings: {[n.surface for n, _ in demo_mod.tythings]}")

    # 4. Core terms (typechecked, not yet evaluated)
    print(f"\n  Core terms (vals):")
    for binding in demo_mod.bindings:
        print(f"\n    {pp_binding_name(binding)}:")
        for line in pp_binding(binding).split("\n"):
            print(f"      {line}")

    # === e2e evaluation ===

    session = ctx.new_session()
    from systemf.elab3.reader_env import ImportSpec
    session.cmd_import(ImportSpec("demo", None, False))

    print("\n\n=== e2e evaluation ===\n")

    def check(expr: str, expected_val, msg: str | None = None):
        ty, val = session.eval(expr)
        assert val == expected_val, f"for {expr}: expected {expected_val}, got {val}"
        label = msg or expr
        print(f">> {label}")
        print(f"  {session.pp_val(ty, val)}  ✓")

    check("1", VLit(LitInt(1)))
    check("True", VData(0, []))
    check("id 42", VLit(LitInt(42)))
    check("1 + 2", VLit(LitInt(3)))
    check("const 1 2", VLit(LitInt(1)))
    check("not True", VData(1, []))
    check("not False", VData(0, []))
    check("compose (\\x -> x + 1) (\\x -> x * 2) 3", VLit(LitInt(7)))
    check("twice (\\x -> x + 1) 0", VLit(LitInt(2)))
    check('greet "world"', VLit(LitString("hello world")))
    check('greet "there"', VLit(LitString("hello there")))
    check("even 4", VData(0, []))
    check("even 3", VData(1, []))
    check("odd 3", VData(0, []))
    check("odd 4", VData(1, []))
    check("testConstMono", VLit(LitInt(1)))
    check("fromMaybe 0 (Just 42)", VLit(LitInt(42)))
    check("fromMaybe 0 Nothing", VLit(LitInt(0)))

    print("\nAll e2e assertions passed.")


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
