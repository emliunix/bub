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
test :: Int = 1"""

        result = parse_program(source)
        assert result[0].pragma == {"LLM": "model=gpt-4 temperature=0.7"}

    def test_multiple_pragmas(self):
        """Multiple pragmas should be merged."""
        source = """{-# INLINE #-}
{-# LLM model=gpt-4 #-}
test :: Int = 1"""

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


class TestElab3SyntaxSample:
    """Test that all elab3-required syntax constructs parse correctly."""

    def test_elab3_sample_program(self, elab3_syntax_sample):
        """Parse comprehensive sample with imports, data, terms, lambda, let, case, literals."""
        from systemf.surface.types import (
            SurfaceImportDeclaration,
            SurfaceDataDeclaration,
            SurfaceTermDeclaration,
            SurfaceConstructorInfo,
            SurfaceTypeVar,
            SurfaceTypeArrow,
            SurfaceTypeForall,
            SurfaceTypeConstructor,
            SurfaceAbs,
            SurfaceVar,
            SurfaceCase,
            SurfaceBranch,
            SurfacePattern,
            SurfaceLitPattern,
            SurfaceLit,
            SurfaceLet,
            ValBind,
            SurfaceApp,
            SurfaceOp,
        )
        from systemf.utils.ast_utils import equals_ignore_location

        result = parse_program(elab3_syntax_sample)

        expected = [
            SurfaceImportDeclaration(module="List"),
            SurfaceDataDeclaration(
                name="Bool",
                constructors=[
                    SurfaceConstructorInfo(name="True"),
                    SurfaceConstructorInfo(name="False"),
                ],
            ),
            SurfaceDataDeclaration(
                name="Maybe",
                params=["a"],
                constructors=[
                    SurfaceConstructorInfo(name="Nothing"),
                    SurfaceConstructorInfo(name="Just", args=[SurfaceTypeVar("a")]),
                ],
            ),
            SurfaceDataDeclaration(
                name="List",
                params=["a"],
                constructors=[
                    SurfaceConstructorInfo(name="Nil"),
                    SurfaceConstructorInfo(
                        name="Cons",
                        args=[
                            SurfaceTypeVar("a"),
                            SurfaceTypeConstructor(name="List", args=[SurfaceTypeVar("a")]),
                        ],
                    ),
                ],
            ),
            SurfaceTermDeclaration(
                name="id",
                type_annotation=SurfaceTypeForall(
                    var="a",
                    body=SurfaceTypeArrow(arg=SurfaceTypeVar("a"), ret=SurfaceTypeVar("a")),
                ),
                body=SurfaceAbs(params=[("x", None)], body=SurfaceVar("x")),
            ),
            SurfaceTermDeclaration(
                name="const",
                type_annotation=SurfaceTypeForall(
                    var="a",
                    body=SurfaceTypeForall(
                        var="b",
                        body=SurfaceTypeArrow(
                            arg=SurfaceTypeVar("a"),
                            ret=SurfaceTypeArrow(
                                arg=SurfaceTypeVar("b"),
                                ret=SurfaceTypeVar("a"),
                            ),
                        ),
                    ),
                ),
                body=SurfaceAbs(
                    params=[("x", None), ("y", None)],
                    body=SurfaceVar("x"),
                ),
            ),
            SurfaceTermDeclaration(
                name="fromMaybe",
                type_annotation=SurfaceTypeForall(
                    var="a",
                    body=SurfaceTypeArrow(
                        arg=SurfaceTypeVar("a"),
                        ret=SurfaceTypeArrow(
                            arg=SurfaceTypeConstructor(name="Maybe", args=[SurfaceTypeVar("a")]),
                            ret=SurfaceTypeVar("a"),
                        ),
                    ),
                ),
                body=SurfaceAbs(
                    params=[("default", None), ("ma", None)],
                    body=SurfaceCase(
                        scrutinee=SurfaceVar("ma"),
                        branches=[
                            SurfaceBranch(
                                pattern=SurfacePattern(constructor="Nothing", vars=[]),
                                body=SurfaceVar("default"),
                            ),
                            SurfaceBranch(
                                pattern=SurfacePattern(
                                    constructor="Just",
                                    vars=[SurfacePattern(constructor="x")],
                                ),
                                body=SurfaceVar("x"),
                            ),
                        ],
                    ),
                ),
            ),
            SurfaceTermDeclaration(
                name="length",
                type_annotation=SurfaceTypeForall(
                    var="a",
                    body=SurfaceTypeArrow(
                        arg=SurfaceTypeConstructor(name="List", args=[SurfaceTypeVar("a")]),
                        ret=SurfaceTypeConstructor(name="Int"),
                    ),
                ),
                body=SurfaceAbs(
                    params=[("xs", None)],
                    body=SurfaceLet(
                        bindings=[
                            ValBind(
                                name="go",
                                type_ann=SurfaceTypeForall(
                                    var="a",
                                    body=SurfaceTypeArrow(
                                        arg=SurfaceTypeConstructor(name="Int"),
                                        ret=SurfaceTypeArrow(
                                            arg=SurfaceTypeConstructor(
                                                name="List", args=[SurfaceTypeVar("a")]
                                            ),
                                            ret=SurfaceTypeConstructor(name="Int"),
                                        ),
                                    ),
                                ),
                                value=SurfaceAbs(
                                    params=[("acc", None), ("ys", None)],
                                    body=SurfaceCase(
                                        scrutinee=SurfaceVar("ys"),
                                        branches=[
                                            SurfaceBranch(
                                                pattern=SurfacePattern(constructor="Nil", vars=[]),
                                                body=SurfaceVar("acc"),
                                            ),
                                            SurfaceBranch(
pattern=SurfacePattern(
                                    constructor="Cons", vars=[SurfacePattern(constructor="z", vars=[]), SurfacePattern(constructor="zs", vars=[])]
                                ),
                                                body=SurfaceApp(
                                                    func=SurfaceApp(
                                                        func=SurfaceVar("go"),
                                                        arg=SurfaceOp(
                                                            left=SurfaceVar("acc"),
                                                            op="+",
                                                            right=SurfaceLit(
                                                                prim_type="Int", value=1
                                                            ),
                                                        ),
                                                    ),
                                                    arg=SurfaceVar("zs"),
                                                ),
                                            ),
                                        ],
                                    ),
                                ),
                            )
                        ],
                        body=SurfaceApp(
                            func=SurfaceApp(
                                func=SurfaceVar("go"),
                                arg=SurfaceLit(prim_type="Int", value=0),
                            ),
                            arg=SurfaceVar("xs"),
                        ),
                    ),
                ),
            ),
            SurfaceTermDeclaration(
                name="factorial",
                type_annotation=SurfaceTypeArrow(
                    arg=SurfaceTypeConstructor(name="Int"),
                    ret=SurfaceTypeConstructor(name="Int"),
                ),
                body=SurfaceAbs(
                    params=[("n", None)],
                    body=SurfaceCase(
                        scrutinee=SurfaceVar("n"),
                        branches=[
                            SurfaceBranch(
                                pattern=SurfaceLitPattern(prim_type="Int", value=0),
                                body=SurfaceLit(prim_type="Int", value=1),
                            ),
                            SurfaceBranch(
                                pattern=SurfacePattern(constructor="m", vars=[]),
                                body=SurfaceOp(
                                    left=SurfaceVar("m"),
                                    op="*",
                                    right=SurfaceApp(
                                        func=SurfaceVar("factorial"),
                                        arg=SurfaceOp(
                                            left=SurfaceVar("m"),
                                            op="-",
                                            right=SurfaceLit(prim_type="Int", value=1),
                                        ),
                                    ),
                                ),
                            ),
                        ],
                    ),
                ),
            ),
            SurfaceTermDeclaration(
                name="greet",
                type_annotation=SurfaceTypeArrow(
                    arg=SurfaceTypeConstructor(name="String"),
                    ret=SurfaceTypeConstructor(name="String"),
                ),
                body=SurfaceAbs(
                    params=[("name", None)],
                    body=SurfaceCase(
                        scrutinee=SurfaceVar("name"),
                        branches=[
                            SurfaceBranch(
                                pattern=SurfaceLitPattern(
                                    prim_type="String", value="world"
                                ),
                                body=SurfaceLit(
                                    prim_type="String", value="hello world"
                                ),
                            ),
                            SurfaceBranch(
                                pattern=SurfacePattern(constructor="other", vars=[]),
                                body=SurfaceOp(
                                    left=SurfaceLit(
                                        prim_type="String", value="hello "
                                    ),
                                    op="++",
                                    right=SurfaceVar("other"),
                                ),
                            ),
                        ],
                    ),
                ),
            ),
        ]

        assert len(result) == len(expected)
        for actual, exp in zip(result, expected):
            assert equals_ignore_location(actual, exp)


class TestMixedDeclarationStyles:
    """Test mixing single-line and multi-line declarations."""

    def test_single_line_followed_by_multi_line(self):
        """Parse single-line term followed by multi-line term."""
        source = """id :: forall a. a -> a = λx -> x

not :: Bool -> Bool =
  λb -> case b of
    True -> False
    False -> True"""
        result = parse_program(source)
        assert len(result) == 2
        assert result[0].name == "id"
        assert result[1].name == "not"

    def test_multi_line_followed_by_single_line(self):
        """Parse multi-line term followed by single-line term."""
        source = """map :: forall a b. (a -> b) -> List a -> List b =
  λf xs -> xs

const :: forall a b. a -> b -> a = λx y -> x"""
        result = parse_program(source)
        assert len(result) == 2
        assert result[0].name == "map"
        assert result[1].name == "const"

    def test_mixed_styles_in_sequence(self):
        """Parse sequence of mixed single-line and multi-line declarations."""
        source = """-- Single line
x :: Int = 1

-- Multi-line
y :: Int -> Int =
  λn -> n + 1

-- Single line
z :: Int = 3

-- Multi-line
w :: Bool -> Bool =
  λb -> not b"""
        result = parse_program(source)
        assert len(result) == 4
        assert result[0].name == "x"
        assert result[1].name == "y"
        assert result[2].name == "z"
        assert result[3].name == "w"

    def test_polymorphic_functions_mixed_styles(self):
        """Parse polymorphic functions with both single and multi-line bodies."""
        source = """-- Single line polymorphic
id :: forall a. a -> a = λx -> x

-- Multi-line polymorphic
mapMaybe :: forall a b. (a -> b) -> Maybe a -> Maybe b =
  λf m ->
    case m of
      Nothing -> Nothing
      Just x -> Just (f x)

-- Another single line
const :: forall a b. a -> b -> a = λx y -> x"""
        result = parse_program(source)
        assert len(result) == 3
        assert result[0].name == "id"
        assert result[1].name == "mapMaybe"
        assert result[2].name == "const"

    def test_multi_line_with_type_abstraction(self):
        """Parse multi-line terms with type abstraction (removed Λ)."""
        source = """isJust :: forall a. Maybe a -> Bool =
  λm ->
    case m of { Nothing -> False | Just x -> True }

isNothing :: forall a. Maybe a -> Bool =
  λm ->
    case m of { Nothing -> True | Just x -> False }

just :: forall a. a -> Maybe a = λx -> Just x"""
        result = parse_program(source)
        assert len(result) == 3
        assert result[0].name == "isJust"
        assert result[1].name == "isNothing"
        assert result[2].name == "just"
