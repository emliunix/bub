"""Tests for LLM integration in System F.

Tests the full pipeline:
1. Parser recognizes -- ^ style parameter docstrings
2. Elaborator detects LLM pragma and creates closures
3. Evaluator can execute LLM primitives
"""

import os
import pytest

from systemf.surface.parser import parse_program
from systemf.surface.elaborator import elaborate, Elaborator
from systemf.surface.ast import SurfaceTermDeclaration, SurfaceAbs
from systemf.eval.machine import Evaluator


class TestLLMParser:
    """Tests for LLM-related parser features."""

    def test_param_docstring_in_lambda(self):
        """Parser captures -- ^ style parameter docstrings."""
        source = r"""
translate = \text -- ^ The English text to translate -> text
"""
        decls = parse_program(source)
        assert len(decls) == 1
        decl = decls[0]

        assert isinstance(decl, SurfaceTermDeclaration)
        assert isinstance(decl.body, SurfaceAbs)
        assert len(decl.body.param_docstrings) == 1
        assert decl.body.param_docstrings[0] == "The English text to translate"

    def test_no_param_docstring(self):
        """Lambda without param docstring has empty list."""
        source = r"""
identity = \x -> x
"""
        decls = parse_program(source)
        assert len(decls) == 1
        decl = decls[0]

        assert isinstance(decl, SurfaceTermDeclaration)
        assert isinstance(decl.body, SurfaceAbs)
        assert len(decl.body.param_docstrings) == 0


class TestLLMElaborator:
    """Tests for LLM elaboration."""

    def test_llm_pragma_detection(self):
        """Elaborator detects LLM pragma on term declarations."""
        source = r"""
{-# LLM model=gpt-4 temperature=0.7 #-}
-- | Translate English to French
translate : String -> String
translate = \text -- ^ The English text to translate -> text
"""
        decls = parse_program(source)
        evaluator = Evaluator()
        elab = Elaborator(evaluator=evaluator)
        module = elab.elaborate(decls)

        # Check that LLM metadata was created
        assert "translate" in module.llm_functions
        metadata = module.llm_functions["translate"]
        assert metadata.function_name == "translate"
        assert metadata.function_docstring == "Translate English to French"
        assert metadata.arg_names == ["text"]
        assert metadata.arg_docstrings == ["The English text to translate"]
        assert metadata.model == "gpt-4"
        assert metadata.temperature == 0.7

    def test_llm_body_is_primop(self):
        """LLM function body is elaborated to PrimOp."""
        source = r"""
{-# LLM #-}
translate = \text -> text
"""
        decls = parse_program(source)
        evaluator = Evaluator()
        elab = Elaborator(evaluator=evaluator)
        module = elab.elaborate(decls)

        # Check the declaration body is a PrimOp
        from systemf.core.ast import TermDeclaration, PrimOp

        decl = module.declarations[0]
        assert isinstance(decl, TermDeclaration)
        assert isinstance(decl.body, PrimOp)
        assert decl.body.name == "llm.translate"

    def test_non_llm_declaration_unchanged(self):
        """Non-LLM declarations are processed normally."""
        source = r"""
identity = \x -> x
"""
        decls = parse_program(source)
        evaluator = Evaluator()
        elab = Elaborator(evaluator=evaluator)
        module = elab.elaborate(decls)

        # No LLM functions registered
        assert len(module.llm_functions) == 0

        # Declaration is normal lambda
        from systemf.core.ast import TermDeclaration, Abs

        decl = module.declarations[0]
        assert isinstance(decl, TermDeclaration)
        assert isinstance(decl.body, Abs)


class TestLLMEvaluator:
    """Tests for LLM evaluation (with mocked API calls)."""

    def test_llm_closure_registration(self):
        """Evaluator registers LLM closures correctly."""
        source = r"""
{-# LLM model=gpt-4 #-}
translate = \text -> text
"""
        decls = parse_program(source)
        evaluator = Evaluator()
        elab = Elaborator(evaluator=evaluator)
        elab.elaborate(decls)

        # Check that closure was registered in evaluator
        assert "translate" in evaluator.llm_closures
        metadata, closure = evaluator.llm_closures["translate"]
        assert metadata.function_name == "translate"

    def test_llm_fallback_without_api_key(self):
        """LLM call falls back to identity when API key is missing."""
        source = r"""
{-# LLM #-}
translate = \text -> text
"""
        decls = parse_program(source)
        evaluator = Evaluator()
        elab = Elaborator(evaluator=evaluator)
        module = elab.elaborate(decls)

        # Evaluate the translate function
        from systemf.eval.value import VString

        evaluator.evaluate_program(module.declarations)

        # Get the translate function from global env
        translate_fn = evaluator.global_env.get("translate")
        assert translate_fn is not None

        # Apply to an argument - should fall back to identity (return the argument)
        result = evaluator.apply(translate_fn, VString("hello"))
        # Should return the input unchanged due to fallback
        assert isinstance(result, VString)
        assert result.value == "hello"

    def test_prompt_crafting(self):
        """Prompt is crafted correctly from metadata."""
        from systemf.core.module import LLMMetadata
        from systemf.core.types import TypeVar
        from systemf.eval.value import VString

        evaluator = Evaluator()

        metadata = LLMMetadata(
            function_name="translate",
            function_docstring="Translate English to French",
            arg_names=["text"],
            arg_types=[TypeVar("String")],
            arg_docstrings=["The English text to translate"],
            model="gpt-4",
            temperature=0.7,
        )

        prompt = evaluator._craft_prompt(metadata, VString("hello world"))

        assert "Translate English to French" in prompt
        assert "text" in prompt
        assert "The English text to translate" in prompt
        assert "hello world" in prompt


