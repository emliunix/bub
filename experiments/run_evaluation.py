#!/usr/bin/env python3
"""
Workflow DSL - Parser Evaluation Script

Runs all parser implementations against the shared test suite.
"""

import sys
import traceback
from typing import List, Tuple

# Import test infrastructure
from dsl_tests import TEST_CASES, TestCase
from dsl_ast import ast_to_dict

# Import parsers
sys.path.insert(0, "/home/liu/Documents/bub/experiments")


def test_parser(parser_file_name: str, parser_name: str) -> Tuple[int, int, List[str]]:
    """
    Test a parser implementation against all test cases.

    Args:
        parser_file_name: Name of the Python file (e.g., "dsl-parser-lark-final.py")
        parser_name: Display name for the parser

    Returns: (passed, failed, error_messages)
    """
    try:
        # Import using importlib since filenames may have hyphens
        import importlib.util
        import os

        file_path = os.path.join("/home/liu/Documents/bub/experiments", parser_file_name)
        if not os.path.exists(file_path):
            return 0, len(TEST_CASES), [f"File not found: {file_path}"]

        spec = importlib.util.spec_from_file_location("parser_module", file_path)
        if spec is None or spec.loader is None:
            return 0, len(TEST_CASES), [f"Could not load spec for {parser_file_name}"]

        parser_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(parser_module)
        WorkflowParser = parser_module.WorkflowParser
    except ImportError as e:
        return 0, len(TEST_CASES), [f"Failed to import {parser_name}: {e}"]
    except AttributeError as e:
        return 0, len(TEST_CASES), [f"{parser_name} missing WorkflowParser class: {e}"]

    passed = 0
    failed = 0
    errors = []

    try:
        parser = WorkflowParser()
    except Exception as e:
        return 0, len(TEST_CASES), [f"Failed to instantiate {parser_name}: {e}"]

    for test in TEST_CASES:
        try:
            result = parser.parse(test.input_code)

            # Compare ASTs by converting to dict
            result_dict = ast_to_dict(result)
            expected_dict = ast_to_dict(test.expected_ast)

            if result_dict == expected_dict:
                passed += 1
            else:
                failed += 1
                errors.append(f"  ❌ {test.name}: AST mismatch")
                # Show diff for debugging
                import json

                result_str = json.dumps(result_dict, indent=2)
                expected_str = json.dumps(expected_dict, indent=2)
                if result_str != expected_str:
                    errors.append(f"     Expected:\n{expected_str[:200]}...")
                    errors.append(f"     Got:\n{result_str[:200]}...")

        except Exception as e:
            failed += 1
            errors.append(f"  ❌ {test.name}: Exception - {e}")
            if "unexpected" in str(e).lower() or "error" in str(e).lower():
                # Include traceback for serious errors
                errors.append(f"     {traceback.format_exc()[:200]}")

    return passed, failed, errors


def main():
    """Run evaluation of all parsers."""
    print("=" * 70)
    print("Workflow DSL Parser Evaluation")
    print("=" * 70)
    print()

    parsers = [
        ("dsl-parser-lark-final.py", "Lark (with Indenter)"),
        ("dsl-parser-tatsu-final.py", "TatSu (PEG)"),
        ("dsl_parser_pratt_final.py", "Pratt (Hand-rolled)"),
    ]

    results = []

    for module_name, display_name in parsers:
        print(f"\n{'=' * 70}")
        print(f"Testing: {display_name}")
        print(f"{'=' * 70}")

        passed, failed, errors = test_parser(module_name, display_name)
        results.append((display_name, passed, failed, len(TEST_CASES)))

        if errors:
            for error in errors:
                print(error)

        if failed == 0:
            print(f"✅ All {passed} tests passed!")
        else:
            print(f"⚠️  {passed} passed, {failed} failed out of {len(TEST_CASES)} total")

    # Summary table
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"{'Parser':<30} {'Passed':<10} {'Failed':<10} {'Success %':<10}")
    print("-" * 70)

    for name, passed, failed, total in results:
        pct = (passed / total * 100) if total > 0 else 0
        print(f"{name:<30} {passed:<10} {failed:<10} {pct:.1f}%")

    print(f"{'=' * 70}")

    # Overall assessment
    all_passed = all(failed == 0 for _, _, failed, _ in results)
    if all_passed:
        print("\n✅ All parsers pass all tests!")
    else:
        print("\n⚠️  Some parsers have failing tests")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
