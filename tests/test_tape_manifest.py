"""Unit tests for tape manifest."""

import pytest

from bub.tape.store import FileTapeStore
from bub.tape.types import Manifest


class TestManifestCreate:
    def test_manifest_create(self):
        manifest = Manifest()
        assert manifest.version == 1
        assert manifest.tapes == {}
        assert manifest.anchors == {}

    def test_manifest_save_and_load(self, tmp_path):
        from republic.tape import TapeEntry

        store = FileTapeStore(home=tmp_path, workspace_path=tmp_path)
        store.create_tape("main", title="Test")
        store.append("main", TapeEntry.message({"role": "user", "content": "hello"}))
        store.fork("main", "other", from_entry=("main", 100))

        loaded_store = FileTapeStore(home=tmp_path, workspace_path=tmp_path)
        assert "main" in loaded_store.list_tapes()
        assert loaded_store.get_title("main") == "Test"


class TestTapeCrud:
    def test_create_tape(self):
        manifest = Manifest()
        manifest.create_tape("main")

        assert "main" in manifest.tapes
        assert manifest.tapes["main"].id == "main"
        assert manifest.tapes["main"].parent is None
        assert manifest.tapes["main"].file == "main.jsonl"

    def test_create_tape_with_file(self):
        manifest = Manifest()
        manifest.create_tape("main", file="shared.jsonl")

        assert manifest.tapes["main"].file == "shared.jsonl"

    def test_get_tape(self):
        manifest = Manifest()
        manifest.create_tape("main", parent=("main", 50))

        tape = manifest.get_tape("main")
        assert tape is not None
        assert tape.parent == ("main", 50)

    def test_get_tape_nonexistent(self):
        manifest = Manifest()
        assert manifest.get_tape("nonexistent") is None

    def test_update_tape(self):
        manifest = Manifest()
        manifest.create_tape("main")
        manifest.update_tape("main", title="Updated")

        assert manifest.tapes["main"].title == "Updated"

    def test_update_tape_not_found(self):
        manifest = Manifest()
        with pytest.raises(KeyError):
            manifest.update_tape("nonexistent", title="test")

    def test_delete_tape(self):
        manifest = Manifest()
        manifest.create_tape("main")
        manifest.delete_tape("main")

        assert "main" not in manifest.tapes

    def test_fork_tape(self):
        manifest = Manifest()
        manifest.create_tape("main", file="main.jsonl")
        manifest.fork_tape("main", "fork", parent=("main", 100))

        assert "fork" in manifest.tapes
        assert manifest.tapes["fork"].parent == ("main", 100)
        assert manifest.tapes["fork"].file == "main.jsonl"


class TestAnchorCrud:
    def test_create_anchor(self):
        manifest = Manifest()
        manifest.create_anchor("phase1", "main", 50, {"summary": "done"})

        assert "phase1" in manifest.anchors
        assert manifest.anchors["phase1"].tape_id == "main"
        assert manifest.anchors["phase1"].entry_id == 50
        assert manifest.anchors["phase1"].state == {"summary": "done"}

    def test_get_anchor(self):
        manifest = Manifest()
        manifest.create_anchor("phase1", "main", 50)

        anchor = manifest.get_anchor("phase1")
        assert anchor is not None
        assert anchor.entry_id == 50

    def test_get_anchor_nonexistent(self):
        manifest = Manifest()
        assert manifest.get_anchor("nonexistent") is None

    def test_update_anchor(self):
        manifest = Manifest()
        manifest.create_anchor("phase1", "main", 50)
        manifest.update_anchor("phase1", entry_id=75)

        assert manifest.anchors["phase1"].entry_id == 75

    def test_update_anchor_not_found(self):
        manifest = Manifest()
        with pytest.raises(KeyError):
            manifest.update_anchor("nonexistent", entry_id=10)

    def test_delete_anchor(self):
        manifest = Manifest()
        manifest.create_anchor("phase1", "main", 50)
        manifest.delete_anchor("phase1")

        assert "phase1" not in manifest.anchors


class TestAnchorResolution:
    def test_resolve_anchor(self):
        manifest = Manifest()
        manifest.create_anchor("phase1", "main", 50)

        entry_id = manifest.resolve_anchor("phase1")
        assert entry_id == 50

    def test_resolve_nonexistent_anchor(self):
        manifest = Manifest()
        with pytest.raises(KeyError):
            manifest.resolve_anchor("nonexistent")
