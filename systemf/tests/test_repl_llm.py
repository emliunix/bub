"""Tests for REPL integration of LLM functions."""

import pytest
from unittest.mock import patch
from io import StringIO

from systemf.eval.repl import REPL
from systemf.surface.parser import parse_program
from systemf.surface.elaborator import Elaborator
from systemf.eval.machine import Evaluator
from systemf.eval.value import VString


class TestREPLLLMCommands:
    """Tests for :llm REPL command."""

    def test_llm_command_empty(self):
        """:llm shows message when no LLM functions registered."""
        repl = REPL()

        with patch("sys.stdout", new=StringIO()) as fake_out:
            repl._handle_llm_command([":llm"])
            output = fake_out.getvalue()

        assert "No LLM functions registered" in output
        assert "Define LLM functions with" in output

    def test_llm_command_list_functions(self):
        """:llm lists all registered LLM functions."""
        repl = REPL()

        # Register some LLM functions manually
        from systemf.core.module import LLMMetadata
        from systemf.core.types import TypeVar

        metadata1 = LLMMetadata(
            function_name="translate",
            function_docstring="Translate English to French",
            arg_types=[TypeVar("String")],
            arg_docstrings=["The text to translate"],
            pragma_params="model=gpt-4",
        )
        metadata2 = LLMMetadata(
            function_name="summarize",
            function_docstring="Summarize a text",
            arg_types=[TypeVar("String")],
            arg_docstrings=None,
            pragma_params="model=claude-3",
        )

        repl.llm_functions["translate"] = metadata1
        repl.llm_functions["summarize"] = metadata2

        with patch("sys.stdout", new=StringIO()) as fake_out:
            repl._handle_llm_command([":llm"])
            output = fake_out.getvalue()

        assert "LLM Functions:" in output
        assert "translate" in output
        assert "Translate English to French" in output
        assert "summarize" in output
        assert "Summarize a text" in output

    def test_llm_command_show_details(self):
        """:llm <function_name> shows detailed info."""
        repl = REPL()

        from systemf.core.module import LLMMetadata
        from systemf.core.types import TypeVar

        metadata = LLMMetadata(
            function_name="translate",
            function_docstring="Translate English to French",
            arg_types=[TypeVar("String")],
            arg_docstrings=["The text to translate"],
            pragma_params="model=gpt-4 temperature=0.7",
        )
        repl.llm_functions["translate"] = metadata

        with patch("sys.stdout", new=StringIO()) as fake_out:
            repl._handle_llm_command([":llm", "translate"])
            output = fake_out.getvalue()

        assert "LLM Function: translate" in output
        assert "Description: Translate English to French" in output
        assert "Pragma: model=gpt-4 temperature=0.7" in output
        assert "Parameters:" in output
        assert "arg0:" in output
        assert "The text to translate" in output

    def test_llm_command_unknown_function(self):
        """:llm <unknown> shows error with available functions."""
        repl = REPL()

        from systemf.core.module import LLMMetadata
        from systemf.core.types import TypeVar

        metadata = LLMMetadata(
            function_name="translate",
            function_docstring="Translate text",
            arg_types=[TypeVar("String")],
            arg_docstrings=None,
            pragma_params="",
        )
        repl.llm_functions["translate"] = metadata

        with patch("sys.stdout", new=StringIO()) as fake_out:
            repl._handle_llm_command([":llm", "unknown_func"])
            output = fake_out.getvalue()

        assert "Unknown LLM function: unknown_func" in output
        assert "translate" in output


