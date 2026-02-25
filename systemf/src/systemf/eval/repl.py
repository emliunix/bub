"""Interactive REPL for System F interpreter."""

import sys
from typing import Optional

from systemf.surface.lexer import Lexer
from systemf.surface.parser import Parser
from systemf.surface.elaborator import Elaborator
from systemf.core.checker import TypeChecker
from systemf.eval.machine import Evaluator
from systemf.eval.value import VClosure, VConstructor, VTypeClosure, Value


class REPL:
    """Interactive Read-Eval-Print Loop."""

    def __init__(self) -> None:
        self.elaborator = Elaborator()
        self.checker = TypeChecker()
        self.evaluator = Evaluator()
        self.environment: dict[str, Value] = {}  # For persistent definitions

    def run(self) -> None:
        """Run the REPL."""
        print("System F REPL v0.1.0")
        print("Type :quit to exit, :help for commands")
        print()

        while True:
            try:
                line = input("> ")
                if not line.strip():
                    continue

                if line.startswith(":"):
                    self.handle_command(line)
                else:
                    self.evaluate_line(line)

            except EOFError:
                print("\nGoodbye!")
                break
            except KeyboardInterrupt:
                print("\nInterrupted")
                continue
            except Exception as e:
                print(f"Error: {e}")

    def handle_command(self, line: str) -> None:
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
            case ":env":
                print("Environment:")
                for name in self.environment:
                    print(f"  {name}")
            case _:
                print(f"Unknown command: {cmd}")

    def evaluate_line(self, line: str) -> None:
        """Parse, type check, and evaluate a line of input."""
        try:
            # Parse
            tokens = Lexer(line).tokenize()
            surface_decls = Parser(tokens).parse()

            # Elaborate
            core_decls = self.elaborator.elaborate(surface_decls)

            # Type check
            types = self.checker.check_program(core_decls)

            # Evaluate
            values = self.evaluator.evaluate_program(core_decls)

            # Print results
            for name, value in values.items():
                ty = types[name]
                print(f"{name} : {ty} = {self.format_value(value)}")
                self.environment[name] = value

        except Exception as e:
            print(f"Error: {e}")

    def format_value(self, value: Value) -> str:
        """Pretty print a value."""
        match value:
            case VConstructor(name, args):
                if not args:
                    return name
                arg_strs = [self.format_value(arg) for arg in args]
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
