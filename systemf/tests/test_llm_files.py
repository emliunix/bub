#!/usr/bin/env python3
"""Tests for LLM example .sf files.

These tests verify that LLM example files parse and elaborate correctly,
with proper LLM metadata extraction.
"""

from pathlib import Path

import pytest

from systemf.surface.parser import parse_program
from systemf.surface.elaborator import Elaborator
from systemf.eval.machine import Evaluator


# Example files to test
LLM_EXAMPLE_FILES = [
    "llm_examples.sf",
    "llm_multiparam.sf",
    "llm_complex.sf",
]


def load_primitive_types(elaborator: Elaborator) -> None:
    """Load minimal primitive types for testing."""
    source = "prim_type String\nprim_type Int"
    decls = parse_program(source)
    elaborator.elaborate(decls)


@pytest.fixture
def test_data_dir() -> Path:
    """Returns the absolute path to the directory containing test data."""
    return Path(__file__).parent


@pytest.mark.parametrize("filename", LLM_EXAMPLE_FILES)
def test_parse_llm_file(filename: str, test_data_dir: Path) -> None:
    """Test that LLM example files parse successfully."""
    filepath = test_data_dir / filename
    source = filepath.read_text()

    # Parse
    decls = parse_program(source)

    # Verify we got some declarations
    assert len(decls) > 0, f"Expected at least one declaration in {filename}"

    # Check that LLM pragmas are captured
    llm_decls = [d for d in decls if hasattr(d, "pragma") and d.pragma]
    assert len(llm_decls) > 0, f"Expected at least one LLM declaration in {filename}"


@pytest.mark.parametrize("filename", LLM_EXAMPLE_FILES)
def test_elaborate_llm_file(filename: str, test_data_dir: Path) -> None:
    """Test that LLM example files elaborate with correct metadata."""
    filepath = test_data_dir / filename
    source = filepath.read_text()

    # Parse and elaborate (with primitive types loaded)
    decls = parse_program(source)
    evaluator = Evaluator()
    elaborator = Elaborator(evaluator=evaluator)
    load_primitive_types(elaborator)
    module = elaborator.elaborate(decls)

    # Verify no errors
    assert len(module.errors) == 0, f"Elaboration errors in {filename}: {module.errors}"

    # Verify we have LLM functions
    assert len(module.llm_functions) > 0, f"Expected at least one LLM function in {filename}"

    # Verify LLM metadata structure
    for name, metadata in module.llm_functions.items():
        assert metadata.function_name == name
        assert isinstance(metadata.arg_names, list)
        assert isinstance(metadata.arg_docstrings, list)


def test_llm_examples_content(test_data_dir: Path) -> None:
    """Test specific content of llm_examples.sf."""
    filepath = test_data_dir / "llm_examples.sf"
    source = filepath.read_text()

    decls = parse_program(source)
    evaluator = Evaluator()
    elaborator = Elaborator(evaluator=evaluator)
    load_primitive_types(elaborator)
    module = elaborator.elaborate(decls)

    # Check translate function
    assert "translate" in module.llm_functions
    translate = module.llm_functions["translate"]
    assert "model=gpt-4" in translate.pragma_params
    assert "temperature=0.7" in translate.pragma_params
    assert translate.function_docstring == "Translate English to French"
    assert translate.arg_names == ["text"]
    assert translate.arg_docstrings == ["The English text to translate"]

    # Check that String is recognized as primitive type
    from systemf.core.types import PrimitiveType

    assert len(translate.arg_types) == 1
    assert isinstance(translate.arg_types[0], PrimitiveType)
    assert translate.arg_types[0].name == "String"

    # Check summarize function
    assert "summarize" in module.llm_functions
    summarize = module.llm_functions["summarize"]
    assert "model=gpt-4" in summarize.pragma_params


def test_llm_multiparam_content(test_data_dir: Path) -> None:
    """Test specific content of llm_multiparam.sf."""
    filepath = test_data_dir / "llm_multiparam.sf"
    source = filepath.read_text()

    decls = parse_program(source)
    evaluator = Evaluator()
    elaborator = Elaborator(evaluator=evaluator)
    load_primitive_types(elaborator)
    module = elaborator.elaborate(decls)

    # Check classify function
    assert "classify" in module.llm_functions
    classify = module.llm_functions["classify"]
    assert "model=gpt-4" in classify.pragma_params
    assert "temperature=0.5" in classify.pragma_params

    # Check codegen function
    assert "codegen" in module.llm_functions
    codegen = module.llm_functions["codegen"]
    assert "model=claude-sonnet" in codegen.pragma_params
    assert "temperature=0.9" in codegen.pragma_params


if __name__ == "__main__":
    # Run tests manually when executed directly
    import sys

    test_dir = Path(__file__).parent
    all_passed = True

    print("\n" + "=" * 60)
    print("SystemF LLM Example Test Suite")
    print("=" * 60)

    for filename in LLM_EXAMPLE_FILES:
        try:
            test_parse_llm_file(filename, test_dir)
            print(f"✓ {filename} parsed successfully")
        except Exception as e:
            print(f"✗ {filename} parse failed: {e}")
            import traceback

            traceback.print_exc()
            all_passed = False

        try:
            test_elaborate_llm_file(filename, test_dir)
            print(f"✓ {filename} elaborated successfully")
        except Exception as e:
            print(f"✗ {filename} elaboration failed: {e}")
            import traceback

            traceback.print_exc()
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        sys.exit(1)
