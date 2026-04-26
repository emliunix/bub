"""
Interactive REPL driver for elab3.

Supports:
  - Expression evaluation: <expr>
  - Multi-line input: :{ ... :}
  - Import: :import <module>
  - Quit: :quit, :q

Usage:
    cd systemf && uv run python -m systemf.elab3.repl_driver
"""

import readline  # noqa: F401 — hooks into input() for line editing + history
import sys

from pathlib import Path

from systemf.elab3.repl import REPL
from systemf.elab3.reader_env import ImportSpec
from systemf.elab3.types.ast import ImportDecl
from systemf.elab3.val_pp import pp_val
from systemf.surface.parser import import_decl_parser, lex
from parsy import eof


PROMPT = ">> "
CONTINUE_PROMPT = ".. "


def _make_session(search_paths: list[str] | None = None):
    if search_paths is None:
        search_paths = [str(Path(__file__).resolve().parent.parent)]
    ctx = REPL(search_paths=search_paths)
    session = ctx.new_session()
    return ctx, session


def _parse_import(line: str) -> ImportDecl | None:
    try:
        tokens = list(lex(line, "<repl import>"))
        imp = (import_decl_parser() << eof).parse(tokens)
    except Exception:
        return None
    if imp is None:
        return None
    return ImportDecl(
        module=imp.module,
        qualified=imp.qualified,
        alias=imp.alias,
        import_items=imp.items if not imp.hiding else None,
        hiding_items=imp.items if imp.hiding else None,
    )


def _handle_import(session, import_text: str) -> None:
    import_line = f"import {import_text}"
    decl = _parse_import(import_line)
    if decl is None:
        print(f"*** invalid import: {import_text}")
        return
    session.cmd_import(ImportSpec(decl.module, decl.alias, decl.qualified))
    print(f"imported {decl.module}")


def _handle_eval(session, input_text: str) -> None:
    try:
        match session.eval(input_text):
            case (val, ty):
                print(pp_val(session, val, ty))
    except Exception as e:
        print(f"*** {e}")
        return


def _read_multiline():
    lines: list[str] = []
    while True:
        try:
            line = input(CONTINUE_PROMPT)
        except EOFError:
            break
        stripped = line.strip()
        if stripped == ":}":
            break
        lines.append(line)
    return "\n".join(lines)


def _repl_loop(session) -> None:
    while True:
        try:
            line = input(PROMPT)
        except (EOFError, KeyboardInterrupt):
            print()
            break

        stripped = line.strip()
        if not stripped:
            continue

        if stripped in (":quit", ":q"):
            break

        if stripped == ":{":
            text = _read_multiline()
            if text.strip():
                _handle_eval(session, text)
            continue

        if stripped.startswith(":import "):
            import_text = stripped[len(":import "):].strip()
            if import_text:
                try:
                    _handle_import(session, import_text)
                except Exception as e:
                    print(f"*** {e}")
            else:
                print("*** :import requires a module name")
            continue

        if stripped.startswith(":"):
            print(f"*** unknown command: {stripped}")
            print("    :import <module>  :{ ... :}  :quit")
            continue

        _handle_eval(session, stripped)


def main() -> None:
    search_paths = sys.argv[1:] if len(sys.argv) > 1 else None
    ctx, session = _make_session(search_paths)
    print("elab3 repl  (:import <mod>  :{ .. :}  :quit)")
    _repl_loop(session)


if __name__ == "__main__":
    main()
