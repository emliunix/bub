#!/usr/bin/env python3
"""Script to load and test LLM example files in SystemF REPL."""

import sys
from pathlib import Path

# Add systemf to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from systemf.surface.lexer import Lexer
from systemf.surface.parser import Parser, parse_program, ParseError
from systemf.surface.elaborator import Elaborator
from systemf.surface.desugar import desugar
from systemf.core.checker import TypeChecker
from systemf.eval.machine import Evaluator


def test_parse_file(filepath: Path) -> bool:
    """Parse a .sf file and return success status."""
    print(f"\n{'=' * 60}")
    print(f"Testing: {filepath.name}")
    print("=" * 60)

    try:
        source = filepath.read_text()
        print(f"Source:\n{source[:500]}...")
        print()

        # Parse using the module-level function
        decls = parse_program(source)
        print(f"✓ Parsed: {len(decls)} declarations")

        # Show declarations
        for i, decl in enumerate(decls):
            print(f"  [{i}] {type(decl).__name__}", end="")
            if hasattr(decl, "name"):
                print(f": {decl.name}", end="")
            if hasattr(decl, "pragma") and decl.pragma:
                print(f" (pragma: {decl.pragma})", end="")
            print()

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_elaborate_file(filepath: Path) -> bool:
    """Elaborate a .sf file and show LLM metadata."""
    print(f"\n{'=' * 60}")
    print(f"Elaborating: {filepath.name}")
    print("=" * 60)

    try:
        source = filepath.read_text()

        # Parse
        decls = parse_program(source)

        # Elaborate
        evaluator = Evaluator()
        elaborator = Elaborator(evaluator=evaluator)
        module = elaborator.elaborate(decls)

        print(f"✓ Elaborated successfully")
        print(f"  Module: {module.name}")
        print(f"  Declarations: {len(module.declarations)}")
        print(f"  LLM functions: {len(module.llm_functions)}")

        # Show LLM metadata
        if module.llm_functions:
            print("\n  LLM Functions:")
            for name, metadata in module.llm_functions.items():
                print(f"    - {name}")
                print(f"      Model: {metadata.model}")
                print(f"      Temperature: {metadata.temperature}")
                print(f"      Docstring: {metadata.function_docstring}")
                print(f"      Args: {metadata.arg_names}")
                print(f"      Arg Docs: {metadata.arg_docstrings}")

        # Show any errors
        if module.errors:
            print(f"\n  Errors ({len(module.errors)}):")
            for err in module.errors:
                print(f"    - {err}")

        return len(module.errors) == 0

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run tests on all LLM example files."""
    test_dir = Path(__file__).parent

    test_files = [
        test_dir / "llm_examples.sf",
        test_dir / "llm_multiparam.sf",
        test_dir / "llm_complex.sf",
    ]

    print("\n" + "=" * 60)
    print("SystemF LLM Example Test Suite")
    print("=" * 60)

    all_passed = True

    # Phase 1: Parse all files
    print("\n\n📋 PHASE 1: Parsing")
    print("=" * 60)
    for filepath in test_files:
        if filepath.exists():
            if not test_parse_file(filepath):
                all_passed = False
        else:
            print(f"✗ File not found: {filepath}")
            all_passed = False

    # Phase 2: Elaborate all files
    print("\n\n📋 PHASE 2: Elaboration")
    print("=" * 60)
    for filepath in test_files:
        if filepath.exists():
            if not test_elaborate_file(filepath):
                all_passed = False

    # Summary
    print("\n\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    if all_passed:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
