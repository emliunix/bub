"""Tests for surface-level pragma pass."""

from systemf.surface.llm.pragma_pass import pragma_pass, parse_pragma_config
from systemf.surface.types import (
    SurfaceVar,
    SurfaceAbs,
    SurfacePrimOpDecl,
    SurfaceTermDeclaration,
    SurfaceDataDeclaration,
    SurfaceConstructorInfo,
)


def test_primop_with_pragma():
    decl = SurfacePrimOpDecl(
        name="translate",
        type_annotation=None,
        docstring="Translate text",
        pragma={"model": "gpt-4", "temperature": "0.7"},
    )
    new_decls, metas = pragma_pass([decl])
    assert new_decls[0] is decl
    assert len(metas) == 1
    assert metas[0].function_name == "translate"
    assert metas[0].pragma_config == {"model": "gpt-4", "temperature": "0.7"}
    assert metas[0].docstring == "Translate text"


def test_primop_no_pragma():
    decl = SurfacePrimOpDecl(
        name="int_plus",
        type_annotation=None,
        docstring=None,
        pragma=None,
    )
    new_decls, metas = pragma_pass([decl])
    assert len(metas) == 0
    assert new_decls[0] is decl


def test_primop_empty_pragma_skipped():
    decl = SurfacePrimOpDecl(
        name="f",
        type_annotation=None,
        docstring=None,
        pragma={},
    )
    new_decls, metas = pragma_pass([decl])
    assert len(metas) == 0


def test_term_decl_ignored():
    decl = SurfaceTermDeclaration(
        name="f",
        type_annotation=None,
        body=SurfaceAbs(var="x", body=SurfaceVar(name="x")),
        docstring=None,
        pragma={"model": "test"},
    )
    new_decls, metas = pragma_pass([decl])
    assert len(metas) == 0
    assert new_decls[0] is decl


def test_data_decl_ignored():
    decl = SurfaceDataDeclaration(
        name="Bool",
        params=[],
        constructors=[SurfaceConstructorInfo(name="True", args=[], docstring=None)],
        docstring=None,
        pragma={"model": "test"},
    )
    new_decls, metas = pragma_pass([decl])
    assert len(metas) == 0
    assert new_decls[0] is decl


def test_mixed_decls():
    primop = SurfacePrimOpDecl(
        name="llm_fn",
        type_annotation=None,
        docstring=None,
        pragma={"model": "test"},
    )
    term = SurfaceTermDeclaration(
        name="plain_fn",
        type_annotation=None,
        body=SurfaceVar(name="x"),
        docstring=None,
        pragma=None,
    )
    new_decls, metas = pragma_pass([primop, term])
    assert len(metas) == 1
    assert metas[0].function_name == "llm_fn"
    assert new_decls[0] is primop
    assert new_decls[1] is term


def test_parse_pragma_config():
    assert parse_pragma_config("model=gpt-4 temperature=0.7") == {
        "model": "gpt-4",
        "temperature": "0.7",
    }
    assert parse_pragma_config("stream") == {"stream": "true"}
    assert parse_pragma_config("") == {}