class TestLLMIntegration:
    """End-to-end integration tests."""

    def test_full_llm_declaration_pipeline(self):
        """Complete pipeline from parsing to evaluation setup."""
        source = r"""
{-# LLM model=gpt-4 temperature=0.7 #-}
-- | Translate English to French
translate : String -> String
translate = \text -- ^ The English text to translate -> text
"""
        # Parse
        decls = parse_program(source)
        assert len(decls) == 1

        # Elaborate with evaluator
        evaluator = Evaluator()
        module = elaborate(decls, evaluator=evaluator)

        # Check module has LLM metadata
        assert "translate" in module.llm_functions

        # Check evaluator has closure
        assert "translate" in evaluator.llm_closures

        # Check declaration is a PrimOp
        from systemf.core.ast import TermDeclaration, PrimOp

        decl = module.declarations[0]
        assert isinstance(decl, TermDeclaration)
        assert isinstance(decl.body, PrimOp)


def elaborate(decls, evaluator=None):
    """Helper to elaborate with optional evaluator."""
    elab = Elaborator(evaluator=evaluator)
    return elab.elaborate(decls)


class TestDocstringStyles:
    """Tests for different docstring styles."""

    def test_preceding_docstring_pipe_style(self):
        """Function docstring with -- | before declaration works."""
        source = r"""
-- | Translate English to French
translate : String -> String
translate = \text -> text
"""
        decls = parse_program(source)
        assert len(decls) == 1
        decl = decls[0]

        assert isinstance(decl, SurfaceTermDeclaration)
        assert decl.docstring == "Translate English to French"

    def test_trailing_docstring_caret_style_after_body(self):
        """Function docstring with -- ^ after body (parameter docstring)."""
        source = r"""
translate : String -> String
translate = \text -- ^ The English text to translate -> text
"""
        decls = parse_program(source)
        assert len(decls) == 1
        decl = decls[0]

        assert isinstance(decl, SurfaceTermDeclaration)
        assert decl.docstring is None  # Function-level docstring not set
        # But parameter docstring is captured in the lambda
        assert isinstance(decl.body, SurfaceAbs)
        assert decl.body.param_docstrings == ["The English text to translate"]

    def test_both_docstring_styles_together(self):
        """Both -- | (function) and -- ^ (parameter) docstrings work together."""
        source = r"""
{-# LLM model=gpt-4 temperature=0.7 #-}
-- | Translate English to French
translate : String -> String
translate = \text -- ^ The English text to translate -> text
"""
        decls = parse_program(source)
        evaluator = Evaluator()
        elab = Elaborator(evaluator=evaluator)
        module = elab.elaborate(decls)

        # Check function docstring captured
        metadata = module.llm_functions["translate"]
        assert metadata.function_docstring == "Translate English to French"
        # Check parameter docstring captured
        assert metadata.arg_docstrings == ["The English text to translate"]

    @pytest.mark.xfail(
        reason="Trailing docstring style not yet supported - requires docstring_processor pass"
    )
    def test_llm_pragma_with_trailing_docstring_style(self):
        """TODO: -- ^ after signature should work as function docstring.

        This test documents the expected behavior once we implement
        the docstring attachment pass. Currently this style is NOT
        supported - only -- | before the declaration works.

        Syntax that should work:
        {-# LLM model=gpt-4 temperature=0.7 #-}
        translate : String -> String
        -- ^ Translate English to French
        translate = \text -> text

        But currently fails to parse because the parser doesn't handle
        standalone docstring lines between type signature and definition.
        """
        source = r"""
{-# LLM model=gpt-4 temperature=0.7 #-}
translate : String -> String
-- ^ Translate English to French
translate = \text -> text
"""
        # This will raise ParseError because the parser can't handle
        # standalone -- ^ lines between type signature and body
        decls = parse_program(source)

        # If parsing succeeds (once we implement the feature):
        assert len(decls) == 1
        decl = decls[0]
        assert isinstance(decl, SurfaceTermDeclaration)
        # The trailing docstring should be captured
        assert decl.docstring == "Translate English to French"