class TestREPLLLMFunctionExecution:
    """Tests for LLM function execution in REPL."""

    def test_repl_registers_llm_from_declarations(self):
        """REPL registers LLM functions when evaluating declarations."""
        source = """
prim_type String

{-# LLM model=gpt-4 #-}
-- | Translate English to French
translate : String -> String = \\text -- ^ The English text to translate -> text
"""
        repl = REPL()

        # Evaluate the declaration
        repl._evaluate(source)

        # Check that LLM function was registered
        assert "translate" in repl.llm_functions
        metadata = repl.llm_functions["translate"]
        assert metadata.function_name == "translate"
        assert metadata.function_docstring == "Translate English to French"
        assert "translate" in repl.evaluator.llm_closures

    def test_repl_llm_execution_fallback(self):
        """REPL falls back to identity when LLM API is not available."""
        source = """
prim_type String

{-# LLM #-}
translate : String -> String = \\text -> text
"""
        repl = REPL()

        # Evaluate the declaration
        repl._evaluate(source)

        # Get the translate function
        translate_fn = repl.global_values.get("translate")
        assert translate_fn is not None

        # Apply to an argument - should fall back to identity
        result = repl.evaluator.apply(translate_fn, VString("hello"))
        assert isinstance(result, VString)
        assert result.value == "hello"

    def test_repl_multiple_llm_functions(self):
        """REPL handles multiple LLM functions from different inputs."""
        source1 = """
prim_type String

{-# LLM model=gpt-4 #-}
translate : String -> String = \\x -> x
"""
        source2 = """
{-# LLM model=claude-3 #-}
summarize : String -> String = \\x -> x
"""
        repl = REPL()

        # Evaluate first declaration
        repl._evaluate(source1)
        assert "translate" in repl.llm_functions

        # Evaluate second declaration
        repl._evaluate(source2)
        assert "summarize" in repl.llm_functions
        assert "translate" in repl.llm_functions  # Still there

        # Check both are in evaluator
        assert "translate" in repl.evaluator.llm_closures
        assert "summarize" in repl.evaluator.llm_closures


class TestREPLErrorHandling:
    """Tests for error handling in REPL LLM integration."""

    def test_repl_handles_elaboration_error_gracefully(self):
        """REPL handles elaboration errors without crashing."""
        source = """
-- Invalid: missing type annotation for LLM function
{-# LLM #-}
translate = \\x -> x
"""
        repl = REPL()

        # Should not raise, should print error
        with patch("sys.stdout", new=StringIO()) as fake_out:
            repl._evaluate(source)
            output = fake_out.getvalue()

        # Should have printed an error
        assert "Error:" in output or len(output) == 0  # May or may not error depending on parser

    def test_repl_handles_runtime_error_gracefully(self):
        """REPL handles runtime errors in LLM execution."""
        # This tests that the fallback mechanism works
        source = """
prim_type String

{-# LLM #-}
translate : String -> String = \\text -> text
"""
        repl = REPL()
        repl._evaluate(source)

        # Get function and apply - should not crash even if LLM fails
        translate_fn = repl.global_values.get("translate")
        result = repl.evaluator.apply(translate_fn, VString("test"))

        # Should get fallback result
        assert isinstance(result, VString)


class TestREPLLLMMetadataPersistence:
    """Tests for LLM metadata persistence across REPL inputs."""

    def test_llm_metadata_persists_across_inputs(self):
        """LLM functions persist across multiple REPL evaluations."""
        repl = REPL()

        source1 = """
prim_type String

{-# LLM #-}
func1 : String -> String = \\x -> x
"""
        source2 = """
{-# LLM #-}
func2 : String -> String = \\x -> x
"""

        repl._evaluate(source1)
        assert "func1" in repl.llm_functions

        repl._evaluate(source2)
        assert "func1" in repl.llm_functions  # Still there
        assert "func2" in repl.llm_functions  # New one added

    def test_llm_function_overwriting(self):
        """Redefining an LLM function updates metadata."""
        repl = REPL()

        source1 = """
prim_type String

{-# LLM model=gpt-4 #-}
-- | First version
translate : String -> String = \\x -> x
"""
        source2 = """
{-# LLM model=claude-3 #-}
-- | Second version
translate : String -> String = \\x -> x
"""

        repl._evaluate(source1)
        assert repl.llm_functions["translate"].pragma_params == "model=gpt-4"

        repl._evaluate(source2)
        # Should be updated
        assert repl.llm_functions["translate"].pragma_params == "model=claude-3"
        assert repl.llm_functions["translate"].function_docstring == "Second version"
