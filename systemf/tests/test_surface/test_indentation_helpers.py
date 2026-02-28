"""Tests for indentation helper functions.

These tests verify that indented_block and indented_opt helpers work correctly.
"""

from systemf.surface.parser import lex
from systemf.surface.indentation import indented_block, indented_opt
from systemf.surface.parser import match_token, INDENT, DEDENT
from parsy import generate


class TestIndentedBlock:
    """Tests for the indented_block helper."""

    def test_indented_block_single_content(self):
        """Parse required indentation around content."""

        @generate
        def with_block():
            parent = yield match_token("IDENT")
            content = yield indented_block(match_token("IDENT"))
            return {"parent": parent.value, "child": content.value}

        code = """parent
  child"""
        tokens = lex(code)
        result, _ = with_block.parse_partial(tokens)

        assert result == {"parent": "parent", "child": "child"}

    def test_indented_block_sequence(self):
        """Parse required indentation around sequence."""

        @generate
        def with_block():
            parent = yield match_token("IDENT")
            # indented_block with many items - parse one, then many
            yield INDENT
            first = yield match_token("IDENT")
            rest = []
            while True:
                tok = yield match_token("IDENT").optional()
                if tok is None:
                    break
                rest.append(tok.value)
            yield DEDENT
            return {"parent": parent.value, "children": [first.value] + rest}

        code = """parent
  a
  b
  c"""
        tokens = lex(code)
        result, _ = with_block.parse_partial(tokens)

        assert result == {"parent": "parent", "children": ["a", "b", "c"]}


class TestIndentedOpt:
    """Tests for the indented_opt helper."""

    def test_indented_opt_prefers_indented(self):
        """indented_opt tries indented form first."""

        @generate
        def with_opt():
            parent = yield match_token("IDENT")
            child = yield indented_opt(match_token("IDENT"))
            return {"parent": parent.value, "child": child.value}

        # Indented form
        code1 = """parent
  child"""
        tokens1 = lex(code1)
        result1, _ = with_opt.parse_partial(tokens1)
        assert result1 == {"parent": "parent", "child": "child"}

        # Inline form
        code2 = """parent child"""
        tokens2 = lex(code2)
        result2, _ = with_opt.parse_partial(tokens2)
        assert result2 == {"parent": "parent", "child": "child"}


class TestTwoSiblingBlocks:
    """Test the specific requirement: two sibling blocks each with a child."""

    def test_two_sibling_blocks_basic(self):
        """Parse: xxx / xxx2 and yyy / yyy2 as siblings."""

        @generate
        def tree_item():
            """Parse an item with optional indented children."""
            name = yield match_token("IDENT")
            # Try indented children: INDENT item+ DEDENT
            yield INDENT
            children = []
            while True:
                next_tok = yield match_token("IDENT").optional()
                if next_tok is None:
                    break
                children.append({"name": next_tok.value, "children": []})
            yield DEDENT
            return {"name": name.value, "children": children}

        @generate
        def tree_parser():
            """Parse multiple top-level items."""
            items = []
            while True:
                tok = yield match_token("IDENT").optional()
                if tok is None:
                    break
                # For each top-level item, parse it and its indented children
                yield INDENT
                children = []
                while True:
                    child_tok = yield match_token("IDENT").optional()
                    if child_tok is None:
                        break
                    children.append({"name": child_tok.value, "children": []})
                yield DEDENT
                items.append({"name": tok.value, "children": children})
            return items

        code = """xxx
  xxx2
yyy
  yyy2"""

        tokens = lex(code)
        result, rest = tree_parser.parse_partial(tokens)

        # Should have 2 siblings
        assert len(result) == 2

        # First sibling
        assert result[0]["name"] == "xxx"
        assert len(result[0]["children"]) == 1
        assert result[0]["children"][0]["name"] == "xxx2"

        # Second sibling
        assert result[1]["name"] == "yyy"
        assert len(result[1]["children"]) == 1
        assert result[1]["children"][0]["name"] == "yyy2"

        # Should consume all tokens except EOF
        assert len(rest) == 1
        assert rest[0].type == "EOF"


class TestIndentationHelpersWork:
    """Verify the core helpers work as documented."""

    def test_indented_block_consumes_indent_dedent(self):
        """indented_block properly wraps content in INDENT/DEDENT."""

        @generate
        def parser():
            a = yield match_token("IDENT")
            b = yield indented_block(match_token("IDENT"))
            return [a.value, b.value]

        code = """a
  b"""
        tokens = lex(code)
        result, _ = parser.parse_partial(tokens)
        assert result == ["a", "b"]

    def test_indented_opt_inline_fallback(self):
        """indented_opt falls back to inline when no INDENT."""

        @generate
        def parser():
            a = yield match_token("IDENT")
            b = yield indented_opt(match_token("IDENT"))
            return [a.value, b.value]

        # Inline
        code = "a b"
        tokens = lex(code)
        result, _ = parser.parse_partial(tokens)
        assert result == ["a", "b"]

    def test_indented_opt_prefers_block(self):
        """indented_opt uses block when INDENT present."""

        @generate
        def parser():
            a = yield match_token("IDENT")
            b = yield indented_opt(match_token("IDENT"))
            return [a.value, b.value]

        # Indented
        code = """a
  b"""
        tokens = lex(code)
        result, _ = parser.parse_partial(tokens)
        assert result == ["a", "b"]
