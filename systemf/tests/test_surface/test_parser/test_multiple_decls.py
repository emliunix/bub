"""Tests for parsing multiple declarations with fixtures.

Uses conftest.py fixtures to test complex multi-declaration programs.
"""

import pytest
from systemf.surface.parser import parse_program, lex
from systemf.surface.types import (
    SurfaceDataDeclaration,
    SurfaceTermDeclaration,
    SurfacePrimTypeDecl,
    SurfacePrimOpDecl,
)


class TestMultipleDeclarationsParsing:
    """Test parsing programs with multiple declarations using fixtures."""

    def test_simple_multiple_decls(self, simple_multiple_decls):
        """Parse simple multiple declarations without docstrings."""
        result = parse_program(simple_multiple_decls)

        assert result is not None
        assert len(result) == 3

        assert isinstance(result[0], SurfaceDataDeclaration)
        assert result[0].name == "Bool"

        assert isinstance(result[1], SurfaceDataDeclaration)
        assert result[1].name == "Maybe"

        assert isinstance(result[2], SurfaceTermDeclaration)
        assert result[2].name == "not"

    def test_bool_with_tostring(self, bool_with_tostring):
        """Parse Bool type with toString function."""
        result = parse_program(bool_with_tostring)

        assert result is not None
        assert len(result) == 2

        # First declaration: Bool data type
        assert isinstance(result[0], SurfaceDataDeclaration)
        assert result[0].name == "Bool"
        assert result[0].docstring == "Boolean type with two values"

        # Second declaration: toString function
        assert isinstance(result[1], SurfaceTermDeclaration)
        assert result[1].name == "toString"
        assert result[1].docstring == 'Convert Bool to String\nReturns "true" or "false"'

    def test_rank2_const_function(self, rank2_const_function):
        """Parse rank-2 polymorphic const function."""
        result = parse_program(rank2_const_function)

        assert result is not None
        assert len(result) == 1

        assert isinstance(result[0], SurfaceTermDeclaration)
        assert result[0].name == "const"
        assert "constant function" in result[0].docstring
        assert "rank-2" in result[0].docstring

    def test_maybe_with_frommaybe(self, maybe_type_with_frommaybe):
        """Parse Maybe type with fromMaybe function."""
        result = parse_program(maybe_type_with_frommaybe)

        assert result is not None
        assert len(result) == 2

        assert isinstance(result[0], SurfaceDataDeclaration)
        assert result[0].name == "Maybe"
        assert result[0].docstring == "Maybe type representing optional values"

        assert isinstance(result[1], SurfaceTermDeclaration)
        assert result[1].name == "fromMaybe"
        assert "Extract value" in result[1].docstring

    def test_natural_numbers(self, natural_numbers_with_conversion):
        """Parse natural numbers with conversion function."""
        result = parse_program(natural_numbers_with_conversion)

        assert result is not None
        assert len(result) == 2

        assert isinstance(result[0], SurfaceDataDeclaration)
        assert result[0].name == "Nat"

        assert isinstance(result[1], SurfaceTermDeclaration)
        assert result[1].name == "natToInt"

    def test_list_with_length(self, list_type_with_length):
        """Parse List type with length function."""
        result = parse_program(list_type_with_length)

        assert result is not None
        assert len(result) == 2

        assert isinstance(result[0], SurfaceDataDeclaration)
        assert result[0].name == "List"

        assert isinstance(result[1], SurfaceTermDeclaration)
        assert result[1].name == "length"

    def test_llm_with_pragma(self, llm_function_with_pragma):
        """Parse LLM function with pragma."""
        result = parse_program(llm_function_with_pragma)

        assert result is not None
        assert len(result) == 1

        decl = result[0]
        assert isinstance(decl, SurfaceTermDeclaration)
        assert decl.name == "translate"
        assert decl.docstring == "Translate English to French"
        assert decl.pragma is not None
        assert "LLM" in decl.pragma
        assert "model=gpt-4" in decl.pragma["LLM"]

    def test_complete_prelude(self, complete_prelude_subset):
        """Parse complete prelude subset with all features."""
        result = parse_program(complete_prelude_subset)

        assert result is not None
        assert len(result) == 9

        # Check all declarations are present
        names = [d.name for d in result]
        assert "Bool" in names
        assert "toString" in names
        assert "const" in names
        assert "Maybe" in names
        assert "fromMaybe" in names
        assert "Nat" in names
        assert "natToInt" in names
        assert "List" in names
        assert "length" in names

        # Check docstrings are preserved
        bool_decl = next(d for d in result if d.name == "Bool")
        assert bool_decl.docstring == "Boolean type with two values"

        const_decl = next(d for d in result if d.name == "const")
        assert "constant function" in const_decl.docstring

    def test_prim_op_no_body(self, term_without_body):
        """Parse prim_op declaration (signature only, no body)."""
        result = parse_program(term_without_body)

        assert result is not None
        assert len(result) == 1

        assert isinstance(result[0], SurfacePrimOpDecl)
        assert result[0].name == "int_plus"
        assert result[0].docstring == "Integer addition primitive"

    def test_mixed_declarations(self, mixed_declarations):
        """Parse mix of all declaration types."""
        result = parse_program(mixed_declarations)

        assert result is not None
        assert len(result) == 4

        assert isinstance(result[0], SurfaceDataDeclaration)
        assert result[0].name == "Bool"

        assert isinstance(result[1], SurfacePrimTypeDecl)
        assert result[1].name == "Int"

        assert isinstance(result[2], SurfacePrimOpDecl)
        assert result[2].name == "int_plus"

        assert isinstance(result[3], SurfaceTermDeclaration)
        assert result[3].name == "not"


class TestDeclarationMetadata:
    """Test that docstrings and pragmas are correctly attached."""

    def test_multiline_docstring_concatenation(self):
        """Multiple -- | lines should be concatenated with newlines (Idris2-style)."""
        source = """-- | First line of doc
-- | Second line of doc
data Test = A | B"""

        result = parse_program(source)
        assert result[0].docstring == "First line of doc\nSecond line of doc"

    def test_pragma_parsed_as_dict(self):
        """Pragma should be parsed into dict[str, str]."""
        source = """{-# LLM model=gpt-4 temperature=0.7 #-}
test : Int = 1"""

        result = parse_program(source)
        assert result[0].pragma == {"LLM": "model=gpt-4 temperature=0.7"}

    def test_multiple_pragmas(self):
        """Multiple pragmas should be merged."""
        source = """{-# INLINE #-}
{-# LLM model=gpt-4 #-}
test : Int = 1"""

        result = parse_program(source)
        assert "INLINE" in result[0].pragma
        assert "LLM" in result[0].pragma

    def test_empty_docstring(self):
        """Empty docstring (just -- |) should be empty string."""
        source = """-- |
data Test = A"""

        result = parse_program(source)
        assert result[0].docstring == ""

    def test_no_docstring_no_pragma(self):
        """Declaration without docstring or pragma should have None."""
        source = "data Bool = True | False"

        result = parse_program(source)
        assert result[0].docstring is None
        assert result[0].pragma is None
