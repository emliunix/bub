"""Interactive REPL for System F interpreter."""

import atexit
import os
import readline
import sys
from pathlib import Path

from systemf.surface.lexer import Lexer
from systemf.surface.parser import Parser, ParseError
from systemf.surface.elaborator import Elaborator
from systemf.surface.desugar import desugar
from systemf.core.checker import TypeChecker
from systemf.core.context import Context
from systemf.core.types import Type
from systemf.eval.machine import Evaluator
from systemf.eval.value import VClosure, VConstructor, VTypeClosure, Value


class REPL:
    """Interactive Read-Eval-Print Loop."""

    HISTORY_FILE = Path.home() / ".systemf_history"
    MAX_HISTORY = 1000
    PRELUDE_FILE = Path(__file__).parent.parent.parent.parent / "prelude.sf"

    def __init__(self) -> None:
        # Persistent environments across REPL inputs
        self.global_values: dict[str, Value] = {}
        self.constructor_types: dict[str, Type] = {}
        self.global_terms: set[str] = set()

        # Initialize elaborator first (it creates its own constructor_types, primitive_types, and global_types)
        self.elaborator = Elaborator()
        # Share the elaborator's global_types so prim_op declarations are visible to checker
        self.global_types = self.elaborator.global_types
        # Share the elaborator's registries with the checker
        self.checker = TypeChecker(
            datatype_constructors=self.elaborator.constructor_types,
            global_types=self.global_types,
            primitive_types=self.elaborator.primitive_types,  # type: ignore[arg-type]
        )
        self.evaluator = Evaluator(global_env=self.global_values)

        self.multiline_buffer: list[str] = []
        self.in_multiline = False

        # Setup readline
        self._setup_readline()

    def _setup_readline(self) -> None:
        """Configure readline for better editing experience."""
        # Load history file
        if self.HISTORY_FILE.exists():
            try:
                readline.read_history_file(str(self.HISTORY_FILE))
            except Exception:
                pass  # History file might be corrupted

        # Set history length limit
        readline.set_history_length(self.MAX_HISTORY)

        # Save history on exit
        atexit.register(self._save_history)

        # Configure tab completion
        readline.set_completer(self._completer)
        readline.parse_and_bind("tab: complete")

        # Set editing mode (check for libedit on macOS)
        if readline.__doc__ and "libedit" in readline.__doc__:
            # macOS libedit
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            # GNU readline
            readline.parse_and_bind("set editing-mode emacs")

        # Set word delimiters (don't break on unicode arrows)
        readline.set_completer_delims(" \t\n`!@#$^&*()=+[{]}|;'\",<>?")

    def _save_history(self) -> None:
        """Save command history to file."""
        try:
            readline.write_history_file(str(self.HISTORY_FILE))
        except Exception:
            pass  # Ignore write errors

    def _completer(self, text: str, state: int) -> str | None:
        """Tab completion for REPL commands and identifiers."""
        # Commands that start with ':'
        commands = [":quit", ":q", ":help", ":h", ":env", ":{", ":}"]

        # Add global identifiers
        identifiers = list(self.global_terms)

        # Filter matches
        all_options = commands + identifiers
        matches = [opt for opt in all_options if opt.startswith(text)]

        if state < len(matches):
            return matches[state]
        return None

    def _load_prelude(self) -> None:
        """Load the prelude file if it exists."""
        if not self.PRELUDE_FILE.exists():
            return

        try:
            source = self.PRELUDE_FILE.read_text()
            if not source.strip():
                return

            # Clear local term environment before loading prelude
            self.elaborator.term_env = {}

            tokens = Lexer(source, filename=str(self.PRELUDE_FILE)).tokenize()
            surface_decls = Parser(tokens).parse()
            core_decls = self.elaborator.elaborate(surface_decls)
            types = self.checker.check_program(core_decls)
            values = self.evaluator.evaluate_program(core_decls)

            # Update environments with prelude definitions
            for name, value in values.items():
                self.global_values[name] = value
                self.global_types[name] = types[name]
                self.global_terms.add(name)
                self.elaborator.global_terms.add(name)

            print(f"Loaded prelude: {len(values)} definitions")

        except Exception as e:
            print(f"Warning: Could not load prelude: {e}")

    def run(self) -> None:
        """Run the REPL."""
        print("System F REPL v0.1.0")
        print("Type :quit to exit, :help for commands")
        print("Use :{ to start multiline input, :} to finish")
        print()

        # Load prelude
        self._load_prelude()
        print()

        while True:
            try:
                prompt = "| " if self.in_multiline else "> "
                line = input(prompt)

                if self.in_multiline:
                    if line.strip() == ":}":
                        self._end_multiline()
                    else:
                        self.multiline_buffer.append(line)
                else:
                    if not line.strip():
                        continue
                    if line.startswith(":"):
                        self._handle_command(line)
                    else:
                        self._evaluate(line)

            except EOFError:
                print("\nGoodbye!")
                break
            except KeyboardInterrupt:
                if self.in_multiline:
                    print("\nCancelled multiline input")
                    self.multiline_buffer = []
                    self.in_multiline = False
                else:
                    print("\nInterrupted")

    def _handle_command(self, line: str) -> None:
        """Handle REPL commands starting with :"""
        parts = line.split()
        cmd = parts[0]

        match cmd:
            case ":quit" | ":q":
                print("Goodbye!")
                sys.exit(0)
            case ":help" | ":h":
                print("Commands:")
                print("  :quit, :q    Exit REPL")
                print("  :help, :h    Show this help")
                print("  :env         Show current environment")
                print("  :{           Start multiline input")
                print("  :}           End multiline input")
                print()
                print("You can enter:")
                print("  - Declarations:  x : Bool = True")
                print("  - Expressions:   id [Bool] True")
                print()
                print("Examples:")
                print("  > id : ∀a. a → a = Λa. λx → x")
                print("  > id [Bool] True")
                print("  it : Bool = True")
                print()
                print("  > :{")
                print("  | not : Bool → Bool = λb →")
                print("  |   case b of")
                print("  |     True → False")
                print("  |     False → True")
                print("  | :}")
                print()
                print("Unicode: ∀ → λ Λ")
            case ":env":
                print("Environment:")
                for name in self.global_values:
                    print(f"  {name}")
            case ":{":
                self.in_multiline = True
                self.multiline_buffer = []
            case ":}":
                print("Error: Not in multiline mode (use :{ first)")
            case _:
                print(f"Unknown command: {cmd}")

    def _end_multiline(self) -> None:
        """End multiline mode and evaluate accumulated input."""
        self.in_multiline = False
        source = "\n".join(self.multiline_buffer)
        self.multiline_buffer = []
        if source.strip():
            self._evaluate(source)

    def _evaluate(self, source: str) -> None:
        """Parse, type check, and evaluate source code.

        First tries to parse as declarations, then falls back to expressions.
        """
        try:
            # Clear local term environment before each input (globals persist via global_terms)
            self.elaborator.term_env = {}

            tokens = Lexer(source).tokenize()

            # Try parsing as declarations first
            try:
                surface_decls = Parser(tokens).parse()
                core_decls = self.elaborator.elaborate(surface_decls)
                types = self.checker.check_program(core_decls)
                values = self.evaluator.evaluate_program(core_decls)

                for name, value in values.items():
                    ty = types[name]
                    print(f"{name} : {ty} = {self._format_value(value)}")
                    # Update persistent environments
                    self.global_values[name] = value
                    self.global_types[name] = ty
                    self.global_terms.add(name)
                    self.elaborator.global_terms.add(name)

            except ParseError:
                # If declaration parsing fails, try as expression
                # Re-tokenize for expression parsing
                tokens = Lexer(source).tokenize()
                surface_term = Parser(tokens).parse_term()

                # Desugar operators before elaboration
                surface_term = desugar(surface_term)

                # Elaborate the expression
                core_term = self.elaborator.elaborate_term(surface_term)

                # Type check the expression
                ctx = Context.empty()
                ty = self.checker.infer(ctx, core_term)

                # Evaluate the expression
                value = self.evaluator.evaluate(core_term)

                # Store as 'it'
                self.global_values["it"] = value
                self.global_types["it"] = ty
                self.global_terms.add("it")
                self.elaborator.global_terms.add("it")

                print(f"it : {ty} = {self._format_value(value)}")

        except Exception as e:
            print(f"\nError: {e}")

    def _format_value(self, value: Value) -> str:
        """Pretty print a value."""
        match value:
            case VConstructor(name, args):
                if not args:
                    return name
                arg_strs = [self._format_value(arg) for arg in args]
                return f"({name} {' '.join(arg_strs)})"
            case VClosure(_, _):
                return "<function>"
            case VTypeClosure(_, _):
                return "<type-function>"
            case _:
                return str(value)


def main() -> None:
    """Entry point for REPL."""
    repl = REPL()
    repl.run()


if __name__ == "__main__":
    main()
